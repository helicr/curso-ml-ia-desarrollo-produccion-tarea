"""Logica de la interfaz: de unos ids de lote (o de un lote nuevo) a su probabilidad de especialidad y su recomendacion. Sin HTTP propio.

POR QUE ES OTRO SERVICIO
    La API (cafe_mlops/api) sirve el modelo: pide las 10 variables de cada lote, ese es su contrato. Quien recibe el cafe conoce
    el lote (su id) o tiene delante uno nuevo. Esta capa hace de puente y NO carga el modelo (la imagen no lleva scikit-learn):

        ids de lote  --> variables ya calculadas en la capa FS (tabla fs_lote, base abierta en SOLO LECTURA) --+
                                                                                                             +--> API /predecir/lote --> tramo
        lote nuevo   --> las 10 variables del formulario o del CSV (se validan aqui con el mismo esquema) -----+      (config.SEGMENTOS)

LA RECOMENDACION
    El modelo da una probabilidad. Convertirla en una accion es una regla de negocio: config.SEGMENTOS (umbrales y textos
    PROVISIONALES, TODO de la decision 15). Si el modelo avisa de algo (categoria nueva, valor fuera de rango, humedad 0, dato sin
    informar), el lote se marca «revisar»: la probabilidad tiene menos respaldo.

ERRORES: nunca trazas. 422 = lo escrito no tiene sentido (se dice campo y motivo en español) · 503 = no hay API, no hay modelo
o no hay base de datos (se dice que hacer).
"""
import json
import os
import sqlite3
import urllib.error
import urllib.request
from typing import get_args

from pydantic import ValidationError

from .. import config, db
from ..api import esquemas

MAXIMO_LOTES = esquemas.MAX_LOTES
TIMEOUT = 10


class PeticionNoValida(ValueError):
    """Lo escrito no tiene sentido: 422. `errores` = lista de {fila, campo, mensaje}."""

    def __init__(self, detalle, errores=None):
        super().__init__(detalle)
        self.errores = errores or []


class NoDisponible(RuntimeError):
    """Falta la API, el modelo o la base de datos: 503, con el motivo y que hacer."""


# --------------------------------------------------------------------------------------------------- traduccion de errores
_RANGOS = {
    'altitud_media_m': (config.ALTITUD_MIN_M, config.ALTITUD_MAX_M, 'm'),
    'humedad': (0, 1, 'fracción, por ejemplo 0,11'),
    'defectos_cat1': (0, esquemas.MAX_DEFECTOS, ''), 'defectos_cat2': (0, esquemas.MAX_DEFECTOS, ''), 'quakers': (0, esquemas.MAX_DEFECTOS, ''),
}
_LISTAS = {
    'especie': get_args(esquemas.Especie), 'metodo_proceso': get_args(esquemas.MetodoProceso), 'color': get_args(esquemas.Color),
}


def _num(x):
    return f'{x:g}'.replace('.', ',')


def explicar(campo, tipo, mensaje=''):
    """Un error de validacion (campo, tipo de pydantic) en una frase en español, sin el valor recibido ni jerga."""
    if tipo == 'missing':
        return 'Falta este dato (si no se conoce, déjalo sin informar).'
    if tipo == 'extra_forbidden':
        return 'Campo no reconocido.'
    if campo in _RANGOS and tipo in ('greater_than_equal', 'less_than_equal', 'finite_number'):
        minimo, maximo, unidad = _RANGOS[campo]
        return f'Debe estar entre {_num(minimo)} y {_num(maximo)}' + (f' ({unidad}).' if unidad else '.')
    if tipo == 'literal_error':
        return 'Valor no permitido. Elige uno de: ' + ', '.join(_LISTAS.get(campo, ())) + '.' if campo in _LISTAS else 'Valor no permitido.'
    if tipo in ('float_type', 'float_parsing', 'int_type'):
        return 'Debe ser un número (con punto o coma decimal, por ejemplo 0,11).'
    if tipo in ('string_type', 'string_too_long'):
        if tipo == 'string_too_long':
            return f'Demasiado largo (máximo {esquemas.MAX_TEXTO} caracteres).'
        return 'Debe ser texto.'
    return 'Valor no válido.'


def _campo_y_fila(loc):
    """('lotes', 3, 'humedad') -> (4, 'humedad'): fila 1-based si hay indice, campo sin prefijo."""
    partes = [p for p in loc if p not in ('body', 'lotes', 'lote')]
    fila = next((p + 1 for p in partes if isinstance(p, int)), None)
    campo = '.'.join(str(p) for p in partes if not isinstance(p, int))
    return fila, campo


def errores_de(excepcion_pydantic, fila=None):
    """Errores de pydantic -> [{fila, campo, mensaje}] en español."""
    salida = []
    for e in excepcion_pydantic.errors():
        f, campo = _campo_y_fila(e['loc'])
        salida.append({'fila': fila or f, 'campo': campo, 'mensaje': explicar(campo, e['type'], e.get('msg', ''))})
    return salida


def _resumen_errores(errores):
    n = len(errores)
    return 'El lote tiene datos que no son válidos.' if n == 1 else f'Hay {n} datos que no son válidos.'


# --------------------------------------------------------------------------------------------------- tramos
def segmento_de(probabilidad, segmentos=None):
    """El primer tramo de config.SEGMENTOS cuyo «desde» no supera la probabilidad."""
    segmentos = segmentos or config.SEGMENTOS
    for s in segmentos:
        if probabilidad >= s['desde']:
            return s
    return segmentos[-1]


def leer_ids(valores):
    """Normaliza los ids: enteros positivos, sin repetir, en el orden recibido."""
    vistos, ids = set(), []
    for v in valores:
        try:
            n = int(str(v).strip())
        except ValueError:
            raise PeticionNoValida(f'«{v}» no es un id de lote (debe ser un número entero).') from None
        if n <= 0:
            raise PeticionNoValida(f'{n} no es un id de lote válido.')
        if n not in vistos:
            vistos.add(n)
            ids.append(n)
    if not ids:
        raise PeticionNoValida('No hay ningún id de lote.')
    if len(ids) > MAXIMO_LOTES:
        raise PeticionNoValida(f'Como mucho {MAXIMO_LOTES} lotes por consulta (llegaron {len(ids)}).')
    return ids


# --------------------------------------------------------------------------------------------------- cliente HTTP de la API
def http_urllib(url_api):
    """Devuelve llamar(metodo, ruta, cuerpo) -> (codigo, json). Lanza OSError si la API no responde."""
    def llamar(metodo, ruta, cuerpo=None):
        datos = None if cuerpo is None else json.dumps(cuerpo).encode('utf-8')
        peticion = urllib.request.Request(f'{url_api}{ruta}', data=datos, method=metodo, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(peticion, timeout=TIMEOUT) as r:
                return r.status, json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode('utf-8'))
            except ValueError:
                return e.code, {}
    return llamar


class Consulta:
    """ruta_db: base analitica (fs_lote) · url_api: la API del modelo · http: sustituto de la llamada HTTP (las pruebas)."""

    def __init__(self, ruta_db=None, url_api=None, http=None):
        self.ruta_db = ruta_db or config.DB
        self.url_api = (url_api or config.URL_API_INTERFAZ).rstrip('/')
        self._http = http or http_urllib(self.url_api)

    # --- base de datos (siempre en solo lectura) ---------------------------------------------------------------------------
    def _abrir(self):
        try:
            con = db.conectar(self.ruta_db, solo_lectura=True)
            if not db.escalar(con, "SELECT COUNT(*) FROM sqlite_master WHERE name = 'fs_lote'"):
                con.close()
                raise NoDisponible('La base no tiene la capa FS (tabla fs_lote). Ejecuta antes:  python -m cafe_mlops.pipeline')
            return con
        except sqlite3.Error:
            raise NoDisponible('No se pudo leer la base de datos. Comprueba que existe y que el volumen está montado.') from None
        except RuntimeError as e:
            raise NoDisponible(str(e)) from None

    # --- la API ------------------------------------------------------------------------------------------------------------
    def _api(self, metodo, ruta, cuerpo=None):
        try:
            codigo, datos = self._http(metodo, ruta, cuerpo)
        except (OSError, ValueError):     # URLError, timeout, conexion rechazada, respuesta que no es JSON
            raise NoDisponible(f'La API del modelo no responde en {self.url_api}. ¿Está arrancada? Compruébalo con  {self.url_api}/listo') from None
        if codigo == 200:
            return datos
        if codigo == 422:
            errores = []
            for e in datos.get('errores', []):
                fila, campo = _campo_y_fila([int(p) if p.isdigit() else p for p in str(e.get('campo', '')).split('.')])
                errores.append({'fila': fila, 'campo': campo, 'mensaje': explicar(campo, e.get('tipo', ''))})
            raise PeticionNoValida('La API del modelo no aceptó los datos del lote.', errores)
        if codigo == 503:
            raise NoDisponible('La API del modelo está en marcha pero no tiene modelo listo: ' + str(datos.get('detalle', 'sin detalle')))
        raise NoDisponible(f'La API del modelo respondió con un error inesperado (código {codigo}). Mira su registro.')

    # --- repositorio -------------------------------------------------------------------------------------------------------
    @staticmethod
    def repositorio():
        """Repositorio e identificacion del entorno. Variables de entorno: sin verificar que el Codespace las ponga con estos nombres."""
        repo = os.environ.get('TALLER_REPOSITORIO') or os.environ.get('GITHUB_REPOSITORY')
        return {'repositorio': repo or None, 'codespace': os.environ.get('CODESPACE_NAME') or None}

    # --- lo que se pregunta ------------------------------------------------------------------------------------------------
    def comprobar(self):
        """¿Puede atender? Base legible y API con modelo listo. Lanza NoDisponible con el motivo."""
        self._abrir().close()
        self._api('GET', '/listo')
        return {'datos': 'ok', 'api': 'ok'}

    def estado(self):
        """Todo lo que necesita la pagina para pintarse. NUNCA falla: si algo no esta, lo dice (la pagina muestra el motivo)."""
        r = {**self.repositorio(), 'segmentos': config.SEGMENTOS, 'maximo_lotes': MAXIMO_LOTES, 'ejemplo_lote': esquemas.EJEMPLO,
             'umbral_especialidad': config.UMBRAL_ESPECIALIDAD, 'url_api': self.url_api,
             'opciones': {'especie': list(_LISTAS['especie']), 'metodo_proceso': list(_LISTAS['metodo_proceso']),
                          'color': list(_LISTAS['color']), 'pais': [], 'variedad': []},
             'limites': {c: {'minimo': a, 'maximo': b, 'unidad': u} for c, (a, b, u) in _RANGOS.items()}}
        try:
            con = self._abrir()
            try:
                n = db.escalar(con, 'SELECT COUNT(*) FROM fs_lote')
                for c in ('pais', 'variedad'):
                    r['opciones'][c] = [x[0] for x in con.execute(f'SELECT DISTINCT {c} FROM fs_lote WHERE {c} IS NOT NULL ORDER BY {c}')]
                ids = [x[0] for x in con.execute('SELECT lote_id FROM fs_lote ORDER BY lote_id')]
            finally:
                con.close()
            r['datos'] = {'estado': 'ok', 'lotes': n}
            r['ejemplos'] = list(dict.fromkeys(ids[min(len(ids) - 1, round(q * (len(ids) - 1)))] for q in (0, 0.25, 0.5, 0.75, 1))) if ids else []
        except NoDisponible as e:
            r['datos'], r['ejemplos'] = {'estado': 'error', 'detalle': str(e)}, []
        try:
            m = self._api('GET', '/modelo')
            r['api'] = {'estado': 'lista'}
            r['modelo'] = {'modelo': m['modelo'], 'version_modelo': m.get('version_modelo'), 'huella_datos': m['huella_datos'],
                           'entrenado_en': m['entrenado_en'], 'metricas_valid': m.get('metricas_valid')}
        except (NoDisponible, PeticionNoValida) as e:
            r['api'], r['modelo'] = {'estado': 'no_disponible', 'detalle': str(e)}, None
        return r

    def _filas_de_fs(self, ids):
        con = self._abrir()
        try:
            marcas = ','.join('?' * len(ids))
            cur = con.execute(f'SELECT lote_id, {", ".join(config.FEATURES)} FROM fs_lote WHERE lote_id IN ({marcas})', ids)
            return {fila[0]: dict(zip(config.FEATURES, fila[1:])) for fila in cur}
        except sqlite3.Error:
            raise NoDisponible('No se pudo leer la base de datos.') from None
        finally:
            con.close()

    def _predecir(self, lotes):
        if not lotes:
            return []
        return self._api('POST', '/predecir/lote', {'lotes': lotes})['predicciones']

    @staticmethod
    def _resultado(clave, variables, pred):
        p = pred['probabilidad_especialidad']
        s = segmento_de(p)
        return {'lote_id': clave, 'probabilidad': round(float(p), 4), 'segmento': s['segmento'], 'recomendacion': s['recomendacion'],
                'revisar': bool(pred['avisos']), 'avisos': pred['avisos'], 'variables': variables}

    def _respuesta(self, origen, pedidos, resultados, no_encontrados, preds):
        por_segmento = {s['segmento']: sum(1 for x in resultados if x['segmento'] == s['segmento']) for s in config.SEGMENTOS}
        modelo = ({'modelo': preds[0]['modelo'], 'version_modelo': preds[0]['version_modelo'], 'huella_datos': preds[0]['huella_datos']}
                  if preds else None)
        return {'origen': origen, 'pedidos': pedidos, 'encontrados': len(resultados), 'por_segmento': por_segmento, 'modelo': modelo,
                'resultados': resultados, 'no_encontrados': no_encontrados}

    def recomendar(self, ids):
        """Lotes existentes: sus variables salen de fs_lote (las mismas con las que se entreno)."""
        ids = leer_ids(ids)
        filas = self._filas_de_fs(ids)
        presentes = [i for i in ids if i in filas]
        preds = self._predecir([filas[i] for i in presentes])
        resultados = [self._resultado(i, filas[i], p) for i, p in zip(presentes, preds)]
        faltan = [{'lote_id': i, 'motivo': 'no existe en la capa FS (solo hay lotes con cata válida)'} for i in ids if i not in filas]
        return self._respuesta('ids', len(ids), resultados, faltan, preds)

    def recomendar_nuevos(self, lotes):
        """Lotes nuevos (formulario o CSV): se validan con el esquema de la API ANTES de llamar, y se avisa de cada fila."""
        if not isinstance(lotes, list) or not lotes:
            raise PeticionNoValida('No hay ningún lote que predecir.')
        if len(lotes) > MAXIMO_LOTES:
            raise PeticionNoValida(f'Como mucho {MAXIMO_LOTES} lotes por consulta (llegaron {len(lotes)}).')
        validos, errores = [], []
        for n, bruto in enumerate(lotes, start=1):
            if not isinstance(bruto, dict):
                errores.append({'fila': n, 'campo': '', 'mensaje': 'El lote debe ser un conjunto de variables.'})
                continue
            try:
                validos.append(esquemas.Lote.model_validate(bruto).model_dump())
            except ValidationError as e:
                errores.extend(errores_de(e, fila=n if len(lotes) > 1 else None))   # con un solo lote no hay «fila»
        if errores:
            raise PeticionNoValida(_resumen_errores(errores) if len(lotes) == 1 else f'Hay datos no válidos en {len({e["fila"] for e in errores})} de {len(lotes)} lotes.', errores)
        preds = self._predecir(validos)
        resultados = [self._resultado(None, v, p) for v, p in zip(validos, preds)]
        return self._respuesta('nuevos', len(lotes), resultados, [], preds)

"""Lógica del servicio: carga del modelo, comprobación del contrato, avisos y predicción. No sabe nada de HTTP.

El modelo se carga en formato MLflow (mlflow.sklearn.load_model; basta mlflow-skinny) y su FIRMA es el contrato. El servicio solo
queda listo si coinciden, en nombres Y tipos: la firma, models/metadatos.json y el esquema de la API (esquemas.Lote). Es mejor
fallar al arrancar (y que /listo diga por qué) que predecir con las columnas o los tipos equivocados.
"""
import json
from pathlib import Path

import numpy as np

from .. import config
from ..modeling import predict, preproceso


class ModeloNoDisponible(RuntimeError):
    pass


class ContratoRoto(RuntimeError):
    pass


def _aviso(tipo, campo, valor, mensaje):
    return {'tipo': tipo, 'campo': campo, 'valor': valor, 'mensaje': mensaje}


class Servicio:
    def __init__(self, modelo, meta, contrato_firma):
        self.modelo = modelo
        self.meta = meta
        self.variables = list(meta['variables'])
        self.contrato_firma = contrato_firma
        self.vistas = {c: set(v) for c, v in meta['categorias_vistas'].items()}
        self.infrecuentes = {c: set(v) for c, v in meta.get('categorias_infrecuentes', {}).items()}

    @classmethod
    def cargar(cls, carpeta=None):
        """Carga models/modelo_mlflow y models/metadatos.json (o los de la carpeta indicada) y comprueba firma = metadatos."""
        carpeta = Path(carpeta or config.MODELOS)
        ruta_modelo, ruta_meta = carpeta / config.CARPETA_MODELO_MLFLOW, carpeta / 'metadatos.json'
        if not (ruta_modelo / 'MLmodel').exists() or not ruta_meta.exists():
            raise ModeloNoDisponible(f'No hay modelo en {carpeta}. Entrénalo antes: python -m cafe_mlops.pipeline')
        try:
            meta = json.loads(ruta_meta.read_text(encoding='utf-8'))
            contrato_firma = [(n, t) for n, t, _ in predict.contrato_de_la_firma(ruta_modelo)]
            import mlflow.sklearn
            modelo = mlflow.sklearn.load_model(str(ruta_modelo))
        except Exception as e:      # noqa: BLE001 - un modelo ilegible deja el servicio vivo pero no listo
            raise ModeloNoDisponible(f'No se pudo cargar el modelo de {carpeta}: {type(e).__name__}: {e}') from e
        if not contrato_firma:
            raise ContratoRoto('El modelo no tiene firma: no se puede comprobar el contrato.')
        nombres = [n for n, _ in contrato_firma]
        if nombres != meta['variables']:
            raise ContratoRoto(f'La firma del modelo {nombres} no coincide con metadatos.json {meta["variables"]}.')
        tipos_meta = [(n, meta['tipos'].get(n)) for n in nombres]
        if tipos_meta != contrato_firma:
            raise ContratoRoto(f'Los tipos de la firma {contrato_firma} no coinciden con los de metadatos.json {tipos_meta}.')
        return cls(modelo, meta, contrato_firma)

    def comprobar_contrato(self, contrato_api):
        """El esquema de la API (lista de (nombre, tipo), ver esquemas.contrato_del_esquema) debe tener las MISMAS variables que la
        firma del modelo y con los MISMOS tipos. Si se reentrena con otra variable o con otro tipo y no se actualiza el esquema,
        sin esta comprobación el servicio diría «listo» y fallaría (o predeciría mal) en cada petición."""
        api, firma = dict(contrato_api), dict(self.contrato_firma)
        faltan = [n for n in firma if n not in api]
        sobran = [n for n in api if n not in firma]
        tipos = [f'{n}: la firma dice {firma[n]} y la API {api[n]}' for n in firma if n in api and api[n] != firma[n]]
        if faltan or sobran or tipos:
            raise ContratoRoto(f'El esquema de la API no coincide con la firma del modelo. Faltan en la API: {faltan}. '
                               f'Sobran en la API: {sobran}. Tipos distintos: {tipos}. '
                               'Actualiza cafe_mlops/api/esquemas.py o reentrena con las variables del esquema.')

    def avisos(self, fila):
        """Lo válido que el modelo no vio al entrenar: no se rechaza, se avisa. `fila` es el diccionario recibido."""
        avisos = []
        for c in config.CATEGORICAS:
            v = fila[c]
            if v is None:
                avisos.append(_aviso('valor_no_informado', c, None, f'{c} no informado: el modelo lo trata como «{preproceso.CATEGORIA_NULA}».'))
            elif v not in self.vistas[c]:
                avisos.append(_aviso('categoria_nueva', c, v, f'«{v}» no estaba en los datos de entrenamiento de {c}: el modelo no la '
                                                              'conoce y la predicción tiene menos respaldo.'))
            elif v in self.infrecuentes.get(c, ()):
                avisos.append(_aviso('categoria_infrecuente', c, v, f'«{v}» tenía menos de {preproceso.MIN_FRECUENCIA} lotes al entrenar: '
                                                                    'el modelo la agrupa con otras raras.'))
        for c in config.NUMERICAS:
            v = fila[c]
            if c == 'humedad' and v == 0:
                avisos.append(_aviso('humedad_cero', c, v, 'humedad 0 se trata como «no medido» (como en el entrenamiento): el modelo usa la mediana.'))
            elif v is None:
                avisos.append(_aviso('valor_no_informado', c, None, f'{c} no informado: el modelo usa la mediana del entrenamiento.'))
            else:
                minimo, maximo = self.meta['rangos_entrenamiento'][c]
                if not minimo <= v <= maximo:
                    avisos.append(_aviso('fuera_de_rango_entrenamiento', c, v, f'{c}={v:g} está fuera del rango visto al entrenar '
                                                                               f'[{minimo:g}, {maximo:g}]: la predicción tiene menos respaldo.'))
        return avisos

    def predecir(self, filas):
        """filas: lista de diccionarios con las variables. Devuelve una lista de (probabilidad, avisos), en el mismo orden."""
        datos = [dict(f, humedad=None) if f['humedad'] == 0 else f for f in filas]    # humedad 0 = no medido (decisión 14)
        X = preproceso.preparar_X(datos)          # columnas en el orden de la firma, None -> np.nan, números float64
        prob = np.asarray(self.modelo.predict_proba(X))[:, 1]
        return [(float(p), self.avisos(f)) for p, f in zip(prob, filas)]

    def info(self):
        m = self.meta
        info = {k: m[k] for k in ('modelo', 'objetivo', 'huella_datos', 'entrenado_en', 'variables', 'tipos', 'filas', 'metricas_valid', 'versiones')}
        info['version_modelo'] = self.version
        return info

    @property
    def version(self):
        v = self.meta.get('version_modelo_registrado')
        return None if v is None else str(v)

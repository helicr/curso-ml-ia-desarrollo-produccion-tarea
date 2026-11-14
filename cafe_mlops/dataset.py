"""Fuente, RAW y MASTER: leer los CSV de CQI, ingerir la base operacional en RAW y depurarla en MASTER.

Es la traducción a Python de los cuadernos 00_pipeline_operacional.ipynb (lectura de los archivos) y
01_pipeline_raw_a_master.ipynb. La base operacional se construye con cafe_mlops/operacional.py.

LECTURA
    Los dos CSV (arábica y robusta) tienen 44 columnas; en robusta cambian cinco notas de cata. Aquí se leen SIN cambiar nada
    (todo como texto) y se convierten solo los tipos: números como números; celdas vacías y «NA» como nulos.
    «--hasta AÑO» deja solo los lotes cuya fecha de cata (Grading.Date) es de ese año o anterior.

RAW (dato crudo)
    Copia FIEL de cada tabla del operacional (lotes -> raw_lotes, ...). No corrige ni valida nada: por eso sus tablas no tienen
    claves. La ingesta es una carga completa: borra RAW y lo vuelve a copiar. Linaje: cada fila conserva su clave de origen y
    _carga_id, que apunta a raw_carga (tabla copiada, filas, huella sha256 del contenido y momento de la carga).

MASTER (dato maestro)
    Dato depurado, regenerable desde RAW (sql/master/): fechas a ISO (quitando espacios y saltos de línea), altitud fuera de
    100–4 000 m -> nula, humedad 0 -> nula (no medido), textos recortados; las catas con total 0 se DESCARTAN con su motivo
    (master_descartes). Después evalúa las reglas de calidad de calidad.py; si falla una regla dura, se detiene.

Por qué dos capas: las reglas de limpieza cambian; con RAW intacto, MASTER se rehace sin volver a pedir los datos al origen.

Datos: Coffee Quality Institute (CQI), recopilados por James LeDoux (jldbc/coffee-quality-database, MIT). Ver references/fuente.md.
"""
import hashlib
import math
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import calidad, config, db

TABLAS_OPERACIONALES = ['paises', 'entidades', 'productores', 'lotes', 'analisis_verde', 'catas', 'notas_cata']

# Columna del CSV -> (campo de tmp_origen, tipo). 'texto' se conserva tal cual; 'real' y 'entero' se convierten (vacío y «NA» -> nulo).
# Las notas de cata no están aquí: van a notas_cata (config.NOTAS_CATA). Total.Cup.Points y Species también se leen aparte.
COLUMNAS_LOTE = [
    ('Unnamed: 0', 'id_origen', 'entero'),
    ('Owner', 'propietario', 'texto'),
    ('Country.of.Origin', 'pais', 'texto'),
    ('Farm.Name', 'finca', 'texto'),
    ('Lot.Number', 'numero_lote', 'texto'),
    ('Mill', 'molino', 'texto'),
    ('ICO.Number', 'numero_ico', 'texto'),
    ('Company', 'compania', 'texto'),
    ('Altitude', 'altitud_texto', 'texto'),
    ('Region', 'region', 'texto'),
    ('Producer', 'productor', 'texto'),
    ('Number.of.Bags', 'numero_sacos', 'entero'),
    ('Bag.Weight', 'peso_saco', 'texto'),
    ('In.Country.Partner', 'socio_pais', 'texto'),
    ('Harvest.Year', 'anio_cosecha', 'texto'),
    ('Grading.Date', 'fecha_cata', 'texto'),
    ('Owner.1', 'propietario_2', 'texto'),
    ('Variety', 'variedad', 'texto'),
    ('Processing.Method', 'metodo_proceso', 'texto'),
    ('Moisture', 'humedad', 'real'),
    ('Category.One.Defects', 'defectos_cat1', 'real'),
    ('Quakers', 'quakers', 'real'),
    ('Color', 'color', 'texto'),
    ('Category.Two.Defects', 'defectos_cat2', 'real'),
    ('Expiration', 'caducidad', 'texto'),
    ('Certification.Body', 'certificadora', 'texto'),
    ('Certification.Address', 'cert_direccion', 'texto'),
    ('Certification.Contact', 'cert_contacto', 'texto'),
    ('unit_of_measurement', 'unidad_altitud', 'texto'),
    ('altitude_low_meters', 'altitud_baja_m', 'real'),
    ('altitude_high_meters', 'altitud_alta_m', 'real'),
    ('altitude_mean_meters', 'altitud_media_m', 'real'),
]
CAMPOS_ORIGEN = ['lote_id', 'especie'] + [c for _, c, _ in COLUMNAS_LOTE] + ['total_puntos']

_MESES = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september',
                                      'october', 'november', 'december'], 1)}
_FECHA = re.compile(r'^([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s*,\s*(\d{4})$')


# --------------------------------------------------------------------------------------------------- utilidades
def sha256_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b''):
            h.update(bloque)
    return h.hexdigest()


def _nulo(valor):
    return valor is None or valor is pd.NaT or (isinstance(valor, float) and math.isnan(valor))


def _texto(valor):
    """Conserva el valor TAL CUAL (con sus espacios y saltos de línea). Las celdas vacías son nulos."""
    return None if _nulo(valor) else str(valor)


def _numero(valor, entero=False):
    """Número, o nulo si la celda está vacía o dice «NA» (así marca el CSV la altitud y algún quakers que faltan)."""
    if _nulo(valor) or str(valor).strip() in ('', 'NA'):
        return None
    return int(float(valor)) if entero else float(valor)


def fecha_iso(texto):
    """«April 4th, 2015» -> '2015-04-04'. Quita espacios y saltos de línea alrededor. Nulo si no se puede leer.
    La registra MASTER como función SQL (fecha_iso) para que la regla se escriba en sql/master/02_poblar_master.sql."""
    if texto is None:
        return None
    m = _FECHA.match(str(texto).strip())
    if not m or m.group(1).lower() not in _MESES:
        return None
    try:
        return datetime(int(m.group(3)), _MESES[m.group(1).lower()], int(m.group(2))).strftime('%Y-%m-%d')
    except ValueError:
        return None


def anio_de_cata(texto):
    """Año de Grading.Date tal como llegó (4 dígitos al final, tras quitar espacios y saltos de línea). None si no se lee."""
    m = re.search(r'(\d{4})\s*$', str(texto or ''))
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------------------------------- fuente
def leer_csv(especie):
    """DataFrame con TODAS las columnas del CSV de la especie ('arabica' | 'robusta'), como texto, sin cambiar nada."""
    ruta = Path(config.FUENTES[especie])
    if not ruta.exists():
        raise FileNotFoundError(f'No existe {ruta}. Los CSV vienen en el repositorio (data/raw/cqi); ¿falta algún archivo?')
    return pd.read_csv(ruta, dtype=object, keep_default_na=False, na_values=[''], encoding='utf-8')


def leer_lotes(hasta=None):
    """Lee los dos CSV y devuelve (archivos, lotes, notas).

    archivos: [{'archivo', 'sha256', 'filas_archivo', 'filas_cargadas'}] (uno por CSV)
    lotes:    una tupla por lote, en el orden de los archivos (arábica y luego robusta), con los campos de CAMPOS_ORIGEN.
              lote_id = 1, 2, 3...: propio, porque los ids de arábica y robusta se solapan.
    notas:    [(lote_id, atributo, valor)], las 10 notas de cata de cada lote con el nombre de columna del CSV.
    hasta:    año máximo de cata (Grading.Date); None = todo. Un lote cuya fecha no se puede leer entra siempre (MASTER lo descarta).
    """
    archivos, lotes, notas = [], [], []
    for clave, especie in config.ESPECIES.items():
        df = leer_csv(clave)
        necesarias = [c for c, _, _ in COLUMNAS_LOTE] + [config.COLUMNA_TOTAL] + config.NOTAS_CATA[especie]
        faltan = [c for c in necesarias if c not in df.columns]
        if faltan:
            raise ValueError(f'Al CSV de {clave} le faltan las columnas {faltan}')
        cargadas = 0
        for _, fila in df.iterrows():
            anio = anio_de_cata(fila['Grading.Date'])
            if hasta is not None and anio is not None and anio > hasta:
                continue
            lote_id = len(lotes) + 1
            valores = []
            for csv_col, _, tipo in COLUMNAS_LOTE:
                v = fila[csv_col]
                valores.append(_texto(v) if tipo == 'texto' else _numero(v, entero=(tipo == 'entero')))
            lotes.append((lote_id, especie, *valores, _numero(fila[config.COLUMNA_TOTAL])))
            notas.extend((lote_id, n, _numero(fila[n])) for n in config.NOTAS_CATA[especie])
            cargadas += 1
        ruta = Path(config.FUENTES[clave])
        archivos.append({'archivo': ruta.name, 'sha256': sha256_archivo(ruta), 'filas_archivo': len(df), 'filas_cargadas': cargadas})
    return archivos, lotes, notas


# --------------------------------------------------------------------------------------------------- RAW
def huella_tabla(con, tabla):
    """(filas, sha256) del contenido de una tabla, recorrida en su orden de inserción."""
    h, n = hashlib.sha256(), 0
    for fila in con.execute(f'SELECT * FROM {tabla} ORDER BY rowid'):
        h.update(repr(fila).encode('utf-8'))
        n += 1
    return n, h.hexdigest()


def cargar_raw(con=None, ruta_operacional=None, verbose=True):
    """Ingesta: copia cada tabla de la base operacional en su tabla RAW, TAL COMO ESTÁ, y registra la carga en raw_carga."""
    ruta_operacional = Path(ruta_operacional or config.DB_OPERACIONAL)
    if not ruta_operacional.exists():
        raise FileNotFoundError(f'No existe la base operacional {ruta_operacional}. Créala con: python -m cafe_mlops.operacional')
    cierre = con is None
    con = con or db.conectar()
    db.ejecutar_script(con, config.SQL / 'raw' / '01_crear_raw.sql')
    con.execute('ATTACH DATABASE ? AS cqi', (str(ruta_operacional),))
    try:
        ahora = datetime.now().isoformat(timespec='seconds')
        total = 0
        for tabla in TABLAS_OPERACIONALES:
            filas, huella = huella_tabla(con, f'cqi.{tabla}')
            carga = con.execute('INSERT INTO raw_carga (origen, tabla, filas, sha256, extraido_en) VALUES (?,?,?,?,?)',
                                ('cqi', tabla, filas, huella, ahora)).lastrowid
            con.execute(f'INSERT INTO raw_{tabla} SELECT t.*, ? FROM cqi.{tabla} AS t ORDER BY t.rowid', (carga,))
            total += filas
            if verbose:
                print(f'  RAW: raw_{tabla:15s} {filas:>8,} filas')
        con.commit()
    except Exception:
        con.rollback()   # una ingesta a medias no se queda en RAW
        raise
    finally:
        con.execute('DETACH DATABASE cqi')
    if cierre:
        con.close()
    return total


# --------------------------------------------------------------------------------------------------- MASTER
def construir_master(con=None, verbose=True):
    """Depura RAW; después evalúa las reglas de calidad (ver calidad.py). Se detiene si falla una regla dura."""
    cierre = con is None
    con = con or db.conectar()
    con.create_function('fecha_iso', 1, fecha_iso, deterministic=True)
    db.ejecutar_script(con, config.SQL / 'master' / '01_crear_master.sql')
    parametros = {
        'altitud_min_m': config.ALTITUD_MIN_M, 'altitud_max_m': config.ALTITUD_MAX_M,
        'humedad_no_medida': config.HUMEDAD_NO_MEDIDA,
    }
    con.executemany('INSERT INTO master_parametros (clave, valor) VALUES (?, ?)', list(parametros.items()))
    db.ejecutar_script(con, config.SQL / 'master' / '02_poblar_master.sql')
    resultados = calidad.evaluar(con, lanzar=True)
    if verbose:
        for tabla in ('master_lotes', 'master_descartes'):
            print(f'  MASTER: {tabla:18s} {db.escalar(con, f"SELECT COUNT(*) FROM {tabla}"):>8,} filas')
        alertas = [r for r in resultados if r['estado'] == 'ALERTA']
        print(f'  MASTER: calidad: {len(resultados)} reglas, {len(alertas)} alertas ({", ".join(r["regla"][:3] for r in alertas) or "ninguna"})')
    if cierre:
        con.close()
    return resultados

"""Base operacional «cqi»: simula el sistema del laboratorio de catas, que es la fuente del pipeline.

Es la traducción a Python del cuaderno notebooks/00_pipeline_operacional.ipynb.

QUÉ ES UN SISTEMA OPERACIONAL (OLTP)
    La base con la que funciona el negocio: registra cada lote y cada cata en el momento. Está NORMALIZADA (cada dato se
    guarda una sola vez, en la tabla a la que pertenece) y tiene claves y restricciones. El pipeline analítico la LEE,
    nunca escribe en ella.

POR QUÉ SE SIMULA
    Los CSV de CQI son una exportación plana (una fila por lote, con el país y las diez notas en columnas). Aquí se hace el
    camino inverso: se reconstruye el modelo normalizado que tendría el laboratorio, y el pipeline ingiere desde una base de
    datos, como en producción.

MODELO (sql/operacional/01_crear_operacional.sql)
    paises, entidades, productores -> lotes 1--1 analisis_verde ; lotes 1--1 catas 1--10 notas_cata
    + origen_simulacion: control (de qué archivos sale la simulación y hasta qué año). No es parte del negocio.

NO LIMPIA NADA
    La suciedad del origen (fechas con saltos de línea, altitudes imposibles, humedad 0, una cata con total 0) se conserva
    para que RAW la reciba y MASTER la trate. La base conserva las 44 columnas de cada CSV: una prueba reconstruye cada fila.

DATOS NUEVOS (--hasta)
    --hasta 2016  situación inicial: solo las catas hasta 2016 (versión 1 de los datos; 1 190 lotes).
    --hasta 2018  llegan los lotes de 2017 y 2018 (versión 2; 1 339 lotes). Los pipelines lo detectan por la huella.

Uso desde la terminal (en la raíz del proyecto):
    python -m cafe_mlops.operacional                 # --hasta 2016 (por defecto)
    python -m cafe_mlops.operacional --hasta 2018
"""
import argparse
from datetime import datetime

from . import config, db
from .dataset import CAMPOS_ORIGEN, leer_lotes

TABLAS = ['paises', 'entidades', 'productores', 'lotes', 'analisis_verde', 'catas', 'notas_cata']   # el modelo de negocio


def crear_operacional(hasta=config.HASTA_INICIAL, ruta=None, verbose=True):
    """Crea data/external/cqi.db con las catas hasta el año `hasta` y devuelve el número de lotes."""
    version = config.version_de_datos(hasta)
    archivos, lotes, notas = leer_lotes(hasta)
    con = db.conectar(ruta or config.DB_OPERACIONAL)
    try:
        db.ejecutar_script(con, config.SQL / 'operacional' / '01_crear_operacional.sql')
        con.execute('DROP TABLE IF EXISTS temp.tmp_origen')
        con.execute('DROP TABLE IF EXISTS temp.tmp_notas')
        con.execute('CREATE TEMP TABLE tmp_origen (' + ', '.join(CAMPOS_ORIGEN) + ')')
        con.execute('CREATE TEMP TABLE tmp_notas (lote_id INTEGER, atributo TEXT, valor REAL)')
        con.executemany(f'INSERT INTO temp.tmp_origen VALUES ({",".join("?" * len(CAMPOS_ORIGEN))})', lotes)
        con.executemany('INSERT INTO temp.tmp_notas VALUES (?,?,?)', notas)
        por_lote = db.escalar(con, 'SELECT COUNT(*) FROM (SELECT lote_id FROM temp.tmp_notas GROUP BY lote_id HAVING COUNT(*) <> 10)')
        if por_lote:
            raise ValueError(f'El origen no tiene diez notas de cata en {por_lote} lotes: no se puede normalizar sin perder información')
        db.ejecutar_script(con, config.SQL / 'operacional' / '02_poblar_operacional.sql')
        ahora = datetime.now().isoformat(timespec='seconds')
        con.executemany('INSERT INTO origen_simulacion (archivo, sha256, filas_archivo, filas_cargadas, hasta, version_datos, creada_en) '
                        'VALUES (?,?,?,?,?,?,?)',
                        [(a['archivo'], a['sha256'], a['filas_archivo'], a['filas_cargadas'], hasta, version, ahora) for a in archivos])
        con.execute('DROP TABLE temp.tmp_origen')
        con.execute('DROP TABLE temp.tmp_notas')
        con.commit()
        if verbose:
            print(f'  OPERACIONAL: catas hasta {hasta} (versión {version} de los datos)')
            for tabla in TABLAS:
                print(f'  OPERACIONAL: {tabla:15s} {db.escalar(con, f"SELECT COUNT(*) FROM {tabla}"):>8,} filas')
        return len(lotes)
    finally:
        con.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--hasta', type=int, choices=sorted(config.VERSIONES_DATOS), default=config.HASTA_INICIAL,
                    help='año de cata máximo: 2016 = versión 1 (situación inicial), 2018 = versión 2 (llegan lotes nuevos)')
    crear_operacional(ap.parse_args().hasta)

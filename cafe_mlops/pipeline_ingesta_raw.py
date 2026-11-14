"""Pipeline de INGESTA A RAW: base operacional (cqi.db) -> capa RAW de la base analítica (cafe.db).

Cuaderno equivalente: notebooks/01_pipeline_raw_a_master.ipynb, sección 1.
Entrada: las 7 tablas de negocio de cqi.db (la crea `python -m cafe_mlops.operacional`, que simula el sistema del laboratorio).
Salida:  raw_paises, raw_entidades, raw_productores, raw_lotes, raw_analisis_verde, raw_catas, raw_notas_cata y raw_carga.

Idempotente (ver control.py): la huella de entrada es el CONTENIDO de las tablas de origen + el SQL de RAW + el código de la ingesta.
Si el origen no cambió desde la última ingesta, no hace nada; si cambió (por ejemplo, de --hasta 2016 a --hasta 2018, o una
sola fila), vuelve a copiar todo.

Uso (desde la raíz del proyecto):
    python -m cafe_mlops.pipeline_ingesta_raw
    python -m cafe_mlops.pipeline_ingesta_raw --forzar        # rehace la ingesta aunque el origen no haya cambiado
"""
import argparse
from pathlib import Path

from . import config, control, dataset, db

PIPELINE = 'pipeline_ingesta_raw'
SALIDA = ['raw_' + t for t in dataset.TABLAS_OPERACIONALES] + ['raw_carga']


def huella_entrada(con, ruta_operacional):
    con.execute('ATTACH DATABASE ? AS cqi', (str(ruta_operacional),))
    try:
        origen = {t: dataset.huella_tabla(con, f'cqi.{t}') for t in dataset.TABLAS_OPERACIONALES}
    finally:
        con.execute('DETACH DATABASE cqi')
    return control.huella(origen, control.huella_archivos(config.SQL / 'raw' / '01_crear_raw.sql'), control.huella_codigo(dataset.cargar_raw))


def ejecutar(ruta_db=None, ruta_operacional=None, forzar=False, verbose=True):
    ruta_operacional = Path(ruta_operacional or config.DB_OPERACIONAL)
    if not ruta_operacional.exists():
        raise control.EntradaFaltanteError(f'No existe la base operacional {ruta_operacional}. Créala con:  python -m cafe_mlops.operacional')
    con = db.conectar(ruta_db)
    try:
        def trabajo():
            dataset.cargar_raw(con, ruta_operacional, verbose)
            return {'tablas': dict(con.execute('SELECT tabla, filas FROM raw_carga ORDER BY carga_id').fetchall())}
        return control.ejecutar(con, PIPELINE, huella_entrada(con, ruta_operacional),
                                lambda: all(control.existe(con, t) for t in SALIDA), trabajo, forzar, verbose)
    finally:
        con.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--forzar', action='store_true', help='rehace la ingesta aunque el origen no haya cambiado')
    control.desde_terminal(ejecutar, forzar=ap.parse_args().forzar)

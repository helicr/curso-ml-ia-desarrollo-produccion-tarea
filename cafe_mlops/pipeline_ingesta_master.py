"""Pipeline RAW -> MASTER: depura RAW y evalúa las reglas de calidad.

Cuaderno equivalente: notebooks/01_pipeline_raw_a_master.ipynb, secciones 2 a 4.
Entrada: la capa RAW (la produce pipeline_ingesta_raw).
Salida:  master_lotes (un lote catado por fila), master_descartes y master_calidad.
Si falla una regla de calidad DURA, se detiene con error y no registra la ejecución.

Idempotente (ver control.py): la huella de entrada es la huella de cada tabla RAW (la guarda raw_carga) + los SQL de MASTER
+ las reglas de calidad + los parámetros de config.py que usa MASTER. Si nada de eso cambió, no hace nada.

Uso (desde la raíz del proyecto):
    python -m cafe_mlops.pipeline_ingesta_master
    python -m cafe_mlops.pipeline_ingesta_master --forzar
"""
import argparse

from . import calidad, config, control, dataset, db

PIPELINE = 'pipeline_ingesta_master'
ENTRADA = ['raw_lotes', 'raw_analisis_verde', 'raw_catas', 'raw_notas_cata', 'raw_paises', 'raw_carga']
SALIDA = ['master_lotes', 'master_calidad']


def huella_entrada(con):
    raw = con.execute('SELECT tabla, filas, sha256 FROM raw_carga ORDER BY tabla').fetchall()
    sql = control.huella_archivos(config.SQL / 'master' / '01_crear_master.sql', config.SQL / 'master' / '02_poblar_master.sql')
    parametros = (config.ALTITUD_MIN_M, config.ALTITUD_MAX_M, config.HUMEDAD_NO_MEDIDA, config.UMBRAL_ESPECIALIDAD,
                  config.FECHA_CATA_MINIMA, config.FECHA_CATA_LIMITE)
    return control.huella(raw, sql, parametros, control.huella_codigo(calidad, dataset.construir_master, dataset.fecha_iso))


def ejecutar(ruta_db=None, forzar=False, verbose=True):
    con = db.conectar(ruta_db)
    try:
        control.exigir(con, ENTRADA, 'pipeline_ingesta_raw')

        def trabajo():
            resultados = dataset.construir_master(con, verbose)
            filas = {t: db.escalar(con, f'SELECT COUNT(*) FROM {t}') for t in SALIDA + ['master_descartes']}
            return {'filas': filas, 'alertas': [r['regla'] for r in resultados if r['estado'] == 'ALERTA']}
        return control.ejecutar(con, PIPELINE, huella_entrada(con), lambda: all(control.existe(con, t) for t in SALIDA), trabajo, forzar, verbose)
    finally:
        con.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--forzar', action='store_true', help='rehace MASTER aunque RAW y las reglas no hayan cambiado')
    control.desde_terminal(ejecutar, forzar=ap.parse_args().forzar)

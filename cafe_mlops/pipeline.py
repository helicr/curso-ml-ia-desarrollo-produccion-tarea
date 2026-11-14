"""Orquestador: ejecuta, en orden, los pipelines que se le pidan. No tiene lógica de datos propia.

Los pipelines son INDEPENDIENTES: cada uno se puede ejecutar solo, comprueba que existe su entrada y es IDEMPOTENTE
(si su entrada no cambió, no hace nada: «sin cambios»). Este módulo es solo una comodidad para lanzarlos seguidos; los
workflows de GitHub Actions lanzan cada uno como un paso.

    pipeline_ingesta_raw     cqi.db (operacional) -> RAW
    pipeline_ingesta_master  RAW -> MASTER (+ reglas de calidad)
    pipeline_ml              MASTER -> FS -> ML
    pipeline_train           ML -> modelo, métricas y MLflow (cada entrenamiento crea una versión nueva del modelo registrado)

La base operacional NO es un pipeline: simula el sistema del laboratorio (python -m cafe_mlops.operacional). Por comodidad, este
orquestador la crea si todavía no existe (un clon recién hecho, el CI, un Codespace) y la vuelve a crear si se pide con --hasta
un año distinto del que tiene. Los pipelines sueltos nunca la crean: si falta, lo dicen.

DATOS NUEVOS:  --hasta 2016 = situación inicial (versión 1 de los datos);  --hasta 2018 = llegan los lotes de 2017 y 2018
(versión 2): se rehacen RAW, MASTER, FS/ML y el entrenamiento, y se registra la versión 2 del modelo.

Uso (desde la raíz del proyecto):
    python -m cafe_mlops.pipeline                       # los cuatro, en orden (los que no cambian, no hacen nada)
    python -m cafe_mlops.pipeline --hasta 2018          # llegan lotes nuevos: rehace todo lo que dependa de ellos
    python -m cafe_mlops.pipeline --solo pipeline_ml pipeline_train
    python -m cafe_mlops.pipeline --forzar              # rehace todos aunque no haya cambios
    python -m cafe_mlops.pipeline --sin-mlflow
"""
import argparse
import sqlite3
import time
from pathlib import Path

from . import config, control, operacional, pipeline_ingesta_master, pipeline_ingesta_raw, pipeline_ml, pipeline_train

PIPELINES = {
    'pipeline_ingesta_raw': lambda a: pipeline_ingesta_raw.ejecutar(a['ruta_db'], a['ruta_operacional'], a['forzar'], a['verbose']),
    'pipeline_ingesta_master': lambda a: pipeline_ingesta_master.ejecutar(a['ruta_db'], a['forzar'], a['verbose']),
    'pipeline_ml': lambda a: pipeline_ml.ejecutar(a['ruta_db'], a['forzar'], a['verbose']),
    'pipeline_train': lambda a: pipeline_train.ejecutar(a['ruta_db'], a['forzar'], a['usar_mlflow'], a['verbose']),
}


def hasta_de_la_operacional(ruta):
    """Año máximo con el que se creó la base operacional (tabla origen_simulacion), o None si no existe o no se puede leer."""
    ruta = Path(ruta)
    if not ruta.exists():
        return None
    con = sqlite3.connect(ruta)
    try:
        fila = con.execute('SELECT MAX(hasta) FROM origen_simulacion').fetchone()
        return fila[0] if fila else None
    except sqlite3.Error:
        return None
    finally:
        con.close()


def preparar_operacional(hasta, ruta_operacional, verbose):
    """Crea la base operacional si no existe (con config.HASTA_INICIAL si no se pide otra) o si se pide un --hasta distinto del
    que tiene. Si ya tiene ese --hasta, no la toca (así la segunda ejecución sigue siendo «sin cambios»)."""
    ruta = Path(ruta_operacional or config.DB_OPERACIONAL)
    actual = hasta_de_la_operacional(ruta)
    if actual is not None and (hasta is None or hasta == actual):
        return
    nuevo = hasta or config.HASTA_INICIAL
    if verbose:
        motivo = 'todavía no existe' if actual is None else f'tenía catas hasta {actual}'
        print(f'[operacional] creando {ruta.name} con catas hasta {nuevo} ({motivo}); es la simulación del laboratorio, no un pipeline')
    operacional.crear_operacional(nuevo, ruta, verbose)


def ejecutar(pipelines=None, ruta_db=None, ruta_operacional=None, forzar=False, usar_mlflow=True, verbose=True, hasta=None):
    """Ejecuta los pipelines pedidos (todos por defecto) en su orden natural y devuelve el resultado de cada uno."""
    pedidos = pipelines or list(PIPELINES)
    desconocidos = [p for p in pedidos if p not in PIPELINES]
    if desconocidos:
        raise ValueError(f'Pipelines desconocidos: {desconocidos}. Válidos: {list(PIPELINES)}')
    if hasta is not None:
        config.version_de_datos(hasta)    # falla con un mensaje claro si no es uno de los previstos
    if 'pipeline_ingesta_raw' in pedidos:
        preparar_operacional(hasta, ruta_operacional, verbose)
    args = dict(ruta_db=ruta_db, ruta_operacional=ruta_operacional, forzar=forzar, usar_mlflow=usar_mlflow, verbose=verbose)
    resultados = []
    for nombre in PIPELINES:              # siempre en el orden natural, aunque se pidan desordenados
        if nombre in pedidos:
            t0 = time.time()
            resultados.append(PIPELINES[nombre](args))
            if verbose:
                print(f'  ({time.time() - t0:.1f} s)')
    if verbose:
        print('Resumen: ' + ' · '.join(f'{r["pipeline"].removeprefix("pipeline_")}: {r["estado"]}' for r in resultados))
    return resultados


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--solo', nargs='+', choices=list(PIPELINES), help='solo estos pipelines')
    ap.add_argument('--hasta', type=int, choices=sorted(config.VERSIONES_DATOS),
                    help='año de cata máximo de la base operacional: 2016 = versión 1, 2018 = versión 2 (llegan lotes nuevos)')
    ap.add_argument('--forzar', action='store_true', help='rehace aunque la entrada no haya cambiado')
    ap.add_argument('--sin-mlflow', action='store_true')
    a = ap.parse_args()
    control.desde_terminal(ejecutar, pipelines=a.solo, forzar=a.forzar, usar_mlflow=not a.sin_mlflow, hasta=a.hasta)

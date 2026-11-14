"""Compara, con dos comprobaciones distintas, el modelo entrenado.

1. CAMINOS: las probabilidades de los distintos caminos hacia el MISMO modelo («comparar predicciones»).
   Toma filas reales de la partición test de `ml_dataset` y calcula la probabilidad de cada una por:
     el paquete (cafe_mlops.modeling.predict) · el archivo joblib · el formato MLflow (sklearn) · MLflow pyfunc
     (pyfunc_predict_fn='predict_proba') · la API (solo si se pasa --url: local o en un contenedor).
   Si el modelo es el mismo, las diferencias son ceros de máquina (tolerancia TOLERANCIA). Una diferencia mayor significa que algo
   cambia entre el entrenamiento y el servicio (otra versión de una librería, otro orden de columnas, otro preprocesado, un None
   que no se trata como nulo...) y hay que encontrarlo ANTES de desplegar.

2. REFERENCIA: la candidata (el modelo recién entrenado, models/metadatos.json) frente a la versión aprobada guardada en el
   repositorio (models/referencia.json). La candidata NO se aprueba si la métrica de comparación (config.METRICA_COMPARACION,
   `auc_comun`) empeora más que config.TOLERANCIA_COMPARACION (diferencia absoluta).
   MÉTRICA COMPARABLE: la partición desliza con la versión de los datos (v1: valid 2015; v2: valid 2016), así que el AUC de valid
   de dos versiones se mide sobre lotes distintos y no se puede comparar. Por eso se compara el AUC sobre una VENTANA COMÚN fija
   (config.VENTANA_COMUN = 2016): son los MISMOS lotes en las dos versiones y ninguna de las dos los vio al entrenar (la v1 es
   su test; la v2, su valid, con lo que su cifra es algo optimista porque también sirvió para elegir modelo). La referencia guarda
   la ventana con la que se calculó y, si no coincide con la de la candidata, no se compara (no se mezclan ventanas distintas).
   TODO-T08: esa tolerancia (0,02) es PROVISIONAL, no sale de una medición; con pocos lotes sin especialidad en la ventana (5) el
   AUC oscila más que eso por puro azar del corte (pico T07). Mejorar un modelo o empeorarlo «0,02» no es una señal fiable.
   `--fijar-referencia` guarda la candidata como nueva referencia (lo hace un humano, o el workflow tras la aprobación).

Uso (desde la raíz del proyecto, con el modelo ya entrenado):
    python -m cafe_mlops.modeling.comparar                              # caminos + referencia
    python -m cafe_mlops.modeling.comparar --url http://127.0.0.1:8080  # además, la API
    python -m cafe_mlops.modeling.comparar --fijar-referencia           # la candidata pasa a ser la referencia
Código de salida: 0 todo coincide y la candidata no empeora · 1 hay diferencias o empeora · 2 no se pudo comparar.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .. import config, db
from . import predict, preproceso

TOLERANCIA = 1e-9       # entre caminos: ceros de máquina
LOTE_API = 100          # lotes por petición (la API admite hasta 1000: esquemas.MAX_LOTES)


class NoSePudoComparar(RuntimeError):
    pass


# ----------------------------------------------------------------------------------------------------------- caminos
def filas_de_test(n, ruta_db=None):
    """Hasta `n` filas reales de la partición test (solo las variables, sin el objetivo), en orden de lote."""
    if not Path(ruta_db or config.DB).exists():
        raise NoSePudoComparar(f'No existe la base {ruta_db or config.DB}. Ejecuta antes: python -m cafe_mlops.pipeline')
    con = db.conectar(ruta_db)
    try:
        df = pd.read_sql(f"SELECT {', '.join(config.FEATURES)} FROM ml_dataset WHERE particion = 'test' ORDER BY lote_id LIMIT {int(n)}", con)
    except Exception as e:      # noqa: BLE001 - sin tabla ml_dataset
        raise NoSePudoComparar(f'No se pudieron leer filas de test de {ruta_db or config.DB}: {e}. Ejecuta antes: python -m cafe_mlops.pipeline') from e
    finally:
        con.close()
    if df.empty:
        raise NoSePudoComparar('La partición test está vacía. Ejecuta antes: python -m cafe_mlops.pipeline')
    return df


def del_paquete(df, carpeta):
    return np.array(predict.predecir_probabilidad(df, ruta=carpeta))


def del_joblib(df, carpeta):
    return joblib.load(carpeta / 'modelo.joblib').predict_proba(preproceso.preparar_X(df))[:, 1]


def _carpeta_mlflow(carpeta):
    ruta = carpeta / config.CARPETA_MODELO_MLFLOW
    if not ruta.exists():
        raise NoSePudoComparar(f'No existe {ruta}. Ejecuta antes: python -m cafe_mlops.pipeline')
    return ruta


def del_mlflow(df, carpeta):
    import mlflow.sklearn
    return mlflow.sklearn.load_model(str(_carpeta_mlflow(carpeta))).predict_proba(preproceso.preparar_X(df))[:, 1]


def del_pyfunc(df, carpeta):
    """mlflow.pyfunc valida la firma y, guardado con pyfunc_predict_fn='predict_proba', devuelve (n, 2): columna 1 = especialidad."""
    import mlflow.pyfunc
    return np.asarray(mlflow.pyfunc.load_model(str(_carpeta_mlflow(carpeta))).predict(preproceso.preparar_X(df)))[:, 1]


def de_la_api(df, url):
    """Pide las probabilidades a la API (POST /predecir/lote, por tandas). Contrato confirmado con la API real (T10, cafe_mlops/api):
    cuerpo {'lotes': [...]} (1 a 1000 lotes) y respuesta {'predicciones': [{'probabilidad_especialidad': ..., ...}]} en el mismo orden."""
    filas = json.loads(preproceso.preparar_X(df).to_json(orient='records'))     # NaN -> null
    salida = []
    for i in range(0, len(filas), LOTE_API):
        cuerpo = json.dumps({'lotes': filas[i:i + LOTE_API]}).encode('utf-8')
        peticion = urllib.request.Request(url.rstrip('/') + '/predecir/lote', data=cuerpo, headers={'content-type': 'application/json'})
        try:
            with urllib.request.urlopen(peticion, timeout=30) as r:
                respuesta = json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise NoSePudoComparar(f'La API respondió {e.code} en {url}: {e.read().decode("utf-8", "replace")[:300]}') from e
        except (urllib.error.URLError, OSError) as e:
            raise NoSePudoComparar(f'No se pudo hablar con la API en {url}: {e}. ¿Está arrancada? (make api, o el contenedor)') from e
        salida += [p['probabilidad_especialidad'] for p in respuesta['predicciones']]
    return np.array(salida)


def comparar_caminos(n=100, url=None, carpeta=None, ruta_db=None, tolerancia=TOLERANCIA):
    """Devuelve (filas, n, tolerancia): una fila por camino con su diferencia máxima respecto al paquete."""
    carpeta = carpeta or config.MODELOS
    if not (carpeta / 'modelo.joblib').exists():
        raise NoSePudoComparar(f'No hay modelo en {carpeta}. Ejecuta antes: python -m cafe_mlops.pipeline')
    df = filas_de_test(n, ruta_db)
    referencia = del_paquete(df, carpeta)
    caminos = [('paquete (referencia)', referencia), ('joblib', del_joblib(df, carpeta)), ('MLflow sklearn', del_mlflow(df, carpeta)),
               ('MLflow pyfunc', del_pyfunc(df, carpeta))]
    if url:
        caminos.append((f'API {url}', de_la_api(df, url)))
    filas = []
    for nombre, p in caminos:
        dif = float(np.max(np.abs(p - referencia))) if len(p) == len(referencia) else float('inf')
        filas.append({'camino': nombre, 'filas': int(len(p)), 'diferencia_maxima': dif, 'coincide': bool(dif <= tolerancia)})
    return filas, len(df), tolerancia


# ----------------------------------------------------------------------------------------------------------- referencia
def leer_candidata(carpeta=None):
    """Lo que se compara de la candidata: huella, métrica de validación y versión de los datos (de models/metadatos.json)."""
    carpeta = carpeta or config.MODELOS
    ruta = carpeta / 'metadatos.json'
    if not ruta.exists():
        raise NoSePudoComparar(f'No hay {ruta}. Ejecuta antes: python -m cafe_mlops.pipeline')
    meta = json.loads(ruta.read_text(encoding='utf-8'))
    metrica = config.METRICA_COMPARACION.removesuffix('_comun')
    return {'modelo': meta['modelo'], 'huella_datos': meta['huella_datos'], 'anio_cata_maximo': meta['anio_cata_maximo'],
            'version_datos': meta['version_datos'], 'ventana_comun': meta['ventana_comun'],
            config.METRICA_COMPARACION: meta['metricas_comun'][metrica], 'metricas_comun': meta['metricas_comun'],
            'metricas_valid': meta['metricas_valid'], 'particiones': meta['particiones'], 'filas': meta['filas'],
            'entrenado_en': meta['entrenado_en']}


def leer_referencia(ruta=None):
    ruta = Path(ruta or config.REFERENCIA)
    if not ruta.exists():
        raise NoSePudoComparar(f'No existe {ruta}: no hay versión de referencia. Fíjala con:  python -m cafe_mlops.modeling.comparar --fijar-referencia')
    return json.loads(ruta.read_text(encoding='utf-8'))


def comparar_con_referencia(candidata, referencia, tolerancia=None):
    """Compara la métrica sobre la ventana común. Devuelve un diccionario con la diferencia y si la candidata se aprueba
    (aprobada = no empeora más que la tolerancia). Si las dos dicen haberse medido en ventanas distintas, no se compara."""
    tolerancia = config.TOLERANCIA_COMPARACION if tolerancia is None else tolerancia
    metrica = config.METRICA_COMPARACION
    if candidata.get('ventana_comun') != referencia.get('ventana_comun') and (candidata.get('ventana_comun') or referencia.get('ventana_comun')):
        raise NoSePudoComparar(f'La referencia se midió en la ventana {referencia.get("ventana_comun")} y la candidata en '
                               f'{candidata.get("ventana_comun")}: no son comparables. Recalcula la referencia (--fijar-referencia).')
    ref, cand = float(referencia[metrica]), float(candidata[metrica])
    dif = cand - ref
    # 1e-12: la tolerancia es «empeora MÁS que», y los flotantes no deben decidir un caso justo en el límite
    return {'metrica': metrica, 'referencia': ref, 'candidata': cand, 'diferencia': dif, 'tolerancia': tolerancia,
            'misma_huella_datos': candidata['huella_datos'] == referencia.get('huella_datos'),
            'aprobada': bool(dif >= -tolerancia - 1e-12)}


def fijar_referencia(carpeta=None, ruta=None):
    """Guarda la candidata como referencia (models/referencia.json). Lo hace una persona o el workflow tras aprobar."""
    ruta = Path(ruta or config.REFERENCIA)
    c = leer_candidata(carpeta)
    ref = {'nota': 'Versión de referencia aprobada: la candidata se compara con esta (python -m cafe_mlops.modeling.comparar). '
                   'No se edita a mano: la actualiza --fijar-referencia (en el workflow, un pull request).',
           'metrica': config.METRICA_COMPARACION, **c}
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(ref, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return ref


# ----------------------------------------------------------------------------------------------------------- terminal
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--url', help='URL base de la API (p. ej. http://127.0.0.1:8080). Sin ella no se comprueba la API.')
    ap.add_argument('--n', type=int, default=100, help='cuántas filas de test usar para los caminos (por defecto 100)')
    ap.add_argument('--tolerancia', type=float, default=TOLERANCIA, help='tolerancia entre caminos')
    ap.add_argument('--tolerancia-referencia', type=float, default=config.TOLERANCIA_COMPARACION,
                    help='cuánto puede empeorar la métrica de validación frente a la referencia (TODO-T08: provisional)')
    ap.add_argument('--fijar-referencia', action='store_true', help='guarda la candidata como nueva referencia y sale')
    a = ap.parse_args(argv)
    try:
        if a.fijar_referencia:
            ref = fijar_referencia()
            print(f'Referencia fijada en {config.REFERENCIA}: {config.METRICA_COMPARACION} = {ref[config.METRICA_COMPARACION]:.4f} '
                  f'(modelo {ref["modelo"]}, datos {ref["huella_datos"]})')
            return 0
        filas, n, tol = comparar_caminos(a.n, a.url, tolerancia=a.tolerancia)
        candidata = leer_candidata()
        resultado = comparar_con_referencia(candidata, leer_referencia(), a.tolerancia_referencia)
    except NoSePudoComparar as e:
        print(f'No se pudo comparar: {e}', file=sys.stderr)
        return 2
    print(f'{n} filas reales de la partición test · tolerancia {tol:g}')
    print(f'{"camino":<40}{"filas":>7}{"diferencia máxima":>22}  resultado')
    for f in filas:
        print(f'{f["camino"]:<40}{f["filas"]:>7}{f["diferencia_maxima"]:>22.3e}  {"coincide" if f["coincide"] else "DIFIERE"}')
    todo = all(f['coincide'] for f in filas)
    print('Todos los caminos dan la misma probabilidad.' if todo else 'HAY DIFERENCIAS: busca qué cambia entre el entrenamiento y el servicio.')
    r = resultado
    print(f'Ventana común {candidata["ventana_comun"][0]}-{candidata["ventana_comun"][1]} (los mismos lotes en todas las versiones; '
          f'versión de datos de la candidata: {candidata["version_datos"]})')
    print(f'Referencia: {r["metrica"]} candidata {r["candidata"]:.4f} frente a referencia {r["referencia"]:.4f} '
          f'(diferencia {r["diferencia"]:+.4f}, tolerancia {r["tolerancia"]:g}; mismos datos: {"sí" if r["misma_huella_datos"] else "no"}) -> '
          + ('APROBADA' if r['aprobada'] else 'RECHAZADA: empeora más que la tolerancia'))
    return 0 if (todo and r['aprobada']) else 1


if __name__ == '__main__':
    sys.exit(main())

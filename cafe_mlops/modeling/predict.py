"""Predicción con el modelo entrenado. Es la base de la API.

El modelo guardado incluye el preprocesado (imputar, one-hot): este módulo solo entrega las variables, en el orden y con los tipos
de la firma (texto con np.nan por nulo, números float64), y el modelo hace el resto. Así el servicio y el entrenamiento comparten
el MISMO preprocesado. Un None, un NaN o un pd.NA en una variable de texto dan la misma probabilidad (pico T07, cambio 1).

Carga models/modelo.joblib (el mejor modelo, guardado por train.py) y models/metadatos.json (la lista de variables).
No usa MLflow para predecir: MLflow es el historial de entrenamientos; el servicio solo necesita el modelo elegido.
(contrato_de_la_firma sí lee la firma guardada en formato MLflow, y la importa solo cuando se llama.)

Uso:
    from cafe_mlops.modeling import predict
    predict.predecir_probabilidad({'especie': 'Arabica', 'pais': 'Colombia', ...})
    python -m cafe_mlops.modeling.predict --lote 12          # un lote de la capa FS
"""
import argparse
import json

import joblib

from .. import config, db
from . import preproceso

_CACHE = {}


class VariablesFaltantesError(ValueError):
    pass


def cargar_modelo(ruta=None):
    """Carga el modelo y sus metadatos (se guardan en memoria para no leer el disco en cada predicción)."""
    carpeta = ruta or config.MODELOS
    clave = str(carpeta)
    if clave not in _CACHE:
        modelo = joblib.load(carpeta / 'modelo.joblib')
        meta = json.loads((carpeta / 'metadatos.json').read_text(encoding='utf-8'))
        _CACHE[clave] = (modelo, meta)
    return _CACHE[clave]


def olvidar_cache():
    _CACHE.clear()


def predecir_probabilidad(variables, ruta=None):
    """Probabilidad de que el lote sea café de especialidad.

    variables: un diccionario o un DataFrame con las columnas de config.FEATURES (cualquier orden). Devuelve un float si recibe
    un diccionario y una lista de floats si recibe un DataFrame. Las variables pueden ser None/NaN (el modelo las imputa).
    """
    modelo, meta = cargar_modelo(ruta)
    datos = [variables] if isinstance(variables, dict) else variables
    try:
        X = preproceso.preparar_X(datos)
    except KeyError as e:
        raise VariablesFaltantesError(str(e.args[0])) from e
    if list(X.columns) != meta['variables']:
        raise VariablesFaltantesError(f'Las variables del modelo son {meta["variables"]}, no {list(X.columns)}')
    prob = modelo.predict_proba(X)[:, 1]
    return float(prob[0]) if isinstance(variables, dict) else [float(p) for p in prob]


def predecir_lote(lote_id, con=None, ruta=None):
    """Lee las variables del lote en la capa FS y devuelve su probabilidad."""
    import pandas as pd
    cierre = con is None
    con = con or db.conectar()
    fila = pd.read_sql(f'SELECT {", ".join(config.FEATURES)} FROM fs_lote WHERE lote_id = :l', con, params={'l': int(lote_id)})
    if cierre:
        con.close()
    if fila.empty:
        raise LookupError(f'No hay variables en FS para el lote {lote_id}.')
    return predecir_probabilidad(fila.iloc[0].to_dict(), ruta)


def contrato_de_la_firma(carpeta=None):
    """La firma del modelo en formato MLflow como lista de (nombre, tipo, required): es el contrato de la API (nombres y TIPOS).
    «required» no impide pasar nulos (pico T07); no se use para decidir si un campo admite nulo."""
    from mlflow.models import Model
    carpeta = carpeta or (config.MODELOS / config.CARPETA_MODELO_MLFLOW)
    firma = Model.load(str(carpeta)).signature
    return [(c.name, c.type.name, bool(c.required)) for c in firma.inputs.inputs]


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--lote', type=int, required=True, help='lote_id de la capa FS')
    a = ap.parse_args()
    print(f'Probabilidad de especialidad (>= {config.UMBRAL_ESPECIALIDAD:g}) del lote {a.lote}: {predecir_lote(a.lote):.3f}')

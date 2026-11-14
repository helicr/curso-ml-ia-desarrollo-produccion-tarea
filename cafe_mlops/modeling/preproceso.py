"""Preprocesado del modelo: todo lo que va DENTRO del Pipeline de scikit-learn y la preparación de las entradas.

Resultado del pico T07 (_exploracion/pico_firma_mlflow/INFORME.md), aplicado aquí:

1. Un None NO es un nulo para SimpleImputer (solo mira np.nan). Con un None en una variable de texto, el one-hot aprendería «None»
   como categoría en vez de «Desconocida» y la API (en JSON el nulo llega como None) daría una probabilidad distinta a la del
   entrenamiento para el mismo lote, SIN ningún aviso. Solución: se entrena con np.nan y el PRIMER paso de la rama de texto es
   nulos_a_nan, que unifica None, pd.NA y NaN. Una prueba (tests/test_modelo.py) lo vigila.
   Esta función está en el paquete cafe_mlops (que va en la imagen) porque el modelo guardado la importa al cargarse.
2. Todas las numéricas son float64 (también los conteos de defectos): con enteros, MLflow avisa y pyfunc rechaza floats.
3. El one-hot (con handle_unknown='ignore') y la imputación van dentro del modelo: la API aplica exactamente el mismo preprocesado.
"""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from .. import config

CATEGORIA_NULA = 'Desconocida'
MIN_FRECUENCIA = 10   # las categorías con menos de 10 lotes en train se agrupan en una sola columna («infrecuente»)


def nulos_a_nan(X):
    """Unifica None, pd.NA y NaN en np.nan. SimpleImputer(missing_values=np.nan) NO trata None como nulo (pico T07, cambio 1)."""
    df = pd.DataFrame(X).astype(object)
    return df.where(df.notna(), np.nan)


def preparar_X(datos):
    """Deja las variables como las espera el modelo: columnas de config.FEATURES, en ese orden; texto con np.nan por nulo
    y numéricas float64. Acepta un DataFrame o una lista de diccionarios. Devuelve una copia."""
    df = pd.DataFrame(datos)
    faltan = [c for c in config.FEATURES if c not in df.columns]
    if faltan:
        raise KeyError(f'Faltan variables: {faltan}')
    X = df.loc[:, config.FEATURES].copy()
    for c in config.CATEGORICAS:
        X[c] = nulos_a_nan(X[[c]])[c]
    for c in config.NUMERICAS:
        X[c] = pd.to_numeric(X[c]).astype('float64')
    return X


def preprocesador():
    """ColumnTransformer: numéricas con mediana y estandarización; texto con nulos_a_nan -> «Desconocida» -> one-hot."""
    num = Pipeline([('imputar', SimpleImputer(strategy='median', keep_empty_features=True)), ('escalar', StandardScaler())])
    cat = Pipeline([
        ('nulos', FunctionTransformer(nulos_a_nan, feature_names_out='one-to-one')),
        ('imputar', SimpleImputer(strategy='constant', fill_value=CATEGORIA_NULA)),
        ('onehot', OneHotEncoder(handle_unknown='ignore', min_frequency=MIN_FRECUENCIA, sparse_output=False)),
    ])
    return ColumnTransformer([('num', num, config.NUMERICAS), ('cat', cat, config.CATEGORICAS)], remainder='drop')


def construir_modelo(clasificador):
    """Pipeline completo: preprocesar + clasificador. Es lo que se entrena, se guarda y sirve la API."""
    return Pipeline([('preprocesar', preprocesador()), ('modelo', clasificador)])

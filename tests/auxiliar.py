"""Ayudas de las pruebas: leen los CSV de data/raw/cqi CON PANDAS y por su cuenta (sin usar cafe_mlops.dataset),
para que las pruebas comparen el paquete contra una lectura independiente del archivo.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CQI = RAIZ / 'data' / 'raw' / 'cqi'
ARCHIVOS = {'Arabica': CQI / 'arabica_data_cleaned.csv', 'Robusta': CQI / 'robusta_data_cleaned.csv'}

NUMERICAS_CSV = ['Unnamed: 0', 'Number.of.Bags', 'Moisture', 'Category.One.Defects', 'Quakers', 'Category.Two.Defects',
                 'Total.Cup.Points', 'altitude_low_meters', 'altitude_high_meters', 'altitude_mean_meters']
NOTAS = {
    'Arabica': ['Aroma', 'Flavor', 'Aftertaste', 'Acidity', 'Body', 'Balance', 'Uniformity', 'Clean.Cup', 'Sweetness', 'Cupper.Points'],
    'Robusta': ['Fragrance...Aroma', 'Flavor', 'Aftertaste', 'Salt...Acid', 'Bitter...Sweet', 'Mouthfeel', 'Uniform.Cup', 'Clean.Cup',
                'Balance', 'Cupper.Points'],
}


def leer(especie):
    """El CSV de la especie, con todas las columnas como texto (vacío = nulo) y una columna extra «_anio» (año de Grading.Date)."""
    df = pd.read_csv(ARCHIVOS[especie], dtype=object, keep_default_na=False, na_values=[''])
    texto = df['Grading.Date'].str.strip().str.replace(r'(\d)(st|nd|rd|th),', r'\1,', regex=True)
    df['_anio'] = pd.to_datetime(texto, format='%B %d, %Y').dt.year
    df['_fecha'] = pd.to_datetime(texto, format='%B %d, %Y').dt.strftime('%Y-%m-%d')
    return df


def esperado(hasta):
    """Lotes que debe tener la base con «--hasta», EN EL ORDEN de lote_id (arábica y luego robusta). Una fila por lote."""
    partes = []
    for especie in ('Arabica', 'Robusta'):
        df = leer(especie)
        partes.append(df[df['_anio'] <= hasta].assign(_especie=especie))
    todo = pd.concat(partes, ignore_index=True)
    todo['lote_id'] = np.arange(1, len(todo) + 1)
    return todo


def numerico(serie):
    """Texto -> número; vacío y «NA» -> NaN."""
    return pd.to_numeric(serie.replace('NA', np.nan))


def sin_comentarios_sql(texto):
    """Quita los comentarios «-- ...» de un SQL."""
    return re.sub(r'--[^\n]*', '', texto)

"""Configuración del taller: rutas, fuentes, versiones de datos, objetivo, variables, partición y segmentos de negocio.

Caso: calidad del café (Coffee Quality Institute, CQI). Pregunta de negocio:
    «Al recibir un lote (origen, variedad, beneficio y análisis del grano verde), antes de catarlo,
     ¿qué probabilidad hay de que alcance el grado de especialidad (>= 80 puntos)?»

Todo lo que define el caso está aquí, en un solo sitio: cambiar el umbral, los cortes o las variables no exige tocar el
resto del código. Los cuadernos repiten estos valores en su celda de parámetros; las pruebas comprueban que dan el mismo resultado.

Las rutas se pueden cambiar con variables de entorno (útil en pruebas y en contenedores):
    TALLER_DB_OPERACIONAL    base operacional «cqi», la fuente        (por defecto data/external/cqi.db)
    TALLER_DB                base SQLite analítica                    (por defecto data/processed/cafe.db)
    TALLER_DB_SOLO_LECTURA   1 = abrir esa base en solo lectura (el contenedor de la interfaz la recibe montada :ro)
    TALLER_URL_API           la API del modelo a la que llama la interfaz (en el contenedor: http://api:8080)
    TALLER_MODELOS           carpeta de modelos                       (por defecto models/)
    TALLER_REPORTES          carpeta de reportes                      (por defecto reports/)
    TALLER_LOG_NIVEL         nivel de registro de la API              (por defecto INFO)
    TALLER_PUERTO_API        puerto de la API del modelo              (por defecto 8080)
    TALLER_HOST_API          dirección en la que escucha la API       (por defecto 127.0.0.1; en el contenedor, 0.0.0.0)
    TALLER_PUERTO_INTERFAZ   puerto de la interfaz                    (por defecto 8090)
    TALLER_HOST_INTERFAZ     dirección en la que escucha la interfaz  (por defecto 127.0.0.1; en el contenedor, 0.0.0.0)
    TALLER_REPOSITORIO       repositorio que muestra la cabecera de la interfaz (si no, GITHUB_REPOSITORY)
"""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DATA_RAW = RAIZ / 'data' / 'raw'
DATA_PROCESSED = RAIZ / 'data' / 'processed'
SQL = RAIZ / 'sql'
# Dos bases: la OPERACIONAL simula el sistema del laboratorio de catas (la fuente); la ANALITICA guarda las capas RAW a ML.
DB_OPERACIONAL = Path(os.environ.get('TALLER_DB_OPERACIONAL', RAIZ / 'data' / 'external' / 'cqi.db'))
DB = Path(os.environ.get('TALLER_DB', DATA_PROCESSED / 'cafe.db'))
DB_SOLO_LECTURA = os.environ.get('TALLER_DB_SOLO_LECTURA', '') == '1'   # 1 = abrir la base sin poder escribir (contenedor de la interfaz)
MODELOS = Path(os.environ.get('TALLER_MODELOS', RAIZ / 'models'))
REPORTES = Path(os.environ.get('TALLER_REPORTES', RAIZ / 'reports'))

# --------------------------------------------------------------------------------------------------- fuente
# Los dos CSV limpios de CQI (copia exacta de jldbc/coffee-quality-database; huellas en data/raw/cqi/SHA256SUMS).
FUENTES = {
    'arabica': DATA_RAW / 'cqi' / 'arabica_data_cleaned.csv',
    'robusta': DATA_RAW / 'cqi' / 'robusta_data_cleaned.csv',
}
ESPECIES = {'arabica': 'Arabica', 'robusta': 'Robusta'}   # valor de la columna Species de cada archivo

# Datos nuevos (decisión 6): «--hasta AÑO» crea la base operacional solo con las catas hasta ese año (año de Grading.Date).
#   2016 = situación inicial, versión 1 de los datos.   2018 = llegan los lotes de 2017 y 2018, versión 2.
VERSIONES_DATOS = {2016: 1, 2018: 2}
HASTA_INICIAL = 2016

# --------------------------------------------------------------------------------------------------- objetivo
# y = 1 si Total.Cup.Points >= UMBRAL_ESPECIALIDAD (el lote es «café de especialidad»); 0 si no.
# Que 80 coincida con la definición oficial de la SCA está SIN VERIFICAR: es el umbral que da el encargo.
UMBRAL_ESPECIALIDAD = 80.0
OBJETIVO = 'y'

# --------------------------------------------------------------------------------------------------- partición TEMPORAL DESLIZANTE
# Por AÑO DE LA CATA (Grading.Date), nunca por orden de fila: el archivo viene ordenado por puntuación.
# Cada partición es un intervalo cerrado de años (desde, hasta). train aprende, valid elige entre modelos, test se mide una vez.
# La partición DESLIZA con la versión de los datos (decisión 2, provisional: la tomó el coordinador, el instructor no eligió):
# al llegar lotes nuevos, la ventana avanza un año y el modelo nuevo aprende también del año que antes era valid.
#     versión 1 (--hasta 2016): train 2009-2014 · valid 2015 · test 2016
#     versión 2 (--hasta 2018): train 2009-2015 · valid 2016 · test 2017-2018
# Lo único que se declara es el año de valid de cada versión; el resto sale de la función particiones_de() (no hay dos listas).
ANIO_PRIMERA_CATA = 2009
ANIO_VALID_POR_VERSION = {1: 2015, 2: 2016}
# Como valid cambia entre versiones, el AUC de valid de una versión NO es comparable con el de otra. La comparación con la
# referencia (models/referencia.json) se hace sobre una VENTANA COMÚN fija: los lotes catados en estos años (intervalo cerrado).
# 2016 queda fuera del entrenamiento de las dos versiones (la v1 entrena hasta 2014, la v2 hasta 2015): es el test de la v1 y el
# valid de la v2. Ojo: en la v2 también sirvió para elegir entre modelos, así que su cifra es algo optimista frente a la v1.
# train.py comprueba que la ventana común es posterior a train en cada versión.
VENTANA_COMUN = (2016, 2016)
SEMILLA = 42   # para el modelo (T08); la partición no usa azar

# --------------------------------------------------------------------------------------------------- reglas de MASTER
ALTITUD_MIN_M = 100        # altitud media fuera de 100–4 000 m -> nula, con alerta de calidad
ALTITUD_MAX_M = 4000
HUMEDAD_NO_MEDIDA = 0.0    # Moisture = 0 se trata como «no medido» (decisión 14): nulo, con alerta de calidad
FECHA_CATA_MINIMA = '2009-01-01'
FECHA_CATA_LIMITE = '2019-01-01'   # exclusiva

# --------------------------------------------------------------------------------------------------- columnas del dato
# Las diez notas de cata de cada especie, con los nombres del CSV. SUMAN Total.Cup.Points (diferencia máxima 0,5 en la exploración):
# usarlas como variables sería FUGA total (el modelo «sumaría», no predeciría) y además no existen al recibir el lote.
NOTAS_CATA = {
    'Arabica': ['Aroma', 'Flavor', 'Aftertaste', 'Acidity', 'Body', 'Balance', 'Uniformity', 'Clean.Cup', 'Sweetness', 'Cupper.Points'],
    'Robusta': ['Fragrance...Aroma', 'Flavor', 'Aftertaste', 'Salt...Acid', 'Bitter...Sweet', 'Mouthfeel', 'Uniform.Cup', 'Clean.Cup',
                'Balance', 'Cupper.Points'],
}
TODAS_LAS_NOTAS = sorted(set(NOTAS_CATA['Arabica']) | set(NOTAS_CATA['Robusta']))   # 15 nombres distintos
COLUMNA_TOTAL = 'Total.Cup.Points'
# Nombres de personas y contactos que trae el CSV (decisión 4: se conservan en los CSV y en la base operacional). NUNCA son variables.
COLUMNAS_PERSONALES = ['Owner', 'Owner.1', 'Producer', 'Farm.Name', 'Certification.Contact', 'Certification.Address']
# Otras columnas fuera del modelo: Expiration = fecha de cata + 1 año; texto libre o identificadores de muchos valores;
# In.Country.Partner es quien pone la nota (no una propiedad del lote).
COLUMNAS_FUERA_DEL_MODELO = ['Expiration', 'Lot.Number', 'ICO.Number', 'Mill', 'Company', 'Region', 'In.Country.Partner', 'Certification.Body']

# --------------------------------------------------------------------------------------------------- variables
# Variables de la capa FS que usa el modelo (columnas de fs_lote), todas conocidas AL RECIBIR EL LOTE, antes de catarlo.
# Un valor ausente es NULO (no «Desconocida»): el Pipeline del modelo lo imputa dentro (T07).
CATEGORICAS = ['especie', 'pais', 'variedad', 'metodo_proceso', 'color']
NUMERICAS = ['altitud_media_m', 'humedad', 'defectos_cat1', 'defectos_cat2', 'quakers']
FEATURES = CATEGORICAS + NUMERICAS
# Cómo se llaman en FS las variables que salen de cada columna del CSV (para la prueba de la fuga y el catálogo).
ORIGEN_DE_LAS_VARIABLES = {
    'especie': 'Species', 'pais': 'Country.of.Origin', 'variedad': 'Variety', 'metodo_proceso': 'Processing.Method',
    'color': 'Color', 'altitud_media_m': 'altitude_mean_meters', 'humedad': 'Moisture',
    'defectos_cat1': 'Category.One.Defects', 'defectos_cat2': 'Category.Two.Defects', 'quakers': 'Quakers',
}

# --------------------------------------------------------------------------------------------------- modelo y comparación
# El modelo en formato MLflow (con su FIRMA) que se guarda dentro de MODELOS. Es lo que carga la API y lo que se copia a la imagen Docker.
CARPETA_MODELO_MLFLOW = 'modelo_mlflow'
EXPERIMENTO_MLFLOW = 'cafe-especialidad'
MODELO_REGISTRADO = 'cafe-especialidad'

# Comparación con la versión de referencia (models/referencia.json): la candidata NO se aprueba si su métrica sobre la ventana común
# empeora más que esta tolerancia (diferencia absoluta). TODO-T08: valor inicial; se fija con las métricas reales de valid
# (la exploración mostró que el AUC oscila ±0,05 según el corte, con pocos negativos: 5 lotes < 80 en la ventana común).
METRICA_COMPARACION = 'auc_comun'   # AUC sobre VENTANA_COMUN (los mismos lotes en cada versión), no el de valid (cambia con la versión)
TOLERANCIA_COMPARACION = 0.02   # TODO-T08: PROVISIONAL, no sale de una medición (ver comentario de arriba)
# La versión de referencia (la última aprobada) vive en el repositorio, no en models/ generado: models/referencia.json (T08).
REFERENCIA = Path(os.environ.get('TALLER_REFERENCIA', RAIZ / 'models' / 'referencia.json'))

# EVALUACIÓN SECUNDARIA (informativa): «ventana creciente con varios cortes» (rolling-origin). Cada corte (desde, hasta) entrena
# con TODOS los años anteriores a «desde» y prueba en los años desde..hasta; las predicciones de los cortes de cada grupo se
# AGRUPAN y se calcula una sola métrica. «seleccion» sería el valid agrupado; «examen», el test agrupado.
# Motivo (pico T07): un único test temporal tiene muy pocos lotes < 80 (v1: 5 en 2016; v2: unos 22) y su AUC oscila; agrupar
# varios cortes lo estabiliza (no lo arregla: sigue habiendo un intervalo de confianza amplio). NO decide nada: la partición
# principal sigue siendo la partición deslizante de particiones_de() (decisión 2). Con --hasta 2016 no hay lotes de 2017-2018 y ese corte se omite.
VENTANA_CRECIENTE = {
    'seleccion': [(2013, 2013), (2014, 2014)],
    'examen': [(2015, 2015), (2016, 2016), (2017, 2018)],
}

# --------------------------------------------------------------------------------------------------- API del modelo
PUERTO_API = int(os.environ.get('TALLER_PUERTO_API', '8080'))
HOST_API = os.environ.get('TALLER_HOST_API', '127.0.0.1')

# --------------------------------------------------------------------------------------------------- interfaz
# Interfaz de consulta (T11): de la PROBABILIDAD que da el modelo a una RECOMENDACIÓN para el negocio. Es una regla de negocio,
# no sale del modelo. Se recorre en orden: el primer tramo cuyo «desde» no supere la probabilidad es el del lote.
# TODO (decisión 15): umbrales y textos PROVISIONALES, por acordar con el instructor; no salen de ninguna medición.
SEGMENTOS = [
    {'segmento': 'alta', 'desde': 0.90,
     'recomendacion': 'Probable café de especialidad: mandar a cata prioritaria.'},
    {'segmento': 'media', 'desde': 0.80,
     'recomendacion': 'Duda razonable: cata normal.'},
    {'segmento': 'baja', 'desde': 0.0,
     'recomendacion': 'Poco probable que llegue a especialidad: revisar beneficio y análisis del grano verde antes de catar.'},
]
URL_API = os.environ.get('TALLER_URL_API')   # la interfaz llama a la API del modelo aquí (en el contenedor: http://api:8080)
PUERTO_INTERFAZ = int(os.environ.get('TALLER_PUERTO_INTERFAZ', '8090'))
HOST_INTERFAZ = os.environ.get('TALLER_HOST_INTERFAZ', '127.0.0.1')   # en el contenedor, 0.0.0.0
URL_API_INTERFAZ = URL_API or f'http://127.0.0.1:{PUERTO_API}'        # sin TALLER_URL_API: la API local del puerto por defecto


def version_de_datos(hasta):
    """Versión de los datos (1 o 2) para un «--hasta». Falla con un mensaje claro si el año no es uno de los previstos."""
    if hasta not in VERSIONES_DATOS:
        raise ValueError(f'--hasta debe ser uno de {sorted(VERSIONES_DATOS)} (recibido: {hasta!r})')
    return VERSIONES_DATOS[hasta]

def version_por_anio(anio_maximo):
    """Versión de los datos (1 o 2) cuyo --hasta cubre un año de cata máximo: la primera versión que lo alcanza. None si ninguna."""
    for hasta in sorted(VERSIONES_DATOS):
        if anio_maximo <= hasta:
            return VERSIONES_DATOS[hasta]
    return None


def particiones_de(version):
    """Intervalos (desde, hasta) de años de cata de train, valid y test para una versión de los datos (ver «partición deslizante»)."""
    hasta_de = {v: h for h, v in VERSIONES_DATOS.items()}
    if version not in hasta_de or version not in ANIO_VALID_POR_VERSION:
        raise ValueError(f'No hay partición para la versión {version!r} (hay: {sorted(ANIO_VALID_POR_VERSION)})')
    valid = ANIO_VALID_POR_VERSION[version]
    return {'train': (ANIO_PRIMERA_CATA, valid - 1), 'valid': (valid, valid), 'test': (valid + 1, hasta_de[version])}
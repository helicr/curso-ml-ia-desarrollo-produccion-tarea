"""Entrenamiento y evaluación, con seguimiento en MLflow.

Es la traducción a Python de  notebooks/04_entrenamiento_y_seguimiento.ipynb.

PREGUNTA: dado un lote que acaba de llegar (antes de catarlo), ¿qué probabilidad hay de que sea café de especialidad (>= 80)?

MÉTODO
    1. Cada modelo se entrena con train (los años más antiguos).  2. Se comparan con valid y se elige el de mayor AUC.
    3. El elegido se mide en test (los años más recientes) y no se usa para elegir.  4. Comprobación temporal: antes de entrenar se
    verifica que train es anterior a valid y valid a test (config.particiones_de, por año de la cata).

MODELOS (los tres llevan el MISMO preprocesado dentro: ver preproceso.py)
    referencia_sin_aprender  da a todos los lotes la tasa base de train (AUC 0,5): el mínimo que hay que superar.
    regresion_logistica      suma ponderada de variables -> probabilidad.
    gradient_boosting        muchos árboles pequeños en secuencia; cada uno corrige los errores de los anteriores.
                             Hiperparámetros fijados de antemano (modestos); no se afinan con test.

MÉTRICAS (metricas)
    auc                      probabilidad de puntuar más alto a un lote de especialidad que a uno que no (0,5 azar, 1 perfecto).
    ap_no_especialidad       precisión media de la clase minoritaria (< 80) y su TASA BASE (el valor que daría el azar). Es la
                             segunda métrica principal: mide si el modelo pone arriba los lotes que de verdad se quedan sin la nota.
    exactitud                NO SIRVE sola: «decir siempre especialidad» da ~0,86 en train. Se imprime junto a ese valor.

PARTICIÓN DESLIZANTE Y VENTANA COMÚN
    La partición avanza con la versión de los datos (v1: train <= 2014, valid 2015, test 2016; v2: train <= 2015, valid 2016,
    test 2017-2018), así que el AUC de valid NO es comparable entre versiones. Para comparar con la referencia se mide cada
    modelo sobre una VENTANA COMÚN fija (config.VENTANA_COMUN, el año 2016: fuera del entrenamiento de las dos versiones). Se
    guarda como «comun» junto a train, valid y test, y como metricas_comun en metadatos.json. Elegir el modelo sigue siendo con valid.

OJO, LAS CIFRAS DE UN SOLO TEST OSCILAN (pico T07)
    El test tiene muy pocos lotes < 80 (con --hasta 2016 solo 5; con --hasta 2018, 22; la ventana común, 5): el AUC de test tiene un intervalo de
    confianza del 95 % de unos ±0,1 y una diferencia de 0,03 entre modelos no significa nada. Por eso se calcula además, SOLO
    COMO INFORMACIÓN, una evaluación de «ventana creciente con varios cortes» (config.VENTANA_CRECIENTE): cada corte entrena con
    todo lo anterior y prueba en el año siguiente, y las predicciones de varios cortes se agrupan en una sola métrica
    (selección 2013-2014, examen 2015 en adelante), con su intervalo. Se imprime y se guarda junto a las métricas. La partición
    principal sigue siendo la temporal deslizante de config.particiones_de.

MLFLOW: el cuaderno de laboratorio del proyecto
    experimento   agrupa los intentos de un mismo problema: 'cafe-especialidad'.
    ejecución     (run) un entrenamiento concreto: una por modelo, más 'MEJOR-<modelo>' para el elegido.
    parámetros    lo que se decide ANTES de entrenar (modelo, huella_datos...).
    métricas      lo que se mide DESPUÉS, con el prefijo de la partición (valid_auc, test_auc...).
    artefactos    el modelo del mejor, con su FIRMA (nombre y tipo de cada variable).
    registro      el elegido se registra como 'cafe-especialidad': cada entrenamiento crea una VERSIÓN nueva (1, 2, 3...).
    Dónde se guarda: models/mlflow.db (tracking URI 'sqlite:///models/mlflow.db') y models/mlartifacts/ (los archivos).
    Para verlo en el navegador:  python -m cafe_mlops.mlflow_ui

FIRMA (pico T07): se escribe EXPLÍCITA (texto = string, números = double, entrada por nombre), no inferida de una muestra, para que
    no dependa de qué filas traían nulos. El modelo se guarda con pyfunc_predict_fn='predict_proba' (si no, pyfunc devolvería
    etiquetas 0/1). La API usará esta misma firma como contrato (nombres y tipos); «required» no impide pasar nulos.

SALIDAS
  models/modelo.joblib       el modelo completo (preprocesado + clasificador), el que carga predict.py
  models/modelo_mlflow/      el mismo modelo en formato MLflow, con su firma (el contrato de entrada que usa la API)
  models/metadatos.json      variables y tipos, categorías vistas, rangos, particiones, huella de los datos, versiones (reproducir)
  models/mlflow.db           seguimiento de MLflow (y models/mlartifacts/ con los modelos registrados)
  reports/metricas.json      métricas de todos los modelos, comprobación temporal y ventana creciente (sin marcas de tiempo)

Uso:  python -m cafe_mlops.modeling.train
"""
import hashlib
import json
import platform
import shutil
import sys
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold

from .. import config, db
from . import preproceso

REFERENCIA_SIN_APRENDER = 'referencia_sin_aprender'
N_BOOTSTRAP = 1000      # remuestreos para el intervalo de confianza del AUC (aproximado: los lotes de un productor no son independientes)
PARTICIONES = ('train', 'valid', 'test')


class ParticionTemporalError(RuntimeError):
    pass


# ----------------------------------------------------------------------------------------------------------- datos
def cargar_datos(con):
    """Lee ml_dataset y lo separa por partición (sin mezclar filas). Devuelve (partes, tabla completa). Las variables se preparan
    después con preproceso.preparar_X (texto con np.nan, números float64)."""
    df = pd.read_sql('SELECT * FROM ml_dataset ORDER BY lote_id', con)
    partes = {p: df[df['particion'] == p].reset_index(drop=True) for p in PARTICIONES}
    return partes, df


def huella_datos(df):
    """Huella del dataset: identifica con qué datos se entrenó el modelo (contenido, no fecha)."""
    h = hashlib.sha256(pd.util.hash_pandas_object(df.sort_values('lote_id'), index=False).values.tobytes())
    return h.hexdigest()[:16]


def comprobar_temporal(df, particiones=None):
    """Comprobación temporal: los años de train < valid < test, sin solaparse, y cada lote cae en el intervalo de su partición
    (por defecto, la de la versión de los datos de df). Devuelve {partición: [año mínimo, año máximo]}; si algo falla,
    ParticionTemporalError."""
    if particiones is None:
        particiones = config.particiones_de(version_de_los_datos(df)[1])
    rangos = {}
    for p in PARTICIONES:
        sub = df[df['particion'] == p]['anio_cata']
        if sub.empty:
            raise ParticionTemporalError(f'La partición {p} está vacía: revisa config.PARTICIONES.')
        rangos[p] = [int(sub.min()), int(sub.max())]
        desde, hasta = particiones[p]
        if rangos[p][0] < desde or rangos[p][1] > hasta:
            raise ParticionTemporalError(f'{p} tiene años {rangos[p]} fuera de su intervalo {[desde, hasta]}.')
    if not (rangos['train'][1] < rangos['valid'][0] and rangos['valid'][1] < rangos['test'][0]):
        raise ParticionTemporalError(f'Las particiones no están en orden temporal sin solaparse: {rangos}')
    return rangos


def version_de_los_datos(df):
    """(año de cata máximo, versión de los datos): la primera de config.VERSIONES_DATOS que cubre ese año."""
    anio = int(df['anio_cata'].max())
    return anio, config.version_por_anio(anio)


# ----------------------------------------------------------------------------------------------------------- modelos
def modelos():
    """Los tres modelos a comparar, sin entrenar. Todos con el preprocesado dentro (Pipeline); semillas fijas."""
    clasificadores = {
        REFERENCIA_SIN_APRENDER: DummyClassifier(strategy='prior'),
        'regresion_logistica': LogisticRegression(max_iter=2000),
        'gradient_boosting': HistGradientBoostingClassifier(max_iter=150, learning_rate=0.05, max_depth=3, min_samples_leaf=20,
                                                            l2_regularization=1.0, early_stopping=False, random_state=config.SEMILLA),
    }
    return {nombre: preproceso.construir_modelo(c) for nombre, c in clasificadores.items()}


def _num(x):
    """float o None (JSON no admite NaN)."""
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)


def metricas(y, prob):
    """Métricas sobre un conjunto: ver «MÉTRICAS» en la cabecera. Con una sola clase, auc y precisiones son None."""
    y = np.asarray(y).astype(int)
    prob = np.asarray(prob, dtype=float)
    n, pos = len(y), int(y.sum())
    neg = n - pos
    m = {'n': n, 'especialidad': pos, 'no_especialidad': neg,
         'tasa_base_especialidad': pos / n, 'tasa_base_no_especialidad': neg / n,
         'exactitud': float(np.mean((prob >= 0.5) == y)), 'exactitud_siempre_especialidad': pos / n,
         'auc': None, 'ap_especialidad': None, 'ap_no_especialidad': None, 'ap_no_especialidad_sobre_base': None}
    if pos and neg:
        m['auc'] = float(roc_auc_score(y, prob))
        m['ap_especialidad'] = float(average_precision_score(y, prob))
        m['ap_no_especialidad'] = float(average_precision_score(1 - y, 1 - prob))
        m['ap_no_especialidad_sobre_base'] = m['ap_no_especialidad'] / m['tasa_base_no_especialidad']
    return m


def ic_auc(y, prob, n=N_BOOTSTRAP, semilla=config.SEMILLA):
    """Intervalo de confianza del 95 % del AUC por bootstrap (aproximado; semilla fija). [None, None] si no se puede."""
    y, prob = np.asarray(y), np.asarray(prob)
    if y.min() == y.max():
        return [None, None]
    rng = np.random.default_rng(semilla)
    ids = np.arange(len(y))
    vals = []
    for _ in range(n):
        s = rng.choice(ids, len(ids))
        if y[s].min() != y[s].max():
            vals.append(roc_auc_score(y[s], prob[s]))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))] if vals else [None, None]


def ventana_comun(df, particiones):
    """Filas de df en la VENTANA COMÚN (config.VENTANA_COMUN). Falla si la ventana no es posterior a train: si no, el modelo
    la habría visto al entrenar y la comparación entre versiones no valdría nada."""
    desde, hasta = config.VENTANA_COMUN
    if desde <= particiones['train'][1]:
        raise ParticionTemporalError(f'La ventana común {config.VENTANA_COMUN} no es posterior a train (hasta {particiones["train"][1]}).')
    sub = df[df['anio_cata'].between(desde, hasta)].reset_index(drop=True)
    if sub.empty or sub[config.OBJETIVO].nunique() < 2:
        raise ParticionTemporalError(f'La ventana común {config.VENTANA_COMUN} está vacía o tiene una sola clase.')
    return sub


def evaluar(modelo, X, y):
    """Métricas de un modelo ya entrenado sobre una partición, con el IC del AUC (valid y test)."""
    prob = modelo.predict_proba(X)[:, 1]
    m = metricas(y, prob)
    m['auc_ic95'] = ic_auc(y, prob)
    return m


# ----------------------------------------------------------------------------------------------------------- ventana creciente
def ventana_creciente(df, nombre_modelo):
    """Evaluación SECUNDARIA e informativa (ver cabecera): cortes con ventana creciente, agrupados, y el contraste con una
    validación cruzada aleatoria sobre las mismas filas. Devuelve un diccionario serializable.
    Ojo: la referencia sin aprender NO da 0,5 al agrupar, porque cada corte reparte SU tasa base (distinta) y al juntar las
    predicciones esas constantes se ordenan entre sí (un artefacto del agrupado, no una señal)."""
    X, y, anio = preproceso.preparar_X(df), df[config.OBJETIVO].to_numpy(), df['anio_cata'].to_numpy()
    resultado = {'cortes': [], 'grupos': {}, 'cv_aleatoria': None}
    filas_evaluadas = np.zeros(len(df), dtype=bool)
    for grupo, cortes in config.VENTANA_CRECIENTE.items():
        ys, ps = [], []
        for desde, hasta in cortes:
            tr, te = anio < desde, (anio >= desde) & (anio <= hasta)
            if tr.sum() == 0 or te.sum() == 0:
                continue   # p. ej. 2017-2018 con --hasta 2016
            modelo = modelos()[nombre_modelo].fit(X[tr], y[tr])
            prob = modelo.predict_proba(X[te])[:, 1]
            m = metricas(y[te], prob)
            resultado['cortes'].append({'grupo': grupo, 'prueba_desde': desde, 'prueba_hasta': hasta, 'entrenado_con': int(tr.sum()),
                                        'n': m['n'], 'no_especialidad': m['no_especialidad'], 'auc': m['auc'],
                                        'ap_no_especialidad': m['ap_no_especialidad']})
            ys.append(y[te])
            ps.append(prob)
            filas_evaluadas |= te
        if ys:
            ya, pa = np.concatenate(ys), np.concatenate(ps)
            g = metricas(ya, pa)
            g['auc_ic95'] = ic_auc(ya, pa)
            g['cortes'] = len(ys)
            resultado['grupos'][grupo] = g
    if filas_evaluadas.sum() >= 50 and len(set(y[filas_evaluadas])) == 2:
        Xs, ys_ = X[filas_evaluadas].reset_index(drop=True), y[filas_evaluadas]
        oof = np.zeros(len(ys_))
        for tr, te in StratifiedKFold(5, shuffle=True, random_state=config.SEMILLA).split(Xs, ys_):
            oof[te] = modelos()[nombre_modelo].fit(Xs.iloc[tr], ys_[tr]).predict_proba(Xs.iloc[te])[:, 1]
        resultado['cv_aleatoria'] = metricas(ys_, oof)
    return resultado


# ----------------------------------------------------------------------------------------------------------- MLflow
def firma_mlflow():
    """Firma EXPLÍCITA del modelo: entrada por nombre (texto = string, números = double) y salida (n, 2) de probabilidades.
    Solo «especie» es obligatoria; el resto puede venir nula (MASTER las deja nulas). OJO: «required» no impide pasar nulos."""
    from mlflow.models import ModelSignature
    from mlflow.types import ColSpec, Schema, TensorSpec
    entrada = Schema([ColSpec('string' if c in config.CATEGORICAS else 'double', c, required=(c == 'especie')) for c in config.FEATURES])
    salida = Schema([TensorSpec(np.dtype('float64'), (-1, 2))])
    return ModelSignature(inputs=entrada, outputs=salida)


def exportar_modelo_mlflow(modelo, muestra, destino):
    """Guarda el modelo en formato MLflow: carpeta autocontenida con MLmodel, firma y ejemplo de entrada.
    Es lo que carga la API y lo que se copia a la imagen Docker."""
    import mlflow.sklearn
    if destino.exists():
        shutil.rmtree(destino)
    # cloudpickle evita la verificación de tipos de skops; pyfunc_predict_fn='predict_proba' hace que pyfunc devuelva probabilidades.
    mlflow.sklearn.save_model(modelo, str(destino), signature=firma_mlflow(), serialization_format='cloudpickle',
                              pyfunc_predict_fn='predict_proba', input_example=muestra.head(3))


def rangos_de_entrenamiento(X):
    """Mínimo y máximo de cada variable numérica en train. La API avisa (no rechaza) cuando llega algo fuera de ese rango."""
    return {c: [float(X[c].min()), float(X[c].max())] for c in config.NUMERICAS}


def categorias_vistas(modelo):
    """Categorías que vio el one-hot al entrenar (para que la API avise de las nuevas) y cuáles quedaron como «infrecuente»."""
    codificador = modelo.named_steps['preprocesar'].named_transformers_['cat'].named_steps['onehot']
    vistas = {c: [str(v) for v in cats] for c, cats in zip(config.CATEGORICAS, codificador.categories_)}
    infrecuentes = {c: [str(v) for v in (ci if ci is not None else [])]
                    for c, ci in zip(config.CATEGORICAS, getattr(codificador, 'infrequent_categories_', [None] * len(config.CATEGORICAS)))}
    return vistas, infrecuentes


def tipos_de_las_variables():
    return {c: ('string' if c in config.CATEGORICAS else 'double') for c in config.FEATURES}


# ----------------------------------------------------------------------------------------------------------- entrenar
def _f(v, d=3):
    return 'n/d' if v is None else f'{v:.{d}f}'


def _ic(m):
    lo, hi = m['auc_ic95']
    return 'n/d' if lo is None else f'[{lo:.2f}; {hi:.2f}]'


def entrenar(con=None, usar_mlflow=True, verbose=True):
    """Entrena y compara los modelos, registra cada uno como ejecución de MLflow y guarda el mejor con sus metadatos."""
    cierre = con is None
    con = con or db.conectar()
    partes, df = cargar_datos(con)
    rangos_anios = comprobar_temporal(df)
    X = {k: preproceso.preparar_X(v) for k, v in partes.items()}
    y = {k: v[config.OBJETIVO] for k, v in partes.items()}
    for k in PARTICIONES:
        if y[k].nunique() < 2:
            raise RuntimeError(f'La partición {k} tiene una sola clase: revisa los cortes de config.py.')
    huella = huella_datos(df)
    anio_max, version_datos = version_de_los_datos(df)
    particiones = config.particiones_de(version_datos)
    comun = ventana_comun(df, particiones)
    X_comun, y_comun = preproceso.preparar_X(comun), comun[config.OBJETIVO]

    mlflow = None
    if usar_mlflow:   # dónde escribir (tracking URI) y en qué experimento; se crea la primera vez con su carpeta de artefactos
        import mlflow
        import mlflow.sklearn
        config.MODELOS.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri('sqlite:///' + (config.MODELOS / 'mlflow.db').resolve().as_posix())
        nombre = config.EXPERIMENTO_MLFLOW
        if mlflow.get_experiment_by_name(nombre) is None:
            mlflow.create_experiment(nombre, artifact_location=(config.MODELOS / 'mlartifacts').resolve().as_uri())
        mlflow.set_experiment(nombre)

    if verbose:
        print(f'  Datos: huella {huella}, catas hasta {anio_max} (versión {version_datos} de los datos). Comprobación temporal OK: '
              + ' < '.join(f'{p} {r[0]}-{r[1]}' for p, r in rangos_anios.items()))
        for p in PARTICIONES:
            n, neg = len(y[p]), int((y[p] == 0).sum())
            print(f'    {p:5s} {n:>5} lotes | {neg:>3} sin especialidad ({100 * neg / n:.1f} %)')

    resultados, ajustados = {}, {}
    for nombre_modelo, modelo in modelos().items():
        modelo.fit(X['train'], y['train'])
        res = {p: evaluar(modelo, X[p], y[p]) for p in PARTICIONES}
        res['comun'] = evaluar(modelo, X_comun, y_comun)
        resultados[nombre_modelo], ajustados[nombre_modelo] = res, modelo
        if verbose:
            print(f'  {nombre_modelo:24s} AUC valid {_f(res["valid"]["auc"])} {_ic(res["valid"])} | test {_f(res["test"]["auc"])} {_ic(res["test"])}'
                  f' | AP(<{config.UMBRAL_ESPECIALIDAD:g}) test {_f(res["test"]["ap_no_especialidad"])} (azar {_f(res["test"]["tasa_base_no_especialidad"])})'
                  f' | ventana común {config.VENTANA_COMUN[0]}-{config.VENTANA_COMUN[1]} AUC {_f(res["comun"]["auc"])} {_ic(res["comun"])}')
        if mlflow:   # una ejecución por modelo: parámetros (lo decidido) y métricas (lo medido)
            with mlflow.start_run(run_name=nombre_modelo):
                mlflow.log_param('modelo', nombre_modelo)
                mlflow.log_param('n_variables', len(config.FEATURES))
                mlflow.log_param('huella_datos', huella)
                mlflow.log_param('anio_cata_maximo', anio_max)
                mlflow.log_param('semilla', config.SEMILLA)
                for p, m in res.items():
                    for k, v in m.items():
                        if isinstance(v, (int, float)) and v is not None:
                            mlflow.log_metric(f'{p}_{k}', v)

    # Se elige con VALID (nunca con test). La referencia sin aprender solo sirve de mínimo.
    mejor = max((n for n in resultados if n != REFERENCIA_SIN_APRENDER), key=lambda n: resultados[n]['valid']['auc'])
    modelo = ajustados[mejor]

    if verbose:
        print('  Evaluación SECUNDARIA (informativa): ventana creciente, varios cortes agrupados')
    ventana = {n: ventana_creciente(df, n) for n in resultados}
    if verbose:
        for n in resultados:
            g = ventana[n]['grupos']
            partes_txt = [f'{k} n={v["n"]} sin-especialidad={v["no_especialidad"]} AUC {_f(v["auc"])} {_ic(v)}' for k, v in g.items()]
            print(f'    {n:24s} ' + ' | '.join(partes_txt))
        cv = ventana[mejor]['cv_aleatoria']
        if cv:
            print(f'    contraste, {mejor} con validación cruzada ALEATORIA sobre las mismas filas ({cv["n"]}): AUC {_f(cv["auc"])} '
                  '(optimista: mezcla pasado y futuro)')
        t, v_ = resultados[mejor]['test'], resultados[mejor]['valid']
        print(f'  AVISO DE RUIDO: valid tiene {v_["no_especialidad"]} lotes < {config.UMBRAL_ESPECIALIDAD:g} y test {t["no_especialidad"]} '
              f'(la ventana común, {resultados[mejor]["comun"]["no_especialidad"]}). '
              f'Un test único oscila: AUC test {_f(t["auc"])} con IC95 % {_ic(t)}. Diferencias de ~0,03 entre modelos no significan nada;'
              ' no concluyas con una sola cifra (mira también la evaluación agrupada).')
        print(f'  exactitud de test del elegido {_f(t["exactitud"])} frente a {_f(t["exactitud_siempre_especialidad"])} de «decir siempre especialidad»: '
              'la exactitud no distingue; se usa AUC y precisión media de la clase < 80.')

    version_registrada = None
    if mlflow:   # el elegido se guarda con el modelo como artefacto, su firma y un ejemplo de entrada, y se REGISTRA
        with mlflow.start_run(run_name=f'MEJOR-{mejor}'):
            mlflow.log_param('modelo', mejor)
            mlflow.log_param('huella_datos', huella)
            mlflow.log_param('anio_cata_maximo', anio_max)
            for p, m in resultados[mejor].items():
                for k, v in m.items():
                    if isinstance(v, (int, float)) and v is not None:
                        mlflow.log_metric(f'{p}_{k}', v)
            info = mlflow.sklearn.log_model(modelo, name='modelo', signature=firma_mlflow(), serialization_format='cloudpickle',
                                            pyfunc_predict_fn='predict_proba', input_example=X['train'].head(3),
                                            registered_model_name=config.MODELO_REGISTRADO)
        version_registrada = int(info.registered_model_version)
        cliente = mlflow.MlflowClient()
        for clave, valor in (('modelo', mejor), ('huella_datos', huella), ('auc_valid', f"{resultados[mejor]['valid']['auc']:.4f}"),
                              ('auc_comun', f"{resultados[mejor]['comun']['auc']:.4f}")):
            cliente.set_model_version_tag(config.MODELO_REGISTRADO, str(version_registrada), clave, valor)

    config.MODELOS.mkdir(parents=True, exist_ok=True)
    config.REPORTES.mkdir(parents=True, exist_ok=True)
    joblib.dump(modelo, config.MODELOS / 'modelo.joblib')
    exportar_modelo_mlflow(modelo, X['train'], config.MODELOS / config.CARPETA_MODELO_MLFLOW)
    vistas, infrecuentes = categorias_vistas(modelo)
    metadatos = {
        'modelo': mejor,
        'objetivo': f'el lote alcanza especialidad: {config.COLUMNA_TOTAL} >= {config.UMBRAL_ESPECIALIDAD:g}',
        'variables': config.FEATURES,
        'tipos': tipos_de_las_variables(),
        'particiones': {p: list(particiones[p]) for p in PARTICIONES},
        'ventana_comun': list(config.VENTANA_COMUN),
        'anios_reales': rangos_anios,
        'filas': {k: int(len(v)) for k, v in partes.items()},
        'anio_cata_maximo': anio_max,
        'version_datos': version_datos,
        'huella_datos': huella,
        'metricas_valid': resultados[mejor]['valid'],
        'metricas_comun': resultados[mejor]['comun'],
        'rangos_entrenamiento': rangos_de_entrenamiento(X['train']),
        'categorias_vistas': vistas,
        'categorias_infrecuentes': infrecuentes,
        'version_modelo_registrado': version_registrada,
        'entrenado_en': datetime.now().isoformat(timespec='seconds'),
        'versiones': {'python': sys.version.split()[0], 'scikit-learn': sklearn.__version__, 'pandas': pd.__version__,
                      'numpy': np.__version__, 'plataforma': platform.system()},
    }
    (config.MODELOS / 'metadatos.json').write_text(json.dumps(metadatos, indent=2, ensure_ascii=False), encoding='utf-8')
    (config.REPORTES / 'metricas.json').write_text(json.dumps({
        'mejor': mejor, 'huella_datos': huella, 'comprobacion_temporal': rangos_anios, 'modelos': resultados,
        'ventana_creciente_informativa': ventana,
        'aviso': 'Un test temporal único tiene pocos lotes sin especialidad y su AUC oscila (ver auc_ic95). La evaluación de ventana '
                 'creciente es informativa y no decide nada.',
    }, indent=2, ensure_ascii=False), encoding='utf-8')
    if verbose:
        print(f'  Mejor modelo: {mejor}. Guardado en {config.MODELOS.name}/modelo.joblib')
        if version_registrada:
            print(f'  Registrado en MLflow como «{config.MODELO_REGISTRADO}», versión {version_registrada}. Para verlo: python -m cafe_mlops.mlflow_ui')
    if cierre:
        con.close()
    return {'mejor': mejor, 'metricas': resultados, 'ventana': ventana, 'metadatos': metadatos, 'version_registrada': version_registrada}


if __name__ == '__main__':
    entrenar()

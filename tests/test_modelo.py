"""Pruebas de T08: entrenamiento, firma de MLflow, predicción, comparación, interfaz de MLflow y orquestador.

El entrenamiento con MLflow tarda (guardar el modelo infiere sus dependencias): se hace UNA vez por versión de los datos en una
carpeta temporal (fixture `orquestado`, con el orquestador, hasta 2016 y luego hasta 2018) y las pruebas leen de ahí.
Las cifras que se comparan con números fijos se recalculan antes por su cuenta (pandas / scikit-learn) desde ml_dataset.
"""
import json
import shutil
import sqlite3
import sys
from types import SimpleNamespace

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score

from auxiliar import RAIZ
from cafe_mlops import config, db, mlflow_ui, pipeline
from cafe_mlops.modeling import comparar, predict, preproceso, train


# --------------------------------------------------------------------------------------------------- fixtures
def _copiar(origen, destino):
    shutil.copytree(origen, destino, ignore=shutil.ignore_patterns('mlflow.db', 'mlartifacts'))
    return destino


@pytest.fixture(scope='module')
def orquestado(tmp_path_factory):
    """Orquestador completo en carpetas temporales: hasta 2016 (dos veces) y después hasta 2018 (dos veces), con MLflow.
    Guarda una copia del modelo de la versión 1 antes de pasar a la 2."""
    raiz = tmp_path_factory.mktemp('orquestado')
    ruta_op, ruta_db = raiz / 'cqi.db', raiz / 'cafe.db'
    modelos, reportes = raiz / 'models', raiz / 'reports'
    out = SimpleNamespace(ruta_db=ruta_db, modelos=modelos, reportes=reportes)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, 'MODELOS', modelos)
        mp.setattr(config, 'REPORTES', reportes)
        ejecutar = lambda **kw: pipeline.ejecutar(ruta_db=ruta_db, ruta_operacional=ruta_op, verbose=False, **kw)  # noqa: E731
        out.v1_primera = ejecutar(hasta=2016)
        out.v1_segunda = ejecutar(hasta=2016)
        out.v1_db = raiz / 'copia_v1_cafe.db'
        shutil.copy(ruta_db, out.v1_db)
        out.v1_modelos = _copiar(modelos, raiz / 'copia_v1_models')
        out.v1_reportes = _copiar(reportes, raiz / 'copia_v1_reports')
        out.v2_primera = ejecutar(hasta=2018)
        out.v2_segunda = ejecutar(hasta=2018)
    return out


def _ml(ruta_db):
    con = sqlite3.connect(ruta_db)
    try:
        return pd.read_sql('SELECT * FROM ml_dataset ORDER BY lote_id', con)
    finally:
        con.close()


# --------------------------------------------------------------------------------------------------- orquestador (criterio de T08)
def test_el_pipeline_completo_dos_veces_dice_sin_cambios_la_segunda(orquestado):
    assert [r['pipeline'] for r in orquestado.v1_primera] == ['pipeline_ingesta_raw', 'pipeline_ingesta_master', 'pipeline_ml', 'pipeline_train']
    assert {r['estado'] for r in orquestado.v1_primera} == {'ejecutado'}
    assert {r['estado'] for r in orquestado.v1_segunda} == {'sin cambios'}
    for a, b in zip(orquestado.v1_primera, orquestado.v1_segunda):
        assert a['huella_entrada'] == b['huella_entrada'] and a['resumen'] == b['resumen']


def test_hasta_2018_rehace_todo_y_crea_la_version_2_del_modelo(orquestado):
    assert {r['estado'] for r in orquestado.v2_primera} == {'ejecutado'}
    assert {r['estado'] for r in orquestado.v2_segunda} == {'sin cambios'}
    v1, v2 = orquestado.v1_primera[-1]['resumen'], orquestado.v2_primera[-1]['resumen']
    assert (v1['version_modelo_registrado'], v2['version_modelo_registrado']) == (1, 2)
    assert v1['huella_datos'] != v2['huella_datos']
    assert all(a['huella_entrada'] != b['huella_entrada'] for a, b in zip(orquestado.v1_primera, orquestado.v2_primera))
    con = sqlite3.connect(orquestado.modelos / 'mlflow.db')
    versiones = con.execute('SELECT version FROM model_versions WHERE name = ? ORDER BY version', (config.MODELO_REGISTRADO,)).fetchall()
    con.close()
    assert versiones == [(1,), (2,)]


def test_el_orquestador_rechaza_un_hasta_desconocido_y_un_pipeline_desconocido(tmp_path):
    with pytest.raises(ValueError, match='--hasta'):
        pipeline.ejecutar(hasta=2017, ruta_db=tmp_path / 'a.db', ruta_operacional=tmp_path / 'o.db', verbose=False)
    with pytest.raises(ValueError, match='desconocidos'):
        pipeline.ejecutar(['pipeline_inventado'], ruta_db=tmp_path / 'a.db', verbose=False)


def test_sin_hasta_no_toca_una_operacional_que_ya_existe(tmp_path):
    from cafe_mlops import operacional
    ruta = tmp_path / 'cqi.db'
    operacional.crear_operacional(2018, ruta, verbose=False)
    pipeline.preparar_operacional(None, ruta, verbose=False)
    assert pipeline.hasta_de_la_operacional(ruta) == 2018
    pipeline.preparar_operacional(2018, ruta, verbose=False)
    assert pipeline.hasta_de_la_operacional(ruta) == 2018


# --------------------------------------------------------------------------------------------------- Pipeline y None frente a NaN (pico T07, cambio 1)
def _modelo(orquestado):
    return joblib.load(orquestado.v1_modelos / 'modelo.joblib')


def test_el_preprocesado_va_dentro_del_modelo_y_la_rama_de_texto_empieza_por_nulos_a_nan(orquestado):
    modelo = _modelo(orquestado)
    assert [n for n, _ in modelo.steps] == ['preprocesar', 'modelo']
    ct = modelo.named_steps['preprocesar']
    assert {n: cols for n, _, cols in ct.transformers_ if n != 'remainder'} == {'num': config.NUMERICAS, 'cat': config.CATEGORICAS}
    cat = ct.named_transformers_['cat']
    assert cat.steps[0][0] == 'nulos'
    assert cat.steps[0][1].func is preproceso.nulos_a_nan
    assert [n for n, _ in cat.steps] == ['nulos', 'imputar', 'onehot']
    assert cat.named_steps['onehot'].handle_unknown == 'ignore'


def test_none_nan_y_pd_na_en_el_texto_dan_la_misma_probabilidad(orquestado):
    """Vigila el desajuste silencioso: SimpleImputer no trata None como nulo, por eso existe nulos_a_nan."""
    modelo = _modelo(orquestado)
    base = preproceso.preparar_X(_ml(orquestado.v1_db).query('particion == "test"').head(30))
    for col in config.CATEGORICAS[1:]:      # pais, variedad, metodo_proceso, color (especie no es nula nunca)
        probs = []
        for nulo in (None, np.nan, pd.NA):
            x = base.copy()
            x[col] = x[col].astype(object)
            x.loc[x.index[:10], col] = nulo
            probs.append(modelo.predict_proba(x)[:, 1])
        assert np.array_equal(probs[0], probs[1]) and np.array_equal(probs[1], probs[2]), col
        # y un nulo es «Desconocida»: da lo mismo que escribir esa palabra
        x = base.copy()
        x.loc[x.index[:10], col] = np.nan
        y = base.copy()
        y.loc[y.index[:10], col] = preproceso.CATEGORIA_NULA
        # (solo si «Desconocida» no es una categoría real de los datos: no lo es, MASTER deja nulos)
        assert np.allclose(modelo.predict_proba(x)[:, 1], modelo.predict_proba(y)[:, 1], atol=1e-12), col


def test_sin_el_primer_paso_un_none_si_se_trataria_distinto():
    """Documenta POR QUÉ existe nulos_a_nan: sin él, None y NaN no son lo mismo para SimpleImputer. Si scikit-learn cambiara
    esto, la prueba fallará y se podrá simplificar el modelo (y revisar la API)."""
    from sklearn.impute import SimpleImputer
    x = pd.DataFrame({'a': pd.Series(['x', None, np.nan], dtype=object)})
    imputado = SimpleImputer(strategy='constant', fill_value='D').fit_transform(x)
    assert list(imputado[:, 0]) == ['x', None, 'D']


def test_las_variables_preparadas_son_float64_y_el_texto_no_lleva_none(orquestado):
    X = preproceso.preparar_X(pd.DataFrame(_ml(orquestado.v1_db)).assign(defectos_cat1=lambda d: d['defectos_cat1'].round().astype('int64')))
    assert all(X[c].dtype == np.float64 for c in config.NUMERICAS)
    assert list(X.columns) == config.FEATURES
    for c in config.CATEGORICAS:
        assert not any(v is None or v is pd.NA for v in X[c]), c
    assert X['variedad'].isna().any()   # los nulos existen y son NaN
    with pytest.raises(KeyError):
        preproceso.preparar_X(X.drop(columns=['pais']))


# --------------------------------------------------------------------------------------------------- firma (pico T07, cambios 2 a 4)
def test_la_firma_guardada_tiene_los_nombres_y_tipos_de_las_variables(orquestado):
    contrato = predict.contrato_de_la_firma(orquestado.v1_modelos / config.CARPETA_MODELO_MLFLOW)
    assert [n for n, _, _ in contrato] == config.FEATURES
    assert {n: t for n, t, _ in contrato} == {c: ('string' if c in config.CATEGORICAS else 'double') for c in config.FEATURES}
    assert not any(t in ('long', 'integer') for _, t, _ in contrato)     # ninguna numérica entera (cambio 2)
    meta = json.loads((orquestado.v1_modelos / 'metadatos.json').read_text(encoding='utf-8'))
    assert meta['tipos'] == {n: t for n, t, _ in contrato}
    assert meta['variables'] == config.FEATURES


def test_el_modelo_mlflow_se_guarda_con_predict_proba(orquestado):
    texto = (orquestado.v1_modelos / config.CARPETA_MODELO_MLFLOW / 'MLmodel').read_text(encoding='utf-8')
    assert 'predict_fn: predict_proba' in texto
    assert 'serialization_format: cloudpickle' in texto


def test_pyfunc_devuelve_probabilidades_iguales_a_las_de_joblib(orquestado):
    """pyfunc valida la firma y, con predict_proba, devuelve (n, 2) (no etiquetas 0/1)."""
    import mlflow.pyfunc
    df = _ml(orquestado.v1_db).query('particion == "test"').head(60)[config.FEATURES]
    esperado = _modelo(orquestado).predict_proba(preproceso.preparar_X(df))
    cargado = mlflow.pyfunc.load_model(str(orquestado.v1_modelos / config.CARPETA_MODELO_MLFLOW))
    obtenido = np.asarray(cargado.predict(preproceso.preparar_X(df)))
    assert obtenido.shape == (60, 2)
    assert np.abs(obtenido - esperado).max() <= 1e-12


# --------------------------------------------------------------------------------------------------- métricas
def test_las_metricas_de_valid_y_test_coinciden_con_recalcularlas(orquestado):
    meta = json.loads((orquestado.v1_modelos / 'metadatos.json').read_text(encoding='utf-8'))
    informe = json.loads((orquestado.v1_reportes / 'metricas.json').read_text(encoding='utf-8'))
    df = _ml(orquestado.v1_db)
    modelo = _modelo(orquestado)
    for p in ('valid', 'test'):
        sub = df[df['particion'] == p]
        prob = modelo.predict_proba(preproceso.preparar_X(sub))[:, 1]
        y = sub['y'].to_numpy()
        m = informe['modelos'][meta['modelo']][p]
        assert m['n'] == len(sub) and m['no_especialidad'] == int((y == 0).sum())
        assert m['auc'] == pytest.approx(roc_auc_score(y, prob), abs=1e-12)
        assert m['ap_no_especialidad'] == pytest.approx(average_precision_score(1 - y, 1 - prob), abs=1e-12)
        assert m['tasa_base_no_especialidad'] == pytest.approx(float(np.mean(y == 0)))
        assert m['auc_ic95'][0] <= m['auc'] <= m['auc_ic95'][1]
    assert meta['metricas_valid'] == informe['modelos'][meta['modelo']]['valid']
    # v1: valid 2015 tiene 12 lotes < 80 y test (2016) solo 5: el aviso de ruido tiene base
    assert (informe['modelos'][meta['modelo']]['valid']['no_especialidad'], informe['modelos'][meta['modelo']]['test']['no_especialidad']) == (12, 5)


def test_se_comparan_tres_modelos_y_el_elegido_se_escoge_con_valid_no_con_test(orquestado):
    informe = json.loads((orquestado.v1_reportes / 'metricas.json').read_text(encoding='utf-8'))
    assert set(informe['modelos']) == {'referencia_sin_aprender', 'regresion_logistica', 'gradient_boosting'}
    aucs = {n: m['valid']['auc'] for n, m in informe['modelos'].items() if n != 'referencia_sin_aprender'}
    assert informe['mejor'] == max(aucs, key=aucs.get)
    ref = informe['modelos']['referencia_sin_aprender']
    for p in ('train', 'valid', 'test'):
        assert ref[p]['auc'] == pytest.approx(0.5)        # el mínimo que hay que superar
        assert ref[p]['ap_no_especialidad'] == pytest.approx(ref[p]['tasa_base_no_especialidad'])
    assert 'oscila' in informe['aviso']


def test_la_exactitud_no_distingue_y_se_guarda_junto_a_la_de_siempre_especialidad(orquestado):
    informe = json.loads((orquestado.v1_reportes / 'metricas.json').read_text(encoding='utf-8'))
    t = informe['modelos']['referencia_sin_aprender']['train']
    assert t['exactitud'] == pytest.approx(t['exactitud_siempre_especialidad'])


def test_comprobacion_temporal_en_el_informe_y_error_si_se_rompe(orquestado):
    informe = json.loads((orquestado.v1_reportes / 'metricas.json').read_text(encoding='utf-8'))
    r = informe['comprobacion_temporal']
    assert r['train'][1] < r['valid'][0] and r['valid'][1] < r['test'][0]
    df = _ml(orquestado.v1_db)
    assert train.comprobar_temporal(df) == r
    roto = df.copy()
    roto.loc[roto.index[roto['particion'] == 'valid'][0], 'anio_cata'] = 2010     # un lote de valid con año de train
    with pytest.raises(train.ParticionTemporalError):
        train.comprobar_temporal(roto)
    roto2 = df.copy()
    roto2.loc[roto2.index[roto2['particion'] == 'valid'], 'particion'] = 'train'   # valid vacía
    with pytest.raises(train.ParticionTemporalError):
        train.comprobar_temporal(roto2)


def test_ventana_creciente_agrupa_los_cortes_y_cuenta_lo_que_hay_en_los_datos(orquestado):
    """v1 (hasta 2016): selección 2013 y 2014; examen 2015 y 2016 (el corte 2017-2018 se omite). v2: 2017-2018 también."""
    df1 = _ml(orquestado.ruta_db)    # la base es ya la de la versión 2 (el fixture termina en 2018): se filtra por año
    for ruta, maximo, cortes_examen in ((orquestado.v1_reportes, 2016, 2), (orquestado.reportes, 2018, 3)):
        informe = json.loads((ruta / 'metricas.json').read_text(encoding='utf-8'))
        v = informe['ventana_creciente_informativa'][informe['mejor']]
        sel, exa = v['grupos']['seleccion'], v['grupos']['examen']
        d = df1[df1['anio_cata'] <= maximo]
        assert sel['cortes'] == 2 and exa['cortes'] == cortes_examen
        assert sel['n'] == int(d['anio_cata'].between(2013, 2014).sum())
        assert sel['no_especialidad'] == int(((d['anio_cata'].between(2013, 2014)) & (d['y'] == 0)).sum())
        assert exa['n'] == int((d['anio_cata'] >= 2015).sum())
        assert exa['no_especialidad'] == int(((d['anio_cata'] >= 2015) & (d['y'] == 0)).sum())
        assert exa['auc_ic95'][0] <= exa['auc'] <= exa['auc_ic95'][1]
        assert v['cv_aleatoria']['n'] == int((d['anio_cata'] >= 2013).sum())
        assert [c['entrenado_con'] for c in v['cortes'] if c['grupo'] == 'seleccion'] == [int((d['anio_cata'] < 2013).sum()), int((d['anio_cata'] < 2014).sum())]


def test_la_particion_desliza_de_la_version_1_a_la_2(orquestado):
    m1 = json.loads((orquestado.v1_modelos / 'metadatos.json').read_text(encoding='utf-8'))
    m2 = json.loads((orquestado.modelos / 'metadatos.json').read_text(encoding='utf-8'))
    assert m1['filas'] == {'train': 866, 'valid': 197, 'test': 127} and m2['filas'] == {'train': 1063, 'valid': 127, 'test': 148}
    assert m1['particiones'] == {'train': [2009, 2014], 'valid': [2015, 2015], 'test': [2016, 2016]}
    assert m2['particiones'] == {'train': [2009, 2015], 'valid': [2016, 2016], 'test': [2017, 2018]}
    assert m1['particiones'] == {p: list(v) for p, v in config.particiones_de(1).items()}
    assert (m1['version_datos'], m2['version_datos']) == (1, 2)
    assert (m1['anio_cata_maximo'], m2['anio_cata_maximo']) == (2016, 2018)


def test_el_modelo_de_la_version_2_cambia_y_da_otras_probabilidades(orquestado):
    """Con la partición deslizante la v2 aprende de 2015 (antes valid): ya no es «el mismo modelo reentrenado»."""
    X = preproceso.preparar_X(_ml(orquestado.ruta_db).query('anio_cata >= 2016'))     # los mismos lotes para los dos modelos
    p1 = joblib.load(orquestado.v1_modelos / 'modelo.joblib').predict_proba(X)[:, 1]
    p2 = joblib.load(orquestado.modelos / 'modelo.joblib').predict_proba(X)[:, 1]
    assert not np.array_equal(p1, p2)
    assert np.abs(p1 - p2).max() > 1e-3
    m1 = json.loads((orquestado.v1_modelos / 'metadatos.json').read_text(encoding='utf-8'))
    m2 = json.loads((orquestado.modelos / 'metadatos.json').read_text(encoding='utf-8'))
    assert m1['huella_datos'] != m2['huella_datos']


def test_la_ventana_comun_son_los_mismos_lotes_en_las_dos_versiones_y_se_recalcula(orquestado):
    m1 = json.loads((orquestado.v1_modelos / 'metadatos.json').read_text(encoding='utf-8'))
    m2 = json.loads((orquestado.modelos / 'metadatos.json').read_text(encoding='utf-8'))
    assert m1['ventana_comun'] == m2['ventana_comun'] == list(config.VENTANA_COMUN)
    for meta, ruta_db, carpeta in ((m1, orquestado.v1_db, orquestado.v1_modelos), (m2, orquestado.ruta_db, orquestado.modelos)):
        df = _ml(ruta_db)
        sub = df[df['anio_cata'].between(*config.VENTANA_COMUN)]
        y = sub['y'].to_numpy()
        prob = joblib.load(carpeta / 'modelo.joblib').predict_proba(preproceso.preparar_X(sub))[:, 1]
        m = meta['metricas_comun']
        assert (m['n'], m['no_especialidad']) == (127, 5)      # los mismos 127 lotes de 2016 con la v1 y con la v2
        assert m['auc'] == pytest.approx(roc_auc_score(y, prob), abs=1e-12)
        assert sub['particion'].isin(['test' if meta['version_datos'] == 1 else 'valid']).all()    # y ninguna versión los vio al entrenar
        assert not sub['particion'].eq('train').any()


def test_metadatos_guardan_categorias_vistas_y_rangos_para_la_api(orquestado):
    meta = json.loads((orquestado.v1_modelos / 'metadatos.json').read_text(encoding='utf-8'))
    df = _ml(orquestado.v1_db)
    tr = df[df['particion'] == 'train']
    assert set(meta['categorias_vistas']) == set(config.CATEGORICAS)
    # lo que ve el codificador son los valores reales de train + «Desconocida» (los nulos) + nan
    for c in config.CATEGORICAS:
        reales = set(tr[c].dropna().unique())
        assert reales <= set(meta['categorias_vistas'][c]), c
    for c in config.NUMERICAS:
        lo, hi = meta['rangos_entrenamiento'][c]
        assert lo == pytest.approx(tr[c].min()) and hi == pytest.approx(tr[c].max())
    assert set(meta['categorias_infrecuentes']) == set(config.CATEGORICAS)


# --------------------------------------------------------------------------------------------------- predict
def test_predecir_probabilidad_coincide_con_el_modelo_y_acepta_nulos(orquestado):
    carpeta = orquestado.v1_modelos
    df = _ml(orquestado.v1_db).query('particion == "test"').head(20)
    esperado = _modelo(orquestado).predict_proba(preproceso.preparar_X(df))[:, 1]
    assert np.array_equal(predict.predecir_probabilidad(df, ruta=carpeta), esperado)
    fila = df.iloc[0][config.FEATURES].to_dict()
    assert predict.predecir_probabilidad(fila, ruta=carpeta) == esperado[0]
    sin = dict(fila, variedad=None, humedad=None)
    assert predict.predecir_probabilidad(sin, ruta=carpeta) == predict.predecir_probabilidad(dict(fila, variedad=np.nan, humedad=np.nan), ruta=carpeta)
    # una categoría que el modelo no vio no rompe (one-hot en ceros)
    assert 0 <= predict.predecir_probabilidad(dict(fila, pais='Atlantis', variedad='Inventada'), ruta=carpeta) <= 1


def test_predecir_sin_una_variable_da_un_error_claro(orquestado):
    fila = _ml(orquestado.v1_db).iloc[0][config.FEATURES].to_dict()
    del fila['pais']
    with pytest.raises(predict.VariablesFaltantesError, match='pais'):
        predict.predecir_probabilidad(fila, ruta=orquestado.v1_modelos)


def test_predecir_un_lote_de_fs(orquestado):
    con = db.conectar(orquestado.v1_db)
    try:
        p = predict.predecir_lote(12, con, ruta=orquestado.v1_modelos)
        with pytest.raises(LookupError):
            predict.predecir_lote(999999, con, ruta=orquestado.v1_modelos)
    finally:
        con.close()
    assert 0 <= p <= 1


# --------------------------------------------------------------------------------------------------- comparar
def test_los_caminos_dan_la_misma_probabilidad(orquestado):
    filas, n, tol = comparar.comparar_caminos(50, carpeta=orquestado.v1_modelos, ruta_db=orquestado.v1_db)
    assert [f['camino'] for f in filas] == ['paquete (referencia)', 'joblib', 'MLflow sklearn', 'MLflow pyfunc']
    assert n == 50 and all(f['coincide'] and f['filas'] == 50 for f in filas)
    assert max(f['diferencia_maxima'] for f in filas) <= 1e-12


def test_comparar_repetido_da_exactamente_lo_mismo(orquestado):
    a = comparar.comparar_caminos(50, carpeta=orquestado.v1_modelos, ruta_db=orquestado.v1_db)
    b = comparar.comparar_caminos(50, carpeta=orquestado.v1_modelos, ruta_db=orquestado.v1_db)
    assert a == b


def test_comparar_con_referencia_usa_la_tolerancia_de_config():
    cand = {'huella_datos': 'a', config.METRICA_COMPARACION: 0.70}
    ref = {'huella_datos': 'b', config.METRICA_COMPARACION: 0.70 + config.TOLERANCIA_COMPARACION}
    r = comparar.comparar_con_referencia(cand, ref)
    assert r['aprobada'] and r['tolerancia'] == config.TOLERANCIA_COMPARACION and not r['misma_huella_datos']   # justo en el límite: se aprueba
    ref[config.METRICA_COMPARACION] += 0.001
    assert not comparar.comparar_con_referencia(cand, ref)['aprobada']
    assert comparar.comparar_con_referencia(cand, ref, tolerancia=0.05)['aprobada']
    assert comparar.comparar_con_referencia({'huella_datos': 'a', config.METRICA_COMPARACION: 0.9}, ref)['aprobada']   # mejorar siempre se aprueba


def test_fijar_referencia_y_comparar_sin_diferencias(orquestado, tmp_path):
    ruta = tmp_path / 'referencia.json'
    ref = comparar.fijar_referencia(orquestado.v1_modelos, ruta)
    assert json.loads(ruta.read_text(encoding='utf-8')) == ref
    cand = comparar.leer_candidata(orquestado.v1_modelos)
    r = comparar.comparar_con_referencia(cand, comparar.leer_referencia(ruta))
    assert r['diferencia'] == 0 and r['aprobada'] and r['misma_huella_datos']


def test_la_version_2_frente_a_la_referencia_de_la_version_1(orquestado, tmp_path):
    """Se compara el AUC sobre la ventana común (2016): los mismos lotes y ninguna versión los vio al entrenar. El modelo SÍ cambia."""
    ruta = tmp_path / 'referencia.json'
    comparar.fijar_referencia(orquestado.v1_modelos, ruta)
    cand, ref = comparar.leer_candidata(orquestado.modelos), comparar.leer_referencia(ruta)
    r = comparar.comparar_con_referencia(cand, ref)
    assert not r['misma_huella_datos'] and r['diferencia'] != 0
    assert r['metrica'] == 'auc_comun' and cand['ventana_comun'] == ref['ventana_comun'] == list(config.VENTANA_COMUN)
    assert r['aprobada'] == (r['diferencia'] >= -config.TOLERANCIA_COMPARACION - 1e-12)


def test_dos_ventanas_distintas_no_se_comparan(orquestado, tmp_path):
    ruta = tmp_path / 'referencia.json'
    comparar.fijar_referencia(orquestado.v1_modelos, ruta)
    ref = comparar.leer_referencia(ruta)
    cand = comparar.leer_candidata(orquestado.modelos)
    with pytest.raises(comparar.NoSePudoComparar, match='ventana'):
        comparar.comparar_con_referencia(dict(cand, ventana_comun=[2015, 2015]), ref)
    sin = {k: v for k, v in ref.items() if k != 'ventana_comun'}      # una referencia antigua, sin ventana, tampoco vale
    with pytest.raises(comparar.NoSePudoComparar, match='ventana'):
        comparar.comparar_con_referencia(cand, sin)


def test_comparar_desde_la_terminal_codigos_de_salida(orquestado, tmp_path, monkeypatch, capsys):
    ruta_ref = tmp_path / 'referencia.json'
    monkeypatch.setattr(config, 'MODELOS', orquestado.v1_modelos)
    monkeypatch.setattr(config, 'DB', orquestado.v1_db)
    monkeypatch.setattr(config, 'REFERENCIA', ruta_ref)
    assert comparar.main(['--n', '20']) == 2                      # sin referencia
    assert 'fijar-referencia' in capsys.readouterr().err
    assert comparar.main(['--fijar-referencia']) == 0
    assert 'Referencia fijada' in capsys.readouterr().out
    assert comparar.main(['--n', '20']) == 0
    salida1 = capsys.readouterr().out
    assert 'APROBADA' in salida1 and 'coincide' in salida1 and 'DIFIERE' not in salida1
    assert comparar.main(['--n', '20']) == 0
    assert capsys.readouterr().out == salida1      # repetido: exactamente la misma salida
    ref = json.loads(ruta_ref.read_text(encoding='utf-8'))
    ref[config.METRICA_COMPARACION] += 0.5
    ruta_ref.write_text(json.dumps(ref), encoding='utf-8')
    assert comparar.main(['--n', '20']) == 1
    assert 'RECHAZADA' in capsys.readouterr().out


def test_comparar_con_una_api_simulada(orquestado, monkeypatch):
    """API simulada: solo se comprueba que comparar sabe pedir el lote y leer la respuesta. Con la API real: tests/test_api.py."""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Manejador(BaseHTTPRequestHandler):
        def do_POST(self):
            cuerpo = json.loads(self.rfile.read(int(self.headers['content-length'])))
            probs = predict.predecir_probabilidad(pd.DataFrame(cuerpo['lotes']), ruta=orquestado.v1_modelos)
            datos = json.dumps({'predicciones': [{'probabilidad_especialidad': p} for p in probs]}).encode()
            self.send_response(200)
            self.send_header('content-type', 'application/json')
            self.send_header('content-length', str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)

        def log_message(self, *a):
            pass

    servidor = HTTPServer(('127.0.0.1', 0), Manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        filas, _, _ = comparar.comparar_caminos(30, url=f'http://127.0.0.1:{servidor.server_port}', carpeta=orquestado.v1_modelos, ruta_db=orquestado.v1_db)
    finally:
        servidor.shutdown()
    assert filas[-1]['camino'].startswith('API') and filas[-1]['coincide']


def test_comparar_sin_modelo_no_se_pudo_comparar(tmp_path):
    with pytest.raises(comparar.NoSePudoComparar, match='pipeline'):
        comparar.comparar_caminos(5, carpeta=tmp_path, ruta_db=tmp_path / 'no.db')


# --------------------------------------------------------------------------------------------------- referencia.json y config
def test_referencia_json_inicial_es_valida():
    ruta = RAIZ / 'models' / 'referencia.json'
    assert config.REFERENCIA == ruta or 'TALLER_REFERENCIA' in __import__('os').environ
    ref = json.loads(ruta.read_text(encoding='utf-8'))
    assert ref['metrica'] == config.METRICA_COMPARACION
    assert 0.5 < ref[config.METRICA_COMPARACION] < 1
    assert ref['version_datos'] == 1 and ref['anio_cata_maximo'] == 2016
    assert ref['metricas_comun']['auc'] == ref[config.METRICA_COMPARACION]
    assert ref['ventana_comun'] == list(config.VENTANA_COMUN) and ref['metricas_comun']['n'] == 127
    assert ref['filas'] == {'train': 866, 'valid': 197, 'test': 127}
    assert ref['modelo'] in ('regresion_logistica', 'gradient_boosting')


def test_la_tolerancia_sigue_marcada_como_provisional():
    texto = (RAIZ / 'cafe_mlops' / 'config.py').read_text(encoding='utf-8')
    linea = next(l for l in texto.splitlines() if l.startswith('TOLERANCIA_COMPARACION'))
    assert 'TODO-T08' in linea
    assert 'TODO-T08' in (RAIZ / 'cafe_mlops' / 'modeling' / 'comparar.py').read_text(encoding='utf-8')


# --------------------------------------------------------------------------------------------------- mlflow_ui
def test_mlflow_ui_resume_el_registro_y_usa_rutas_absolutas(orquestado, monkeypatch, capsys):
    monkeypatch.setattr(config, 'MODELOS', orquestado.modelos)
    ejecuciones, versiones = mlflow_ui.resumen()
    assert versiones == 2 and ejecuciones == 8       # (tres modelos + MEJOR) x dos versiones de los datos
    assert mlflow_ui.uri().startswith('sqlite:///') and orquestado.modelos.name in mlflow_ui.uri()
    orden = mlflow_ui.comando(5001)
    assert orden[:4] == [sys.executable, '-m', 'mlflow', 'ui'] and '5001' in orden and mlflow_ui.uri() in orden
    assert mlflow_ui.main(['--comprobar']) == 0
    assert 'Experimento' in capsys.readouterr().out


def test_mlflow_ui_sin_registro_dice_que_hay_que_entrenar(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, 'MODELOS', tmp_path / 'vacio')
    assert mlflow_ui.resumen() is None and mlflow_ui.main(['--comprobar']) == 1
    assert 'cafe_mlops.pipeline' in capsys.readouterr().out


# --------------------------------------------------------------------------------------------------- determinismo
def test_entrenar_dos_veces_da_exactamente_lo_mismo(bases_v1, tmp_path, monkeypatch):
    """Semillas fijas: mismas métricas (el informe es byte a byte igual) y mismas probabilidades."""
    resultados = []
    for i in (1, 2):
        monkeypatch.setattr(config, 'MODELOS', tmp_path / f'm{i}')
        monkeypatch.setattr(config, 'REPORTES', tmp_path / f'r{i}')
        con = db.conectar(bases_v1[1])
        train.entrenar(con, usar_mlflow=False, verbose=False)
        con.close()
        resultados.append(tmp_path)
    assert (tmp_path / 'r1' / 'metricas.json').read_bytes() == (tmp_path / 'r2' / 'metricas.json').read_bytes()
    X = preproceso.preparar_X(_ml(bases_v1[1]))
    a = joblib.load(tmp_path / 'm1' / 'modelo.joblib').predict_proba(X)
    b = joblib.load(tmp_path / 'm2' / 'modelo.joblib').predict_proba(X)
    assert np.array_equal(a, b)
    m1, m2 = (json.loads((tmp_path / f'm{i}' / 'metadatos.json').read_text(encoding='utf-8')) for i in (1, 2))
    for m in (m1, m2):
        m.pop('entrenado_en')
    assert m1 == m2

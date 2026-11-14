"""Pruebas de las capas FS y ML (T06): sin fuga, particiones temporales disjuntas y objetivo recalculado con pandas."""
import re
import shutil

import numpy as np
import pandas as pd
import pytest

from auxiliar import RAIZ, esperado, numerico, sin_comentarios_sql
from cafe_mlops import config, db
from cafe_mlops.modeling import ml_dataset

# Conteos verificados el 14/11/2026 (año de Grading.Date), partición DESLIZANTE: v1 train <= 2014, valid 2015, test 2016;
# v2 train <= 2015, valid 2016, test 2017-2018.
PARTICIONES = {
    2016: {'train': (866, 152), 'valid': (197, 12), 'test': (127, 5)},     # (lotes, no especialidad)
    2018: {'train': (1063, 164), 'valid': (127, 5), 'test': (148, 17)},
}
PROHIBIDAS_EN_FS = ['notas_cata', 'total_puntos', 'catas', 'raw_', 'propietario', 'productor', 'finca']


def _norm(n):
    return n.lower().replace('.', '_')


# --------------------------------------------------------------------------------------------------- FS: sin fuga
def test_fs_tiene_exactamente_las_variables_de_config(con):
    columnas = [c[1] for c in con.execute('PRAGMA table_info(fs_lote)')]
    assert columnas == ['lote_id'] + config.FEATURES


def test_ninguna_columna_de_fs_sale_de_las_notas_de_cata_ni_del_total(con):
    columnas = {c[1] for c in con.execute('PRAGMA table_info(fs_lote)')} - {'lote_id'}
    prohibidas = {_norm(n) for n in config.TODAS_LAS_NOTAS} | {_norm(config.COLUMNA_TOTAL), 'total_puntos', 'y'}
    assert not columnas & prohibidas
    assert not columnas & {_norm(c) for c in config.COLUMNAS_PERSONALES + config.COLUMNAS_FUERA_DEL_MODELO}


def test_el_sql_de_fs_no_lee_notas_ni_total_ni_personas():
    """Lo que hace FS es leer master_lotes: ni una referencia a notas, total o nombres (comentarios aparte)."""
    for ruta in (RAIZ / 'sql' / 'fs').glob('*.sql'):
        texto = re.sub(r"'[^']*'", "''", sin_comentarios_sql(ruta.read_text(encoding='utf-8')).lower())   # sin comentarios ni textos entre comillas
        for p in PROHIBIDAS_EN_FS:
            assert p not in texto, f'{ruta.name} menciona {p}'
        assert 'master_lotes' in texto or 'create table' in texto


def test_el_catalogo_describe_cada_variable_y_cuando_se_conoce(con):
    filas = con.execute('SELECT feature, tipo, origen, cuando_se_conoce FROM fs_catalogo ORDER BY rowid').fetchall()
    assert [f[0] for f in filas] == config.FEATURES
    for feature, tipo, origen, cuando in filas:
        assert tipo == ('categorica' if feature in config.CATEGORICAS else 'numerica')
        assert cuando == 'al recibir el lote'
        assert config.ORIGEN_DE_LAS_VARIABLES[feature] in origen
        assert 'notas_cata' not in origen and 'total' not in origen.lower()


def test_fs_una_fila_por_lote_de_master_y_con_sus_valores(con, hasta):
    fs = pd.read_sql('SELECT * FROM fs_lote ORDER BY lote_id', con).set_index('lote_id')
    m = pd.read_sql('SELECT * FROM master_lotes ORDER BY lote_id', con).set_index('lote_id')
    assert list(fs.index) == list(m.index) and len(fs) == (1190 if hasta == 2016 else 1338)
    for col in config.FEATURES:
        pd.testing.assert_series_equal(fs[col], m[col], check_dtype=False, check_names=False, obj=col)


def test_fs_numericas_son_reales_para_que_la_firma_admita_nulos(con):
    tipos = {c[1]: c[2] for c in con.execute('PRAGMA table_info(fs_lote)')}
    for col in config.NUMERICAS:
        assert tipos[col] == 'REAL', col
        assert db.escalar(con, f"SELECT COUNT(*) FROM fs_lote WHERE typeof({col}) NOT IN ('real', 'null')") == 0, col


def test_fs_no_inventa_valores_los_ausentes_siguen_nulos(con, hasta):
    ids = [i for (i,) in con.execute('SELECT lote_id FROM fs_lote')]
    csv_ = esperado(hasta).set_index('lote_id').loc[ids]
    assert db.escalar(con, 'SELECT COUNT(*) FROM fs_lote WHERE variedad IS NULL') == csv_['Variety'].isna().sum()
    assert db.escalar(con, 'SELECT COUNT(*) FROM fs_lote WHERE metodo_proceso IS NULL') == csv_['Processing.Method'].isna().sum()
    assert db.escalar(con, 'SELECT COUNT(*) FROM fs_lote WHERE color IS NULL') == csv_['Color'].isna().sum()
    assert db.escalar(con, "SELECT COUNT(*) FROM fs_lote WHERE variedad = 'Desconocida' OR pais = 'Desconocida'") == 0

def test_ninguna_variable_numerica_reproduce_el_total(con):
    """Comprobación numérica de la fuga: ninguna variable (sola) explica el total; las notas sumadas, en cambio, sí."""
    df = pd.read_sql('SELECT f.*, m.total_puntos FROM fs_lote f JOIN master_lotes m USING (lote_id)', con)
    for col in config.NUMERICAS:
        r = df[[col, 'total_puntos']].dropna().corr().iloc[0, 1]
        assert abs(r) < 0.5, f'{col} se parece demasiado al total (r={r:.2f})'
    suma = pd.read_sql('SELECT cata_id AS lote_id, SUM(valor) AS suma FROM raw_notas_cata GROUP BY cata_id', con)
    unido = df.merge(suma, on='lote_id')
    assert unido['suma'].corr(unido['total_puntos']) > 0.99   # la fuga que NO debe entrar al modelo


# --------------------------------------------------------------------------------------------------- ML
def test_ml_tiene_las_columnas_esperadas_y_ningun_lote_pierde_su_particion(con, hasta):
    columnas = [c[1] for c in con.execute('PRAGMA table_info(ml_dataset)')]
    assert columnas == ['lote_id', 'particion', 'anio_cata', 'y'] + config.FEATURES
    assert db.escalar(con, 'SELECT COUNT(*) FROM ml_dataset') == db.escalar(con, 'SELECT COUNT(*) FROM fs_lote')


def test_las_particiones_son_disjuntas_y_cubren_todo(con):
    assert db.escalar(con, 'SELECT COUNT(*) FROM (SELECT lote_id FROM ml_dataset GROUP BY lote_id HAVING COUNT(*) > 1)') == 0
    assert db.escalar(con, 'SELECT COUNT(*) FROM ml_dataset WHERE lote_id NOT IN (SELECT lote_id FROM fs_lote)') == 0
    assert {p for (p,) in con.execute('SELECT DISTINCT particion FROM ml_dataset')} == {'train', 'valid', 'test'}


def test_la_particion_es_temporal_train_antes_que_valid_antes_que_test(con, hasta):
    rango = {p: (a, b) for p, a, b in con.execute('SELECT particion, MIN(anio_cata), MAX(anio_cata) FROM ml_dataset GROUP BY particion')}
    assert rango['train'][1] < rango['valid'][0] <= rango['valid'][1] < rango['test'][0]
    for p, (desde, hasta_) in config.particiones_de(config.VERSIONES_DATOS[hasta]).items():
        assert desde <= rango[p][0] and rango[p][1] <= hasta_


def test_la_particion_no_depende_del_orden_del_archivo(con, hasta):
    """El archivo viene ordenado por puntuación; la partición se decide por la fecha, no por la fila."""
    ml = pd.read_sql('SELECT lote_id, particion, anio_cata FROM ml_dataset ORDER BY lote_id', con)
    valid = {2016: 2015, 2018: 2016}[hasta]    # el año de valid desliza con la versión
    por_fecha = np.select([ml['anio_cata'] < valid, ml['anio_cata'] == valid], ['train', 'valid'], 'test')
    assert list(ml['particion']) == list(por_fecha)
    assert ml['lote_id'].is_monotonic_increasing and not ml['anio_cata'].is_monotonic_increasing


def test_tamanos_y_no_especialidad_por_particion(con, hasta):
    obtenido = {p: (n, n - s) for p, n, s in con.execute('SELECT particion, COUNT(*), SUM(y) FROM ml_dataset GROUP BY particion')}
    assert obtenido == PARTICIONES[hasta]
    assert all(neg > 0 for _, neg in obtenido.values())   # cada partición tiene las dos clases (aunque el test de v1 tiene pocos negativos)


def test_el_objetivo_se_recalcula_igual_con_pandas(con, hasta):
    csv_ = esperado(hasta).set_index('lote_id')
    ml = pd.read_sql('SELECT lote_id, particion, anio_cata, y FROM ml_dataset ORDER BY lote_id', con).set_index('lote_id')
    total = numerico(csv_['Total.Cup.Points']).loc[ml.index]
    esperada_y = (total >= 80).astype(int)
    assert (total > 0).all()   # el lote de total 0 ya no está
    assert list(ml['y']) == list(esperada_y)
    assert list(ml['anio_cata']) == list(csv_.loc[ml.index, '_anio'])
    # proporción de positivos por partición, también con pandas
    esperada_tasa = esperada_y.groupby(ml['particion']).mean()
    obtenida_tasa = ml.groupby('particion')['y'].mean()
    pd.testing.assert_series_equal(obtenida_tasa, esperada_tasa, check_names=False)


def test_ml_trae_las_mismas_variables_que_fs(con):
    ml = pd.read_sql(f'SELECT lote_id, {", ".join(config.FEATURES)} FROM ml_dataset ORDER BY lote_id', con).set_index('lote_id')
    fs = pd.read_sql('SELECT * FROM fs_lote ORDER BY lote_id', con).set_index('lote_id')
    pd.testing.assert_frame_equal(ml, fs, check_dtype=False)


def test_el_objetivo_y_el_anio_no_son_variables():
    assert config.OBJETIVO not in config.FEATURES and 'anio_cata' not in config.FEATURES and 'particion' not in config.FEATURES


def test_ml_registra_las_particiones_y_el_umbral(con, hasta):
    assert con.execute('SELECT particion, anio_desde, anio_hasta FROM ml_particiones ORDER BY anio_desde').fetchall() == \
        [(p, d, h) for p, (d, h) in config.particiones_de(config.VERSIONES_DATOS[hasta]).items()]
    assert dict(con.execute('SELECT clave, valor FROM ml_parametros').fetchall()) == {'umbral_especialidad': config.UMBRAL_ESPECIALIDAD}


# --------------------------------------------------------------------------------------------------- particiones inválidas
@pytest.mark.parametrize('particiones', [
    {'train': (2009, 2014), 'valid': (2014, 2015), 'test': (2016, 2018)},   # se solapan
    {'train': (2009, 2013), 'valid': (2015, 2015), 'test': (2016, 2018)},   # hueco
    {'train': (2009, 2014), 'valid': (2015, 2015)},                          # falta test
    {'train': (2015, 2014), 'valid': (2015, 2015), 'test': (2016, 2018)},   # intervalo al revés
])
def test_comprobar_particiones_rechaza_las_invalidas(particiones):
    with pytest.raises(ml_dataset.ParticionInvalidaError):
        ml_dataset.comprobar_particiones(particiones)


@pytest.mark.parametrize('version', sorted(config.VERSIONES_DATOS.values()))
def test_comprobar_particiones_acepta_la_de_config(version):
    ml_dataset.comprobar_particiones(config.particiones_de(version))


# --------------------------------------------------------------------------------------------------- partición DESLIZANTE
def test_la_version_2_incluye_2015_en_train_y_2016_en_valid(bases_v1, bases_v2):
    """Versión 1: train <= 2014, valid 2015, test 2016. Versión 2: train <= 2015, valid 2016, test 2017-2018 (la ventana desliza)."""
    def anios(ruta):
        con = db.conectar(ruta)
        try:
            return {p: (a, b) for p, a, b in con.execute('SELECT particion, MIN(anio_cata), MAX(anio_cata) FROM ml_dataset GROUP BY particion')}
        finally:
            con.close()
    a1, a2 = anios(bases_v1[1]), anios(bases_v2[1])
    assert (a1['train'][1], a1['valid'], a1['test']) == (2014, (2015, 2015), (2016, 2016))
    assert (a2['train'][1], a2['valid'], a2['test']) == (2015, (2016, 2016), (2017, 2018))


def test_el_modelo_nuevo_aprende_del_anio_que_antes_era_valid(bases_v1, bases_v2):
    """Los años de cata de v1 y v2 coinciden hasta 2016 (los identificadores no: se reasignan al crear cada base operacional)."""
    def lotes_por_anio(ruta):
        con = db.conectar(ruta)
        try:
            return {(p, a): n for p, a, n in con.execute('SELECT particion, anio_cata, COUNT(*) FROM ml_dataset GROUP BY 1, 2')}
        finally:
            con.close()
    a1, a2 = lotes_por_anio(bases_v1[1]), lotes_por_anio(bases_v2[1])
    assert a1[('valid', 2015)] == a2[('train', 2015)] == 197                  # 2015: valid en la v1, train en la v2
    assert a1[('test', 2016)] == a2[('valid', 2016)] == 127                   # 2016: test en la v1, valid en la v2
    assert {a: n for (p, a), n in a1.items() if p == 'train'}.items() <= {a: n for (p, a), n in a2.items() if p == 'train'}.items()
    assert sum(n for (p, _), n in a2.items() if p == 'train') == 866 + 197    # la v2 entrena con todo lo de la v1 menos test, y valid de la v1


def test_ningun_lote_se_pierde_en_ninguna_version(bases_v1, bases_v2):
    for ruta in (bases_v1[1], bases_v2[1]):
        con = db.conectar(ruta)
        try:
            assert db.escalar(con, 'SELECT COUNT(*) FROM ml_dataset') == db.escalar(con, 'SELECT COUNT(*) FROM master_lotes')
            assert db.escalar(con, 'SELECT COUNT(*) FROM master_lotes WHERE lote_id NOT IN (SELECT lote_id FROM ml_dataset)') == 0
        finally:
            con.close()


def test_un_lote_sin_particion_es_un_error_claro(bases_v2, tmp_path, monkeypatch):
    """Si la partición de la versión deja fuera algún año de cata, ML falla con un mensaje (no pierde lotes en silencio)."""
    copia = tmp_path / 'cafe.db'
    shutil.copyfile(bases_v2[1], copia)
    monkeypatch.setattr(config, 'particiones_de', lambda version: {'train': (2009, 2015), 'valid': (2016, 2016), 'test': (2017, 2017)})
    con = db.conectar(copia)
    with pytest.raises(ml_dataset.ParticionInvalidaError, match=r'2018'):
        ml_dataset.construir_ml(con, verbose=False)
    con.close()

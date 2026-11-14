"""Pruebas de las capas RAW y MASTER y de la calidad (T05): RAW = operacional; raw = master + descartes; una prueba por regla."""
import shutil

import numpy as np
import pandas as pd
import pytest

from auxiliar import esperado, numerico
from cafe_mlops import calidad, config, dataset, db

TEXTO_VACIO = ' \t\r\n'


# --------------------------------------------------------------------------------------------------- RAW
def test_raw_copia_cada_tabla_del_operacional_tal_cual(con, bases):
    con.execute('ATTACH DATABASE ? AS cqi', (str(bases[0]),))
    try:
        for tabla in dataset.TABLAS_OPERACIONALES:
            origen = pd.read_sql(f'SELECT * FROM cqi.{tabla} ORDER BY rowid', con)
            copia = pd.read_sql(f'SELECT * FROM raw_{tabla} ORDER BY rowid', con).drop(columns='_carga_id')
            pd.testing.assert_frame_equal(origen, copia, obj=tabla)
    finally:
        con.execute('DETACH DATABASE cqi')


def test_raw_registra_cada_carga_con_su_huella(con):
    cargas = pd.read_sql('SELECT * FROM raw_carga', con)
    assert list(cargas['tabla']) == dataset.TABLAS_OPERACIONALES and (cargas['origen'] == 'cqi').all()
    for c in cargas.itertuples():
        n = db.escalar(con, f'SELECT COUNT(*) FROM raw_{c.tabla} WHERE _carga_id = ?', (c.carga_id,))
        assert n == c.filas > 0
        assert len(c.sha256) == 64


def test_raw_la_huella_identifica_el_contenido(con, bases):
    con.execute('ATTACH DATABASE ? AS cqi', (str(bases[0]),))
    try:
        sha = db.escalar(con, "SELECT sha256 FROM raw_carga WHERE tabla = 'lotes'")
        assert dataset.huella_tabla(con, 'cqi.lotes') == (db.escalar(con, 'SELECT COUNT(*) FROM raw_lotes'), sha)
    finally:
        con.execute('DETACH DATABASE cqi')


def test_raw_tiene_linaje(con):
    assert db.escalar(con, 'SELECT COUNT(*) FROM raw_lotes WHERE lote_id IS NULL OR id_origen IS NULL OR _carga_id IS NULL') == 0


def test_raw_no_limpia_nada(con, hasta):
    """La suciedad llega a RAW tal cual: fecha con salto de línea, altitud imposible, humedad 0."""
    assert db.escalar(con, "SELECT COUNT(*) FROM raw_catas WHERE fecha_cata_texto LIKE '%' || char(10) || '%'") >= 1
    assert db.escalar(con, 'SELECT MAX(altitud_media_m) FROM raw_lotes') > 4000
    assert db.escalar(con, 'SELECT COUNT(*) FROM raw_analisis_verde WHERE humedad = 0') > 0


def test_raw_no_tiene_claves_ni_restricciones(con):
    """RAW no valida: si el origen trae un problema, lo conserva."""
    for tabla in dataset.TABLAS_OPERACIONALES:
        columnas = con.execute(f'PRAGMA table_info(raw_{tabla})').fetchall()
        assert not any(c[5] for c in columnas), f'raw_{tabla} declara clave primaria'   # c[5] = pk
        assert con.execute(f'PRAGMA foreign_key_list(raw_{tabla})').fetchall() == []


# --------------------------------------------------------------------------------------------------- MASTER: conciliación
def test_master_concilia_con_raw(con, hasta):
    raw = db.escalar(con, 'SELECT COUNT(*) FROM raw_lotes')
    master = db.escalar(con, 'SELECT COUNT(*) FROM master_lotes')
    descartes = db.escalar(con, 'SELECT COUNT(*) FROM master_descartes')
    assert raw == master + descartes
    assert (raw, master, descartes) == ((1190, 1190, 0) if hasta == 2016 else (1339, 1338, 1))


def test_master_y_descartes_son_disjuntos_y_cubren_raw(con):
    ids_raw = {i for (i,) in con.execute('SELECT lote_id FROM raw_lotes')}
    ids_master = {i for (i,) in con.execute('SELECT lote_id FROM master_lotes')}
    ids_desc = {i for (i,) in con.execute('SELECT lote_id FROM master_descartes')}
    assert not ids_master & ids_desc
    assert ids_master | ids_desc == ids_raw


def test_master_no_tiene_reglas_de_calidad_en_error(con):
    estados = dict(con.execute('SELECT regla, estado FROM master_calidad').fetchall())
    assert len(estados) == 17
    assert 'ERROR' not in estados.values(), estados


def test_master_no_lleva_datos_de_personas_ni_notas(con):
    columnas = {c[1] for c in con.execute('PRAGMA table_info(master_lotes)')}
    assert not columnas & {'propietario', 'propietario_2', 'productor', 'productor_id', 'finca', 'cert_contacto', 'cert_direccion',
                           'molino', 'compania'}
    assert not any(n.lower().replace('.', '_') in columnas for n in config.TODAS_LAS_NOTAS)


def test_master_lotes_coincide_con_la_lectura_independiente_del_csv(con, hasta):
    """Cada lote de MASTER = la fila del CSV con las reglas aplicadas (calculadas aquí con pandas)."""
    csv_ = esperado(hasta).set_index('lote_id')
    m = pd.read_sql('SELECT * FROM master_lotes ORDER BY lote_id', con).set_index('lote_id')
    csv_ = csv_.loc[m.index]
    assert list(m['especie']) == list(csv_['_especie'])
    for col_m, col_csv in [('pais', 'Country.of.Origin'), ('variedad', 'Variety'), ('metodo_proceso', 'Processing.Method'), ('color', 'Color')]:
        esperada = csv_[col_csv].str.strip(TEXTO_VACIO)
        assert list(m[col_m].fillna('¤')) == list(esperada.fillna('¤')), col_m
    alt = numerico(csv_['altitude_mean_meters'])
    alt_ok = alt.where((alt >= 100) & (alt <= 4000))
    np.testing.assert_allclose(m['altitud_media_m'].astype(float), alt_ok.astype(float), equal_nan=True)
    np.testing.assert_allclose(m['altitud_media_origen_m'].astype(float), alt.astype(float), equal_nan=True)
    hum = numerico(csv_['Moisture'])
    np.testing.assert_allclose(m['humedad'].astype(float), hum.where(hum != 0).astype(float), equal_nan=True)
    for col_m, col_csv in [('defectos_cat1', 'Category.One.Defects'), ('defectos_cat2', 'Category.Two.Defects'), ('quakers', 'Quakers'),
                           ('total_puntos', 'Total.Cup.Points'), ('numero_sacos', 'Number.of.Bags')]:
        np.testing.assert_allclose(m[col_m].astype(float), numerico(csv_[col_csv]).astype(float), equal_nan=True, err_msg=col_m)
    assert list(m['fecha_cata']) == list(csv_['_fecha'])
    assert list(m['anio_cata']) == list(csv_['_anio'])


# --------------------------------------------------------------------------------------------------- una prueba por regla de depuración
def test_regla_fechas_con_espacios_o_saltos_de_linea(con, hasta):
    """Grading.Date trae saltos de línea al final en 2 lotes (uno de 2013 y uno de 2017): MASTER los lee igual que los demás."""
    csv_ = esperado(hasta)
    sucias = csv_[csv_['Grading.Date'] != csv_['Grading.Date'].str.strip(TEXTO_VACIO)]
    assert len(sucias) == (1 if hasta == 2016 else 2)
    assert db.escalar(con, "SELECT COUNT(*) FROM raw_catas WHERE fecha_cata_texto <> TRIM(fecha_cata_texto, char(32, 9, 10, 13))") == len(sucias)
    for fila in sucias.itertuples():
        fecha = db.escalar(con, 'SELECT fecha_cata FROM master_lotes WHERE lote_id = ?', (fila.lote_id,))
        assert fecha == csv_.loc[csv_['lote_id'] == fila.lote_id, '_fecha'].iloc[0]
    assert db.escalar(con, "SELECT COUNT(*) FROM master_lotes WHERE fecha_cata NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'") == 0
    assert db.escalar(con, "SELECT valor FROM master_calidad WHERE regla = 'R06_fechas_con_espacios_o_saltos'") == len(sucias)
    assert db.escalar(con, "SELECT estado FROM master_calidad WHERE regla = 'R06_fechas_con_espacios_o_saltos'") == 'ALERTA'


def test_regla_altitud_fuera_de_100_a_4000_pasa_a_nula(con, hasta):
    csv_ = esperado(hasta)
    alt = numerico(csv_['altitude_mean_meters'])
    fuera = csv_[(alt < 100) | (alt > 4000)]
    assert len(fuera) == (22 if hasta == 2016 else 25)   # contado con pandas el 14/11/2026 (arábica + robusta)
    assert len(fuera) == (db.escalar(con, "SELECT valor FROM master_calidad WHERE regla = 'R07_altitud_fuera_de_rango'"))
    assert db.escalar(con, "SELECT estado FROM master_calidad WHERE regla = 'R07_altitud_fuera_de_rango'") == 'ALERTA'
    for lote in fuera['lote_id']:
        altitud, origen = con.execute('SELECT altitud_media_m, altitud_media_origen_m FROM master_lotes WHERE lote_id = ?', (int(lote),)).fetchone()
        assert altitud is None and (origen < 100 or origen > 4000)
    assert db.escalar(con, 'SELECT COUNT(*) FROM master_lotes WHERE altitud_media_m < 100 OR altitud_media_m > 4000') == 0
    # el valor imposible se conserva en altitud_media_origen_m (en la versión 2 llega el de 190 164 m)
    assert db.escalar(con, 'SELECT MAX(altitud_media_origen_m) FROM master_lotes') == alt.max()
    assert alt.max() == (110000 if hasta == 2016 else 190164)


def test_regla_total_cero_se_descarta_con_su_motivo(con, hasta):
    csv_ = esperado(hasta)
    ceros = csv_[numerico(csv_['Total.Cup.Points']) == 0]
    assert len(ceros) == (0 if hasta == 2016 else 1)
    descartes = con.execute('SELECT lote_id, motivo FROM master_descartes ORDER BY lote_id').fetchall()
    assert descartes == [(int(l), 'cata_incompleta_total_cero') for l in ceros['lote_id']]
    assert db.escalar(con, "SELECT COUNT(*) FROM master_lotes WHERE total_puntos <= 0") == 0
    assert db.escalar(con, "SELECT valor FROM master_calidad WHERE regla = 'R09_catas_con_total_cero'") == len(ceros)
    assert db.escalar(con, "SELECT estado FROM master_calidad WHERE regla = 'R09_catas_con_total_cero'") == ('ALERTA' if len(ceros) else 'OK')


def test_regla_humedad_cero_es_no_medido_y_pasa_a_nula(con, hasta):
    csv_ = esperado(hasta)
    hum = numerico(csv_['Moisture'])
    ceros = csv_[hum == 0]
    assert len(ceros) > 0
    assert db.escalar(con, "SELECT valor FROM master_calidad WHERE regla = 'R10_humedad_cero'") == len(ceros)
    assert db.escalar(con, "SELECT estado FROM master_calidad WHERE regla = 'R10_humedad_cero'") == 'ALERTA'
    assert db.escalar(con, 'SELECT COUNT(*) FROM master_lotes WHERE humedad = 0') == 0
    nulas = db.escalar(con, 'SELECT COUNT(*) FROM master_lotes WHERE humedad IS NULL')
    assert nulas == len(ceros.loc[ceros['lote_id'].isin([i for (i,) in con.execute('SELECT lote_id FROM master_lotes')])])
    for lote in ceros['lote_id'].head(20):
        fila = con.execute('SELECT humedad, humedad_origen FROM master_lotes WHERE lote_id = ?', (int(lote),)).fetchone()
        assert fila == (None, 0.0)


def test_total_en_2018_hay_un_descarte_y_en_2016_ninguno(bases_v1, bases_v2):
    for ruta, esperado_n in ((bases_v1[1], 0), (bases_v2[1], 1)):
        c = db.conectar(ruta)
        assert db.escalar(c, 'SELECT COUNT(*) FROM master_descartes') == esperado_n
        c.close()


def test_regla_textos_recortados_y_vacios_son_nulos(con):
    for col in ('pais', 'variedad', 'metodo_proceso', 'color'):
        assert db.escalar(con, f"SELECT COUNT(*) FROM master_lotes WHERE {col} <> TRIM({col}, char(32, 9, 10, 13)) OR {col} = ''") == 0, col


# --------------------------------------------------------------------------------------------------- reglas de calidad
@pytest.mark.parametrize('regla, tipo_esperado', [
    ('R01_conciliacion', 'OK'), ('R02_lotes_sin_las_diez_notas', 'OK'), ('R03_lotes_con_varias_catas', 'OK'),
    ('R05_fechas_de_cata_en_rango', 'OK'), ('R11_humedad_fuera_de_0_a_1', 'OK'), ('R12_defectos_negativos', 'OK'),
])
def test_reglas_duras_en_ok(con, regla, tipo_esperado):
    estado, valor = con.execute('SELECT estado, valor FROM master_calidad WHERE regla = ?', (regla,)).fetchone()
    assert (estado, valor) == (tipo_esperado, 0)


def test_la_diferencia_entre_el_total_y_las_notas_es_pequena(con):
    """La fuga, medida: el total ES la suma de las diez notas (diferencia máxima de la exploración: 0,5)."""
    assert 0 <= db.escalar(con, "SELECT valor FROM master_calidad WHERE regla = 'R04_diferencia_total_menos_notas'") <= 0.5


def test_reglas_informativas_dan_los_conteos_esperados(con, hasta):
    reglas = dict(con.execute('SELECT regla, valor FROM master_calidad').fetchall())
    assert reglas['R16_lotes_en_master'] == (1190 if hasta == 2016 else 1338)
    assert 0 < reglas['R17_pct_especialidad'] < 100
    csv_ = esperado(hasta)
    total = numerico(csv_['Total.Cup.Points'])
    validos = total[total > 0]
    assert reglas['R17_pct_especialidad'] == pytest.approx(round(100 * (validos >= 80).mean(), 2), abs=0.005)
    assert reglas['R13_pct_sin_variedad'] > 0


def test_ejecutar_dos_veces_las_reglas_da_la_misma_tabla(con):
    antes = con.execute('SELECT regla, descripcion, valor, umbral, estado FROM master_calidad ORDER BY regla').fetchall()
    resultados = calidad.evaluar(con, lanzar=False)
    despues = con.execute('SELECT regla, descripcion, valor, umbral, estado FROM master_calidad ORDER BY regla').fetchall()
    assert antes == despues and len(resultados) == 17


def test_una_regla_dura_que_falla_detiene_el_pipeline(bases_v1, tmp_path):
    copia = tmp_path / 'cafe.db'
    shutil.copyfile(bases_v1[1], copia)
    con = db.conectar(copia)
    con.execute('PRAGMA foreign_keys = OFF')   # fs_lote apunta a master_lotes: aquí solo se prueba la regla
    con.execute('DELETE FROM master_lotes WHERE lote_id = 1')    # RAW ya no concilia con MASTER
    resultados = calidad.evaluar(con, lanzar=False)
    assert {r['regla']: r['estado'] for r in resultados}['R01_conciliacion'] == 'ERROR'
    with pytest.raises(calidad.CalidadError, match='R01_conciliacion'):
        calidad.evaluar(con, lanzar=True)
    con.close()


def test_los_limites_de_depuracion_salen_de_config_y_no_estan_escritos_en_el_sql(con):
    """Los límites viven en config.py; el SQL los lee de master_parametros (así no pueden separarse)."""
    parametros = dict(con.execute('SELECT clave, valor FROM master_parametros').fetchall())
    assert parametros == {'altitud_min_m': config.ALTITUD_MIN_M, 'altitud_max_m': config.ALTITUD_MAX_M,
                          'humedad_no_medida': config.HUMEDAD_NO_MEDIDA}
    sql = (config.SQL / 'master' / '02_poblar_master.sql').read_text(encoding='utf-8')
    sin_comentarios = '\n'.join(l for l in sql.splitlines() if not l.strip().startswith('--'))
    assert '4000' not in sin_comentarios and '100' not in sin_comentarios
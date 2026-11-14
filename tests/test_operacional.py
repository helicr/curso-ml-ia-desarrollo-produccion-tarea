"""Pruebas de la base operacional (T04): reconstruye cada fila de los CSV y --hasta da los conteos esperados."""
import hashlib
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from auxiliar import ARCHIVOS, CQI, NOTAS, NUMERICAS_CSV, RAIZ, esperado, leer, numerico
from cafe_mlops import config, dataset, db

# Conteos verificados el 14/11/2026 con la lectura independiente de los CSV (año de Grading.Date).
CONTEOS = {2016: {'Arabica': 1164, 'Robusta': 26, 'total': 1190}, 2018: {'Arabica': 1311, 'Robusta': 28, 'total': 1339}}

CONSULTA_LOTES = '''
SELECT l.lote_id, l.especie AS "Species", l.id_origen AS "Unnamed: 0", l.propietario AS "Owner", p.nombre AS "Country.of.Origin",
       l.finca AS "Farm.Name", l.numero_lote AS "Lot.Number", l.molino AS "Mill", l.numero_ico AS "ICO.Number",
       l.compania AS "Company", l.altitud_texto AS "Altitude", l.region AS "Region", pr.nombre AS "Producer",
       l.numero_sacos AS "Number.of.Bags", l.peso_saco AS "Bag.Weight", e1.nombre AS "In.Country.Partner",
       l.anio_cosecha AS "Harvest.Year", c.fecha_cata_texto AS "Grading.Date", l.propietario_2 AS "Owner.1",
       l.variedad AS "Variety", l.metodo_proceso AS "Processing.Method", c.total_puntos AS "Total.Cup.Points",
       a.humedad AS "Moisture", a.defectos_cat1 AS "Category.One.Defects", a.quakers AS "Quakers", a.color AS "Color",
       a.defectos_cat2 AS "Category.Two.Defects", c.caducidad_texto AS "Expiration", e2.nombre AS "Certification.Body",
       c.cert_direccion AS "Certification.Address", c.cert_contacto AS "Certification.Contact",
       l.unidad_altitud AS "unit_of_measurement", l.altitud_baja_m AS "altitude_low_meters",
       l.altitud_alta_m AS "altitude_high_meters", l.altitud_media_m AS "altitude_mean_meters"
FROM lotes l
LEFT JOIN paises p ON p.pais_id = l.pais_id
LEFT JOIN productores pr ON pr.productor_id = l.productor_id
JOIN analisis_verde a ON a.lote_id = l.lote_id
JOIN catas c ON c.lote_id = l.lote_id
LEFT JOIN entidades e1 ON e1.entidad_id = c.entidad_id
LEFT JOIN entidades e2 ON e2.entidad_id = c.certificadora_id
ORDER BY l.lote_id'''


def reconstruir(con_operacional, especie):
    """Une las tablas de la base y devuelve un DataFrame con las 44 columnas del CSV de la especie (los lotes de esa especie)."""
    lotes = pd.read_sql(CONSULTA_LOTES, con_operacional)
    lotes = lotes[lotes['Species'] == especie].reset_index(drop=True)
    notas = pd.read_sql('SELECT cata_id AS lote_id, atributo, valor FROM notas_cata', con_operacional)
    ancho = notas.pivot(index='lote_id', columns='atributo', values='valor').reset_index()
    ancho = ancho[['lote_id'] + [n for n in NOTAS[especie]]]
    return lotes.merge(ancho, on='lote_id', how='left')


def _igual(esperada, obtenida, columna):
    if columna in NUMERICAS_CSV or columna in NOTAS['Arabica'] + NOTAS['Robusta']:
        a, b = numerico(esperada).astype(float), obtenida.astype(float)
        np.testing.assert_allclose(a.to_numpy(), b.to_numpy(), rtol=0, atol=1e-9, equal_nan=True, err_msg=columna)
    else:
        a = esperada.astype(object).where(esperada.notna(), None)
        b = obtenida.astype(object).where(obtenida.notna(), None)
        assert list(a) == list(b), columna


# --------------------------------------------------------------------------------------------------- reconstrucción
@pytest.mark.parametrize('especie', ['Arabica', 'Robusta'])
def test_el_operacional_reconstruye_cada_fila_del_csv(con_operacional, hasta, especie):
    """Normalizar no pierde información: uniendo las tablas se recuperan las 44 columnas de cada fila, en el mismo orden."""
    csv_ = esperado(hasta)
    csv_ = csv_[csv_['_especie'] == especie].reset_index(drop=True)
    cabecera_csv = [c for c in leer(especie).columns if not c.startswith('_')]
    assert len(cabecera_csv) == 44
    rec = reconstruir(con_operacional, especie)
    assert len(rec) == len(csv_) == CONTEOS[hasta][especie]
    assert list(rec['lote_id']) == list(csv_['lote_id'])
    for columna in cabecera_csv:
        _igual(csv_[columna], rec[columna], columna)


def test_el_operacional_conserva_los_nombres_de_personas_tal_cual(con_operacional, hasta):
    """Decisión 4: los CSV se usan tal cual, incluidos los nombres. Están en la base operacional (y NO en MASTER; ver test de MASTER)."""
    csv_ = esperado(hasta)
    n = db.escalar(con_operacional, 'SELECT COUNT(*) FROM lotes WHERE propietario IS NOT NULL')
    assert n == csv_['Owner'].notna().sum() > 0


# --------------------------------------------------------------------------------------------------- conteos y --hasta
def test_conteos_por_version(con_operacional, hasta):
    esp = CONTEOS[hasta]
    assert db.escalar(con_operacional, 'SELECT COUNT(*) FROM lotes') == esp['total'] == len(esperado(hasta))
    por_especie = dict(con_operacional.execute('SELECT especie, COUNT(*) FROM lotes GROUP BY especie').fetchall())
    assert por_especie == {'Arabica': esp['Arabica'], 'Robusta': esp['Robusta']}
    for tabla in ('analisis_verde', 'catas'):
        assert db.escalar(con_operacional, f'SELECT COUNT(*) FROM {tabla}') == esp['total']
    assert db.escalar(con_operacional, 'SELECT COUNT(*) FROM notas_cata') == 10 * esp['total']


def test_los_lotes_nuevos_de_la_version_2_son_149(bases_v1, bases_v2):
    n1 = db.escalar(db.conectar(bases_v1[0]), 'SELECT COUNT(*) FROM lotes')
    n2 = db.escalar(db.conectar(bases_v2[0]), 'SELECT COUNT(*) FROM lotes')
    assert (n1, n2, n2 - n1) == (1190, 1339, 149)


def test_el_año_maximo_de_cata_respeta_hasta(con_operacional, hasta):
    anios = [dataset.anio_de_cata(t) for (t,) in con_operacional.execute('SELECT fecha_cata_texto FROM catas')]
    assert max(anios) <= hasta
    if hasta == 2018:
        assert max(anios) == 2018 and 2017 in anios


def test_los_ids_de_lote_son_propios_aunque_los_del_origen_se_solapen(con_operacional):
    assert db.escalar(con_operacional, 'SELECT COUNT(DISTINCT lote_id) FROM lotes') == db.escalar(con_operacional, 'SELECT COUNT(*) FROM lotes')
    solapados = db.escalar(con_operacional, 'SELECT COUNT(*) FROM (SELECT id_origen FROM lotes GROUP BY id_origen HAVING COUNT(DISTINCT especie) > 1)')
    assert solapados > 0   # el origen reutiliza ids entre arábica y robusta: por eso lote_id es propio


def test_origen_simulacion_deja_constancia(con_operacional, hasta):
    filas = con_operacional.execute('SELECT archivo, sha256, filas_archivo, filas_cargadas, hasta, version_datos FROM origen_simulacion ORDER BY archivo').fetchall()
    assert [f[0] for f in filas] == sorted(p.name for p in ARCHIVOS.values())
    assert {f[4] for f in filas} == {hasta} and {f[5] for f in filas} == {config.VERSIONES_DATOS[hasta]}
    assert sum(f[3] for f in filas) == CONTEOS[hasta]['total']
    assert [f[2] for f in filas] == [1311, 28]
    sumas = dict(reversed(linea.split(maxsplit=1)) for linea in (CQI / 'SHA256SUMS').read_text(encoding='utf-8').splitlines() if linea.strip())
    for archivo, sha, *_ in filas:
        assert sha == sumas[archivo] == hashlib.sha256((CQI / archivo).read_bytes()).hexdigest()


# --------------------------------------------------------------------------------------------------- integridad y suciedad
def test_el_operacional_respeta_sus_claves_foraneas(con_operacional):
    assert con_operacional.execute('PRAGMA foreign_key_check').fetchall() == []


def test_cada_cata_tiene_diez_notas_y_cada_lote_una_cata(con_operacional):
    assert con_operacional.execute('SELECT cata_id FROM notas_cata GROUP BY cata_id HAVING COUNT(*) <> 10').fetchall() == []
    assert con_operacional.execute('SELECT lote_id FROM catas GROUP BY lote_id HAVING COUNT(*) <> 1').fetchall() == []


def test_el_operacional_conserva_la_suciedad_del_origen(con_operacional, hasta):
    """No limpia nada: la suciedad llega intacta a RAW y la trata MASTER."""
    assert db.escalar(con_operacional, "SELECT COUNT(*) FROM catas WHERE fecha_cata_texto LIKE '%' || char(10) || '%'") >= 1   # fecha con salto de línea
    assert db.escalar(con_operacional, 'SELECT COUNT(*) FROM lotes WHERE altitud_media_m > 4000') > 0
    assert db.escalar(con_operacional, 'SELECT COUNT(*) FROM lotes WHERE altitud_media_m < 100') > 0
    assert db.escalar(con_operacional, 'SELECT COUNT(*) FROM analisis_verde WHERE humedad = 0') > 0
    assert db.escalar(con_operacional, 'SELECT COUNT(*) FROM catas WHERE total_puntos = 0') == (1 if hasta == 2018 else 0)


def test_celdas_vacias_y_na_son_nulos_no_texto(con_operacional):
    assert db.escalar(con_operacional, "SELECT COUNT(*) FROM lotes WHERE altitud_media_m = 'NA' OR variedad = '' OR metodo_proceso = 'NA'") == 0
    assert db.escalar(con_operacional, 'SELECT COUNT(*) FROM lotes WHERE altitud_media_m IS NULL') > 0
    assert db.escalar(con_operacional, "SELECT COUNT(*) FROM lotes WHERE typeof(altitud_media_m) NOT IN ('real', 'null', 'integer')") == 0


def test_notas_y_atributos_son_los_del_csv(con_operacional):
    atributos = {a for (a,) in con_operacional.execute('SELECT DISTINCT atributo FROM notas_cata')}
    assert atributos == set(NOTAS['Arabica']) | set(NOTAS['Robusta'])
    por_especie = con_operacional.execute(
        'SELECT l.especie, n.atributo FROM notas_cata n JOIN lotes l ON l.lote_id = n.cata_id GROUP BY l.especie, n.atributo').fetchall()
    for especie in ('Arabica', 'Robusta'):
        assert {a for e, a in por_especie if e == especie} == set(NOTAS[especie])


# --------------------------------------------------------------------------------------------------- lectura y utilidades
def test_leer_lotes_devuelve_las_cifras_esperadas():
    archivos, lotes, notas = dataset.leer_lotes(2016)
    assert [a['filas_cargadas'] for a in archivos] == [1164, 26] and [a['filas_archivo'] for a in archivos] == [1311, 28]
    assert len(lotes) == 1190 and len(notas) == 11900
    assert len(dataset.leer_lotes(None)[1]) == 1339
    assert len(lotes[0]) == len(dataset.CAMPOS_ORIGEN)


@pytest.mark.parametrize('texto, iso', [
    ('April 4th, 2015', '2015-04-04'),
    ('November 15th, 2017\n', '2017-11-15'),
    ('  December 26th, 2013\n', '2013-12-26'),
    ('May 31st, 2010', '2010-05-31'),
    ('June 2nd, 2012', '2012-06-02'),
    ('March 23rd, 2016', '2016-03-23'),
    ('Smarch 3rd, 2015', None),
    ('February 30th, 2015', None),
    ('2015-04-04', None),
    (None, None),
])
def test_fecha_iso(texto, iso):
    assert dataset.fecha_iso(texto) == iso


def test_fecha_iso_lee_todas_las_fechas_de_los_csv():
    for especie in ('Arabica', 'Robusta'):
        df = leer(especie)
        obtenidas = [dataset.fecha_iso(t) for t in df['Grading.Date']]
        assert obtenidas == list(df['_fecha'])
        assert [dataset.anio_de_cata(t) for t in df['Grading.Date']] == list(df['_anio'])


# --------------------------------------------------------------------------------------------------- terminal
def _ejecutar_modulo(args, tmp_path):
    entorno = dict(os.environ, TALLER_DB_OPERACIONAL=str(tmp_path / 'cqi.db'), TALLER_DB=str(tmp_path / 'cafe.db'),
                   PYTHONIOENCODING='utf-8')
    return subprocess.run([sys.executable, '-m', 'cafe_mlops.operacional', *args], cwd=RAIZ, env=entorno, capture_output=True,
                          text=True, encoding='utf-8')


def test_terminal_hasta_2016_y_2018(tmp_path):
    r = _ejecutar_modulo(['--hasta', '2016'], tmp_path)
    assert r.returncode == 0, r.stderr
    assert '1,190' in r.stdout and 'versión 1' in r.stdout
    r = _ejecutar_modulo(['--hasta', '2018'], tmp_path)
    assert r.returncode == 0, r.stderr
    assert '1,339' in r.stdout and 'versión 2' in r.stdout
    con = db.conectar(tmp_path / 'cqi.db')
    assert db.escalar(con, 'SELECT COUNT(*) FROM lotes') == 1339   # rehecha desde cero, no añadida a la anterior
    con.close()


def test_terminal_por_defecto_es_la_version_1(tmp_path):
    r = _ejecutar_modulo([], tmp_path)
    assert r.returncode == 0, r.stderr
    assert 'catas hasta 2016' in r.stdout


def test_terminal_rechaza_un_hasta_desconocido(tmp_path):
    r = _ejecutar_modulo(['--hasta', '2017'], tmp_path)
    assert r.returncode == 2 and '2016' in r.stderr and '2018' in r.stderr
    assert not (tmp_path / 'cqi.db').exists()

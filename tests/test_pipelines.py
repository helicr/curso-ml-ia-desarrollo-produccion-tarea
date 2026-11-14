"""Pruebas de los pipelines RAW, MASTER y FS+ML: idempotencia, independencia y rehacerse al llegar datos nuevos."""
import os
import subprocess
import sys

import pytest

from auxiliar import RAIZ
from cafe_mlops import config, control, db, operacional as op, pipeline_ingesta_master, pipeline_ingesta_raw, pipeline_ml

PIPELINES = [
    ('pipeline_ingesta_raw', lambda ruta_db, ruta_op, **kw: pipeline_ingesta_raw.ejecutar(ruta_db, ruta_op, verbose=False, **kw)),
    ('pipeline_ingesta_master', lambda ruta_db, ruta_op, **kw: pipeline_ingesta_master.ejecutar(ruta_db, verbose=False, **kw)),
    ('pipeline_ml', lambda ruta_db, ruta_op, **kw: pipeline_ml.ejecutar(ruta_db, verbose=False, **kw)),
]


def _todos(ruta_db, ruta_op, **kw):
    return {n: f(ruta_db, ruta_op, **kw) for n, f in PIPELINES}


def test_primera_ejecucion_hace_todo_y_la_segunda_no_cambia_nada(tmp_path):
    ruta_op, ruta_db = tmp_path / 'cqi.db', tmp_path / 'cafe.db'
    op.crear_operacional(2016, ruta_op, verbose=False)
    primera = _todos(ruta_db, ruta_op)
    assert {r['estado'] for r in primera.values()} == {'ejecutado'}
    segunda = _todos(ruta_db, ruta_op)
    assert {r['estado'] for r in segunda.values()} == {'sin cambios'}
    for nombre in primera:
        assert primera[nombre]['huella_entrada'] == segunda[nombre]['huella_entrada']
        assert primera[nombre]['resumen'] == segunda[nombre]['resumen']


def test_forzar_rehace_aunque_no_haya_cambios(tmp_path):
    ruta_op, ruta_db = tmp_path / 'cqi.db', tmp_path / 'cafe.db'
    op.crear_operacional(2016, ruta_op, verbose=False)
    _todos(ruta_db, ruta_op)
    assert {r['estado'] for r in _todos(ruta_db, ruta_op, forzar=True).values()} == {'ejecutado'}


def test_la_segunda_ejecucion_no_cambia_el_contenido(tmp_path):
    ruta_op, ruta_db = tmp_path / 'cqi.db', tmp_path / 'cafe.db'
    op.crear_operacional(2016, ruta_op, verbose=False)
    _todos(ruta_db, ruta_op)
    con = db.conectar(ruta_db)
    antes = {t: control.huella_tablas(con, t) for t in ('raw_lotes', 'master_lotes', 'fs_lote', 'ml_dataset')}
    con.close()
    _todos(ruta_db, ruta_op, forzar=True)    # rehacer desde cero deja EXACTAMENTE lo mismo
    con = db.conectar(ruta_db)
    assert antes == {t: control.huella_tablas(con, t) for t in antes}
    con.close()


def test_hasta_2018_rehace_los_tres_pipelines_y_cambian_los_conteos(tmp_path):
    ruta_op, ruta_db = tmp_path / 'cqi.db', tmp_path / 'cafe.db'
    op.crear_operacional(2016, ruta_op, verbose=False)
    v1 = _todos(ruta_db, ruta_op)
    assert v1['pipeline_ingesta_raw']['resumen']['tablas']['lotes'] == 1190
    op.crear_operacional(2018, ruta_op, verbose=False)   # «llegan lotes nuevos»
    v2 = _todos(ruta_db, ruta_op)
    assert {r['estado'] for r in v2.values()} == {'ejecutado'}
    assert v2['pipeline_ingesta_raw']['resumen']['tablas']['lotes'] == 1339
    assert v2['pipeline_ingesta_master']['resumen']['filas']['master_lotes'] == 1338
    assert v2['pipeline_ingesta_master']['resumen']['filas']['master_descartes'] == 1
    assert v2['pipeline_ml']['resumen']['ml_filas_por_particion'] == {'test': 148, 'train': 1063, 'valid': 127}
    assert all(v1[n]['huella_entrada'] != v2[n]['huella_entrada'] for n in v1)
    assert {r['estado'] for r in _todos(ruta_db, ruta_op).values()} == {'sin cambios'}


def test_volver_a_hasta_2016_vuelve_a_dar_la_version_1(tmp_path):
    ruta_op, ruta_db = tmp_path / 'cqi.db', tmp_path / 'cafe.db'
    op.crear_operacional(2018, ruta_op, verbose=False)
    _todos(ruta_db, ruta_op)
    op.crear_operacional(2016, ruta_op, verbose=False)
    r = _todos(ruta_db, ruta_op)
    assert r['pipeline_ml']['resumen']['ml_filas_por_particion'] == {'test': 127, 'train': 866, 'valid': 197}
    con = db.conectar(ruta_db)
    assert db.escalar(con, 'SELECT COUNT(*) FROM master_descartes') == 0
    con.close()


def test_cambiar_la_particion_en_config_rehace_solo_ml(tmp_path, monkeypatch):
    ruta_op, ruta_db = tmp_path / 'cqi.db', tmp_path / 'cafe.db'
    op.crear_operacional(2018, ruta_op, verbose=False)
    _todos(ruta_db, ruta_op)
    monkeypatch.setitem(config.ANIO_VALID_POR_VERSION, 2, 2015)    # la v2 deslizaría menos: train <= 2014, valid 2015, test 2016-2018
    r = _todos(ruta_db, ruta_op)
    assert [r[n]['estado'] for n in ('pipeline_ingesta_raw', 'pipeline_ingesta_master', 'pipeline_ml')] == ['sin cambios', 'sin cambios', 'ejecutado']


def test_cambiar_un_umbral_de_master_rehace_master_y_ml(tmp_path, monkeypatch):
    ruta_op, ruta_db = tmp_path / 'cqi.db', tmp_path / 'cafe.db'
    op.crear_operacional(2016, ruta_op, verbose=False)
    _todos(ruta_db, ruta_op)
    monkeypatch.setattr(config, 'ALTITUD_MAX_M', 5000)
    r = _todos(ruta_db, ruta_op)
    assert r['pipeline_ingesta_raw']['estado'] == 'sin cambios'
    assert r['pipeline_ingesta_master']['estado'] == 'ejecutado' and r['pipeline_ml']['estado'] == 'ejecutado'


# --------------------------------------------------------------------------------------------------- independencia
@pytest.mark.parametrize('modulo, previo', [
    ('pipeline_ingesta_master', 'pipeline_ingesta_raw'),
    ('pipeline_ml', 'pipeline_ingesta_master'),
])
def test_un_pipeline_sin_entrada_dice_cual_ejecutar_y_sale_con_2(tmp_path, modulo, previo):
    entorno = dict(os.environ, TALLER_DB=str(tmp_path / 'vacia.db'), TALLER_DB_OPERACIONAL=str(tmp_path / 'no_existe.db'),
                   PYTHONIOENCODING='utf-8')
    r = subprocess.run([sys.executable, '-m', f'cafe_mlops.{modulo}'], cwd=RAIZ, env=entorno, capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 2
    assert f'python -m cafe_mlops.{previo}' in r.stderr
    assert 'Traceback' not in r.stderr


def test_ingesta_raw_sin_operacional_dice_como_crearla(tmp_path):
    entorno = dict(os.environ, TALLER_DB=str(tmp_path / 'cafe.db'), TALLER_DB_OPERACIONAL=str(tmp_path / 'no_existe.db'),
                   PYTHONIOENCODING='utf-8')
    r = subprocess.run([sys.executable, '-m', 'cafe_mlops.pipeline_ingesta_raw'], cwd=RAIZ, env=entorno, capture_output=True, text=True,
                       encoding='utf-8')
    assert r.returncode == 2 and 'python -m cafe_mlops.operacional' in r.stderr and 'Traceback' not in r.stderr


def test_cada_pipeline_funciona_solo_desde_la_terminal(tmp_path):
    """Los tres, por separado, en orden, como los lanzaría un workflow: cada uno es una orden independiente."""
    entorno = dict(os.environ, TALLER_DB=str(tmp_path / 'cafe.db'), TALLER_DB_OPERACIONAL=str(tmp_path / 'cqi.db'), PYTHONIOENCODING='utf-8')
    for modulo in ('operacional', 'pipeline_ingesta_raw', 'pipeline_ingesta_master', 'pipeline_ml', 'pipeline_ml'):
        r = subprocess.run([sys.executable, '-m', f'cafe_mlops.{modulo}'], cwd=RAIZ, env=entorno, capture_output=True, text=True, encoding='utf-8')
        assert r.returncode == 0, r.stderr
    assert 'sin cambios' in r.stdout   # la segunda vez de pipeline_ml

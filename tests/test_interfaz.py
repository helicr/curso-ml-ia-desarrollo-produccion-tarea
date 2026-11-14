"""Pruebas de la interfaz (T11): API real (TestClient y uvicorn) y API simulada, lotes existentes y nuevos, 422 y 503 sin trazas,
base en solo lectura, pagina sin recursos externos ni nombres de personas.

El modelo se entrena UNA vez (orquestador hasta 2016) en carpetas temporales; nada toca data/ ni models/.
"""
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from auxiliar import RAIZ
from cafe_mlops import config, db, pipeline
from cafe_mlops.api import esquemas
from cafe_mlops.api.app import crear_app as crear_api
from cafe_mlops.interfaz import pagina
from cafe_mlops.interfaz.app import crear_app
from cafe_mlops.interfaz.consulta import NoDisponible, segmento_de

DATOS = RAIZ / 'tests' / 'datos'


def _json(nombre):
    return json.loads((DATOS / nombre).read_text(encoding='utf-8'))


EJEMPLO = _json('lote_ejemplo.json')


@pytest.fixture(scope='module')
def entrenado(tmp_path_factory):
    raiz = tmp_path_factory.mktemp('interfaz')
    modelos, reportes, ruta_db = raiz / 'models', raiz / 'reports', raiz / 'cafe.db'
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, 'MODELOS', modelos)
        mp.setattr(config, 'REPORTES', reportes)
        pipeline.ejecutar(hasta=2016, ruta_db=ruta_db, ruta_operacional=raiz / 'cqi.db', verbose=False)
    return SimpleNamespace(modelos=modelos, ruta_db=ruta_db)


@pytest.fixture(scope='module')
def api_real(entrenado):
    """La API de verdad (modelo cargado), en memoria."""
    with TestClient(crear_api(carpeta_modelo=entrenado.modelos)) as c:
        yield c


def _http_de(cliente):
    def llamar(metodo, ruta, cuerpo=None):
        r = cliente.request(metodo, ruta, json=cuerpo)
        return r.status_code, r.json()
    return llamar


@pytest.fixture(scope='module')
def cliente(entrenado, api_real):
    """La interfaz sobre la API real y la base de lotes."""
    return TestClient(crear_app(ruta_db=entrenado.ruta_db, url_api='http://api-simulada:8080', http=_http_de(api_real)))


def _interfaz(entrenado, http):
    return TestClient(crear_app(ruta_db=entrenado.ruta_db, url_api='http://api-simulada:8080', http=http), raise_server_exceptions=False)


def _ids(entrenado, n=3):
    con = db.conectar(entrenado.ruta_db)
    try:
        return [f[0] for f in con.execute('SELECT lote_id FROM fs_lote ORDER BY lote_id LIMIT ?', (n,))]
    finally:
        con.close()


# --------------------------------------------------------------------------------------------------- rutas y estado
def test_salud_listo_y_pagina(cliente):
    assert cliente.get('/salud').json() == {'estado': 'ok'}
    r = cliente.get('/listo')
    assert r.status_code == 200 and r.json()['estado'] == 'listo'
    p = cliente.get('/')
    assert p.status_code == 200 and 'text/html' in p.headers['content-type'] and '<form' in p.text


def test_estado_lleva_repositorio_modelo_listas_y_tramos(cliente, entrenado, monkeypatch):
    monkeypatch.setenv('TALLER_REPOSITORIO', 'alumno/taller-ml-ia-dev-production')
    e = cliente.get('/estado').json()
    assert e['repositorio'] == 'alumno/taller-ml-ia-dev-production'
    assert e['api']['estado'] == 'lista' and e['modelo']['huella_datos'] and e['modelo']['modelo']
    assert e['datos']['estado'] == 'ok' and e['datos']['lotes'] > 100
    assert e['segmentos'] == config.SEGMENTOS and e['maximo_lotes'] == 1000
    o = e['opciones']
    assert o['especie'] == ['Arabica', 'Robusta'] and 'Colombia' in o['pais'] and len(o['variedad']) > 5
    assert o['pais'] == sorted(o['pais']) and None not in o['pais']
    assert 'None' in o['color'] and len(o['metodo_proceso']) == 5
    assert e['limites']['humedad']['maximo'] == 1 and e['limites']['altitud_media_m']['minimo'] == config.ALTITUD_MIN_M
    assert all(isinstance(i, int) for i in e['ejemplos']) and e['ejemplos']
    assert set(e['ejemplo_lote']) == set(config.FEATURES)


def test_repositorio_sin_identificar(cliente, monkeypatch):
    for v in ('TALLER_REPOSITORIO', 'GITHUB_REPOSITORY'):
        monkeypatch.delenv(v, raising=False)
    assert cliente.get('/estado').json()['repositorio'] is None


# --------------------------------------------------------------------------------------------------- lotes existentes
def test_recomendar_ids_coincide_con_la_api_y_los_tramos(cliente, api_real, entrenado):
    ids = _ids(entrenado, 5)
    r = cliente.post('/recomendar', json={'lote_ids': ids})
    assert r.status_code == 200
    cuerpo = r.json()
    assert [x['lote_id'] for x in cuerpo['resultados']] == ids and cuerpo['origen'] == 'ids'
    con = db.conectar(entrenado.ruta_db)
    try:
        for x in cuerpo['resultados']:
            fila = dict(zip(config.FEATURES, con.execute(f'SELECT {", ".join(config.FEATURES)} FROM fs_lote WHERE lote_id = ?', (x['lote_id'],)).fetchone()))
            assert x['variables'] == fila                                  # las variables de FS, tal cual
            directo = api_real.post('/predecir', json=fila).json()
            assert x['probabilidad'] == round(directo['probabilidad_especialidad'], 4)
            tramo = segmento_de(directo['probabilidad_especialidad'])
            assert x['segmento'] == tramo['segmento'] and x['recomendacion'] == tramo['recomendacion']
            assert x['avisos'] == directo['avisos'] and x['revisar'] == bool(directo['avisos'])
    finally:
        con.close()
    assert sum(cuerpo['por_segmento'].values()) == 5 and cuerpo['modelo']['huella_datos']


def test_recomendar_get_repetidos_y_no_encontrados(cliente, entrenado):
    i = _ids(entrenado, 1)[0]
    uno = cliente.get(f'/recomendar/{i}').json()
    assert uno['encontrados'] == 1 and uno['resultados'][0]['lote_id'] == i
    r = cliente.post('/recomendar', json={'lote_ids': [i, i, 99999999]}).json()
    assert r['pedidos'] == 2 and r['encontrados'] == 1
    assert r['no_encontrados'][0]['lote_id'] == 99999999 and 'FS' in r['no_encontrados'][0]['motivo']
    solo_falta = cliente.post('/recomendar', json={'lote_ids': [99999999]}).json()
    assert solo_falta['encontrados'] == 0 and solo_falta['modelo'] is None


@pytest.mark.parametrize('cuerpo', [{'lote_ids': []}, {'lote_ids': ['abc']}, {'lote_ids': [0]}, {'lote_ids': list(range(1, 1002))}, {}, {'otro': 1}])
def test_ids_no_validos_dan_422_en_espanol(cliente, cuerpo):
    r = cliente.post('/recomendar', json=cuerpo)
    assert r.status_code == 422
    texto = r.text
    assert 'detalle' in r.json() and 'detail' not in r.json() and 'Traceback' not in texto and 'pydantic' not in texto
    if cuerpo.get('lote_ids') == [0]:
        assert 'no es un id de lote válido' in r.json()['detalle']


def test_id_que_no_es_numero_en_la_ruta(cliente):
    r = cliente.get('/recomendar/abc')
    assert r.status_code == 422 and 'Traceback' not in r.text and 'detalle' in r.json()


# --------------------------------------------------------------------------------------------------- lote nuevo
def test_lote_nuevo_ejemplo(cliente, api_real):
    r = cliente.post('/recomendar/nuevo', json=EJEMPLO)
    assert r.status_code == 200
    x = r.json()['resultados'][0]
    directo = api_real.post('/predecir', json=EJEMPLO).json()
    assert x['lote_id'] is None and x['probabilidad'] == round(directo['probabilidad_especialidad'], 4)
    assert x['segmento'] in {s['segmento'] for s in config.SEGMENTOS} and x['variables'] == EJEMPLO


def test_lote_nuevo_categoria_nueva_avisa_y_marca_revisar(cliente):
    r = cliente.post('/recomendar/nuevo', json=_json('lote_categoria_nueva.json'))
    assert r.status_code == 200
    x = r.json()['resultados'][0]
    assert x['revisar'] and [a['tipo'] for a in x['avisos']] == ['categoria_nueva'] and x['avisos'][0]['campo'] == 'pais'
    assert 'Atlantida' in x['avisos'][0]['mensaje']


def test_lote_nuevo_humedad_cero_y_sin_dato_avisan(cliente):
    r = cliente.post('/recomendar/nuevo', json=dict(EJEMPLO, humedad=0, altitud_media_m=None, variedad=''))
    assert r.status_code == 200
    tipos = {(a['tipo'], a['campo']) for a in r.json()['resultados'][0]['avisos']}
    assert ('humedad_cero', 'humedad') in tipos and ('valor_no_informado', 'altitud_media_m') in tipos and ('valor_no_informado', 'variedad') in tipos


def test_lote_nuevo_fuera_del_rango_de_train_avisa(cliente):
    r = cliente.post('/recomendar/nuevo', json=dict(EJEMPLO, defectos_cat1=900))
    assert r.status_code == 200
    assert any(a['tipo'] == 'fuera_de_rango_entrenamiento' for a in r.json()['resultados'][0]['avisos'])


def test_lote_nuevo_imposible_da_422_con_campo_y_motivo(cliente):
    r = cliente.post('/recomendar/nuevo', json=_json('lote_imposible.json'))
    assert r.status_code == 422
    errores = {e['campo']: e['mensaje'] for e in r.json()['errores']}
    assert set(errores) == {'altitud_media_m', 'humedad', 'defectos_cat1'}
    assert '100 y 4000' in errores['altitud_media_m'] and 'entre 0 y 1' in errores['humedad'] and 'entre 0 y 1000' in errores['defectos_cat1']
    assert 'Traceback' not in r.text and 'Input should' not in r.text and '190164' not in r.text      # ni inglés ni el valor recibido
    assert all(e['fila'] is None for e in r.json()['errores'])                                       # un solo lote: sin «fila»


def test_lote_nuevo_categoria_cerrada_numero_como_texto_y_campos(cliente):
    r = cliente.post('/recomendar/nuevo', json=dict(EJEMPLO, metodo_proceso='Secado al sol', humedad='mucha', sobrante=1))
    assert r.status_code == 422
    errores = {e['campo']: e['mensaje'] for e in r.json()['errores']}
    assert 'Elige uno de' in errores['metodo_proceso'] and 'Washed / Wet' in errores['metodo_proceso']
    assert 'número' in errores['humedad'] and 'no reconocido' in errores['sobrante']
    r2 = cliente.post('/recomendar/nuevo', json={k: v for k, v in EJEMPLO.items() if k != 'quakers'})
    assert r2.status_code == 422 and r2.json()['errores'][0]['campo'] == 'quakers' and 'Falta' in r2.json()['errores'][0]['mensaje']


def test_nuevos_en_lote_y_error_con_numero_de_fila(cliente):
    ok = cliente.post('/recomendar/nuevos', json={'lotes': [EJEMPLO, dict(EJEMPLO, pais='Brazil'), _json('lote_categoria_nueva.json')]})
    assert ok.status_code == 200 and ok.json()['encontrados'] == 3 and ok.json()['pedidos'] == 3
    mal = cliente.post('/recomendar/nuevos', json={'lotes': [EJEMPLO, dict(EJEMPLO, humedad=7)]})
    assert mal.status_code == 422
    assert mal.json()['errores'][0]['fila'] == 2 and mal.json()['errores'][0]['campo'] == 'humedad'
    assert cliente.post('/recomendar/nuevos', json={'lotes': []}).status_code == 422
    assert cliente.post('/recomendar/nuevos', json={'lotes': [EJEMPLO] * 1001}).status_code == 422
    assert cliente.post('/recomendar/nuevo', json=[1, 2]).status_code == 422


# --------------------------------------------------------------------------------------------------- 503 y 500
def _caida(metodo, ruta, cuerpo=None):
    raise urllib.error.URLError('conexion rechazada')


def test_api_caida_da_503_claro_pero_la_interfaz_sigue_viva(entrenado):
    c = _interfaz(entrenado, _caida)
    assert c.get('/salud').status_code == 200
    for r in (c.get('/listo'), c.post('/recomendar', json={'lote_ids': _ids(entrenado, 1)}), c.post('/recomendar/nuevo', json=EJEMPLO)):
        assert r.status_code == 503
        d = r.json()['detalle']
        assert 'API del modelo no responde' in d and 'Traceback' not in r.text and 'URLError' not in r.text
    e = c.get('/estado')
    assert e.status_code == 200 and e.json()['api']['estado'] == 'no_disponible' and e.json()['modelo'] is None
    assert e.json()['datos']['estado'] == 'ok' and e.json()['opciones']['pais']       # el formulario sigue teniendo sus listas


def test_api_sin_modelo_503_con_su_motivo(entrenado):
    c = _interfaz(entrenado, lambda m, r, b=None: (503, {'detalle': 'No hay modelo cargado', 'id_peticion': 'x'}))
    r = c.post('/recomendar', json={'lote_ids': _ids(entrenado, 1)})
    assert r.status_code == 503 and 'no tiene modelo listo' in r.json()['detalle'] and 'No hay modelo cargado' in r.json()['detalle']
    assert c.get('/listo').status_code == 503


def test_api_error_inesperado_y_respuesta_que_no_es_json(entrenado):
    c = _interfaz(entrenado, lambda m, r, b=None: (500, {'detalle': 'Error interno'}))
    r = c.post('/recomendar/nuevo', json=EJEMPLO)
    assert r.status_code == 503 and 'error inesperado (código 500)' in r.json()['detalle']

    def no_json(m, r, b=None):
        raise ValueError('Expecting value')
    r = _interfaz(entrenado, no_json).post('/recomendar/nuevo', json=EJEMPLO)
    assert r.status_code == 503 and 'Expecting' not in r.text


def test_api_simulada_que_rechaza_con_422_se_traduce(entrenado):
    simulada = lambda m, r, b=None: (422, {'detalle': 'x', 'errores': [{'campo': 'lotes.0.humedad', 'mensaje': 'Input should be less than or equal to 1', 'tipo': 'less_than_equal'}]})
    con = _interfaz(entrenado, simulada)
    r = con.post('/recomendar', json={'lote_ids': _ids(entrenado, 1)})
    assert r.status_code == 422 and r.json()['errores'][0] == {'fila': 1, 'campo': 'humedad', 'mensaje': 'Debe estar entre 0 y 1 (fracción, por ejemplo 0,11).'}


def test_sin_base_503_pero_salud_y_formulario_funcionan(entrenado, api_real, tmp_path):
    c = TestClient(crear_app(ruta_db=tmp_path / 'no_existe.db', url_api='http://api-simulada:8080', http=_http_de(api_real)), raise_server_exceptions=False)
    assert c.get('/salud').status_code == 200
    r = c.get('/listo')
    assert r.status_code == 503 and 'No existe la base' in r.json()['detalle']
    assert c.post('/recomendar', json={'lote_ids': [1]}).status_code == 503
    e = c.get('/estado').json()
    assert e['datos']['estado'] == 'error' and e['api']['estado'] == 'lista'
    assert not (tmp_path / 'no_existe.db').exists()                           # solo lectura: ni siquiera la crea
    assert c.post('/recomendar/nuevo', json=EJEMPLO).status_code == 200       # el lote nuevo no necesita la base


def test_base_sin_capa_fs_503(entrenado, api_real, tmp_path):
    vacia = tmp_path / 'vacia.db'
    sqlite3.connect(vacia).close()
    c = TestClient(crear_app(ruta_db=vacia, http=_http_de(api_real)), raise_server_exceptions=False)
    r = c.post('/recomendar', json={'lote_ids': [1]})
    assert r.status_code == 503 and 'fs_lote' in r.json()['detalle'] and 'python -m cafe_mlops.pipeline' in r.json()['detalle']


def test_error_inesperado_da_500_sin_traza(entrenado, monkeypatch):
    c = _interfaz(entrenado, _http_de(None))      # _http_de(None) falla con AttributeError al llamar
    r = c.post('/recomendar', json={'lote_ids': _ids(entrenado, 1)})
    assert r.status_code == 500 and r.json()['detalle'].startswith('Error interno') and 'Traceback' not in r.text and 'NoneType' not in r.text


# --------------------------------------------------------------------------------------------------- base solo lectura
def test_la_base_se_abre_en_solo_lectura_aunque_no_se_pida(cliente, entrenado):
    con = cliente.app.state.consulta._abrir()
    try:
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            con.execute('DELETE FROM fs_lote')
    finally:
        con.close()
    # y con TALLER_DB_SOLO_LECTURA, db.conectar tambien (el contenedor monta la base :ro)
    con2 = db.conectar(entrenado.ruta_db, solo_lectura=True)
    with pytest.raises(sqlite3.OperationalError):
        con2.execute('CREATE TABLE x (a)')
    con2.close()


# --------------------------------------------------------------------------------------------------- tramos, pagina, privacidad
def test_tramos_provisionales_con_marcador_todo():
    assert [segmento_de(p)['segmento'] for p in (1.0, 0.90, 0.8999, 0.80, 0.7999, 0.0)] == ['alta', 'alta', 'media', 'media', 'baja', 'baja']
    codigo = (RAIZ / 'cafe_mlops' / 'config.py').read_text(encoding='utf-8')
    assert re.search(r'TODO \(decisión 15\).*PROVISIONALES', codigo)           # el marcador sigue donde se definen los tramos
    assert 'TODO' in pagina.HTML or 'provisional' in pagina.HTML


def test_pagina_sin_recursos_externos_ni_nombres_de_personas():
    html = pagina.HTML
    assert not re.search(r'(src|href)\s*=\s*["\']https?://', html) and 'url(http' not in html and '@import' not in html
    assert not re.search(r'\bfetch\(\s*[\'"]https?://', html)
    minusculas = html.lower()
    for palabra in ('propietario', 'productor', 'owner', 'producer', 'farm', 'finca', 'certification'):
        assert palabra not in minusculas, palabra
    for c in config.COLUMNAS_PERSONALES:
        assert c.lower() not in minusculas
    # el formulario tiene las 10 variables del contrato
    for v in config.FEATURES:
        assert f'id="f-{v}"' in html


def test_respuestas_solo_con_las_variables_del_modelo(cliente, entrenado):
    r = cliente.post('/recomendar', json={'lote_ids': _ids(entrenado, 20)})
    for x in r.json()['resultados']:
        assert list(x['variables']) == config.FEATURES
    texto = r.text.lower()
    assert 'owner' not in texto and 'producer' not in texto and 'propietario' not in texto


def test_la_interfaz_no_importa_el_modelo():
    """La imagen de la interfaz no lleva scikit-learn ni mlflow: importar la app no debe cargarlos."""
    codigo = f"import sys; sys.path.insert(0, {str(RAIZ)!r}); import cafe_mlops.interfaz.app, cafe_mlops.interfaz.__main__; " \
             "malos = [m for m in ('sklearn', 'mlflow', 'scipy') if m in sys.modules]; assert not malos, malos"
    r = subprocess.run([sys.executable, '-I', '-c', codigo], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-1500:]


# --------------------------------------------------------------------------------------------------- uvicorn real (API e interfaz)
def _puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _esperar(url, proceso):
    for _ in range(100):
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return
        except OSError:
            time.sleep(0.3)
    proceso.terminate()
    pytest.fail(f'{url} no quedó listo: ' + proceso.communicate(timeout=10)[0][-1500:])


def _parar(proceso):
    proceso.terminate()
    try:
        return proceso.communicate(timeout=15)[0]
    except subprocess.TimeoutExpired:
        proceso.kill()
        return proceso.communicate()[0]


def _pedir(url, cuerpo=None):
    peticion = urllib.request.Request(url, data=None if cuerpo is None else json.dumps(cuerpo).encode(), headers={'content-type': 'application/json'})
    try:
        with urllib.request.urlopen(peticion, timeout=20) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_uvicorn_real_api_e_interfaz(entrenado):
    p_api, p_int = _puerto_libre(), _puerto_libre()
    base = dict(os.environ, PYTHONPATH=str(RAIZ))
    api = subprocess.Popen([sys.executable, '-m', 'cafe_mlops.api'], cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                           env=dict(base, TALLER_MODELOS=str(entrenado.modelos), TALLER_PUERTO_API=str(p_api)))
    interfaz = subprocess.Popen([sys.executable, '-m', 'cafe_mlops.interfaz'], cwd=RAIZ, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                env=dict(base, TALLER_DB=str(entrenado.ruta_db), TALLER_DB_SOLO_LECTURA='1', TALLER_PUERTO_INTERFAZ=str(p_int),
                                         TALLER_URL_API=f'http://127.0.0.1:{p_api}', TALLER_REPOSITORIO='alumno/taller-ml-ia-dev-production'))
    url = f'http://127.0.0.1:{p_int}'
    try:
        _esperar(f'http://127.0.0.1:{p_api}/listo', api)
        _esperar(url + '/listo', interfaz)
        codigo, e = _pedir(url + '/estado')
        assert codigo == 200 and e['api']['estado'] == 'lista' and e['repositorio'] == 'alumno/taller-ml-ia-dev-production'
        codigo, r = _pedir(url + '/recomendar', {'lote_ids': _ids(entrenado, 3) + [99999999]})
        assert codigo == 200 and r['encontrados'] == 3 and len(r['no_encontrados']) == 1
        codigo, r = _pedir(url + '/recomendar/nuevo', _json('lote_categoria_nueva.json'))
        assert codigo == 200 and r['resultados'][0]['avisos'][0]['tipo'] == 'categoria_nueva'
        codigo, r = _pedir(url + '/recomendar/nuevo', _json('lote_imposible.json'))
        assert codigo == 422 and len(r['errores']) == 3
        # se cae la API: la interfaz sigue viva y da 503 claro
        _parar(api)
        assert _pedir(url + '/salud')[0] == 200
        codigo, r = _pedir(url + '/recomendar', {'lote_ids': _ids(entrenado, 1)})
        assert codigo == 503 and 'no responde' in r['detalle']
    finally:
        _parar(api)
        salida = _parar(interfaz)
    assert 'Atlantida' not in salida                                          # el registro de la interfaz tampoco lleva datos del lote
    assert '"evento": "consulta' in salida

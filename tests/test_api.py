"""Pruebas de la API del modelo (T10): contrato = firma, 200 / 422 / 503 / 500, avisos, registro sin datos y uvicorn real.

El modelo se entrena UNA vez (orquestador hasta 2016) en carpetas temporales; nada toca data/ ni models/.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from auxiliar import RAIZ, leer
from cafe_mlops import config, pipeline
from cafe_mlops.api import esquemas
from cafe_mlops.api.app import crear_app
from cafe_mlops.api.servicio import ContratoRoto, ModeloNoDisponible, Servicio
from cafe_mlops.modeling import comparar, predict

DATOS = RAIZ / 'tests' / 'datos'


def _json(nombre):
    return json.loads((DATOS / nombre).read_text(encoding='utf-8'))


EJEMPLO = _json('lote_ejemplo.json')


@pytest.fixture(scope='module')
def entrenado(tmp_path_factory):
    raiz = tmp_path_factory.mktemp('api')
    modelos, reportes = raiz / 'models', raiz / 'reports'
    ruta_db = raiz / 'cafe.db'
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, 'MODELOS', modelos)
        mp.setattr(config, 'REPORTES', reportes)
        pipeline.ejecutar(hasta=2016, ruta_db=ruta_db, ruta_operacional=raiz / 'cqi.db', verbose=False)
    return SimpleNamespace(modelos=modelos, ruta_db=ruta_db)


@pytest.fixture(scope='module')
def meta(entrenado):
    return json.loads((entrenado.modelos / 'metadatos.json').read_text(encoding='utf-8'))


@pytest.fixture()
def cliente(entrenado):
    with TestClient(crear_app(entrenado.modelos)) as c:
        yield c


@pytest.fixture()
def cliente_sin_modelo(tmp_path):
    with TestClient(crear_app(tmp_path / 'no_hay_nada')) as c:
        yield c


def con(**cambios):
    return {**EJEMPLO, **cambios}


def sin(*claves):
    return {k: v for k, v in EJEMPLO.items() if k not in claves}


# --------------------------------------------------------------------------------------------------- contrato = firma
def test_el_esquema_tiene_los_nombres_y_los_tipos_de_la_firma_guardada(entrenado):
    firma = [(n, t) for n, t, _ in predict.contrato_de_la_firma(entrenado.modelos / config.CARPETA_MODELO_MLFLOW)]
    assert esquemas.contrato_del_esquema() == firma
    assert [n for n, _ in firma] == config.FEATURES
    assert {t for n, t in firma if n in config.CATEGORICAS} == {'string'}
    assert {t for n, t in firma if n in config.NUMERICAS} == {'double'}


def test_servicio_acepta_el_contrato_y_rechaza_nombres_y_tipos_distintos(entrenado):
    s = Servicio.cargar(entrenado.modelos)
    contrato = esquemas.contrato_del_esquema()
    s.comprobar_contrato(contrato)
    with pytest.raises(ContratoRoto, match='Faltan en la API.*quakers'):
        s.comprobar_contrato(contrato[:-1])
    with pytest.raises(ContratoRoto, match='Sobran en la API.*extra'):
        s.comprobar_contrato(contrato + [('extra', 'double')])
    cambiado = [(n, 'string' if n == 'altitud_media_m' else t) for n, t in contrato]
    with pytest.raises(ContratoRoto, match='altitud_media_m: la firma dice double y la API string'):
        s.comprobar_contrato(cambiado)


def test_un_contrato_roto_deja_la_api_viva_pero_no_lista(entrenado):
    cambiado = [(n, 'string' if n == 'humedad' else t) for n, t in esquemas.contrato_del_esquema()]
    with TestClient(crear_app(entrenado.modelos, contrato_api=cambiado)) as c:
        assert c.get('/salud').status_code == 200
        r = c.get('/listo')
        assert r.status_code == 503 and 'humedad' in r.json()['detalle']
        assert c.post('/predecir', json=EJEMPLO).status_code == 503


def test_la_firma_y_los_metadatos_deben_coincidir(entrenado, tmp_path):
    carpeta = tmp_path / 'm'
    shutil.copytree(entrenado.modelos, carpeta, ignore=shutil.ignore_patterns('mlflow.db', 'mlartifacts'))
    ruta = carpeta / 'metadatos.json'
    m = json.loads(ruta.read_text(encoding='utf-8'))
    m['tipos']['humedad'] = 'string'
    ruta.write_text(json.dumps(m), encoding='utf-8')
    with pytest.raises(ContratoRoto, match='tipos'):
        Servicio.cargar(carpeta)
    m['tipos']['humedad'] = 'double'
    m['variables'] = list(reversed(m['variables']))
    ruta.write_text(json.dumps(m), encoding='utf-8')
    with pytest.raises(ContratoRoto, match='no coincide con metadatos'):
        Servicio.cargar(carpeta)


def test_las_listas_cerradas_son_los_valores_de_los_datos():
    datos = pd.concat([leer('Arabica'), leer('Robusta')])
    assert set(datos['Processing.Method'].dropna().str.strip()) == set(esquemas.MetodoProceso.__args__)
    assert set(datos['Color'].dropna().str.strip()) == set(esquemas.Color.__args__)
    assert set(datos['Species']) == set(esquemas.Especie.__args__)


# --------------------------------------------------------------------------------------------------- 200
def test_salud_y_listo_y_modelo(cliente, meta):
    assert cliente.get('/salud').json() == {'estado': 'ok'}
    assert cliente.get('/listo').json() == {'estado': 'listo'}
    r = cliente.get('/modelo')
    assert r.status_code == 200
    info = r.json()
    assert info['huella_datos'] == meta['huella_datos'] and info['variables'] == config.FEATURES
    assert info['tipos']['pais'] == 'string' and info['version_modelo'] == str(meta['version_modelo_registrado'])


def test_predecir_200_coincide_con_el_paquete_y_trae_los_campos_acordados(cliente, entrenado, meta):
    r = cliente.post('/predecir', json=EJEMPLO)
    assert r.status_code == 200 and r.headers['x-request-id']
    cuerpo = r.json()
    assert set(cuerpo) == {'probabilidad_especialidad', 'modelo', 'version_modelo', 'huella_datos', 'avisos'}
    assert cuerpo['modelo'] == meta['modelo'] and cuerpo['huella_datos'] == meta['huella_datos']
    esperado = predict.predecir_probabilidad(EJEMPLO, ruta=entrenado.modelos)
    assert cuerpo['probabilidad_especialidad'] == pytest.approx(esperado, abs=1e-12)
    assert 0 <= cuerpo['probabilidad_especialidad'] <= 1
    assert cuerpo['avisos'] == []        # país, variedad, método y color del ejemplo se vieron al entrenar


def test_predecir_lote_200_mismo_orden_y_mismas_probabilidades(cliente, entrenado):
    lotes = [EJEMPLO, con(especie='Robusta', pais=None, variedad=None, metodo_proceso=None, color=None, altitud_media_m=None, humedad=None),
             con(altitud_media_m=900.5, defectos_cat1=3, quakers=1)]
    r = cliente.post('/predecir/lote', json={'lotes': lotes})
    assert r.status_code == 200
    probs = [p['probabilidad_especialidad'] for p in r.json()['predicciones']]
    assert probs == pytest.approx(predict.predecir_probabilidad(pd.DataFrame(lotes), ruta=entrenado.modelos), abs=1e-12)
    assert len(set(probs)) == 3
    uno = cliente.post('/predecir', json=lotes[2]).json()['probabilidad_especialidad']
    assert uno == pytest.approx(probs[2], abs=1e-12)


def test_los_nulos_se_aceptan_y_avisan_y_dan_lo_mismo_que_desconocida(cliente):
    r = cliente.post('/predecir', json=con(pais=None, variedad='  ', humedad=None, altitud_media_m=None))
    assert r.status_code == 200
    campos = {a['campo']: a for a in r.json()['avisos']}
    assert set(campos) == {'pais', 'variedad', 'humedad', 'altitud_media_m'}
    assert all(a['tipo'] == 'valor_no_informado' and a['valor'] is None for a in campos.values())
    # «Desconocida» es la categoría con la que el modelo imputa un nulo: misma probabilidad (None = NaN = Desconocida)
    otra = cliente.post('/predecir', json=con(pais='Desconocida', variedad='Desconocida', humedad=None, altitud_media_m=None))
    assert otra.json()['probabilidad_especialidad'] == pytest.approx(r.json()['probabilidad_especialidad'], abs=1e-12)


def test_una_categoria_nunca_vista_da_200_con_aviso_de_campo_y_valor(cliente):
    r = cliente.post('/predecir', json=_json('lote_categoria_nueva.json'))
    assert r.status_code == 200
    (aviso,) = r.json()['avisos']
    assert aviso['tipo'] == 'categoria_nueva' and aviso['campo'] == 'pais' and aviso['valor'] == 'Atlantida'
    assert 'Atlantida' in aviso['mensaje']
    # variedad nueva también; y una cadena con espacios se compara ya recortada
    r = cliente.post('/predecir', json=con(variedad=' Variedad Inventada '))
    (aviso,) = r.json()['avisos']
    assert (aviso['campo'], aviso['valor']) == ('variedad', 'Variedad Inventada')


def test_el_aviso_de_categoria_nueva_vale_para_lotes_sueltos_dentro_de_un_lote(cliente):
    r = cliente.post('/predecir/lote', json={'lotes': [EJEMPLO, con(pais='Atlantida'), EJEMPLO]})
    avisos = [p['avisos'] for p in r.json()['predicciones']]
    assert avisos[0] == [] and avisos[2] == [] and avisos[1][0]['valor'] == 'Atlantida'


def test_categoria_conocida_pero_infrecuente_avisa_distinto(cliente, meta):
    infrecuentes = [(c, v) for c, vs in meta['categorias_infrecuentes'].items() for v in vs if c in ('pais', 'variedad', 'metodo_proceso', 'color')]
    if not infrecuentes:
        pytest.skip('este modelo no tiene categorías infrecuentes')
    campo, valor = infrecuentes[0]
    if campo in ('metodo_proceso', 'color') and valor not in (esquemas.MetodoProceso.__args__ + esquemas.Color.__args__):
        pytest.skip('categoría infrecuente fuera de la lista cerrada')
    r = cliente.post('/predecir', json=con(**{campo: valor}))
    assert r.status_code == 200
    assert [(a['tipo'], a['campo'], a['valor']) for a in r.json()['avisos']] == [('categoria_infrecuente', campo, valor)]


def test_valor_fuera_del_rango_de_train_avisa_sin_rechazar(cliente, meta):
    maximo = meta['rangos_entrenamiento']['altitud_media_m'][1]
    r = cliente.post('/predecir', json=con(altitud_media_m=min(maximo + 100, config.ALTITUD_MAX_M)))
    if maximo + 100 > config.ALTITUD_MAX_M and maximo >= config.ALTITUD_MAX_M:
        pytest.skip('train cubre toda la altitud permitida')
    assert r.status_code == 200
    assert [(a['tipo'], a['campo']) for a in r.json()['avisos']] == [('fuera_de_rango_entrenamiento', 'altitud_media_m')]


def test_humedad_cero_se_trata_como_no_medida(cliente):
    r0 = cliente.post('/predecir', json=con(humedad=0))
    rn = cliente.post('/predecir', json=con(humedad=None))
    assert r0.status_code == 200
    assert [a['tipo'] for a in r0.json()['avisos']] == ['humedad_cero']
    assert r0.json()['probabilidad_especialidad'] == pytest.approx(rn.json()['probabilidad_especialidad'], abs=1e-12)


def test_los_limites_de_los_rangos_se_aceptan(cliente):
    for cambio in ({'altitud_media_m': 100}, {'altitud_media_m': 4000}, {'humedad': 1}, {'defectos_cat1': 0, 'quakers': 0.0}):
        assert cliente.post('/predecir', json=con(**cambio)).status_code == 200, cambio


# --------------------------------------------------------------------------------------------------- 422
CASOS_422 = [
    ('campo desconocido', con(notas_cata=88), 'notas_cata'),
    ('falta una variable', sin('humedad'), 'humedad'),
    ('altitud bajo el mínimo', con(altitud_media_m=99.9), 'altitud_media_m'),
    ('altitud sobre el máximo', con(altitud_media_m=4000.1), 'altitud_media_m'),
    ('humedad negativa', con(humedad=-0.01), 'humedad'),
    ('humedad mayor que 1', con(humedad=1.01), 'humedad'),
    ('defectos negativos', con(defectos_cat1=-1), 'defectos_cat1'),
    ('defectos2 negativos', con(defectos_cat2=-0.5), 'defectos_cat2'),
    ('quakers negativos', con(quakers=-1), 'quakers'),
    ('número como cadena', con(altitud_media_m='1500'), 'altitud_media_m'),
    ('booleano en un número', con(humedad=True), 'humedad'),
    ('texto en un número', con(quakers='alto'), 'quakers'),
    ('especie desconocida', con(especie='Liberica'), 'especie'),
    ('especie nula', con(especie=None), 'especie'),
    ('método fuera de la lista', con(metodo_proceso='Inventado'), 'metodo_proceso'),
    ('color fuera de la lista', con(color='Rojo'), 'color'),
    ('país numérico', con(pais=5), 'pais'),
    ('variedad booleana', con(variedad=False), 'variedad'),
    ('país demasiado largo', con(pais='x' * (esquemas.MAX_TEXTO + 1)), 'pais'),
]


@pytest.mark.parametrize('cuerpo,campo', [(c[1], c[2]) for c in CASOS_422], ids=[c[0] for c in CASOS_422])
def test_422_dice_en_que_campo_y_no_devuelve_el_valor(cliente, cuerpo, campo):
    r = cliente.post('/predecir', json=cuerpo)
    assert r.status_code == 422
    j = r.json()
    assert j['id_peticion'] and campo in [e['campo'] for e in j['errores']]
    assert set(j['errores'][0]) == {'campo', 'mensaje', 'tipo'}
    assert 'Traceback' not in r.text


def test_422_lote_imposible_de_laboratorio_senala_los_tres_campos(cliente):
    r = cliente.post('/predecir', json=_json('lote_imposible.json'))
    assert r.status_code == 422
    assert {e['campo'] for e in r.json()['errores']} == {'altitud_media_m', 'humedad', 'defectos_cat1'}


def test_422_nan_infinito_y_cuerpo_que_no_es_json(cliente):
    cabecera = {'content-type': 'application/json'}
    for malo in ('NaN', 'Infinity'):
        cuerpo = json.dumps(EJEMPLO).replace('"humedad": 0.11', f'"humedad": {malo}')
        assert cliente.post('/predecir', content=cuerpo, headers=cabecera).status_code == 422, malo
    assert cliente.post('/predecir', content='esto no es json', headers=cabecera).status_code == 422
    assert cliente.post('/predecir', content=json.dumps([EJEMPLO]), headers=cabecera).status_code == 422


def test_422_del_lote_vacio_demasiado_grande_y_con_campos_de_mas(cliente):
    assert cliente.post('/predecir/lote', json={'lotes': []}).status_code == 422
    assert cliente.post('/predecir/lote', json={}).status_code == 422
    assert cliente.post('/predecir/lote', json={'clientes': [EJEMPLO]}).status_code == 422
    assert cliente.post('/predecir/lote', json={'lotes': [EJEMPLO], 'otro': 1}).status_code == 422
    assert cliente.post('/predecir/lote', json={'lotes': [EJEMPLO] * (esquemas.MAX_LOTES + 1)}).status_code == 422
    assert cliente.post('/predecir/lote', json={'lotes': [EJEMPLO] * esquemas.MAX_LOTES}).status_code == 200


def test_422_en_un_lote_dice_que_fila_falla(cliente):
    r = cliente.post('/predecir/lote', json={'lotes': [EJEMPLO, con(humedad=7)]})
    assert r.status_code == 422
    assert [e['campo'] for e in r.json()['errores']] == ['lotes.1.humedad']


# --------------------------------------------------------------------------------------------------- 503
def test_503_sin_modelo_en_todo_salvo_salud(cliente_sin_modelo):
    c = cliente_sin_modelo
    assert c.get('/salud').status_code == 200            # el proceso vive
    for ruta in ('/listo', '/modelo'):
        r = c.get(ruta)
        assert r.status_code == 503 and 'No hay modelo' in r.json()['detalle'] and r.json()['id_peticion'], ruta
    assert c.post('/predecir', json=EJEMPLO).status_code == 503
    assert c.post('/predecir/lote', json={'lotes': [EJEMPLO]}).status_code == 503
    assert 'Traceback' not in c.get('/listo').text


def test_503_si_el_modelo_esta_estropeado(entrenado, tmp_path):
    carpeta = tmp_path / 'm'
    shutil.copytree(entrenado.modelos, carpeta, ignore=shutil.ignore_patterns('mlflow.db', 'mlartifacts'))
    (carpeta / config.CARPETA_MODELO_MLFLOW / 'model.pkl').write_bytes(b'basura')
    with TestClient(crear_app(carpeta)) as c:
        assert c.get('/salud').status_code == 200
        assert c.get('/listo').status_code == 503
    with pytest.raises(ModeloNoDisponible):
        Servicio.cargar(carpeta)


def test_503_si_falta_solo_el_modelo_mlflow(entrenado, tmp_path):
    carpeta = tmp_path / 'm'
    carpeta.mkdir()
    shutil.copy(entrenado.modelos / 'metadatos.json', carpeta)
    with TestClient(crear_app(carpeta)) as c:
        assert c.get('/listo').status_code == 503


# --------------------------------------------------------------------------------------------------- 500
def test_500_no_filtra_la_traza_ni_el_mensaje_interno(entrenado, capsys):
    class Roto:
        def predict_proba(self, X):
            raise RuntimeError('SECRETO-INTERNO /ruta/privada')

    with TestClient(crear_app(entrenado.modelos)) as c:
        c.app.state.servicio.modelo = Roto()
        r = c.post('/predecir', json=EJEMPLO, headers={'x-request-id': 'prueba-500'})
        r2 = c.post('/predecir/lote', json={'lotes': [EJEMPLO]})
        assert c.get('/salud').status_code == 200        # el proceso sigue vivo
    for resp in (r, r2):
        assert resp.status_code == 500
        assert resp.json()['detalle'] == 'Error interno'
        assert 'SECRETO' not in resp.text and 'Traceback' not in resp.text and 'ruta' not in resp.text
    assert r.json()['id_peticion'] == 'prueba-500' and r.headers['x-request-id'] == 'prueba-500'
    salida = capsys.readouterr().out
    registro = [json.loads(linea) for linea in salida.splitlines() if linea.startswith('{')]
    error = [x for x in registro if x.get('evento') == 'error_no_controlado' and x['id'] == 'prueba-500']
    assert error and 'SECRETO-INTERNO' in error[0]['traceback']      # la traza va al registro, no al cliente


# --------------------------------------------------------------------------------------------------- registro
def test_registro_json_por_peticion_sin_datos_del_lote(cliente, capsys):
    cliente.post('/predecir', json=con(pais='Atlantida'), headers={'x-request-id': 'abc123'})
    cliente.post('/predecir', json=con(humedad=9))
    cliente.get('/listo')
    salida = capsys.readouterr().out
    lineas = [json.loads(linea) for linea in salida.splitlines() if linea.startswith('{')]
    peticiones = [x for x in lineas if x.get('evento') == 'peticion']
    assert [(x['ruta'], x['codigo']) for x in peticiones] == [('/predecir', 200), ('/predecir', 422), ('/listo', 200)]
    assert peticiones[0]['id'] == 'abc123' and all('ms' in x and x['severity'] == 'INFO' for x in peticiones)
    for dato in ('Atlantida', 'Colombia', 'Caturra', '1700', '0.11'):
        assert dato not in salida, f'el registro contiene datos del lote: {dato}'


# --------------------------------------------------------------------------------------------------- uvicorn real y comparar --url
def _puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def test_uvicorn_real_y_comparar_con_url_da_diferencia_cero(entrenado):
    puerto = _puerto_libre()
    entorno = dict(os.environ, TALLER_MODELOS=str(entrenado.modelos), TALLER_PUERTO_API=str(puerto), PYTHONPATH=str(RAIZ))
    proceso = subprocess.Popen([sys.executable, '-m', 'cafe_mlops.api'], cwd=RAIZ, env=entorno, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    url = f'http://127.0.0.1:{puerto}'
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(url + '/listo', timeout=2) as r:
                    if r.status == 200:
                        break
            except OSError:
                time.sleep(0.3)
        else:
            proceso.terminate()
            pytest.fail('uvicorn no quedó listo: ' + proceso.communicate(timeout=10)[0][-1500:])
        filas, n, _ = comparar.comparar_caminos(40, url=url, carpeta=entrenado.modelos, ruta_db=entrenado.ruta_db)
        assert filas[-1]['camino'].startswith('API') and filas[-1]['filas'] == n == 40
        assert all(f['coincide'] for f in filas), filas
        # 422 y 200 con aviso, de verdad por HTTP
        def enviar(cuerpo):
            peticion = urllib.request.Request(url + '/predecir', data=json.dumps(cuerpo).encode(), headers={'content-type': 'application/json'})
            try:
                with urllib.request.urlopen(peticion, timeout=10) as r:
                    return r.status, json.loads(r.read())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read())
        assert enviar(_json('lote_imposible.json'))[0] == 422
        codigo, cuerpo = enviar(_json('lote_categoria_nueva.json'))
        assert codigo == 200 and cuerpo['avisos'][0]['campo'] == 'pais'
    finally:
        proceso.terminate()
        try:
            salida = proceso.communicate(timeout=15)[0]
        except subprocess.TimeoutExpired:
            proceso.kill()
            salida = proceso.communicate()[0]
    assert 'Atlantida' not in salida and 'Colombia' not in salida        # el registro real de uvicorn tampoco lleva datos
    assert '"evento": "peticion"' in salida                              # y sí muestra los eventos de la aplicación

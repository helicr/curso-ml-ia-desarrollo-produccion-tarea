"""Pruebas de la imagen de la INTERFAZ y del compose SIN Docker (T12): lo que se comprueba leyendo los archivos.

Que se construyan y arranquen juntas solo lo demuestra Docker de verdad (Codespace o GitHub Actions, T14/T15).
"""
import json
import re
import subprocess
import sys

import pytest

from cafe_mlops import config
from test_imagen import _instrucciones, _regex, _versiones

RAIZ = config.RAIZ
DOCKERFILE = RAIZ / 'deploy' / 'docker' / 'interfaz.Dockerfile'
IGNORAR = RAIZ / 'deploy' / 'docker' / 'interfaz.Dockerfile.dockerignore'
COMPOSE = RAIZ / 'deploy' / 'docker' / 'compose.yaml'
PROHIBIDAS = ('scikit-learn', 'sklearn', 'mlflow', 'mlflow-skinny', 'scipy', 'joblib', 'pandas', 'numpy', 'matplotlib', 'cloudpickle')


def ins():
    return _instrucciones(DOCKERFILE.read_text(encoding='utf-8'))


def entra_en_el_contexto(ruta):
    """Reglas de Docker: gana el ULTIMO patron que coincide con la ruta o con una de sus carpetas; «!» vuelve a incluir."""
    partes = ruta.split('/')
    prefijos = ['/'.join(partes[:k]) for k in range(1, len(partes) + 1)]
    dentro = True
    for linea in IGNORAR.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#'):
            continue
        negar = linea.startswith('!')
        patron = _regex(linea.lstrip('!'))
        if any(patron.fullmatch(p) for p in prefijos):
            dentro = negar
    return dentro


# --- Dockerfile ------------------------------------------------------------------------------------------------------------------

def test_misma_base_y_mismas_versiones_que_la_imagen_de_la_api():
    assert [r for i, r in ins() if i == 'FROM'] == ['python:3.11-slim']
    pip = [r for i, r in ins() if i == 'RUN' and 'pip install' in r]
    assert len(pip) == 1 and '-c requirements-api.lock' in pip[0] and '-r requirements-interfaz.txt' in pip[0]
    bloqueadas = _versiones(RAIZ / 'requirements-api.lock')
    nombres = [l.strip() for l in (RAIZ / 'requirements-interfaz.txt').read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')]
    assert nombres
    for nombre in nombres:
        assert nombre.lower() in bloqueadas, f'{nombre} no esta en requirements-api.lock: su version no quedaria fijada'


def test_la_interfaz_no_instala_scikit_learn_ni_mlflow_ni_las_librerias_del_modelo():
    texto = (RAIZ / 'requirements-interfaz.txt').read_text(encoding='utf-8')
    pedidas = {re.split(r'[=<>\[ ]', l.strip())[0].lower() for l in texto.splitlines() if l.strip() and not l.startswith('#')}
    assert pedidas == {'fastapi', 'uvicorn', 'pydantic'}
    assert not pedidas & set(PROHIBIDAS)
    for _, resto in ins():
        for p in PROHIBIDAS:
            assert not re.search(rf'\b{re.escape(p)}\b', resto), f'{p} aparece en el Dockerfile de la interfaz: {resto}'


def test_no_lleva_ni_modelo_ni_datos_solo_el_codigo():
    copias = [r.split() for i, r in ins() if i == 'COPY']
    origenes = [o for c in copias for o in c[:-1]]
    assert sorted(origenes) == sorted(['requirements-api.lock', 'requirements-interfaz.txt', 'cafe_mlops/'])
    assert not any(o.startswith(('models', 'data', 'sql')) for o in origenes)


def test_la_configuracion_va_por_variables_taller():
    texto = DOCKERFILE.read_text(encoding='utf-8')
    env = ' '.join(r for i, r in ins() if i == 'ENV')
    for esperado in ('TALLER_DB=/datos/cafe.db', 'TALLER_DB_SOLO_LECTURA=1', 'TALLER_URL_API=http://api:8080'):
        assert esperado in env, esperado
    assert 'CURSO_' not in texto
    # y son variables que config.py de verdad lee
    fuente = (RAIZ / 'cafe_mlops' / 'config.py').read_text(encoding='utf-8')
    for nombre in ('TALLER_DB', 'TALLER_DB_SOLO_LECTURA', 'TALLER_URL_API', 'TALLER_HOST_INTERFAZ', 'TALLER_PUERTO_INTERFAZ'):
        assert f"'{nombre}'" in fuente, nombre


def test_usuario_10001_salud_y_puerto_8090():
    usuario = [r for i, r in ins() if i == 'USER']
    assert usuario == ['10001']
    assert any(i == 'RUN' and 'useradd --uid 10001' in r for i, r in ins())
    salud = [r for i, r in ins() if i == 'HEALTHCHECK']
    assert len(salud) == 1 and '/salud' in salud[0] and '8090' in salud[0] and '/listo' not in salud[0]
    assert [r for i, r in ins() if i == 'EXPOSE'] == ['8090']
    cmd = json.loads([r for i, r in ins() if i == 'CMD'][0])
    assert cmd[:3] == ['python', '-m', 'cafe_mlops.interfaz'] and cmd[cmd.index('--host') + 1] == '0.0.0.0'
    assert cmd[cmd.index('--puerto') + 1] == '8090'
    import cafe_mlops.interfaz.__main__ as principal       # el modulo que nombra el CMD existe y tiene main
    assert callable(principal.main)


def test_el_contexto_solo_deja_pasar_lo_que_se_copia_y_todo_ello_existe():
    for ruta in ('cafe_mlops/interfaz/app.py', 'cafe_mlops/config.py', 'requirements-api.lock', 'requirements-interfaz.txt'):
        assert entra_en_el_contexto(ruta), ruta
    for ruta in ('data/processed/cafe.db', 'models/metadatos.json', 'models/modelo_mlflow/MLmodel', 'sql/fs/02_poblar_fs.sql', '.env',
                 'tests/test_api.py', 'notebooks/00_intro.ipynb', 'cafe_mlops/__pycache__/config.cpython-311.pyc', 'mlruns/0/x', 'requirements-dev.txt'):
        assert not entra_en_el_contexto(ruta), ruta
    for o in ('requirements-api.lock', 'requirements-interfaz.txt', 'cafe_mlops/interfaz/app.py'):
        assert (RAIZ / o).exists(), o


def test_la_interfaz_no_carga_las_librerias_del_modelo():
    """La imagen no instala scikit-learn ni mlflow (ni pandas ni numpy): importar la aplicacion no debe necesitarlos."""
    codigo = ("import os, sys; os.environ['TALLER_URL_API'] = 'http://api:8080'; import cafe_mlops.interfaz.app, cafe_mlops.interfaz.__main__; "
              "print([m for m in ('sklearn', 'mlflow', 'scipy', 'joblib', 'matplotlib', 'pandas', 'numpy') if m in sys.modules])")
    salida = subprocess.run([sys.executable, '-c', codigo], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.strip()
    assert salida == '[]'


# --- compose ---------------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope='module')
def compose():
    yaml = pytest.importorskip('yaml')
    return yaml.safe_load(COMPOSE.read_text(encoding='utf-8'))


def test_compose_nombre_imagenes_y_solo_la_interfaz_se_publica(compose):
    assert compose['name'] == 'cafe'                  # la red se llama cafe_default
    s = compose['services']
    assert set(s) == {'api', 'interfaz'}
    assert 'ports' not in s['api']                     # la API solo se alcanza desde la red interna
    assert s['interfaz']['ports'] == ['8090:8090']
    assert s['api']['image'] == 'cafe-api:local' and s['interfaz']['image'] == 'cafe-interfaz:local'
    assert s['api']['build']['dockerfile'] == 'deploy/docker/Dockerfile'
    assert s['interfaz']['build']['dockerfile'] == 'deploy/docker/interfaz.Dockerfile'
    for nombre in ('api', 'interfaz'):
        contexto = (COMPOSE.parent / s[nombre]['build']['context']).resolve()
        assert contexto == RAIZ.resolve()
        assert (contexto / s[nombre]['build']['dockerfile']).is_file()


def test_compose_la_interfaz_llama_a_la_api_por_su_nombre_y_lee_la_base_en_solo_lectura(compose):
    i = compose['services']['interfaz']
    assert i['environment']['TALLER_URL_API'] == 'http://api:8080'
    assert i['environment']['TALLER_DB'] == '/datos/cafe.db' and str(i['environment']['TALLER_DB_SOLO_LECTURA']) == '1'
    assert i['volumes'] == ['../../data/processed:/datos:ro']
    assert (COMPOSE.parent / '../../data/processed').resolve() == (RAIZ / 'data' / 'processed').resolve()
    assert config.DB.name == 'cafe.db'                  # el archivo que se espera dentro del volumen
    assert i['depends_on'] == {'api': {'condition': 'service_healthy'}}
    assert 'HEALTHCHECK' in (RAIZ / 'deploy' / 'docker' / 'Dockerfile').read_text(encoding='utf-8')   # sin el, «healthy» no llega nunca
    assert 'networks' not in compose and 'networks' not in i      # sin red propia: cafe_default


def test_compose_no_usa_nombres_del_curso(compose):
    texto = COMPOSE.read_text(encoding='utf-8')
    for prohibido in ('retencion', 'ia_mlops', 'CURSO_'):
        assert prohibido not in texto

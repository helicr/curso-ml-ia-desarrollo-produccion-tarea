"""Pruebas de la imagen Docker de la API SIN Docker (T12): lo que se comprueba leyendo el Dockerfile, el .dockerignore, el Makefile
y las dependencias, y arrancando la API con SOLO lo que el Dockerfile copia (imagen simulada).

Que NO prueban: que `docker build` y `docker run` funcionen, ni el tamaño real de la imagen, ni el modelo cargado en Linux. Eso solo lo
demuestra Docker (Codespace o GitHub Actions, T14/T15). Lo que si evitan es llegar al `docker build` con errores que se ven a simple vista.
"""
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from cafe_mlops import config, pipeline

RAIZ = config.RAIZ
DOCKERFILE = RAIZ / 'deploy' / 'docker' / 'Dockerfile'
MAKEFILE = RAIZ / 'Makefile'


def _instrucciones(texto):
    """Instrucciones del Dockerfile (une las lineas que terminan en «\\» y descarta comentarios)."""
    unido = re.sub(r'\\\s*\n', ' ', texto)
    lineas = [l.strip() for l in unido.splitlines() if l.strip() and not l.strip().startswith('#')]
    return [(l.split(None, 1)[0].upper(), l.split(None, 1)[1] if ' ' in l else '') for l in lineas]


def _copias(texto):
    return [resto.split()[:-1] for inst, resto in _instrucciones(texto) if inst == 'COPY']


def _regex(patron):
    """Traduce un patron de .dockerignore a expresion regular: `*` no cruza «/», `**/` cruza carpetas, `?` es un caracter, `[abc]` un conjunto."""
    p, salida, i = patron.rstrip('/'), '', 0
    while i < len(p):
        if p.startswith('**/', i):
            salida += '(?:.*/)?'
            i += 3
        elif p[i] == '*':
            salida += '[^/]*'
            i += 1
        elif p[i] == '?':
            salida += '[^/]'
            i += 1
        elif p[i] == '[':
            j = p.index(']', i)
            salida += p[i:j + 1]
            i = j + 1
        else:
            salida += re.escape(p[i])
            i += 1
    return re.compile(salida)


def _ignorado(ruta, patrones):
    """Un patron se compara con la ruta (relativa al contexto) y con cada una de sus carpetas; si coincide una carpeta, se excluye lo que contiene.

    Ojo: `*.pyc` sin «**/» solo vale en la raiz del contexto; para cualquier carpeta hay que escribir `**/*.pyc`.
    """
    partes = ruta.split('/')
    prefijos = ['/'.join(partes[:k]) for k in range(1, len(partes) + 1)]
    return any(_regex(p).fullmatch(pre) for p in patrones for pre in prefijos)


def _patrones():
    return [l.strip() for l in (RAIZ / '.dockerignore').read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')]


def _versiones(ruta):
    out = {}
    for linea in ruta.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if linea and not linea.startswith('#') and '==' in linea:
            nombre, version = linea.split('==')
            out[nombre.strip().lower().replace('_', '-')] = version.strip()
    return out


def _puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


# --- Dockerfile ------------------------------------------------------------------------------------------------------------------

def test_el_dockerfile_usa_la_misma_version_de_python_que_el_entorno():
    base = [r for i, r in _instrucciones(DOCKERFILE.read_text(encoding='utf-8')) if i == 'FROM']
    assert base == ['python:3.11-slim']                  # el entorno del taller es Python 3.11


def test_las_dependencias_se_instalan_antes_de_copiar_el_codigo():
    """Si el codigo se copiara primero, cualquier cambio de una linea reinstalaria todas las dependencias."""
    orden = [(i, r) for i, r in _instrucciones(DOCKERFILE.read_text(encoding='utf-8')) if i in ('COPY', 'RUN')]
    instalar = next(k for k, (i, t) in enumerate(orden) if i == 'RUN' and 'pip install' in t)
    codigo = next(k for k, (i, t) in enumerate(orden) if i == 'COPY' and 'cafe_mlops/' in t)
    assert instalar < codigo
    assert any(i == 'COPY' and 'requirements-api.lock' in t for i, t in orden[:instalar])
    assert '-r requirements-api.lock' in [t for i, t in orden if i == 'RUN' and 'pip install' in t][0]


def test_usuario_no_root_10001_y_comprobacion_de_salud():
    texto = DOCKERFILE.read_text(encoding='utf-8')
    ins = _instrucciones(texto)
    usuario = [r for i, r in ins if i == 'USER']
    assert usuario == ['10001']
    assert any(i == 'RUN' and 'useradd --uid 10001' in r for i, r in ins)
    assert ins.index(('USER', '10001')) > max(k for k, (i, r) in enumerate(ins) if i == 'RUN')   # root solo para instalar; luego se baja
    salud = [r for i, r in ins if i == 'HEALTHCHECK']
    assert len(salud) == 1 and '/salud' in salud[0] and '8080' in salud[0] and '/listo' not in salud[0]


def test_el_puerto_y_el_comando_coinciden_con_la_aplicacion():
    ins = _instrucciones(DOCKERFILE.read_text(encoding='utf-8'))
    assert [r for i, r in ins if i == 'EXPOSE'] == ['8080']
    cmd = json.loads([r for i, r in ins if i == 'CMD'][0])
    assert cmd[:2] == ['uvicorn', 'cafe_mlops.api.app:app']
    assert cmd[cmd.index('--port') + 1] == '8080' and cmd[cmd.index('--host') + 1] == '0.0.0.0'
    from cafe_mlops.api.app import app            # el objeto que nombra el CMD existe
    assert app.title


def test_el_dockerfile_dice_donde_estan_los_modelos_con_variables_taller():
    texto = DOCKERFILE.read_text(encoding='utf-8')
    env = ' '.join(r for i, r in _instrucciones(texto) if i == 'ENV')
    assert 'TALLER_MODELOS=/app/models' in env
    assert 'CURSO_' not in texto                        # nada heredado del curso


def test_el_dockerfile_no_copia_datos_ni_secretos_ni_sql():
    origenes = sum(_copias(DOCKERFILE.read_text(encoding='utf-8')), [])
    assert sorted(origenes) == sorted(['requirements-api.lock', 'cafe_mlops/', 'models/modelo_mlflow/', 'models/metadatos.json'])
    for origen in origenes:
        assert not origen.startswith(('data', 'sql', 'tests', 'notebooks', '.env', '.git')) and '.db' not in origen, origen


# --- .dockerignore: lo que se copia no puede estar excluido -----------------------------------------------------------------------

@pytest.fixture(scope='module')
def entrenado(tmp_path_factory):
    """Entrena una vez (--hasta 2016) en una carpeta temporal: el modelo MLflow y metadatos.json que la imagen copiaria de models/."""
    raiz = tmp_path_factory.mktemp('imagen')
    modelos = raiz / 'models'
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, 'MODELOS', modelos)
        mp.setattr(config, 'REPORTES', raiz / 'reports')
        pipeline.ejecutar(hasta=2016, ruta_db=raiz / 'cafe.db', ruta_operacional=raiz / 'cqi.db', verbose=False)
    return SimpleNamespace(modelos=modelos, ruta_db=raiz / 'cafe.db')


def _archivos_de_la_imagen(carpeta_modelos):
    """(ruta relativa al contexto, archivo) de lo que el Dockerfile copia. Lo de models/ sale de la carpeta temporal recien entrenada."""
    rutas = []
    for origenes in _copias(DOCKERFILE.read_text(encoding='utf-8')):
        for origen in origenes:
            if origen.startswith('models/'):
                p, base = carpeta_modelos / origen[len('models/'):].rstrip('/'), carpeta_modelos.parent
            else:
                p, base = RAIZ / origen.rstrip('/'), RAIZ
            if p.is_dir():
                rutas += [(f.relative_to(base).as_posix(), f) for f in sorted(p.rglob('*')) if f.is_file()]
            else:
                rutas.append((p.relative_to(base).as_posix(), p))
    return rutas


def test_lo_que_el_dockerfile_copia_existe_y_no_queda_excluido_por_dockerignore(entrenado):
    rutas = _archivos_de_la_imagen(entrenado.modelos)
    assert any(r.endswith('MLmodel') for r, _ in rutas) and any(r == 'models/metadatos.json' for r, _ in rutas)
    assert any(r == 'cafe_mlops/api/app.py' for r, _ in rutas) and any(r == 'cafe_mlops/modeling/preproceso.py' for r, _ in rutas)
    assert any(r == 'requirements-api.lock' for r, _ in rutas)
    for ruta, archivo in rutas:
        if '__pycache__' in ruta or ruta.endswith('.pyc'):
            continue
        assert archivo.exists(), ruta
        assert not _ignorado(ruta, _patrones()), f'{ruta} lo copia el Dockerfile pero .dockerignore lo excluye'


def test_dockerignore_deja_fuera_datos_pruebas_y_artefactos_pesados():
    patrones = _patrones()
    for ruta in ['data/raw/cqi/arabica_data_cleaned.csv', 'data/processed/cafe.db', 'tests/test_api.py', 'notebooks/00_intro.ipynb',
                 'models/mlflow.db', 'models/mlartifacts/0/x/model.pkl', 'models/modelo.joblib', '.git/config', '.env', 'sql/fs/02_poblar_fs.sql',
                 'deploy/docker/compose.yaml', 'cafe_mlops/__pycache__/x.pyc']:
        assert _ignorado(ruta, patrones), ruta
    for ruta in ['models/modelo_mlflow/MLmodel', 'models/metadatos.json', 'cafe_mlops/api/app.py', 'cafe_mlops/modeling/preproceso.py',
                 'requirements-api.lock']:
        assert not _ignorado(ruta, patrones), ruta


# --- imagen simulada: arranca solo con lo que copia, y carga el modelo (nulos_a_nan) -------------------------------------------------

def test_la_imagen_simulada_carga_el_modelo_con_nulos_a_nan_solo_con_lo_que_el_dockerfile_copia(entrenado, tmp_path):
    """Replica la disposicion de la imagen (/app/cafe_mlops, /app/models/...) en una carpeta nueva, sin datos, SQL ni pruebas, y arranca uvicorn alli.

    El modelo guarda una referencia a cafe_mlops.modeling.preproceso.nulos_a_nan: si el paquete no viajara en la imagen, /listo daria 503.
    NO prueba la imagen base, `pip install` ni Linux.
    """
    app = tmp_path / 'app'
    for ruta, archivo in _archivos_de_la_imagen(entrenado.modelos):
        if '__pycache__' in ruta or _ignorado(ruta, _patrones()):
            continue
        destino = app / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(archivo, destino)
    assert sorted(p.name for p in app.iterdir()) == ['cafe_mlops', 'models', 'requirements-api.lock']
    assert not (app / 'data').exists() and not (app / 'sql').exists()
    assert (app / 'cafe_mlops' / 'modeling' / 'preproceso.py').is_file()

    puerto = _puerto_libre()
    entorno = {k: v for k, v in os.environ.items() if not k.startswith('TALLER_') and k != 'PYTHONPATH'}
    entorno.update(TALLER_MODELOS=str(app / 'models'), PYTHONDONTWRITEBYTECODE='1')
    # `python -m uvicorn` desde /app: el directorio actual va primero en sys.path (como en la imagen), no el repositorio.
    proceso = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'cafe_mlops.api.app:app', '--host', '127.0.0.1', '--port', str(puerto)],
                               cwd=app, env=entorno, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    base = f'http://127.0.0.1:{puerto}'
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(base + '/listo', timeout=2) as r:
                    if r.status == 200:
                        break
            except OSError:
                time.sleep(0.3)
        else:
            proceso.terminate()
            pytest.fail('la API de la imagen simulada no quedo lista: ' + proceso.communicate(timeout=10)[0][-1500:])
        assert json.loads(urllib.request.urlopen(base + '/salud', timeout=5).read())
        ejemplo = (RAIZ / 'tests' / 'datos' / 'lote_ejemplo.json').read_bytes()
        pet = urllib.request.Request(base + '/predecir', data=ejemplo, headers={'content-type': 'application/json'})
        cuerpo = json.loads(urllib.request.urlopen(pet, timeout=10).read())
        assert 0 <= cuerpo['probabilidad_especialidad'] <= 1
    finally:
        proceso.terminate()
        try:
            proceso.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proceso.kill()
            proceso.communicate()
    # y que el codigo servido es el de la copia, no el del repositorio
    r = subprocess.run([sys.executable, '-c', 'import cafe_mlops, cafe_mlops.modeling.preproceso as p; print(cafe_mlops.__file__); print(p.nulos_a_nan.__name__)'],
                       cwd=app, env=entorno, capture_output=True, text=True)
    assert Path(r.stdout.splitlines()[0]).is_relative_to(app) and r.stdout.splitlines()[1] == 'nulos_a_nan', r.stderr


# --- dependencias de la imagen ----------------------------------------------------------------------------------------------------

def test_el_archivo_de_versiones_exactas_contiene_las_dependencias_directas():
    directas, exactas = _versiones(RAIZ / 'requirements-api.txt'), _versiones(RAIZ / 'requirements-api.lock')
    assert directas
    for nombre, version in directas.items():
        assert exactas.get(nombre) == version, nombre


def test_el_lock_es_el_del_pico_t07_53_paquetes_todos_fijados():
    lineas = [l.strip() for l in (RAIZ / 'requirements-api.lock').read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')]
    assert len(lineas) == 53                              # los 53 del entorno limpio probado en el pico T07
    assert all(re.fullmatch(r'[A-Za-z0-9_.\-]+==[0-9][^\s=]*', l) for l in lineas), 'todas las lineas son nombre==version'
    exactas = _versiones(RAIZ / 'requirements-api.lock')
    assert exactas['mlflow-skinny'] == '3.18.0' and exactas['scikit-learn'] == '1.9.1' and exactas['pandas'] == '2.3.3'


def test_la_imagen_no_lleva_herramientas_de_desarrollo_ni_mlflow_completo():
    exactas = _versiones(RAIZ / 'requirements-api.lock')
    for ausente in ('pytest', 'jupyterlab', 'papermill', 'jupytext', 'matplotlib', 'mlflow', 'openpyxl', 'httpx', 'sqlalchemy'):
        assert ausente not in exactas, ausente
    assert 'mlflow-skinny' in exactas and 'fastapi' in exactas and 'uvicorn' in exactas


# --- nombres, Makefile ------------------------------------------------------------------------------------------------------------

def test_makefile_tiene_los_objetivos_de_docker_con_los_nombres_cafe():
    texto = MAKEFILE.read_text(encoding='utf-8')
    objetivos = set(re.findall(r'^([a-z-]+):', texto, flags=re.M))
    assert {'imagen', 'imagen-interfaz', 'imagenes', 'contenedor', 'compose-arriba', 'compose-abajo'} <= objetivos
    phony = next(l for l in texto.splitlines() if l.startswith('.PHONY'))
    for o in ('imagenes', 'compose-arriba', 'compose-abajo'):
        assert o in phony.split()
    assert re.search(r'^imagenes: imagen imagen-interfaz', texto, flags=re.M)
    assert 'docker build -f deploy/docker/Dockerfile -t cafe-api:local .' in texto
    assert 'docker build -f deploy/docker/interfaz.Dockerfile -t cafe-interfaz:local .' in texto
    assert 'docker compose -f deploy/docker/compose.yaml up --build -d --wait' in texto
    assert 'docker compose -f deploy/docker/compose.yaml down' in texto
    assert 'retencion' not in texto and 'ia_mlops' not in texto
    for linea in texto.splitlines():                       # las ordenes van con tabulador, no con espacios
        assert not re.match(r' +(docker|\$\(PYTHON\))', linea), linea


def test_make_api_respeta_taller_puerto_api():
    texto = MAKEFILE.read_text(encoding='utf-8')
    orden = re.search(r'^api:.*\n\t(.*)', texto, flags=re.M).group(1)
    assert orden.strip() == '$(PYTHON) -m cafe_mlops.api'           # el puerto y el host salen de config (TALLER_PUERTO_API / TALLER_HOST_API)
    assert '--port 8080' not in orden


def test_ningun_archivo_de_deploy_nombra_el_curso_ni_rutas_personales():
    for ruta in (RAIZ / 'deploy' / 'docker').iterdir():
        if ruta.is_file():
            texto = ruta.read_text(encoding='utf-8')
            for prohibido in ('retencion', 'ia_mlops', 'CURSO_', 'C:\\', '/Users/', 'BK' + '70827'):   # el literal va partido: test_higiene.py busca ese texto en todo el arbol
                assert prohibido not in texto, f'{ruta.name}: {prohibido}'

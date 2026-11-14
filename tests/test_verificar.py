"""Pruebas de T16 (parte estática): cafe_mlops.verificar y .devcontainer/devcontainer.json. Sin Codespace ni Docker reales."""
import hashlib
import json
import subprocess
import sys

import pytest

from auxiliar import RAIZ
from cafe_mlops import verificar

DEVCONTAINER = RAIZ / '.devcontainer' / 'devcontainer.json'


# ------------------------------------------------------------------------------------------------------------- devcontainer
@pytest.fixture(scope='module')
def dc():
    return json.loads(DEVCONTAINER.read_text(encoding='utf-8'))


def test_devcontainer_es_json_valido_y_usa_python_311(dc):
    # la imagen sale de un Dockerfile propio (ver el motivo en él): Python 3.11 de Microsoft sin el repositorio apt de yarn
    assert dc['build']['dockerfile'] == 'Dockerfile'
    dockerfile = (RAIZ / '.devcontainer' / 'Dockerfile').read_text(encoding='utf-8')
    assert 'FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm' in dockerfile
    assert '/etc/apt/sources.list.d/yarn.list' in dockerfile, 'sin quitar yarn, Docker-in-Docker falla (NO_PUBKEY 62D54FD4003F6525)'


def test_devcontainer_docker_en_docker_sin_moby(dc):
    feature = [v for k, v in dc['features'].items() if 'docker-in-docker' in k]
    assert feature and feature[0].get('moby') is False


def test_devcontainer_instala_lo_mismo_que_el_ci(dc):
    orden = dc['postCreateCommand']
    assert 'pip install -r requirements-dev.txt' in orden and 'pip install -e . --no-deps' in orden
    assert 'cafe_mlops.verificar' in orden
    assert orden.rstrip().endswith('|| true'), 'verificar no debe impedir crear el Codespace'
    # el CI hace exactamente las mismas dos instalaciones
    ci = (RAIZ / '.github' / 'workflows' / 'validar.yml').read_text(encoding='utf-8')
    assert 'pip install -r requirements-dev.txt' in ci and 'pip install -e . --no-deps' in ci


def test_devcontainer_reenvia_los_puertos_con_etiqueta(dc):
    assert dc['forwardPorts'] == [8080, 8090, 5000]
    for puerto in ('8080', '8090', '5000'):
        assert dc['portsAttributes'][puerto]['label']


def test_devcontainer_sin_rutas_ni_datos_personales(dc):
    texto = DEVCONTAINER.read_text(encoding='utf-8')
    assert 'Users' not in texto and 'HC-' not in texto


# ------------------------------------------------------------------------------------------------------------- verificar: piezas
def test_leer_fijados_toma_solo_lo_fijado_con_dobles_iguales():
    texto = '# c\n-r otro.txt\nnumpy==2.4.6\nmlflow-skinny==3.18.0  # nota\nsuelto\npandas>=2\n'
    assert verificar.leer_fijados(texto) == {'numpy': '2.4.6', 'mlflow-skinny': '3.18.0'}


def test_los_requisitos_reales_se_leen_y_no_estan_vacios():
    fijados = verificar.leer_fijados(verificar.REQUISITOS.read_text(encoding='utf-8'))
    assert len(fijados) >= 10  # solo lo fijado directamente en requirements-dev.txt (el -r de la API no se sigue)
    assert 'pytest' in fijados


def test_comprobar_paquetes_detecta_falta_y_version_distinta():
    fijados = {'a': '1.0', 'b': '2.0', 'c': '3.0'}
    ok, msg, problemas = verificar.comprobar_paquetes(fijados, {'a': '1.0', 'b': '2.1', 'c': None})
    assert not ok and len(problemas) == 2 and 'b 2.1' in msg and 'c no está instalado' in msg
    assert verificar.comprobar_paquetes(fijados, {'a': '1.0', 'b': '2.0', 'c': '3.0'})[0]


def test_comprobar_python():
    assert verificar.comprobar_python((3, 11, 9))[0]
    ok, msg = verificar.comprobar_python((3, 12, 1))
    assert not ok and '3.11' in msg


def test_datos_reales_pasan_y_detecta_un_byte_cambiado(tmp_path):
    assert verificar.comprobar_datos()[0]
    csv = tmp_path / 'x.csv'
    csv.write_bytes(b'a,b\n1,2\n')
    sumas = tmp_path / 'SHA256SUMS'
    sumas.write_text(f'{hashlib.sha256(csv.read_bytes()).hexdigest()}  x.csv\n', encoding='utf-8')
    assert verificar.comprobar_datos(tmp_path, sumas)[0]
    csv.write_bytes(b'a,b\n1,3\n')
    ok, msg = verificar.comprobar_datos(tmp_path, sumas)
    assert not ok and 'x.csv' in msg
    csv.unlink()
    assert 'falta x.csv' in verificar.comprobar_datos(tmp_path, sumas)[1]
    assert not verificar.comprobar_datos(tmp_path, tmp_path / 'no-existe')[0]


def test_docker_responde_o_dice_que_falta():
    def sin_docker(orden):
        return None, 'orden no encontrada'

    def servidor_parado(orden):
        return 1, ['Cannot connect to the Docker daemon']

    def bien(orden):
        return 0, ['27.0.0' if orden[1] != 'compose' else '2.29.0']

    def sin_compose(orden):
        return (0, ['27.0.0']) if orden[1] == 'version' else (1, ['no such plugin'])

    assert 'no está instalado' in verificar.comprobar_docker(sin_docker)[1]
    assert 'no responde' in verificar.comprobar_docker(servidor_parado)[1]
    assert verificar.comprobar_docker(bien)[0]
    assert 'compose' in verificar.comprobar_docker(sin_compose)[1] and not verificar.comprobar_docker(sin_compose)[0]


# ------------------------------------------------------------------------------------------------------------- verificar: la línea final
def test_la_linea_final_dice_que_falta(monkeypatch):
    monkeypatch.setattr(verificar, 'comprobar_docker', lambda *a, **k: (False, 'docker no está instalado'))
    lineas = []
    codigo = verificar.verificar(con_docker=True, salida=lineas.append)
    assert codigo == 1
    assert lineas[-1].startswith('FALTA: ') and 'docker' in lineas[-1]
    assert 'LISTO PARA EL TALLER' not in '\n'.join(lineas)


def test_la_linea_final_es_listo_si_todo_pasa(monkeypatch):
    monkeypatch.setattr(verificar, 'comprobar_python', lambda: (True, 'Python 3.11.0'))
    monkeypatch.setattr(verificar, 'comprobar_paquetes', lambda fijados: (True, 'ok', []))
    monkeypatch.setattr(verificar, 'comprobar_docker', lambda *a, **k: (True, 'ok'))
    lineas = []
    assert verificar.verificar(con_docker=True, salida=lineas.append) == 0
    assert lineas[-1] == 'LISTO PARA EL TALLER'
    lineas.clear()
    assert verificar.verificar(con_docker=False, salida=lineas.append) == 0
    assert lineas[-1].startswith('LISTO PARA EL TALLER') and 'sin comprobar Docker' in lineas[-1]


def test_verificar_se_ejecuta_como_modulo_y_termina_con_una_linea_final():
    r = subprocess.run([sys.executable, '-m', 'cafe_mlops.verificar', '--sin-docker'], cwd=RAIZ, capture_output=True, text=True,
                       encoding='utf-8', timeout=120)
    ultima = r.stdout.strip().splitlines()[-1]
    assert ultima.startswith(('LISTO PARA EL TALLER', 'FALTA: ')), r.stdout + r.stderr
    assert r.returncode == (0 if ultima.startswith('LISTO') else 1)


def test_el_makefile_tiene_verificar_y_la_orden_por_defecto_sigue_siendo_ayuda():
    texto = (RAIZ / 'Makefile').read_text(encoding='utf-8')
    assert '\nverificar:' in texto and 'cafe_mlops.verificar' in texto
    assert texto.index('\nayuda:') < texto.index('\nverificar:')   # la primera orden es la que se ejecuta con «make» a secas

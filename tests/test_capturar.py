"""T18: el capturador de salidas reales (taller/capturar.py) y el JSON que deja (taller/salidas-reales.json)."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
JSON = RAIZ / 'taller' / 'salidas-reales.json'
PERSONAL = [
    re.compile(r'[A-Za-z]:[\\/]+Users[\\/]', re.I), re.compile(r'(?<![\w.])/Users/[A-Za-z]'),
    re.compile(r'(?<![\w.])/home/(?!runner\b|vscode\b|codespace\b|appuser\b|user\b|usuario\b)[A-Za-z]'),
    re.compile('BK' + '70827', re.I), re.compile('claude-' + 'profiles', re.I), re.compile('HC-' + 'Cursos', re.I),
    re.compile('bankinter-' + 'cowork', re.I), re.compile('helicr', re.I), re.compile(r'[A-Za-z]:\\'),
    re.compile(r'taller-capturar-', re.I),
]


@pytest.fixture(scope='module')
def datos():
    return json.loads(JSON.read_text(encoding='utf-8'))


def test_el_json_tiene_pasos_y_cifras_de_github_actions(datos):
    assert set(datos) == {'meta', 'pasos', 'github_actions'}
    ga = datos['github_actions']
    assert ga['origen'] == 'github-actions'
    for clave in ('validar', 'nueva_version_rechazada', 'nueva_version_aprobada'):
        assert ga[clave]['origen'] == 'github-actions'
    assert ga['nueva_version_rechazada']['diferencia'] == -0.0574
    assert ga['validar']['imagen_cafe_api']['tamano'] == '826 MB'


def test_todos_los_pasos_tienen_salida_y_orden_correlativo(datos):
    pasos = datos['pasos']
    assert [p['orden'] for p in pasos.values()] == list(range(1, len(pasos) + 1))
    for clave, p in pasos.items():
        assert p['salida'], f'{clave} sin salida'
        if not p.get('omitido'):
            assert p['codigo'] is not None, clave


def test_pasos_obligatorios_y_resultados_esperados(datos):
    p = datos['pasos']
    for clave in ('verificar_entorno', 'pipeline_hasta_2016', 'pipeline_segunda_ejecucion', 'pipeline_hasta_2018',
                  'comparar_tolerancia_por_defecto', 'comparar_tolerancia_010', 'api_salud', 'api_listo', 'api_predecir',
                  'api_predecir_422', 'api_predecir_aviso', 'interfaz_recomendar'):
        assert clave in p, clave
    assert 'sin cambios' in ' '.join(p['pipeline_segunda_ejecucion']['salida'])
    assert 'RECHAZADA' in p['comparar_tolerancia_por_defecto']['salida'][-1]
    assert 'APROBADA' in p['comparar_tolerancia_010']['salida'][-1]
    assert (p['api_predecir']['codigo'], p['api_predecir_422']['codigo'], p['api_predecir_aviso']['codigo']) == (200, 422, 200)
    assert p['api_predecir_aviso']['salida']['avisos']
    assert p['interfaz_recomendar']['salida']['encontrados'] == 3


def test_el_json_no_tiene_rutas_personales_ni_nombres_de_personas(datos):
    texto = JSON.read_text(encoding='utf-8')
    for patron in PERSONAL:
        assert not patron.search(texto), patron.pattern
    import pandas as pd
    nombres = set()
    for archivo in (RAIZ / 'data' / 'raw' / 'cqi').glob('*.csv'):
        df = pd.read_csv(archivo, usecols=lambda c: c in ('Owner', 'Producer', 'Farm.Name'))
        for col in df.columns:
            nombres |= {str(v).strip().lower() for v in df[col].dropna() if len(str(v).strip()) >= 8}
    bajo = texto.lower()
    # una cadena del texto que sea un nombre del CSV (con comillas, para no confundir con palabras sueltas)
    hallados = sorted(n for n in nombres if f'"{n}"' in bajo)
    assert not hallados, hallados[:5]


def test_cada_orden_citada_existe(datos):
    for clave, p in datos['pasos'].items():
        if p.get('omitido'):
            continue
        if p['tipo'] == 'terminal':
            modulo = re.search(r'python -m ([\w.]+)', p['comando']).group(1)
            assert (RAIZ / (modulo.replace('.', '/') + '.py')).exists() or (RAIZ / modulo.replace('.', '/') / '__main__.py').exists(), clave
        elif p['tipo'] == 'proceso':
            modulo = re.search(r'python -m ([\w.]+)', p['comando']).group(1)
            assert (RAIZ / modulo.replace('.', '/') / '__main__.py').exists(), clave
        else:
            if 'cuerpo' in p and isinstance(p['cuerpo'], str):
                assert (RAIZ / p['cuerpo']).exists(), clave
            assert re.search(rf'{p["metodo"]}\s+{re.escape(p["ruta"])}', p['comando']), clave
    texto = (RAIZ / 'cafe_mlops' / 'api' / 'app.py').read_text(encoding='utf-8')
    for p in datos['pasos'].values():
        if p.get('tipo') == 'http' and p['ruta'] in ('/salud', '/listo', '/predecir'):
            assert f"'{p['ruta']}'" in texto
    assert "'/recomendar'" in (RAIZ / 'cafe_mlops' / 'interfaz' / 'app.py').read_text(encoding='utf-8')


@pytest.mark.lento
def test_se_regenera_sin_errores(tmp_path):
    destino = tmp_path / 'salidas.json'
    r = subprocess.run([sys.executable, '-m', 'taller.capturar', '--salida', str(destino)], cwd=RAIZ, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=1200)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    nuevo = json.loads(destino.read_text(encoding='utf-8'))
    guardado = json.loads(JSON.read_text(encoding='utf-8'))
    assert list(nuevo['pasos']) == list(guardado['pasos'])
    for clave, p in nuevo['pasos'].items():
        assert p['salida'] and p['codigo'] == guardado['pasos'][clave]['codigo'], clave

"""Higiene de la plantilla (T13): lo que NO debe haber en ningun sitio del arbol ni de las capas de modelado.

Son pruebas transversales: no prueban una funcion, vigilan que nada se cuele (una ruta personal, el nombre de una persona, una nota de
cata como variable, un dato de terceros alterado). Complementan a las de cada modulo:
    - variables sin notas de cata ni total ........ test_config.py (FEATURES), test_fs_y_ml.py (columnas y SQL de FS), aqui (FS, ML y MASTER reales)
    - nombres de personas fuera de variables y pantallas ... test_interfaz.py (pagina), test_raw_y_master.py (MASTER), aqui (todo el arbol y las capas)
    - rutas personales ........................... test_config.py (codigo y SQL), test_imagen.py (deploy), aqui (TODO el arbol de la plantilla)
    - SHA256SUMS ................................. test_dato.py (huellas), aqui (formato, nada sin listar, Git no toca los bytes)
    - determinismo ............................... test_modelo.py (entrenar dos veces), test_raw_y_master.py, aqui (la base operacional)
"""
import csv
import re
import sqlite3
from pathlib import Path

import pytest

from auxiliar import ARCHIVOS, RAIZ
from cafe_mlops import config

# ------------------------------------------------------------------------------------------------------------- recorrer el arbol
CARPETAS_IGNORADAS = {'.git', '__pycache__', '.pytest_cache', '.venv', 'venv', 'env', 'node_modules', '.ipynb_checkpoints', 'mlruns',
                      'mlartifacts', '.mypy_cache', '.ruff_cache'}
# Carpetas que el pipeline GENERA (estan en .gitignore): no forman parte de la plantilla que se publica.
GENERADO = ('data/processed', 'data/external', 'data/interim', 'reports', 'models')
# Documentos de construccion que describen la regla (citan «C:\Users...» como ejemplo de lo prohibido). Se retiran de la plantilla en T24.
DOCUMENTOS_DE_CONSTRUCCION = {'PLANIFICACION.md', 'TAREAS.md', 'DECISIONES-APLICADAS.md'}
TOPE_BYTES = 5_000_000


def archivos_de_texto(incluir_datos=True, incluir_exploracion=True, incluir_pruebas=True):
    """(ruta relativa con «/», texto) de cada archivo de texto del arbol de la plantilla (los binarios y los generados se saltan)."""
    for ruta in sorted(RAIZ.rglob('*')):
        if not ruta.is_file():
            continue
        rel = ruta.relative_to(RAIZ)
        if CARPETAS_IGNORADAS & set(rel.parts):
            continue
        r = rel.as_posix()
        if any(r.startswith(g + '/') for g in GENERADO) and r != 'models/referencia.json':
            continue
        if rel.parts[0] in ('data',) and not incluir_datos or rel.parts[0] == '_exploracion' and not incluir_exploracion:
            continue
        if rel.parts[0] == 'tests' and not incluir_pruebas:
            continue
        if ruta.stat().st_size > TOPE_BYTES:
            continue
        datos = ruta.read_bytes()
        if b'\x00' in datos:
            continue
        try:
            yield r, datos.decode('utf-8')
        except UnicodeDecodeError:
            continue


def _tokens_personales():
    """Patrones de lo que identifica a una persona o a un equipo concreto. Los literales se parten para que este archivo no se delate a si mismo."""
    return [
        ('ruta de Windows de un usuario', re.compile(r'[A-Za-z]:[\\/]+Users[\\/]', re.I)),
        ('ruta de macOS de un usuario', re.compile(r'(?<![\w.])/Users/[A-Za-z]')),
        ('ruta Linux de un usuario', re.compile(r'(?<![\w.])/home/(?!runner\b|vscode\b|codespace\b|appuser\b|user\b|usuario\b)[A-Za-z]')),
        ('usuario del equipo', re.compile('BK' + '70827', re.I)),
        ('perfil de Claude', re.compile('claude-' + 'profiles', re.I)),
        ('carpeta de trabajo del docente', re.compile('HC-' + 'Cursos', re.I)),
        ('entorno del equipo del docente', re.compile('bankinter-' + 'cowork', re.I)),
    ]


# ------------------------------------------------------------------------------------------------------------- rutas personales
def test_ninguna_ruta_personal_en_todo_el_arbol_de_la_plantilla():
    """Ni en el codigo, ni en el SQL, ni en los workflows, ni en la documentacion, las pruebas o los datos de texto."""
    encontrados = []
    for rel, texto in archivos_de_texto():
        if rel in DOCUMENTOS_DE_CONSTRUCCION:
            continue
        for motivo, patron in _tokens_personales():
            m = patron.search(texto)
            if m:
                linea = texto.count('\n', 0, m.start()) + 1
                encontrados.append(f'{rel}:{linea} ({motivo})')
    assert not encontrados, 'rutas o datos personales en: ' + '; '.join(encontrados)


def test_el_recorrido_del_arbol_ve_lo_que_debe():
    """Que la prueba anterior no pase por no estar mirando: el recorrido incluye codigo, SQL, deploy, workflows, pruebas y datos."""
    vistos = {r for r, _ in archivos_de_texto()}
    for esperado in ('cafe_mlops/config.py', 'sql/fs/01_crear_fs.sql', 'deploy/docker/compose.yaml', 'Makefile', 'pyproject.toml',
                     'models/referencia.json', 'tests/test_higiene.py', 'data/raw/cqi/SHA256SUMS', '.github/workflows/validar.yml',
                     '.github/workflows/nueva-version.yml'):
        assert esperado in vistos, esperado
    assert not any(r.startswith(('reports/', 'data/processed/')) for r in vistos)


@pytest.mark.parametrize('texto', ['C:' + '\\Users\\alguien\\x', 'C:' + '/Users' + '/alguien/x', '/Users' + '/alguien/x', '/home' + '/alguien/x', 'BK' + '70827'])
def test_los_patrones_personales_detectan_lo_que_dicen(texto):
    assert any(p.search(texto) for _, p in _tokens_personales())


@pytest.mark.parametrize('texto', ['/home' + '/runner/work', '/home' + '/vscode', '/home' + '/codespace/x', '/app/models', 'C:\\Windows\\x', 'usuarios'])
def test_los_patrones_personales_no_saltan_con_rutas_de_ejecucion(texto):
    assert not any(p.search(texto) for _, p in _tokens_personales())


# ------------------------------------------------------------------------------------------------------------- nombres de personas
def _nombres_de_personas():
    """Nombres y contactos de personas tal como vienen en los CSV (columnas personales de config), de al menos 8 caracteres."""
    nombres = set()
    for ruta in ARCHIVOS.values():
        with open(ruta, encoding='utf-8', newline='') as f:
            for fila in csv.DictReader(f):
                for columna in ('Owner', 'Owner.1', 'Producer', 'Certification.Contact'):
                    valor = (fila.get(columna) or '').strip().lower()
                    if len(valor) >= 8 and ' ' in valor:
                        nombres.add(valor)
    return nombres


def test_hay_nombres_de_personas_contra_los_que_comparar():
    assert len(_nombres_de_personas()) > 100


def test_ningun_nombre_de_persona_aparece_fuera_de_los_datos():
    """Los nombres solo viven en los CSV de data/ y en la base operacional (decision 4). Ni en el codigo, SQL, deploy, workflows,
    documentacion, pantallas o pruebas: si alguna vez se pega un ejemplo real en un texto, esta prueba lo dice."""
    nombres = _nombres_de_personas()
    donde = []
    for rel, texto in archivos_de_texto(incluir_datos=False, incluir_exploracion=False):
        if rel in DOCUMENTOS_DE_CONSTRUCCION:
            continue
        bajo = texto.lower()
        donde += [f'{rel}: {n!r}' for n in nombres if n in bajo]
    assert not donde, '; '.join(donde[:10])


def test_las_capas_de_modelado_no_llevan_columnas_ni_valores_de_personas(bases_v2):
    """MASTER, FS y ML: sin columnas personales y sin ningun valor de texto que sea el nombre de una persona."""
    nombres = _nombres_de_personas()
    con = sqlite3.connect(bases_v2[1])
    try:
        tablas = [t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'") if t.startswith(('master_', 'fs_', 'ml_'))]
        assert {'master_lotes', 'fs_lote', 'ml_dataset'} <= set(tablas)
        personales = {c.lower().replace('.', '_') for c in config.COLUMNAS_PERSONALES} | {
            'propietario', 'propietario_2', 'productor', 'productor_id', 'finca', 'cert_contacto', 'cert_direccion', 'molino', 'compania'}
        for t in tablas:
            columnas = [c[1] for c in con.execute(f'PRAGMA table_info({t})')]
            assert not set(columnas) & personales, f'{t}: {sorted(set(columnas) & personales)}'
            for c, tipo in [(c[1], c[2]) for c in con.execute(f'PRAGMA table_info({t})')]:
                if tipo.upper() not in ('TEXT', ''):
                    continue
                valores = {(v or '').strip().lower() for (v,) in con.execute(f'SELECT DISTINCT {c} FROM {t}') if isinstance(v, str)}
                assert not valores & nombres, f'{t}.{c}: {sorted(valores & nombres)[:3]}'
    finally:
        con.close()


# ------------------------------------------------------------------------------------------------------------- variables
def _normalizar(nombre):
    return nombre.lower().replace('.', '_').replace(' ', '_')


def test_ninguna_variable_sale_de_las_notas_de_cata_ni_del_total_en_las_capas_reales(bases_v2):
    """FS y ML de verdad (no solo config): ninguna columna es una nota de cata ni el total, y las variables de ML son las de config."""
    notas = {_normalizar(n) for n in config.TODAS_LAS_NOTAS}
    total = _normalizar(config.COLUMNA_TOTAL)
    con = sqlite3.connect(bases_v2[1])
    try:
        for tabla in ('fs_lote', 'ml_dataset'):
            columnas = {c[1] for c in con.execute(f'PRAGMA table_info({tabla})')}
            assert not columnas & notas, f'{tabla}: {sorted(columnas & notas)}'
            assert total not in columnas and not any('total' in c or 'puntos' in c for c in columnas), tabla
            assert set(config.FEATURES) <= columnas, tabla
    finally:
        con.close()


def test_el_modelo_guardado_no_conoce_notas_ni_personas(bases_v2, tmp_path, monkeypatch):
    """Los metadatos de un entrenamiento real: variables = config.FEATURES, y ni el nombre de una nota ni el de una columna personal."""
    import json

    from cafe_mlops import db
    from cafe_mlops.modeling import train
    monkeypatch.setattr(config, 'MODELOS', tmp_path / 'm')
    monkeypatch.setattr(config, 'REPORTES', tmp_path / 'r')
    con = db.conectar(bases_v2[1])
    try:
        train.entrenar(con, usar_mlflow=False, verbose=False)
    finally:
        con.close()
    meta = json.loads((tmp_path / 'm' / 'metadatos.json').read_text(encoding='utf-8'))
    assert meta['variables'] == config.FEATURES
    variables_y_tipos = {_normalizar(v) for v in meta['variables']} | {_normalizar(v) for v in meta['tipos']}
    assert not variables_y_tipos & {_normalizar(n) for n in config.TODAS_LAS_NOTAS + config.COLUMNAS_PERSONALES + [config.COLUMNA_TOTAL]}


# ------------------------------------------------------------------------------------------------------------- SHA256SUMS
def test_sha256sums_tiene_el_formato_de_sha256sum_y_no_deja_nada_sin_listar():
    """Formato «huella·dos espacios·nombre» (lo que verifica `sha256sum -c`), en minusculas, y todo CSV de la carpeta esta listado."""
    carpeta = RAIZ / 'data' / 'raw' / 'cqi'
    lineas = [l for l in (carpeta / 'SHA256SUMS').read_text(encoding='utf-8').splitlines() if l.strip()]
    assert lineas
    listados = []
    for l in lineas:
        assert re.fullmatch(r'[0-9a-f]{64}  [^/\\ ]+', l), l      # nombre de archivo suelto, sin rutas
        listados.append(l.split('  ', 1)[1])
    assert len(set(listados)) == len(listados)
    assert sorted(listados) == sorted(p.name for p in carpeta.glob('*.csv'))


def test_git_no_toca_los_bytes_de_los_csv_de_terceros():
    """Si Git cambiara los saltos de linea de los CSV al clonar (sobre todo en Windows), las huellas de SHA256SUMS dejarian de coincidir."""
    reglas = (RAIZ / '.gitattributes').read_text(encoding='utf-8').splitlines()
    activas = [l.split() for l in reglas if l.strip() and not l.lstrip().startswith('#')]
    assert any(len(r) >= 2 and r[0] == 'data/raw/cqi/*.csv' and '-text' in r[1:] for r in activas)


# ------------------------------------------------------------------------------------------------------------- determinismo
def _volcado(ruta):
    con = sqlite3.connect(ruta)
    try:
        tablas = [t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {t: con.execute(f'SELECT * FROM {t} ORDER BY 1, 2').fetchall() for t in tablas}
    finally:
        con.close()


@pytest.mark.parametrize('hasta', [2016, 2018])
def test_crear_la_base_operacional_dos_veces_da_el_mismo_contenido(tmp_path, hasta):
    """Mismo CSV y mismo --hasta = misma base (los identificadores de lote no dependen del azar ni del reloj)."""
    from cafe_mlops import operacional
    a, b = tmp_path / 'a.db', tmp_path / 'b.db'
    operacional.crear_operacional(hasta, a, verbose=False)
    operacional.crear_operacional(hasta, b, verbose=False)
    va, vb = _volcado(a), _volcado(b)
    for tabla in va:
        if tabla == 'origen_simulacion':     # puede llevar la fecha de creacion
            continue
        assert va[tabla] == vb[tabla], tabla

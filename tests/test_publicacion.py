"""T24: la copia limpia que se publica al alumno (docente/publicar_plantilla.py) no lleva material del docente ni datos personales.

Ejecuta el script hacia una carpeta temporal y comprueba sobre ESA copia: que no estan los archivos del docente ni lo generado, que no hay
rutas personales ni nombres de personas del CSV fuera de data/raw/cqi/ y references/, que estan los tres PDF y los diagramas, y que el
README y el comprobador de entrega apuntan a archivos que existen en la copia.
`docente/` se retira al publicar: si no esta, estas pruebas se omiten (en la copia ya no hacen falta).
"""
import csv
import getpass
import importlib.util
import os
import re

import pytest

from auxiliar import RAIZ

SCRIPT = RAIZ / 'docente' / 'publicar_plantilla.py'
pytestmark = pytest.mark.skipif(not SCRIPT.is_file(), reason='docente/ se retira de la plantilla del alumno')

DEL_DOCENTE = ('docente', '_exploracion', 'PLANIFICACION.md', 'TAREAS.md', 'DECISIONES-APLICADAS.md', 'REQUISITOS-DEL-ENUNCIADO.md')
GENERADO = ('data/interim/', 'data/processed/', 'data/external/', 'models/', 'reports/')
PDF = ('taller/instrucciones-del-trabajo.pdf', 'taller/guia-detallada-del-trabajo.pdf', 'taller/diapositivas-del-trabajo.pdf')
# Donde si pueden estar los nombres de personas: los datos originales y la nota de la fuente.
CON_NOMBRES = ('data/raw/cqi/', 'references/')


@pytest.fixture(scope='module')
def modulo():
    espec = importlib.util.spec_from_file_location('docente_publicar_plantilla', SCRIPT)
    m = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(m)
    return m


@pytest.fixture(scope='module')
def copia(tmp_path_factory):
    """Ejecuta el script como lo haria el docente (por linea de ordenes) y devuelve (carpeta, salida impresa)."""
    import subprocess
    import sys
    destino = tmp_path_factory.mktemp('publicacion') / 'copia'
    r = subprocess.run([sys.executable, str(SCRIPT), '--destino', str(destino)], capture_output=True, text=True, encoding='utf-8')
    assert r.returncode == 0, r.stdout + r.stderr
    return destino, r.stdout


def _archivos(carpeta):
    return sorted(p for p in carpeta.rglob('*') if p.is_file())


def _rel(carpeta, ruta):
    return ruta.relative_to(carpeta).as_posix()


def _textos(carpeta):
    for ruta in _archivos(carpeta):
        if ruta.stat().st_size > 5_000_000:
            continue
        datos = ruta.read_bytes()
        if b'\x00' in datos:
            continue
        try:
            yield _rel(carpeta, ruta), datos.decode('utf-8')
        except UnicodeDecodeError:
            continue


# ------------------------------------------------------------------------------------------------------------- qué sale y qué no
def test_la_copia_no_lleva_nada_del_docente(copia):
    carpeta, _ = copia
    for nombre in DEL_DOCENTE:
        assert not (carpeta / nombre).exists(), nombre
    # ni los archivos concretos de docente/ en ningun sitio
    for nombre in ('revisar_entregas.py', 'checklist-docente.md', 'guion-con-tiempos.md', 'publicar_plantilla.py'):
        assert not [p for p in _archivos(carpeta) if p.name == nombre], nombre


def test_la_copia_no_lleva_cachés_ni_git_ni_datos_generados(copia):
    carpeta, _ = copia
    rels = [_rel(carpeta, p) for p in _archivos(carpeta)]
    malos = [r for r in rels if set(r.split('/')) & {'.git', '.pytest_cache', '__pycache__', 'mlruns'}
             or r.endswith(('.db', '.db-wal', '.db-shm', '.pyc')) or '.egg-info' in r]
    assert not malos, malos
    generados = [r for r in rels if r.startswith(GENERADO) and r.rsplit('/', 1)[-1] not in ('.gitkeep', 'referencia.json')]
    assert not generados, generados
    assert (carpeta / 'models' / 'referencia.json').is_file()
    assert (carpeta / 'models' / '.gitkeep').is_file() and (carpeta / 'reports' / '.gitkeep').is_file()
    assert (carpeta / 'data' / 'processed' / '.gitkeep').is_file() and (carpeta / 'data' / 'interim' / '.gitkeep').is_file()


def test_la_copia_conserva_lo_del_alumno(copia):
    carpeta, _ = copia
    for ruta in ('README.md', 'Makefile', 'pyproject.toml', 'requirements-dev.txt', 'cafe_mlops/config.py', 'tests/test_higiene.py',
                 'data/raw/cqi/arabica_data_cleaned.csv', 'data/raw/cqi/SHA256SUMS', 'evidencias/plantilla-evidencias.md',
                 'taller/comprobar_entrega.py', 'taller/guia-detallada.md', 'taller/instrucciones.md', 'taller/criterios-de-evaluacion.md',
                 'taller/slides/index.html', 'taller/slides/pruebas/test_slides.py', '.github/workflows/validar.yml',
                 '.github/workflows/nueva-version.yml', '.github/workflows/comprobar-entrega.yml', 'notebooks'):
        assert (carpeta / ruta).exists(), ruta
    assert len(list((carpeta / 'notebooks').glob('*.ipynb'))) == len(list((RAIZ / 'notebooks').glob('*.ipynb'))) >= 5


def test_estan_los_tres_pdf_y_los_diagramas(copia):
    carpeta, _ = copia
    for pdf in PDF:
        ruta = carpeta / pdf
        assert ruta.is_file() and ruta.read_bytes()[:5] == b'%PDF-', pdf
    diagramas = list((carpeta / 'docs' / 'img').glob('diagrama-*.svg'))
    originales = list((RAIZ / 'docs' / 'img').glob('diagrama-*.svg'))
    assert len(diagramas) >= 3 and len(diagramas) == len(originales)


def test_el_script_imprime_lo_excluido_y_el_numero_de_archivos(copia):
    carpeta, salida = copia
    assert f'Archivos copiados: {len(_archivos(carpeta))}' in salida
    for nombre in ('docente/', '_exploracion/', 'TAREAS.md', 'PLANIFICACION.md'):
        assert nombre in salida


def test_el_destino_debe_estar_vacio_o_no_existir(modulo, tmp_path):
    (tmp_path / 'algo.txt').write_text('x', encoding='utf-8')
    with pytest.raises(SystemExit):
        modulo.publicar(tmp_path)
    with pytest.raises(SystemExit):
        modulo.publicar(RAIZ / 'dentro-del-repositorio')


def test_el_script_no_usa_git():
    texto = SCRIPT.read_text(encoding='utf-8')
    assert 'subprocess' not in texto and not re.search(r'["\']git["\']', texto)


# ------------------------------------------------------------------------------------------------------------- nada personal
def _patrones_personales():
    usuario = (os.environ.get('USERNAME') or os.environ.get('USER') or getpass.getuser() or '').strip()
    pat = [('ruta de Windows de un usuario', re.compile(r'[A-Za-z]:[\\/]+Users[\\/]', re.I)),
           ('ruta de macOS de un usuario', re.compile(r'(?<![\w.])/Users/[A-Za-z]')),
           ('usuario del equipo del docente', re.compile('BK' + '70827', re.I)),
           ('carpeta de trabajo del docente', re.compile('HC-' + 'Cursos', re.I))]
    # el nombre de usuario del equipo que ejecuta la prueba (si es una palabra corriente de 6 o mas letras daria falsos positivos)
    if len(usuario) >= 6 and re.fullmatch(r'[\w.-]+', usuario) and usuario.lower() not in ('runner', 'vscode', 'codespace', 'default', 'student',
                                                                                         'usuario', 'administrator', 'vagrant'):
        pat.append((f'usuario del equipo ({len(usuario)} letras)', re.compile(r'(?<![\w])' + re.escape(usuario) + r'(?![\w])', re.I)))
    return pat


def test_la_copia_no_lleva_rutas_ni_usuarios_personales(copia):
    carpeta, _ = copia
    halladas = []
    for rel, texto in _textos(carpeta):
        for motivo, patron in _patrones_personales():
            m = patron.search(texto)
            if m:
                halladas.append(f'{rel}:{texto.count(chr(10), 0, m.start()) + 1} ({motivo})')
    assert not halladas, '; '.join(halladas)


def _nombres_de_personas():
    nombres = set()
    for archivo in ('arabica_data_cleaned.csv', 'robusta_data_cleaned.csv'):
        with open(RAIZ / 'data' / 'raw' / 'cqi' / archivo, encoding='utf-8', newline='') as f:
            for fila in csv.DictReader(f):
                for columna in ('Owner', 'Owner.1', 'Producer', 'Farm.Name'):
                    valor = (fila.get(columna) or '').strip().lower()
                    if len(valor) >= 8 and ' ' in valor:
                        nombres.add(valor)
    return nombres


def test_la_copia_no_lleva_nombres_de_personas_fuera_de_los_datos_originales(copia):
    carpeta, _ = copia
    nombres = _nombres_de_personas()
    assert len(nombres) > 100
    donde = []
    for rel, texto in _textos(carpeta):
        if rel.startswith(CON_NOMBRES):
            continue
        bajo = texto.lower()
        donde += [f'{rel}: {n!r}' for n in nombres if n in bajo]
    assert not donde, '; '.join(donde[:10])


# ------------------------------------------------------------------------------------------------------------- referencias que se resuelven
def _existe_en_la_copia(carpeta, desde, destino):
    destino = destino.split('#')[0].split('?')[0].strip()
    if not destino:
        return True
    base = carpeta if destino.startswith('/') else (carpeta / desde).parent
    return (base / destino.lstrip('/')).resolve().exists()


def test_el_readme_apunta_a_archivos_que_existen_en_la_copia(copia):
    carpeta, _ = copia
    texto = (carpeta / 'README.md').read_text(encoding='utf-8')
    rotos = []
    for destino in re.findall(r'\]\(([^)\s]+)\)', texto):
        if re.match(r'^(https?:|mailto:|#)', destino):
            continue
        if not _existe_en_la_copia(carpeta, 'README.md', destino):
            rotos.append(destino)
    # rutas escritas entre comillas invertidas que son archivos de la plantilla (no las generadas: se crean al ejecutar)
    for ruta in re.findall(r'`([\w./-]+/[\w.-]+\.(?:md|pdf|py|yml|yaml|json|svg|sql|html|txt|ipynb))`', texto):
        if ruta.startswith(GENERADO) or ruta in ('models/referencia.json',):
            continue
        if not (carpeta / ruta).exists():
            rotos.append(ruta)
    assert not rotos, rotos
    for pdf in PDF:
        assert pdf in texto, f'el README no cita {pdf}'


def test_el_comprobador_de_entrega_y_su_workflow_apuntan_a_archivos_de_la_copia(copia):
    carpeta, _ = copia
    flujo = (carpeta / '.github' / 'workflows' / 'comprobar-entrega.yml').read_text(encoding='utf-8')
    scripts = re.findall(r'run:\s*python\s+(\S+\.py)', flujo)
    assert scripts == ['taller/comprobar_entrega.py']
    for s in scripts:
        assert (carpeta / s).is_file(), s
    assert (carpeta / 'evidencias' / 'plantilla-evidencias.md').is_file()
    assert (carpeta / 'evidencias' / 'capturas').is_dir() and (carpeta / 'evidencias' / 'video').is_dir()
    codigo = (carpeta / 'taller' / 'comprobar_entrega.py').read_text(encoding='utf-8')
    for ruta in re.findall(r"['\"](evidencias/[\w./-]+)['\"]", codigo):
        assert (carpeta / ruta.rstrip('/')).exists(), ruta
    # el comprobador de la copia carga y sus capturas son las de la plantilla de la copia
    espec = importlib.util.spec_from_file_location('comprobar_entrega_copia', carpeta / 'taller' / 'comprobar_entrega.py')
    ce = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(ce)
    plantilla = (carpeta / 'evidencias' / 'plantilla-evidencias.md').read_text(encoding='utf-8')
    assert plantilla.count(ce.MARCADOR) > 0
    assert re.findall(r'^## \d+\. `(\d\d-[a-z0-9-]+)` \(paso \d+\)', plantilla, flags=re.M) == list(ce.CAPTURAS)


def test_los_workflows_de_la_copia_no_citan_archivos_que_faltan(copia):
    carpeta, _ = copia
    for flujo in (carpeta / '.github' / 'workflows').glob('*.yml'):
        texto = flujo.read_text(encoding='utf-8')
        for ruta in re.findall(r'(?:python|pip install -r|cat|-f)\s+((?:[\w.-]+/)*[\w.-]+\.(?:py|txt|lock|yaml|yml))\b', texto):
            if ruta.startswith(GENERADO):
                continue
            assert (carpeta / ruta).exists(), f'{flujo.name}: {ruta}'

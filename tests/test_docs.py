"""Pruebas de T17: la documentación técnica. Cada orden citada existe y los enlaces internos son válidos."""
import re
import importlib.util

import pytest

from auxiliar import RAIZ

DOCS = [RAIZ / 'README.md'] + sorted((RAIZ / 'docs').glob('*.md'))
ESPERADOS = ['README.md', 'docs/modelo-de-datos.md', 'docs/de-notebook-a-python.md', 'docs/api-y-contenedor.md',
             'docs/del-ordenador-al-servicio.md']
# Se escribe en T19 (guía detallada). Mientras no exista, es el único enlace que se permite roto.
PENDIENTES = {'taller/guia-detallada.md'}


def _texto(ruta):
    return ruta.read_text(encoding='utf-8')


def _objetivos_make():
    return set(re.findall(r'^([a-z][a-z-]*):', _texto(RAIZ / 'Makefile'), flags=re.M))


def test_estan_los_cinco_documentos():
    for rel in ESPERADOS:
        assert (RAIZ / rel).is_file(), rel


@pytest.mark.parametrize('ruta', DOCS, ids=lambda r: r.name)
def test_cada_make_citado_existe(ruta):
    objetivos = _objetivos_make()
    citados = set(re.findall(r'`make ([a-z][a-z-]*)', _texto(ruta))) | set(re.findall(r'^make ([a-z][a-z-]*)', _texto(ruta), flags=re.M))
    assert citados - objetivos == set(), f'{ruta.name}: órdenes que no están en el Makefile'


@pytest.mark.parametrize('ruta', DOCS, ids=lambda r: r.name)
def test_cada_modulo_citado_existe(ruta):
    modulos = set(re.findall(r'python -m (cafe_mlops(?:\.[a-z_]+)*)', _texto(ruta)))
    for m in modulos:
        assert importlib.util.find_spec(m) is not None, f'{ruta.name}: {m}'


@pytest.mark.parametrize('ruta', DOCS, ids=lambda r: r.name)
def test_los_enlaces_internos_son_validos(ruta):
    rotos = []
    for destino in re.findall(r'\]\(([^)\s]+)\)', _texto(ruta)):
        if destino.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        sin_ancla = destino.split('#')[0]
        objetivo = (ruta.parent / sin_ancla).resolve()
        rel = objetivo.relative_to(RAIZ.resolve()).as_posix() if RAIZ.resolve() in objetivo.parents else sin_ancla
        if not objetivo.exists() and rel not in PENDIENTES:
            rotos.append(destino)
    assert not rotos, f'{ruta.name}: {rotos}'


@pytest.mark.parametrize('ruta', DOCS, ids=lambda r: r.name)
def test_las_rutas_citadas_en_codigo_existen(ruta):
    """Lo que está entre comillas invertidas y parece una ruta del repositorio (carpeta/archivo con extensión conocida)."""
    inexistentes = []
    for c in set(re.findall(r'`([A-Za-z_.][A-Za-z0-9_./\-]*\.(?:py|sql|md|yml|yaml|json|ipynb|lock|txt|Dockerfile))`', _texto(ruta))):
        if '/' not in c:
            continue
        existe = (RAIZ / c).exists() or (RAIZ / 'cafe_mlops' / c).exists()   # los módulos se citan a veces desde cafe_mlops/
        if not existe and c not in PENDIENTES and not c.startswith(('data/processed', 'data/external', 'models/', 'reports/')):
            inexistentes.append(c)
    assert not inexistentes, f'{ruta.name}: {inexistentes}'


def test_las_cifras_de_las_imagenes_son_las_medidas_en_t15():
    texto = _texto(RAIZ / 'docs' / 'api-y-contenedor.md')
    assert '826 MB' in texto and '213 MB' in texto and '183 MB' in texto and '51 MB' in texto


def test_el_readme_lleva_el_recorrido_de_diez_pasos():
    texto = _texto(RAIZ / 'README.md')
    seccion = texto.split('## El recorrido de despliegue, en 10 líneas')[1].split('\n## ')[0]
    pasos = re.findall(r'^\d+\. ', seccion, flags=re.M)
    assert len(pasos) == 10

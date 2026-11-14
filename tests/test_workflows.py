"""Pruebas ESTATICAS de los workflows de GitHub Actions (T14): parsean los YAML y vigilan permisos minimos, environment, acciones
fijadas, ausencia de secretos propios, de rutas personales y de «!» como negacion en los scripts.

Que NO prueban: que los workflows funcionen en GitHub (publicar en GHCR, abrir el PR y la aprobacion manual solo se ven ejecutandolos:
tarea T15) ni que el nombre de una accion exista; `actionlint` no esta instalado en este equipo (sin verificar).
Usan PyYAML (pyyaml==6.0.3 esta en requirements-dev.txt): sin el, estas pruebas no se pueden ejecutar.
"""
import importlib.util
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from cafe_mlops import config

RAIZ = config.RAIZ
CARPETA = RAIZ / '.github' / 'workflows'
NOMBRES = ('validar.yml', 'nueva-version.yml')


def _cargar(nombre):
    texto = (CARPETA / nombre).read_text(encoding='utf-8')
    doc = yaml.safe_load(texto)
    doc['on'] = doc.pop(True, doc.get('on'))      # PyYAML (YAML 1.1) lee la clave «on» como True
    return doc, texto


@pytest.fixture(params=NOMBRES, scope='module')
def workflow(request):
    doc, texto = _cargar(request.param)
    return request.param, doc, texto


def _pasos(doc):
    for trabajo, datos in doc['jobs'].items():
        for i, paso in enumerate(datos['steps']):
            yield trabajo, i, paso


def _scripts(doc):
    return [(t, i, p['run']) for t, i, p in _pasos(doc) if 'run' in p]


# ------------------------------------------------------------------------------------------------------------- estructura
def test_la_carpeta_solo_tiene_los_workflows_previstos():
    assert sorted(p.name for p in CARPETA.glob('*.y*ml')) == sorted(NOMBRES)


def test_parsean_y_tienen_nombre_y_trabajos(workflow):
    nombre, doc, _ = workflow
    assert doc['name'] and doc['jobs'], nombre
    for trabajo, datos in doc['jobs'].items():
        assert datos['runs-on'] == 'ubuntu-latest', trabajo
        assert isinstance(datos.get('timeout-minutes'), int), f'{trabajo}: sin timeout-minutes'
        assert datos['steps'], trabajo


def test_validar_se_dispara_en_push_pr_y_a_mano():
    doc, _ = _cargar('validar.yml')
    assert {'push', 'pull_request', 'workflow_dispatch'} <= set(doc['on'])


def test_nueva_version_solo_se_lanza_a_mano_con_hasta_2018_por_defecto():
    doc, _ = _cargar('nueva-version.yml')
    assert set(doc['on']) == {'workflow_dispatch'}              # nada de publicar por un push
    hasta = doc['on']['workflow_dispatch']['inputs']['hasta']
    assert str(hasta['default']) == '2018'
    assert {str(o) for o in hasta['options']} == {str(h) for h in config.VERSIONES_DATOS}


# ------------------------------------------------------------------------------------------------------------- permisos minimos
ESCRITURA_PERMITIDA = {      # permiso -> unico trabajo que puede tenerlo
    ('nueva-version.yml', 'publicar'): {'packages'},
    ('nueva-version.yml', 'referencia'): {'contents', 'pull-requests'},
}


def test_permisos_de_nivel_superior_solo_lectura(workflow):
    nombre, doc, _ = workflow
    assert doc['permissions'] == {'contents': 'read'}, nombre


def test_cada_trabajo_declara_sus_permisos_y_solo_escribe_donde_hace_falta(workflow):
    nombre, doc, _ = workflow
    for trabajo, datos in doc['jobs'].items():
        permisos = datos.get('permissions')
        assert isinstance(permisos, dict), f'{trabajo}: sin permissions propios (heredaria los del repositorio)'
        assert permisos.get('contents') in ('read', 'write')
        escritura = {k for k, v in permisos.items() if v == 'write'}
        assert not [k for k, v in permisos.items() if v not in ('read', 'write', 'none')], trabajo
        assert escritura == ESCRITURA_PERMITIDA.get((nombre, trabajo), set()), f'{nombre}:{trabajo} escribe en {sorted(escritura)}'
    assert not re.search(r'write-all|read-all|id-token|actions:\s*write|security-events|deployments', _cargar(nombre)[1])


def test_validar_no_escribe_nada():
    doc, _ = _cargar('validar.yml')
    for datos in doc['jobs'].values():
        assert set(datos['permissions'].values()) == {'read'}


def test_el_pr_y_la_publicacion_estan_en_trabajos_distintos_con_sus_permisos():
    doc, texto = _cargar('nueva-version.yml')
    trabajos = doc['jobs']
    assert set(trabajos) == {'entrenar', 'construir', 'publicar', 'referencia'}
    assert trabajos['publicar']['permissions'] == {'contents': 'read', 'packages': 'write'}
    assert trabajos['referencia']['permissions'] == {'contents': 'write', 'pull-requests': 'write'}
    # «docker push» solo en publicar; «gh pr create» y «git push» solo en referencia
    for trabajo in trabajos:
        todo = '\n'.join(s for t, _, s in _scripts(doc) if t == trabajo)
        assert ('docker push' in todo) == (trabajo == 'publicar'), trabajo
        assert ('gh pr create' in todo) == (trabajo == 'referencia'), trabajo
        assert ('git push' in todo) == (trabajo == 'referencia'), trabajo


# ------------------------------------------------------------------------------------------------------------- aprobacion manual
def test_publicar_pide_el_environment_produccion_y_va_despues_de_probar():
    doc, _ = _cargar('nueva-version.yml')
    publicar = doc['jobs']['publicar']
    env = publicar['environment']
    assert (env['name'] if isinstance(env, dict) else env) == 'produccion'
    assert set(publicar['needs']) == {'entrenar', 'construir'}
    assert 'publicar' in doc['jobs']['referencia']['needs']          # el PR solo se abre si se publico (y se aprobo)
    # ningun otro trabajo usa environment (la aprobacion es una sola, antes de publicar)
    assert [t for t, d in doc['jobs'].items() if 'environment' in d] == ['publicar']


def test_validar_no_publica_ni_usa_environments():
    doc, texto = _cargar('validar.yml')
    assert not any('environment' in d for d in doc['jobs'].values())
    cuerpo = texto.split('\njobs:', 1)[1]       # sin la cabecera, que explica que NO publica
    assert 'docker push' not in cuerpo and 'docker login' not in cuerpo and 'ghcr.io' not in cuerpo


def test_la_comparacion_con_la_referencia_para_el_workflow_con_un_mensaje_claro():
    doc, _ = _cargar('nueva-version.yml')
    pasos = {p['name']: p for p in doc['jobs']['entrenar']['steps'] if 'name' in p}
    comparar = next(p for n, p in pasos.items() if 'Comparar' in n)['run']
    assert 'cafe_mlops.modeling.comparar' in comparar and 'RECHAZADA' in comparar and 'TOLERANCIA_COMPARACION' in comparar
    assert re.search(r'::error title=[^:]+::', comparar) and 'exit 1' in comparar
    # y las etapas siguientes dependen de ese trabajo (si falla, no se construye ni se publica)
    assert 'entrenar' in doc['jobs']['construir']['needs'] and doc['jobs']['construir']['if']


def test_el_pr_sale_de_una_rama_nueva_nunca_de_main_ni_de_develop():
    doc, _ = _cargar('nueva-version.yml')
    script = next(s for t, _, s in _scripts(doc) if t == 'referencia')
    assert 'git checkout -b' in script and 'refs/heads/${rama}' in script
    assert not re.search(r'git push[^\n]*(\bmain\b|\bdevelop\b|\bmaster\b|--force|-f\b)', script)
    assert re.search(r'case "\$rama" in main\|develop', script)


# ------------------------------------------------------------------------------------------------------------- sin secretos propios
def test_no_hay_secretos_propios_solo_el_github_token(workflow):
    nombre, doc, texto = workflow
    usados = set(re.findall(r'secrets\.([A-Za-z0-9_]+)', texto))
    assert usados <= {'GITHUB_TOKEN'}, f'{nombre}: {sorted(usados)}'
    assert not re.search(r'secrets\[|secrets:\s*inherit|toJSON\(secrets\)|\bvars\.', texto)
    assert not re.search(r'(?i)\b(password|passwd|api[_-]?key|pat)\s*[:=]\s*[\'"]?[A-Za-z0-9]{8,}', texto)
    assert not re.search(r'\bgh[pousr]_[A-Za-z0-9]{20,}', texto)       # ningun token pegado


# ------------------------------------------------------------------------------------------------------------- acciones fijadas
def _usos(doc):
    return [p['uses'] for _, _, p in _pasos(doc) if 'uses' in p]


def test_las_acciones_estan_fijadas_y_son_de_github(workflow):
    nombre, doc, _ = workflow
    usos = _usos(doc)
    assert usos
    for uso in usos:
        accion, _, version = uso.partition('@')
        assert accion.startswith('actions/'), f'{nombre}: {uso} (solo acciones oficiales de GitHub)'
        assert re.fullmatch(r'v\d+(\.\d+){0,2}|[0-9a-f]{40}', version), f'{nombre}: {uso} sin version fijada'
    assert not re.search(r'@(main|master|latest|HEAD)\b', yaml.safe_dump(doc))


# ------------------------------------------------------------------------------------------------------------- scripts
def test_los_scripts_no_usan_expresiones_de_github_ni_la_negacion_con_signo(workflow):
    nombre, doc, _ = workflow
    for trabajo, i, script in _scripts(doc):
        assert '${{' not in script, f'{nombre}:{trabajo}[{i}]: pasa los valores por env, no los pegues en el script (inyeccion)'
        for n, linea in enumerate(script.splitlines(), 1):
            if linea.lstrip().startswith('#'):
                continue
            # «set -e» no se detiene ante una orden negada con «!»: se escribe «if ...; then exit 1»
            assert not re.search(r'(^|[;&|({]|\b(if|while|until|elif))\s*!\s', linea), f'{nombre}:{trabajo}[{i}] linea {n}: {linea.strip()}'
            assert not re.search(r'\[\s+!\s', linea), f'{nombre}:{trabajo}[{i}] linea {n}: {linea.strip()}'


def test_el_shell_es_bash_con_pipefail(workflow):
    _, doc, _ = workflow
    assert doc['defaults']['run']['shell'] == 'bash'     # en GitHub: bash -e -o pipefail


def test_las_ordenes_que_citan_existen(workflow):
    nombre, doc, texto = workflow
    # modulos de Python
    for modulo in set(re.findall(r'python -m (cafe_mlops[\w.]*)', texto)):
        assert importlib.util.find_spec(modulo) is not None, modulo
    # archivos de Docker y compose
    for ruta in set(re.findall(r'(?:-f|--file) ((?:deploy|sql|data)/[\w./-]+)', texto)):
        assert (RAIZ / ruta).is_file(), ruta
    for archivo in ('requirements-dev.txt', 'models/referencia.json'):
        assert (RAIZ / archivo).is_file()
    # --hasta con valores previstos
    for valor in re.findall(r'--hasta (\d{4})\b', texto):
        assert int(valor) in config.VERSIONES_DATOS, valor
    # las imagenes de compose son las que construye y prueba el workflow
    compose = yaml.safe_load((RAIZ / 'deploy' / 'docker' / 'compose.yaml').read_text(encoding='utf-8'))
    for servicio in compose['services'].values():
        assert servicio['image'] in ('cafe-api:local', 'cafe-interfaz:local')
        assert servicio['image'] in texto
    # el puerto de la interfaz y los endpoints que se consultan
    assert 'http://127.0.0.1:8090/salud' in texto and '/listo' in texto and '/recomendar' in texto
    assert f':{config.PUERTO_INTERFAZ}/' in texto


def test_las_cifras_se_publican_como_anotaciones_notice(workflow):
    nombre, doc, texto = workflow
    assert '::notice title=' in texto


def test_python_del_workflow_es_el_de_la_imagen():
    dockerfile = (RAIZ / 'deploy' / 'docker' / 'Dockerfile').read_text(encoding='utf-8')
    version = re.search(r'FROM python:(\d+\.\d+)', dockerfile).group(1)
    for nombre in NOMBRES:
        doc, _ = _cargar(nombre)
        for _, _, paso in _pasos(doc):
            if str(paso.get('uses', '')).startswith('actions/setup-python'):
                assert str(paso['with']['python-version']) == version, nombre


def test_el_python_de_los_scripts_compila(workflow):
    """Los bloques «python - <<'FIN' ... FIN» y los «python -c» de una linea son Python valido."""
    nombre, doc, _ = workflow
    bloques = 0
    for trabajo, i, script in _scripts(doc):
        for cuerpo in re.findall(r"<<'FIN'[^\n]*\n(.*?)\nFIN\b", script, flags=re.S):
            compile(cuerpo, f'{nombre}:{trabajo}[{i}]', 'exec')
            bloques += 1
    assert bloques or nombre == 'x'


def test_los_scripts_son_validos_para_bash():
    """`bash -n` (solo sintaxis) sobre cada script, si hay un bash utilizable en este equipo."""
    bash = None
    for candidato in (shutil.which('bash'), r'C:\Program Files\Git\bin\bash.exe'):
        try:
            if candidato and 'GNU bash' in subprocess.run([candidato, '--version'], capture_output=True, text=True, timeout=30).stdout:
                bash = candidato      # solo GNU bash (el «bash» de MKS Toolkit u otros no sirven para comprobar la sintaxis)
                break
        except (OSError, subprocess.SubprocessError):
            continue
    if not bash:
        pytest.skip('no hay GNU bash en este equipo (la sintaxis se comprobara en GitHub)')
    for nombre in NOMBRES:
        doc, _ = _cargar(nombre)
        for trabajo, i, script in _scripts(doc):
            r = subprocess.run([bash, '-n'], input=script, capture_output=True, text=True, timeout=30)
            assert r.returncode == 0, f'{nombre}:{trabajo}[{i}]: {r.stderr}'


# ------------------------------------------------------------------------------------------------------------- documentacion y limpieza
def test_la_cabecera_explica_que_hace_y_que_configura_quien_administra(workflow):
    nombre, _, texto = workflow
    cabecera = '\n'.join(l for l in texto.splitlines()[:60] if l.startswith('#'))
    assert 'QUE HACE' in cabecera and 'QUE CONFIGURA QUIEN ADMINISTRA' in cabecera and 'SIN VERIFICAR' in cabecera, nombre


def test_la_cabecera_de_nueva_version_cita_lo_que_hay_que_configurar():
    _, texto = _cargar('nueva-version.yml')
    cabecera = '\n'.join(l for l in texto.splitlines()[:60] if l.startswith('#'))
    for pista in ('produccion', 'Required reviewers', 'Allow GitHub Actions to create and approve pull requests', 'Public',
                  'GITHUB_TOKEN', 'ghcr.io', 'models/referencia.json'):
        assert pista in cabecera, pista


def test_los_workflows_no_llevan_rutas_personales_ni_nombres_del_curso(workflow):
    nombre, _, texto = workflow
    for prohibido in ('C:' + '\\', 'C:' + '/', '/Users' + '/', '/home' + '/', 'BK' + '70827', 'retencion', 'ia_mlops', 'CURSO_'):
        assert prohibido not in texto, f'{nombre}: {prohibido}'
    assert not re.search(r'github\.com/(?!\$\{GITHUB_REPOSITORY\})[\w-]+/[\w-]+', texto), 'no fijes un repositorio concreto'

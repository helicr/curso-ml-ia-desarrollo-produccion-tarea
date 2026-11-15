"""T19 y T21: la guía detallada, las instrucciones (completas y en breve), los criterios de evaluación, el checklist, la plantilla de
evidencias, la guía de grabación del vídeo, los tres diagramas y los dos PDF (instrucciones en breve y guía detallada).

Qué vigila (cada cosa que un alumno copia, ve o busca tiene que existir y ser cierta):
    - cada orden citada (`make X`, `python -m cafe_mlops...`, archivos de deploy/ y tests/) existe;
    - cada salida marcada como real (bloques ```salida-real y ```salida-real-json) es EXACTAMENTE una de taller/salidas-reales.json;
    - las cifras medidas (tiempos, tamaños, huellas, AUC) son las del JSON y de las notas de la prueba real;
    - las capturas citadas existen, no sobra ninguna en docs/img y las 16 capturas exigidas son las mismas en la guía, la plantilla y las instrucciones;
    - los enlaces internos (y sus anclas) son válidos;
    - ninguna ruta personal, ningún nombre de persona del CSV, ningún marcador pendiente;
    - tono sobrio: sin emojis ni guiones largos; colores de la UNTRM y nada más;
    - los diagramas existen, usan solo la paleta, citan órdenes reales y están en los documentos que dicen citarlos;
    - los dos PDF existen, tienen texto extraíble, portada, pie en todas las páginas, están al día respecto de sus fuentes, y el corto
      tiene entre 8 y 14 páginas.
"""
import importlib.util
import json
import re
import unicodedata
from pathlib import Path

import pytest

from auxiliar import RAIZ
from test_higiene import _nombres_de_personas, _tokens_personales

TALLER = RAIZ / 'taller'
GUIA = TALLER / 'guia-detallada.md'
INSTRUCCIONES = TALLER / 'instrucciones.md'
BREVE = TALLER / 'instrucciones-en-breve.md'
CRITERIOS = TALLER / 'criterios-de-evaluacion.md'
CHECKLIST = TALLER / 'checklist.md'
VIDEO = TALLER / 'guia-grabacion-video.md'
PLANTILLA = RAIZ / 'evidencias' / 'plantilla-evidencias.md'
PDF = TALLER / 'instrucciones-del-trabajo.pdf'          # el resumen corto
PDF_GUIA = TALLER / 'guia-detallada-del-trabajo.pdf'
PDFS = [PDF, PDF_GUIA]
DOCUMENTOS = [GUIA, INSTRUCCIONES, BREVE, CRITERIOS, CHECKLIST, VIDEO, PLANTILLA]
IMG = RAIZ / 'docs' / 'img'
ESCUDO = TALLER / 'img' / 'escudo-untrm.svg'
DIAGRAMAS = [IMG / f'diagrama-{n}.svg' for n in ('recorrido', 'docker', 'cicd')]
URL_PLANTILLA = 'https://github.com/helicr/curso-ml-ia-desarrollo-produccion-tarea'
FECHA = '30/11/2026'
ENTREGA = 'el lunes 30/11/2026, durante ese día'
UNIVERSIDAD = 'Universidad Nacional Toribio Rodríguez de Mendoza de Amazonas (UNTRM)'
PROFESOR = 'Profesor: Helí Campos R'
TITULO = 'Tarea Curso Taller «De Modelo de ML/IA a Producción»'
NUM_PASOS = 24            # pasos 0 a 23


def texto(ruta):
    return ruta.read_text(encoding='utf-8')


def ids(r):
    return r.name


def bloques(txt):
    """[(lenguaje, [líneas sin la sangría])] de los bloques con ``` (también los que están dentro de una lista, con sangría)."""
    res, actual, lang, sangria = [], None, '', 0
    for linea in txt.splitlines():
        m = re.match(r'^(\s*)```(\S*)\s*$', linea)
        if m and actual is None:
            actual, lang, sangria = [], m.group(2), len(m.group(1))
        elif m and actual is not None:
            res.append((lang, actual))
            actual = None
        elif actual is not None:
            actual.append(linea[sangria:] if linea[:sangria].strip() == '' else linea)
    assert actual is None, 'un bloque ``` sin cerrar'
    return res


def modulo_generar_pdf():
    espec = importlib.util.spec_from_file_location('taller_generar_pdf', TALLER / 'generar_pdf.py')
    m = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(m)
    return m


@pytest.fixture(scope='module')
def salidas():
    return json.loads(texto(TALLER / 'salidas-reales.json'))


def normalizar(t):
    """Sin acentos ni espacios y en minúsculas: para comparar texto extraído de un PDF (que parte líneas y palabras)."""
    t = unicodedata.normalize('NFD', t)
    t = ''.join(c for c in t if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', '', t).lower()


# ------------------------------------------------------------------------------------------------------------- existen
def test_estan_todos_los_archivos_de_t19_y_t21():
    for r in DOCUMENTOS + [TALLER / 'generar_pdf.py', TALLER / 'estilo-documento.css', ESCUDO] + PDFS + DIAGRAMAS:
        assert r.is_file(), r
    assert not (TALLER / 'rubrica.md').exists(), 'la rúbrica se llama ahora criterios-de-evaluacion.md'
    assert (RAIZ / 'evidencias' / 'capturas' / '.gitkeep').is_file()
    assert (RAIZ / 'evidencias' / 'video' / '.gitkeep').is_file()


# ------------------------------------------------------------------------------------------------------------- órdenes
def _objetivos_make():
    return set(re.findall(r'^([a-z][a-z-]*):', texto(RAIZ / 'Makefile'), flags=re.M))


@pytest.mark.parametrize('ruta', DOCUMENTOS, ids=ids)
def test_cada_make_citado_existe(ruta):
    txt = texto(ruta)
    citados = set(re.findall(r'`(?:time )?make ([a-z][a-z-]*)', txt))
    for _, lineas in bloques(txt):
        for l in lineas:
            m = re.match(r'^(?:time )?make ([a-z][a-z-]*)', l.strip())
            if m:
                citados.add(m.group(1))
    assert citados - _objetivos_make() == set(), f'{ruta.name}: órdenes que no están en el Makefile'


def test_la_guia_cita_las_ordenes_del_recorrido():
    """El recorrido de la tarea: estas órdenes tienen que estar en la guía, en un bloque copiable."""
    copiables = {l.strip() for lang, ls in bloques(texto(GUIA)) if lang in ('bash', 'sh') for l in ls}
    for orden in ('make verificar', 'time make pipeline', 'make pipeline', 'make comparar', 'make api', 'time make imagenes',
                  "docker image ls 'cafe-*'", 'time make compose-arriba', 'docker compose -f deploy/docker/compose.yaml ps',
                  'make compose-abajo', 'make pipeline HASTA=2018', 'make ayuda'):
        assert orden in copiables, orden


@pytest.mark.parametrize('ruta', DOCUMENTOS, ids=ids)
def test_cada_modulo_citado_existe(ruta):
    for m in set(re.findall(r'python -m (cafe_mlops(?:\.[a-z_]+)*)', texto(ruta))):
        assert importlib.util.find_spec(m) is not None, f'{ruta.name}: {m}'


@pytest.mark.parametrize('ruta', DOCUMENTOS, ids=ids)
def test_las_rutas_del_repositorio_citadas_existen(ruta):
    txt = texto(ruta)
    rutas = set(re.findall(r'(?<![\w/.<-])((?:deploy|tests|docs|taller|sql|notebooks|references|\.devcontainer|\.github)/[A-Za-z0-9_./\-]*[A-Za-z0-9_])', txt))
    inexistentes = sorted(r for r in rutas if not (RAIZ / r).exists())
    assert not inexistentes, f'{ruta.name}: {inexistentes}'


def test_la_orden_de_docker_image_ls_lleva_un_solo_argumento():
    """Hallazgo de la prueba en el Codespace: Docker 29 admite un solo argumento. La guía no puede mandar la forma con dos."""
    for ruta in DOCUMENTOS:
        for lang, lineas in bloques(texto(ruta)):
            if lang in ('bash', 'sh'):
                for l in lineas:
                    assert not re.search(r'docker image ls\s+cafe-api\s+cafe-interfaz', l), f'{ruta.name}: {l}'
    assert "docker image ls 'cafe-*'" in texto(GUIA)


# ------------------------------------------------------------------------------------------------------------- salidas reales
def _lineas_reales(salidas):
    reales = set()
    for p in salidas['pasos'].values():
        if isinstance(p['salida'], list):
            reales |= {l.rstrip() for l in p['salida']}
    return reales


def test_las_salidas_citadas_como_reales_son_las_del_json(salidas):
    reales = _lineas_reales(salidas)
    n = 0
    for lang, lineas in bloques(texto(GUIA)):
        if lang != 'salida-real':
            continue
        n += 1
        no_vacias = [l.rstrip() for l in lineas if l.strip()]
        assert no_vacias, 'bloque salida-real vacío'
        for l in no_vacias:
            assert l == '...' or l in reales, f'no está en salidas-reales.json: {l!r}'
        assert any(l != '...' for l in no_vacias)
    assert n >= 6      # verificar (falla), pipeline, segunda ejecución, comparar, v2, rechazada, aprobada


def test_los_json_citados_como_reales_son_los_del_json(salidas):
    json_reales = [p['salida'] for p in salidas['pasos'].values() if isinstance(p['salida'], dict)]
    n = 0
    for lang, lineas in bloques(texto(GUIA)):
        if lang != 'salida-real-json':
            continue
        n += 1
        assert json.loads('\n'.join(lineas)) in json_reales
    assert n >= 3      # /salud, /listo, /predecir


def test_los_bloques_marcados_como_reales_no_se_mezclan_con_otros():
    """Si un bloque se marca como salida real tiene que ser solo eso: los demás usan `text`, `bash` o `json`."""
    for lang, _ in bloques(texto(GUIA)):
        assert lang in ('bash', 'text', 'salida-real', 'salida-real-json'), lang


def test_los_bloques_de_la_guia_con_salida_del_codespace_estan_marcados_como_medidos():
    """Las cifras que solo salen de la prueba en el Codespace (no del JSON) van en bloques `text`, y se dice que son del Codespace."""
    txt = texto(GUIA)
    for fragmento in ('Python 3.11.13', 'cliente 29.9.3 / servidor 29.9.3 · compose 2.40.3', 'real    0m49.003s', 'real    1m18.367s',
                      'real    0m13.116s', 'Container cafe-api-1  Healthy', '5 de 6 lotes con predicción'):
        assert fragmento in txt, fragmento
    assert txt.count('medido en un Codespace real') >= 4


# ------------------------------------------------------------------------------------------------------------- cifras
def test_las_cifras_medidas_son_las_del_json_y_las_de_la_prueba_real(salidas):
    guia = texto(GUIA)
    ga = salidas['github_actions']
    assert ga['validar']['duracion'] == '7 min 42 s' and '7 min 42 s' in guia
    assert ga['nueva_version_rechazada']['duracion'] == '1 min 34 s' and '1 min 34 s' in guia
    assert ga['nueva_version_aprobada']['duracion'] == '4 min 30 s' and '4 min 30 s' in guia
    assert ga['validar']['pruebas_que_pasan'] == 422 and '422 pasan' in guia
    api, ui = ga['validar']['imagen_cafe_api'], ga['validar']['imagen_cafe_interfaz']
    for valor in (api['tamano'], api['comprimida'], ui['tamano'], ui['comprimida']):
        assert valor in guia, valor
    assert ga['validar']['imagen_cafe_api']['usuario'] == 10001 and '10001' in guia
    r = ga['nueva_version_rechazada']
    for cifra in ('0,7951', '0,8525', '-0,0574', '0,02'):
        assert cifra in guia, cifra
    assert (r['auc_ventana_comun_candidata'], r['auc_ventana_comun_referencia'], r['diferencia']) == (0.7951, 0.8525, -0.0574)
    assert ga['nueva_version_aprobada']['tolerancia'] == 0.1 and '0.10' in guia
    # huellas de datos de la versión 1 y de la versión 2 (las de la prueba real)
    assert 'c83699881a8880b9' in guia
    assert ga['nueva_version_aprobada']['huella_datos'] == 'bebc87b9eddf0199' and 'bebc87b9eddf0199' in guia
    # tiempos medidos en el Codespace (notas de T16)
    for tiempo in ('49 s', '1 min 18 s', '13 s', 'unos 4,5 min'):
        assert tiempo in guia, tiempo
    assert 'v2-bebc87b9eddf0199' in guia


def test_la_guia_dice_que_las_salidas_de_la_api_son_de_la_version_2():
    """Las salidas de la API del JSON se capturaron tras --hasta 2018 (versión 2); la del Codespace será la versión 1: hay que avisarlo."""
    guia = texto(GUIA)
    assert '"version_modelo": "1"' in guia and '"huella_datos": "c83699881a8880b9"' in guia
    assert 'versión 2' in guia and 'bebc87b9eddf0199' in guia


# ------------------------------------------------------------------------------------------------------------- capturas
def _imagenes(txt):
    return re.findall(r'!\[[^\]]*\]\(([^)\s]+)\)', txt)


def test_las_capturas_citadas_existen_y_no_sobra_ninguna():
    citadas = _imagenes(texto(GUIA))
    assert len(citadas) == len(set(citadas)), 'una captura de ejemplo se cita dos veces'
    for c in citadas:
        assert (GUIA.parent / c).resolve().is_file(), c
        assert (GUIA.parent / c).resolve().parent == IMG.resolve(), c
    capturas = [c for c in citadas if c.endswith('.webp')]
    assert len(capturas) == len(set(capturas))
    for c in capturas:
        assert (GUIA.parent / c).resolve().parent == IMG.resolve(), c
    en_disco = {p.name for p in IMG.iterdir() if p.suffix == '.webp'}
    assert {Path(c).name for c in capturas} == en_disco
    assert en_disco == {f'cs-taller-{i:02d}.webp' for i in range(1, 11)}
    # lo demás que hay en docs/img son los tres diagramas (la guía cita los tres)
    assert {p.name for p in IMG.iterdir()} - en_disco - {'.gitkeep'} == {d.name for d in DIAGRAMAS}


@pytest.mark.parametrize('ruta', DOCUMENTOS, ids=ids)
def test_todas_las_imagenes_de_los_documentos_existen(ruta):
    for c in _imagenes(texto(ruta)):
        assert (ruta.parent / c).resolve().is_file(), c


def test_las_capturas_de_ejemplo_pesan_poco():
    assert sum(p.stat().st_size for p in IMG.iterdir() if p.suffix in ('.webp', '.svg')) < 2_000_000


def _capturas_de_la_plantilla():
    return re.findall(r'^## \d+\. `(\d\d-[a-z0-9-]+)` \(paso (\d+)\)', texto(PLANTILLA), flags=re.M)


def test_las_capturas_exigidas_son_las_mismas_en_la_guia_la_plantilla_y_las_instrucciones():
    plantilla = _capturas_de_la_plantilla()
    nombres = [n for n, _ in plantilla]
    assert len(nombres) == 16 and nombres == sorted(nombres)
    assert [int(n[:2]) for n in nombres] == list(range(1, 17))
    guia = texto(GUIA)
    # tabla final de la guía
    tabla = re.findall(r'^\| `(\d\d-[a-z0-9-]+)` \| (\d+) \|', guia, flags=re.M)
    assert tabla == plantilla
    # en cada paso, «Evidencia (captura `nombre`)»
    paso_de = {}
    for bloque in re.split(r'^## (?=Paso \d+ ·)', guia, flags=re.M)[1:]:
        numero = int(re.match(r'Paso (\d+) ·', bloque).group(1))
        for n in re.findall(r'(?:Evidencia \(captura|Captura) `(\d\d-[a-z0-9-]+)`', bloque):
            paso_de[n] = numero
    assert paso_de == {n: int(p) for n, p in plantilla}
    # las instrucciones, la rúbrica y el checklist hablan de 16 capturas y citan la primera y la última
    ins, chk, rub = texto(INSTRUCCIONES), texto(CHECKLIST), texto(CRITERIOS).lower()
    assert '(16)' in ins and '01-fork-renombrado' in ins
    assert 'Las 16 capturas' in chk and '16-paquetes-y-pr' in chk and '01-fork-renombrado' in chk
    assert 'las 16 de la plantilla' in rub
    # el resumen cita las 16, cada una con su paso (el mismo de la plantilla)
    breve = texto(BREVE)
    pares = re.findall(r'`(\d\d-[a-z0-9-]+)` \| (\d+)', breve)
    assert sorted(pares) == sorted(plantilla)


def test_el_video_se_pide_igual_en_todas_partes():
    for r in (INSTRUCCIONES, BREVE, CHECKLIST, PLANTILLA, VIDEO, GUIA):
        t = texto(r)
        assert 'evidencias/video/servicio-en-produccion.mp4' in t, r.name
    for r in (INSTRUCCIONES, BREVE, VIDEO, CHECKLIST):
        t = texto(r)
        assert '50 MB' in t and '2' in t and 'MP4' in t, r.name
    assert re.search(r'2 a 4 minutos|2 y 4 minutos|de 2 a 4', texto(INSTRUCCIONES))


# ------------------------------------------------------------------------------------------------------------- estructura de la guía
def _pasos():
    guia = texto(GUIA)
    partes = re.split(r'^## (?=Paso \d+ ·)', guia, flags=re.M)[1:]
    return {int(re.match(r'Paso (\d+) ·', p).group(1)): p for p in partes}


def test_los_pasos_van_de_0_a_23_sin_huecos():
    assert sorted(_pasos()) == list(range(NUM_PASOS))


@pytest.mark.parametrize('numero', range(NUM_PASOS))
def test_cada_paso_tiene_donde_si_falla_y_decision_de_arquitectura(numero):
    p = _pasos()[numero]
    assert '**Dónde:**' in p
    assert '**Si falla:**' in p
    assert '**Decisión de arquitectura:**' in p
    if numero > 0:
        assert '**Qué debes ver' in p
    # un paso con orden para copiar la muestra en un bloque bash
    if 'make ' in p.split('**Si falla:**')[0] and numero not in (6, 9, 15, 16, 23):
        assert any(lang == 'bash' for lang, _ in bloques(p)), numero


def test_la_guia_recoge_los_fallos_reales_encontrados():
    guia = texto(GUIA)
    for fragmento in ('Confiar en la carpeta y continuar', 'Sign in to GitHub', "docker image ls 'cafe-*'", 'modo de recuperación',
                      'Rebuild Container', 'View Creation Log', 'privados por defecto', 'yarn', '.devcontainer/Dockerfile',
                      'Allow GitHub Actions to create and approve pull requests', 'environment `produccion`', 'desactivados',
                      'Nueva version del modelo', 'Review deployments'):
        assert fragmento in guia, fragmento


def test_la_guia_marca_lo_que_no_se_probo():
    guia = texto(GUIA)
    seccion = guia.split('## Qué se probó y qué no')[1].split('\n## ')[0].lower()
    for fragmento in ('cuadernos', 'mlflow ui en el puerto 5000', 'docker pull', 'cuenta de otro alumno', 'fork'):
        assert fragmento in seccion, fragmento
    assert seccion.count('sin verificar') >= 6
    assert 'probado' in seccion


# ------------------------------------------------------------------------------------------------------------- enlaces
def _slug(titulo):
    s = unicodedata.normalize('NFC', titulo.strip().lower())
    s = re.sub(r'[^\w\- ]', '', s)
    return s.replace(' ', '-')


def _anclas(ruta):
    return {_slug(re.sub(r'[`*]', '', t)) for t in re.findall(r'^#{1,6} (.+?)\s*$', texto(ruta), flags=re.M)}


@pytest.mark.parametrize('ruta', DOCUMENTOS, ids=ids)
def test_los_enlaces_internos_son_validos(ruta):
    rotos = []
    for destino in re.findall(r'\]\(([^)\s]+)\)', texto(ruta)):
        if destino.startswith(('http://', 'https://', 'mailto:')):
            continue
        sin_ancla, _, ancla = destino.partition('#')
        objetivo = ruta if not sin_ancla else (ruta.parent / sin_ancla).resolve()
        if not objetivo.exists():
            rotos.append(destino)
        elif ancla and objetivo.suffix == '.md' and ancla not in _anclas(objetivo):
            rotos.append(destino + ' (ancla)')
    assert not rotos, f'{ruta.name}: {rotos}'


def test_el_readme_enlaza_la_guia_y_las_instrucciones():
    readme = texto(RAIZ / 'README.md')
    assert '(taller/guia-detallada.md)' in readme and '(taller/instrucciones.md)' in readme
    assert 'taller/instrucciones-del-trabajo.pdf' in readme


def test_no_queda_ningun_enlace_pendiente_en_test_docs():
    assert "PENDIENTES = set()" in texto(RAIZ / 'tests' / 'test_docs.py')


# ------------------------------------------------------------------------------------------------------------- datos de la entrega
def test_fecha_url_y_canal_de_entrega():
    for r in (INSTRUCCIONES, BREVE, CRITERIOS, CHECKLIST, PLANTILLA):
        assert FECHA in texto(r), r.name
    for r in (INSTRUCCIONES, BREVE, GUIA):
        assert ENTREGA in texto(r), r.name
    for r in DOCUMENTOS:
        assert 'La hora límite no está definida' not in texto(r), r.name
    assert URL_PLANTILLA in texto(INSTRUCCIONES) and URL_PLANTILLA in texto(GUIA) and URL_PLANTILLA in texto(BREVE)
    for r in DOCUMENTOS:
        t = texto(r)
        for marcador in ('[FECHA A DEFINIR]', '[URL DE LA PLANTILLA]', '[ENLACE DEL FORMULARIO]', '[URL DEL REPOSITORIO PLANTILLA]'):
            assert marcador not in t, f'{r.name}: {marcador}'
        assert 'formulario del curso' not in t.lower() and 'enlace del formulario' not in t.lower(), r.name
    for r in (INSTRUCCIONES, BREVE, PLANTILLA, GUIA):     # el checklist solo dice «por el canal del curso» (abajo)
        t = ' '.join(texto(r).lower().split())
        assert 'google classroom' in t and 'correo del curso' in t and 'chat del grupo' in t, r.name
    assert 'envié el enlace de mi fork por el canal del curso' in texto(CHECKLIST).lower()
    # el nombre del fork y las tres cosas que hace el alumno en su fork
    ins = texto(INSTRUCCIONES)
    assert ins.count('taller-ml-ia-dev-production') >= 3
    for fragmento in ('desactivados', '`produccion`', 'Allow GitHub Actions to create and approve pull requests', 'ghcr.io/<tu-usuario>',
                      'conserva el vínculo', 'público'):
        assert fragmento in ins, fragmento


def test_los_pesos_de_los_criterios_de_evaluacion_son_40_30_30():
    t = texto(CRITERIOS)
    breve = texto(BREVE)
    assert re.search(r'\| Ejecución y reproducibilidad \| 40 \|', breve) and re.search(r'\| Evidencias \| 30 \|', breve)
    assert re.search(r'\| Comprensión \(criterio de arquitecto\) \| 30 \|', breve)
    assert re.search(r'\|\s*1\. Ejecución y reproducibilidad\s*\|\s*40\s*\|', t)
    assert re.search(r'\|\s*2\. Evidencias\s*\|\s*30\s*\|', t)
    assert re.search(r'\|\s*3\. Comprensión \(criterio de arquitecto\)\s*\|\s*30\s*\|', t)

    def suma(titulo, siguiente):
        parte = t.split(titulo)[1].split(siguiente)[0]
        return sum(int(x) for x in re.findall(r'^\|[^|\n]+\|\s*(\d+)\s*\|', parte, flags=re.M))
    assert suma('## 1. Ejecución y reproducibilidad (40)', '## 2.') == 40
    assert suma('## 2. Evidencias (30)', '## 3.') == 30
    assert suma('## 3. Comprensión, criterio de arquitecto (30)', '## Cómo se aplican') == 30


def test_las_instrucciones_piden_el_entregable_del_instructor():
    t = texto(INSTRUCCIONES)
    for fragmento in ('arquitecto', 'fork', 'taller-ml-ia-dev-production', 'MP4', '50 MB', 'con tu voz', 'a través de la interfaz',
                      'Capturas de evidencia', 'público', 'make pipeline', 'make imagenes', 'make compose-arriba', '8090',
                      '`tolerancia` = 0.10', 'hasta', 'Entrega: el lunes 30/11/2026, durante ese día',
                      'instrucciones-del-trabajo.pdf', 'guia-detallada-del-trabajo.pdf', 'criterios-de-evaluacion.md'):
        assert fragmento in t, fragmento


# ------------------------------------------------------------------------------------------------------------- nada personal
@pytest.mark.parametrize('ruta', DOCUMENTOS + [TALLER / 'generar_pdf.py', TALLER / 'estilo-documento.css'], ids=ids)
def test_ninguna_ruta_personal_ni_nombre_de_persona(ruta):
    txt = texto(ruta)
    for motivo, patron in _tokens_personales():
        assert not patron.search(txt), f'{ruta.name}: {motivo}'
    bajo = txt.lower()
    assert not [n for n in _nombres_de_personas() if n in bajo]
    sin_url = txt.replace(URL_PLANTILLA, '').replace('helicr/curso-ml-ia-desarrollo-produccion-tarea', '')
    assert 'helicr' not in sin_url.lower(), f'{ruta.name}: el usuario del instructor solo puede salir en la dirección de la plantilla'
    assert not re.search(r'[A-Za-z]:\\', txt), f'{ruta.name}: ruta de Windows'


# ------------------------------------------------------------------------------------------------------------- tono y colores
EMOJIS = re.compile('[\U0001F300-\U0001FAFF☀-➿⭐✅❌]')
PALETA = {'#003769', '#0063b1', '#002a52', '#00508f', '#d8eaff', '#eef6ff', '#f3f4f6', '#e5e7eb', '#6b7280', '#374151',
          '#f4f4f9', '#1a1a1a', '#636975', '#ffffff', '#fff'}


@pytest.mark.parametrize('ruta', DOCUMENTOS, ids=ids)
def test_tono_sobrio_sin_emojis_ni_guiones_largos(ruta):
    t = texto(ruta)
    assert not EMOJIS.search(t), f'{ruta.name}: emoji o icono'
    assert '—' not in t, f'{ruta.name}: guion largo'


def test_el_estilo_usa_solo_los_colores_de_la_untrm():
    css = texto(TALLER / 'estilo-documento.css')
    colores = {c.lower() for c in re.findall(r'#[0-9a-fA-F]{3,6}\b', css)}
    assert colores <= PALETA, sorted(colores - PALETA)
    for base in ('#003769', '#0063b1', '#002a52', '#00508f', '#d8eaff', '#eef6ff'):
        assert base in colores, base
    assert not re.search(r'gradient', css)


# ------------------------------------------------------------------------------------------------------------- escudo y diagramas
def test_el_escudo_es_solo_el_circulo():
    svg = texto(ESCUDO)
    assert "viewBox='4 0 218 211'" in svg
    assert 'logo-untrm' not in svg and ESCUDO.stat().st_size < 120_000


def _svg(ruta):
    import xml.etree.ElementTree as ET
    return ET.parse(ruta).getroot()


@pytest.mark.parametrize('ruta', DIAGRAMAS, ids=ids)
def test_los_diagramas_son_svg_validos_y_usan_la_paleta(ruta):
    raiz = _svg(ruta)
    assert raiz.tag.endswith('svg') and raiz.get('viewBox')
    contenido = texto(ruta)
    colores = {c.lower() for c in re.findall(r'(?:fill|stroke)="(#[0-9a-fA-F]{3,6})"', contenido)}
    assert colores <= PALETA, sorted(colores - PALETA)
    assert 'http://' not in contenido.replace('http://www.w3.org/2000/svg', '').replace('http://api:8080', '')
    assert not EMOJIS.search(contenido) and '—' not in contenido


def _textos_svg(ruta):
    return ' '.join(''.join(e.itertext()) for e in _svg(ruta).iter() if e.tag.endswith('text'))


def test_los_diagramas_citan_ordenes_y_datos_reales():
    objetivos = _objetivos_make()
    recorrido = _textos_svg(DIAGRAMAS[0])
    for orden in ('make verificar', 'make pipeline', 'make comparar', 'make api', 'make imagenes', 'make compose-arriba', 'make compose-abajo'):
        assert orden in recorrido, orden
        assert orden.split()[1] in objetivos, orden
    for palabra in ('8090', 'Validar', 'Nueva version del modelo'):
        assert palabra in recorrido, palabra
    docker = _textos_svg(DIAGRAMAS[1])
    compose = texto(RAIZ / 'deploy' / 'docker' / 'compose.yaml')
    assert '8090:8090' in compose and 'Sin «ports»' in compose        # solo la interfaz publica un puerto
    assert ':ro' in compose and 'TALLER_URL_API: http://api:8080' in compose
    for fragmento in ('puerto 8090 publicado', 'puerto 8080 sin publicar', 'solo lectura', 'cafe-api', 'cafe-interfaz', 'http://api:8080', '10001'):
        assert fragmento in docker, fragmento
    cicd = _textos_svg(DIAGRAMAS[2])
    for fragmento in ('Validar', 'Nueva version del modelo', 'Puerta 1', 'Puerta 2', 'Rechazada', 'Aprobada', 'produccion', '0,02', '0.10', '0,7951', '0,8525'):
        assert fragmento in cicd, fragmento


def test_los_diagramas_estan_citados_donde_toca():
    for ruta in (BREVE, GUIA):
        t = texto(ruta)
        for d in DIAGRAMAS:
            assert f'../docs/img/{d.name}' in t, f'{ruta.name}: {d.name}'
    assert 'docs/img/diagrama-recorrido.svg' in texto(RAIZ / 'README.md')


# ------------------------------------------------------------------------------------------------------------- los PDF
def test_el_script_del_pdf_se_importa_sin_playwright_y_cita_las_partes_correctas():
    m = modulo_generar_pdf()
    breve, guia = m.DOCUMENTOS
    assert breve['pdf'] == PDF and guia['pdf'] == PDF_GUIA
    assert [p for p, _ in breve['partes']] == ['taller/instrucciones-en-breve.md', 'taller/checklist.md']
    assert [p for p, _ in guia['partes']] == ['taller/guia-detallada.md']
    for doc in m.DOCUMENTOS:
        for p, _ in doc['partes']:
            assert (RAIZ / p).is_file()
        assert len(m.huella_fuentes(doc)) == 16
    assert m.huella_fuentes(breve) != m.huella_fuentes(guia)
    assert m.FECHA_ENTREGA == FECHA and m.REPOSITORIO_PLANTILLA == URL_PLANTILLA and m.TITULO == TITULO and m.UNIVERSIDAD == UNIVERSIDAD
    assert breve['paginas'] == (8, 14)
    # las fuentes incluyen el escudo, el estilo, los tres diagramas (resumen) y las diez capturas (guía)
    nombres_breve = {p.name for p in m.fuentes(breve)}
    assert {'escudo-untrm.svg', 'estilo-documento.css'} | {d.name for d in DIAGRAMAS} <= nombres_breve
    assert {p.name for p in m.fuentes(guia) if p.suffix == '.webp'} == {f'cs-taller-{i:02d}.webp' for i in range(1, 11)}


def test_el_pie_lleva_el_escudo_el_nombre_del_taller_y_la_pagina():
    m = modulo_generar_pdf()
    pie = m.pie()
    assert 'data:image/svg+xml;base64,' in pie and TITULO in pie and PROFESOR in pie and m.PROFESOR == PROFESOR
    assert 'class="pageNumber"' in pie and 'class="totalPages"' in pie and 'Página' in pie


@pytest.mark.parametrize('ruta', PDFS, ids=ids)
def test_el_pdf_existe_y_tiene_cabecera(ruta):
    datos = ruta.read_bytes()
    assert datos.startswith(b'%PDF-') and b'%%EOF' in datos[-2048:]
    assert 100_000 < len(datos) < 25_000_000
    assert b'file:///' not in datos


def _paginas(ruta):
    pypdf = pytest.importorskip('pypdf')
    lector = pypdf.PdfReader(str(ruta))
    return lector, [(p.extract_text() or '') for p in lector.pages]


@pytest.mark.parametrize('ruta', PDFS, ids=ids)
def test_el_pdf_tiene_portada_y_pie_en_todas_las_paginas(ruta):
    lector, paginas = _paginas(ruta)
    n = len(lector.pages)
    assert all(len(t.strip()) > 100 for t in paginas), 'una página sin texto extraíble'
    for i, t in enumerate(paginas, 1):
        plano = normalizar(t)
        assert normalizar(TITULO) in plano, f'página {i}: falta el nombre del taller en el pie'
        assert normalizar(PROFESOR) in plano, f'página {i}: falta «{PROFESOR}» en el pie'
        assert f'pagina{i}de{n}' in plano, f'página {i}: falta «Página {i} de {n}»'
    portada = normalizar(paginas[0])
    assert normalizar(UNIVERSIDAD) in portada and normalizar(FECHA) in portada and normalizar(PROFESOR) in portada
    assert normalizar(PROFESOR) in normalizar(paginas[0].split(FECHA)[1].split('Página')[0]), 'el profesor, en el cuerpo de la portada y no solo en el pie'


def test_el_pdf_corto_tiene_entre_8_y_14_paginas_y_lo_esencial():
    lector, paginas = _paginas(PDF)
    assert 8 <= len(lector.pages) <= 14, len(lector.pages)
    todo = '\n'.join(paginas)
    plano = normalizar(todo)
    for p, _ in modulo_generar_pdf().BREVE['partes']:
        h1 = re.search(r'^# (.+)$', texto(RAIZ / p), flags=re.M).group(1)
        assert normalizar(h1) in plano, h1
    for h2 in re.findall(r'^## (.+)$', texto(BREVE), flags=re.M):
        assert normalizar(re.sub(r'[`*]', '', h2)) in plano, h2
    for fragmento in ('make verificar', 'time make pipeline', 'make compose-arriba', 'Nueva version del modelo', '16-paquetes-y-pr',
                      'servicio-en-produccion.mp4', 'Envié el enlace de mi fork por el canal del curso', ENTREGA,
                      'guia-detallada-del-trabajo.pdf', 'Ejecución y reproducibilidad'):
        assert normalizar(fragmento) in plano, fragmento
    assert 'Rúbrica'.lower() not in todo.lower() and 'rubrica' not in plano


def test_el_pdf_de_la_guia_tiene_los_pasos_y_las_capturas():
    m = modulo_generar_pdf()
    lector, paginas = _paginas(PDF_GUIA)
    minimo, maximo = m.GUIA['paginas']
    assert minimo <= len(lector.pages) <= maximo, len(lector.pages)
    plano = normalizar('\n'.join(paginas))
    h1 = re.search(r'^# (.+)$', texto(GUIA), flags=re.M).group(1)
    assert normalizar(h1) in plano
    for linea in re.findall(r'^## (Paso \d+ · .+)$', texto(GUIA), flags=re.M):
        assert normalizar(re.sub(r'[`*]', '', linea)) in plano, linea
    for fragmento in ('make verificar', 'time make pipeline', 'make compose-arriba', 'Nueva version del modelo', 'c83699881a8880b9',
                      '826 MB', '16-paquetes-y-pr', 'servicio-en-produccion.mp4'):
        assert normalizar(fragmento) in plano, fragmento
    for lang, ls in bloques(texto(GUIA)):
        if lang == 'salida-real':
            for l in ls:
                if l.strip() and l.strip() != '...':
                    assert normalizar(l)[:60] in plano, l
                    break
    imagenes = sum(len(p.images) for p in lector.pages)
    assert imagenes >= 10, imagenes


@pytest.mark.parametrize('doc_nombre', ['BREVE', 'GUIA'])
def test_el_pdf_esta_al_dia_y_sin_datos_personales(doc_nombre):
    m = modulo_generar_pdf()
    doc = getattr(m, doc_nombre)
    lector, paginas = _paginas(doc['pdf'])
    assert lector.metadata.get('/Subject') == f'fuentes:{m.huella_fuentes(doc)}', 'regenera los PDF: python -I taller/generar_pdf.py'
    assert 'Producción' in lector.metadata.get('/Title', '')
    errores, _ = m.comprobar(doc)
    assert errores == []
    todo = '\n'.join(paginas)
    for motivo, patron in _tokens_personales():
        assert not patron.search(todo), motivo
    assert not re.search(r'[A-Za-z]:\\', todo)
    plano = re.sub(r'\s+', '', todo).lower()
    assert not re.search(r'helicr(?!/curso-ml-ia-desarrollo-produccion-tarea)', plano), 'el usuario del instructor solo sale en la dirección de la plantilla'
    bajo = todo.lower().replace('\n', ' ')
    assert not [n for n in _nombres_de_personas() if n in bajo]

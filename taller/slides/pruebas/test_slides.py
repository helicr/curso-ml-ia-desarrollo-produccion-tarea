"""T20: pruebas de las diapositivas de la tarea (sin navegador).

Qué vigilan: que index.html y las imágenes copiadas están al día con generar.py (--comprobar); título, parte, minutos y notas de cada
diapositiva; el pie (escudo, nombre del taller y profesor); que nada se pide a un servidor externo; que cada orden copiable existe en el
Makefile o en los módulos del proyecto; que las cifras son las medidas (guía detallada y TAREAS.md) y no hay otras; que las capturas
citadas existen y no sobra ninguna; que los SVG tienen ids de marcador únicos; que las 16 capturas son las de la plantilla de evidencias;
los enlaces desde las instrucciones y el README; y el PDF (una página por diapositiva y al día).
El aspecto (que nada se salga del marco) se revisa en un navegador real: ver generar.py y generar_pdf.py.

Ejecutar desde la raíz:  python -m pytest taller/slides/pruebas -q
"""
import hashlib
import importlib.util
import re
import subprocess
import sys
from html import unescape
from pathlib import Path

import pytest

AQUI = Path(__file__).resolve().parents[1]
RAIZ = AQUI.parents[1]
TALLER = RAIZ / 'taller'
PDF = TALLER / 'diapositivas-del-trabajo.pdf'

_spec = importlib.util.spec_from_file_location('generar_diapositivas', AQUI / 'generar.py')
G = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(G)


def leer(ruta):
    return Path(ruta).read_text(encoding='utf-8')


@pytest.fixture(scope='module')
def html():
    return leer(AQUI / 'index.html')


def secciones(texto):
    return re.findall(r'<section class="slide"([^>]*)>(.*?)</section>', texto, re.S)


def texto_visible(cuerpo):
    return unescape(re.sub(r'<[^>]+>', ' ', cuerpo))


def todo_el_texto(html):
    """Lo que se lee en pantalla y en las notas del ponente (para las cifras)."""
    visible = ' '.join(texto_visible(c) for _, c in secciones(html))
    notas = ' '.join(unescape(n) for n in re.findall(r'data-notes="([^"]*)"', html))
    return re.sub(r'\s+', ' ', visible + ' ' + notas)


# ----------------------------------------------------------------------------------------------------------------- al día
def test_esta_al_dia_con_el_generador(html):
    assert html == G.html_completo(), 'index.html no coincide con generar.py: ejecuta  python taller/slides/generar.py'
    assert G.imagenes_al_dia(), 'las imágenes de slides/img no son las de docs/img: ejecuta  python taller/slides/generar.py'


def test_comprobar_sale_con_cero():
    r = subprocess.run([sys.executable, '-I', str(AQUI / 'generar.py'), '--comprobar'], capture_output=True, text=True)
    assert r.returncode == 0 and 'al día' in r.stdout, r.stdout + r.stderr


# ----------------------------------------------------------------------------------------------------------------- estructura
def test_cada_diapositiva_tiene_titulo_parte_minutos_y_notas(html):
    s = secciones(html)
    assert 14 <= len(s) <= 18, len(s)
    total = 0
    for attrs, cuerpo in s:
        assert re.search(r'data-part="[ABCD]"', attrs) and re.search(r'data-title="[^"]+"', attrs), attrs[:80]
        assert re.search(r'<h1>[^<]+', cuerpo), f'sin título visible: {attrs[:80]}'
        notas = re.search(r'data-notes="([^"]*)"', attrs).group(1)
        assert len(notas) > 80, f'notas del ponente demasiado cortas: {attrs[:80]}'
        minutos = int(re.search(r'data-min="(\d+)"', attrs).group(1))
        assert minutos >= 1
        total += minutos
    assert 25 <= total <= 30, total
    assert f'{total} minutos' in html                      # la portada dice cuánto dura


def test_las_cuatro_partes_estan_en_la_barra_y_en_las_diapositivas(html):
    partes = set(re.findall(r'data-part="([ABCD])"', html))
    assert partes == {'A', 'B', 'C', 'D'}
    for p in partes:
        assert f'<button class="part" data-p="{p}">' in html


def test_las_teclas_y_las_notas_del_marco(html):
    for trozo in ("k==='ArrowRight'", "k==='ArrowLeft'", "k==='o'||k==='O'", "k==='s'||k==='S'", "k==='f'||k==='F'",
                  'id="notes"', 'id="index"', 'id="bfull"', 'data-notes='):
        assert trozo in html, trozo


def test_el_pie_lleva_escudo_taller_y_profesor_en_cada_diapositiva(html):
    for attrs, cuerpo in secciones(html):
        pie = re.search(r'<div class="foot">(.*?)</div>', cuerpo, re.S)
        assert pie, attrs[:80]
        assert 'src="img/escudo-untrm.svg"' in pie.group(1), attrs[:80]
        assert 'Tarea Curso Taller «De Modelo de ML/IA a Producción»' in unescape(pie.group(1))
        assert 'Profesor: Helí Campos R' in unescape(pie.group(1))


def test_la_paleta_es_la_de_la_untrm_y_sin_colores_ajenos(html):
    css = re.search(r'<style>(.*?)</style>', html, re.S).group(1)
    for color in ('#003769', '#0063b1', '#002a52', '#f3f4f6', '#e5e7eb', '#6b7280', '#374151', '#f4f4f9', '#1a1a1a'):
        assert color in css, color
    # ningún tono verde o naranja: los colores hexadecimales del CSS y de los SVG se miran por su matiz
    import colorsys
    for h in set(re.findall(r'#([0-9a-fA-F]{6})\b', html)):
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        tono, sat, val = colorsys.rgb_to_hsv(r, g, b)
        if sat > 0.25 and val > 0.2:
            assert not (0.05 <= tono <= 0.45), f'#{h} es naranja, amarillo o verde'    # 18 a 162 grados


def test_sin_emojis_ni_rayas_largas_ni_rutas_personales(html):
    visible = todo_el_texto(html)
    assert not re.search('[\U0001F000-\U0001FAFF☀-➿⬀-⯿]', visible.replace('⧉', '')), 'emoji'
    assert '—' not in html and '–' not in visible, 'raya larga o media'
    assert not re.search(r'[A-Za-z]:\\|/Users/|/home/|AppData|BK\d{5}', html), 'ruta personal'


# ----------------------------------------------------------------------------------------------------------------- sin recursos externos
def test_sin_recursos_externos(html):
    assert not re.search(r'<(script|link|img|iframe|source|video|audio)\b[^>]*\b(src|href)="(https?:)?//', html)
    assert not re.search(r'\b(src|href)="https?://', html), 'ningún enlace ni recurso externo'
    assert not re.search(r'url\(\s*["\']?(https?:)?//', html) and '@import' not in html
    assert not re.search(r'<script[^>]*\bsrc=', html) and '<link' not in html


# ----------------------------------------------------------------------------------------------------------------- imágenes
def test_las_capturas_citadas_existen_y_no_sobra_ninguna(html):
    citadas = set(re.findall(r'src="img/([^"]+)"', html))
    en_disco = {p.name for p in (AQUI / 'img').iterdir() if p.is_file()}
    assert citadas == en_disco, f'citadas sin archivo: {citadas - en_disco}; archivos sin usar: {en_disco - citadas}'
    assert citadas == set(G.CAPTURAS) | {G.ESCUDO}
    for c in G.CAPTURAS:
        assert f'<a class="capa" href="img/{c}"' in html, f'{c} no se abre a tamaño completo'     # a tamaño completo
        assert (RAIZ / 'docs' / 'img' / c).read_bytes() == (AQUI / 'img' / c).read_bytes(), c      # copia exacta
    assert (TALLER / 'img' / G.ESCUDO).read_bytes() == (AQUI / 'img' / G.ESCUDO).read_bytes()
    # y todo enlace local de la presentación apunta a algo que existe
    for ref in set(re.findall(r'\bhref="([^"#]+)"', html)):
        assert (AQUI / ref).exists(), ref


def test_los_tres_diagramas_estan_en_linea_con_ids_de_marcador_unicos(html):
    assert html.count('aria-label="Recorrido de punta a punta') == 1
    assert html.count('aria-label="Las dos piezas en Docker') == 1
    assert html.count('aria-label="CI/CD en GitHub Actions') == 1
    ids = re.findall(r'<marker id="([^"]+)"', html)
    assert len(ids) == 3 and len(ids) == len(set(ids)), f'ids de marcador repetidos: el navegador pinta flechas sin punta ({ids})'
    refs = re.findall(r'url\(#([^)]+)\)', html)
    assert refs and set(refs) <= set(ids), set(refs) - set(ids)
    # cada flecha (marker-end) usa el marcador de su propia diapositiva
    for attrs, cuerpo in secciones(html):
        propios = set(re.findall(r'<marker id="([^"]+)"', cuerpo))
        usados = set(re.findall(r'url\(#([^)]+)\)', cuerpo))
        assert usados <= propios, attrs[:80]
    # los diagramas son los de docs/img (los que usan los PDF): mismos textos
    for nombre in ('diagrama-recorrido.svg', 'diagrama-docker.svg', 'diagrama-cicd.svg'):
        for t in re.findall(r'<text [^>]*>([^<]+)</text>', leer(RAIZ / 'docs' / 'img' / nombre))[:6]:
            assert t in html, (nombre, t)


# ----------------------------------------------------------------------------------------------------------------- órdenes
def ordenes_copiables(html):
    return re.findall(r'<div class="tln(?: solo)?"><span class="ps">\$</span> <code>(.*?)</code><button class="cp" data-t="(.*?)"', html)


def test_cada_orden_tiene_su_boton_de_copiar_con_la_misma_orden(html):
    ordenes = ordenes_copiables(html)
    assert len(ordenes) >= 12
    for visible, copiar in ordenes:
        assert visible == copiar
    # «Copiar todo» copia exactamente las órdenes (no los comentarios) de su terminal
    for term in re.findall(r'<div class="term">(.*?)</div></div>', html, re.S):
        todo = re.search(r'class="cp cpall" data-t="(.*?)"', term, re.S).group(1)
        lineas = [m[1] for m in re.findall(r'<code>(.*?)</code><button class="cp" data-t="(.*?)"', term)]
        assert unescape(todo) == '\n'.join(unescape(l) for l in lineas)


def test_cada_orden_existe_en_el_makefile_o_en_los_modulos(html):
    makefile = leer(RAIZ / 'Makefile')
    objetivos = set(re.findall(r'^([a-z-]+):', makefile, re.M))
    variables = set(re.findall(r'^([A-Z_]+) \?=', makefile, re.M))
    vistas = set()
    for _, copiar in ordenes_copiables(html):
        orden = unescape(copiar)
        sin_time = re.sub(r'^time ', '', orden)
        vistas.add(sin_time.split()[0])
        if sin_time.startswith('make '):
            partes = sin_time.split()[1:]
            assert partes[0] in objetivos, f'make {partes[0]} no está en el Makefile'
            for extra in partes[1:]:
                nombre = extra.split('=')[0]
                assert '=' in extra and nombre in variables, f'variable {nombre} no está en el Makefile'
            if len(partes) > 1:      # la variable se lee en la regla de ese objetivo
                regla = re.search(rf'^{partes[0]}:.*?(?=^\S|\Z)', makefile, re.M | re.S).group(0)
                assert all(f'$({e.split("=")[0]}' in regla or f'$(origin {e.split("=")[0]}' in regla for e in partes[1:]), orden
        elif sin_time.startswith('python -m '):
            modulo = sin_time.split()[2]
            fuente = RAIZ / (modulo.replace('.', '/') + '.py')
            assert fuente.is_file(), modulo
            for opcion in re.findall(r'(--[a-z-]+)', sin_time):
                assert f"'{opcion}'" in leer(fuente), (modulo, opcion)
        elif sin_time.startswith('docker compose -f '):
            assert (RAIZ / sin_time.split()[3]).is_file(), sin_time
            assert 'ps' in sin_time.split()
        elif sin_time.startswith('docker image ls '):
            assert sin_time == "docker image ls 'cafe-*'"                  # un solo argumento (Docker 29)
            assert re.search(r'cafe-api:local.*cafe-interfaz:local|-t cafe-api:local', makefile, re.S)
        elif sin_time.startswith('git '):
            assert sin_time in ('git add evidencias', 'git commit -m "Evidencias de la tarea"', 'git push')
            assert (RAIZ / 'evidencias').is_dir() and sin_time in leer(TALLER / 'guia-detallada.md').replace('   ', '') \
                or sin_time.split()[1] in leer(TALLER / 'guia-detallada.md')
        else:
            pytest.fail(f'orden que no se sabe comprobar: {orden}')
    assert {'make', 'python', 'docker', 'git'} <= vistas


def test_los_archivos_y_carpetas_que_se_citan_existen(html):
    texto = todo_el_texto(html)
    citadas = set(re.findall(r'(?<![\w/.<-])((?:taller|docs|evidencias|deploy)/[A-Za-z0-9_./\-]*[A-Za-z0-9_])', texto))
    assert {'taller/criterios-de-evaluacion.md', 'taller/guia-detallada.md', 'taller/instrucciones.md', 'taller/checklist.md',
            'evidencias/video/servicio-en-produccion.mp4', 'evidencias/capturas', 'deploy/docker/compose.yaml'} <= citadas | {'evidencias/capturas'}
    for c in citadas:
        if c == 'evidencias/video/servicio-en-produccion.mp4':
            assert (RAIZ / 'evidencias' / 'video').is_dir()      # el vídeo lo pone el alumno; su carpeta ya viene en la plantilla
        else:
            assert (RAIZ / c).exists(), c


# ----------------------------------------------------------------------------------------------------------------- cifras
def fuentes_de_cifras():
    fuentes = [leer(TALLER / 'guia-detallada.md')]
    if (RAIZ / 'TAREAS.md').exists():           # se retira de la plantilla en T24: entonces basta la guía
        fuentes.append(leer(RAIZ / 'TAREAS.md'))
    return fuentes


def test_las_cifras_citadas_son_las_medidas():
    guia = leer(TALLER / 'guia-detallada.md')
    for visto, fuente in G.CIFRAS.items():
        assert fuente in guia, f'«{visto}» no está en la guía detallada como «{fuente}»'
    todas = ' '.join(fuentes_de_cifras())
    if (RAIZ / 'TAREAS.md').exists():
        medidas = ('49 s', '1 min 18 s', '13 s', '826 MB', '213 MB', 'c83699881a8880b9', '0,7951', '0,8525', '0,02')
        for m in medidas:
            assert m in todas.replace('0.7951', '0,7951').replace('0.8525', '0,8525'), m


def test_todas_las_cifras_citadas_estan_en_la_lista_de_cifras(html):
    visible = todo_el_texto(html)
    permitidas = ' '.join(G.CIFRAS) + ' 50 MB 5 min 0.10 3.11 Docker 29'
    unidades = re.compile(r'\b\d+(?:,\d+)? (?:min|s|MB)\b')
    for u in unidades.findall(visible):
        assert u in permitidas, f'cifra con unidad que no es una medida de la lista: {u}'
    normal = lambda t: t.replace('.', ',')
    decimales = {normal(d) for d in re.findall(r'(?<![\w.])\d+[.,]\d+(?![\w])', visible)}
    ok = {normal(d) for d in re.findall(r'\d+[.,]\d+', permitidas)}
    assert decimales <= ok, f'decimales que no son una medida de la lista: {decimales - ok}'
    huellas = set(re.findall(r'\b[0-9a-f]{16}\b', visible))
    assert huellas <= {'c83699881a8880b9'}, huellas
    for visto in G.CIFRAS:
        assert visto in visible, f'la cifra «{visto}» ya no se cita: quítala de CIFRAS'


def test_las_cifras_de_cada_afirmacion_son_las_de_la_guia(html):
    visible = todo_el_texto(html)
    for trozo in ('49 s', '1 min 18 s', '13 s', '826 MB', '213 MB', 'c83699881a8880b9', '0,7951', '0,8525', '-0,0574',
                  '7 min 42 s', '1 min 34 s', '4 min 30 s', '5 lotes sin especialidad', '0,49 a 1,00', '5 de 6 lotes', '1190',
                  'cuatro caminos', 'versión 1', 'gradient_boosting'):
        assert trozo in visible, trozo
    # puerto, usuario y tolerancia de la aprobación
    assert '8090' in visible and 'tolerancia' in visible and '= 0.10' in visible


# ----------------------------------------------------------------------------------------------------------------- contenido pedido
def test_las_16_capturas_son_las_de_la_plantilla_y_las_instrucciones(html):
    plantilla = leer(RAIZ / 'evidencias' / 'plantilla-evidencias.md')
    breve = leer(TALLER / 'instrucciones-en-breve.md')
    guia = leer(TALLER / 'guia-detallada.md')
    nombres = [n for n, _ in G.LAS_16]
    assert len(nombres) == 16 and len(set(nombres)) == 16
    for n in nombres:
        assert n in plantilla and n in breve and n in guia, n
        assert f'<span class="mono">{n}</span>' in html, n
    # y el paso de cada una es el de la guía (tabla «Lista de capturas que se piden»)
    for n, paso in G.LAS_16:
        assert re.search(rf'\| `{re.escape(n)}` \| {paso} \|', guia), (n, paso)
    en_plantilla = re.findall(r'`(\d\d-[a-z0-9-]+)`', plantilla)
    assert nombres == [x for i, x in enumerate(en_plantilla) if x not in en_plantilla[:i]][:16]


def test_los_pasos_citados_son_los_de_la_guia(html):
    guia = leer(TALLER / 'guia-detallada.md')
    for paso, texto in ((17, 'Habilitar GitHub Actions'), (19, 'Preparar el environment'), (16, 'Llegan lotes nuevos'),
                        (23, 'Entregar'), (22, 'Comprobar los paquetes')):
        assert re.search(rf'## Paso {paso} · {texto}', guia), (paso, texto)
    visible = todo_el_texto(html)
    for paso in ('paso 17', 'paso 19', 'pasos 17 a 22', 'paso 23'):
        assert paso in visible, paso


def test_lo_que_se_pide_es_lo_que_piden_las_instrucciones(html):
    ins = leer(TALLER / 'instrucciones.md')
    visible = todo_el_texto(html)
    for trozo in ('2 a 4 minutos', 'con tu voz', '50 MB', 'servicio-en-produccion.mp4', G.FORK, '30/11/2026', 'Google Classroom',
                  'chat del grupo', 'correo del curso', 'Restricted'.replace('Restricted', 'Confiar en la carpeta y continuar'),
                  'View Creation Log', 'Rebuild Container', "docker image ls 'cafe-*'",
                  'I understand my workflows, go ahead and enable them', 'Allow GitHub Actions to create and approve pull requests',
                  'Helí Campos R'):
        assert trozo in visible, trozo
    assert G.FORK in ins and G.PLANTILLA in ins and G.PLANTILLA.replace('https://', '') in html
    assert '40' in visible and '30' in visible and 'Ejecución y reproducibilidad' in visible and 'Comprensión' in visible
    criterios = leer(TALLER / 'criterios-de-evaluacion.md')
    assert '| 1. Ejecución y reproducibilidad | 40 |' in criterios and '| 3. Comprensión (criterio de arquitecto) | 30 |' in criterios


def test_el_tono_es_sobrio(html):
    visible = todo_el_texto(html).lower()
    for palabra in ('increíble', 'revolucion', 'potente', 'fantástic', 'sin esfuerzo', 'transform', '!'):
        assert palabra not in visible, palabra


# ----------------------------------------------------------------------------------------------------------------- enlaces
def test_las_instrucciones_y_el_readme_enlazan_las_diapositivas():
    ins = leer(TALLER / 'instrucciones.md')
    readme = leer(RAIZ / 'README.md')
    assert '(slides/index.html)' in ins, 'instrucciones.md debe enlazar slides/index.html'
    assert 'diapositivas-del-trabajo.pdf' in ins
    assert '(taller/slides/index.html)' in readme and 'taller/diapositivas-del-trabajo.pdf' in readme
    # el enlace de vuelta de las diapositivas existe
    assert (TALLER / 'instrucciones.md').is_file()


# ----------------------------------------------------------------------------------------------------------------- PDF
def normalizar(t):
    return re.sub(r'[^a-z0-9]', '', t.lower().translate(str.maketrans('áéíóúüñ', 'aeiouun')))


def test_el_pdf_existe_tiene_una_pagina_por_diapositiva_y_esta_al_dia(html):
    assert PDF.is_file(), 'falta taller/diapositivas-del-trabajo.pdf: python -I taller/slides/generar_pdf.py'
    datos = PDF.read_bytes()
    assert datos.startswith(b'%PDF-') and b'%%EOF' in datos[-2048:]
    pypdf = pytest.importorskip('pypdf')
    lector = pypdf.PdfReader(str(PDF))
    n = len(secciones(html))
    assert len(lector.pages) == n
    assert lector.metadata['/HuellaIndex'] == hashlib.sha256((AQUI / 'index.html').read_bytes()).hexdigest()[:16], \
        'el PDF no corresponde a este index.html: python -I taller/slides/generar_pdf.py'
    for i, pag in enumerate(lector.pages, 1):
        plano = normalizar(pag.extract_text() or '')
        assert normalizar('Tarea Curso Taller «De Modelo de ML/IA a Producción»') in plano, f'página {i}: falta el pie'
        assert normalizar('Profesor: Helí Campos R') in plano, f'página {i}: falta el profesor'
        assert 'copiartodo' not in plano, f'página {i}: salió un botón de copiar'
    assert len(lector.outline) == n
    assert PDF.stat().st_size < 6_000_000

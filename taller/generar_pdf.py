"""Genera los dos PDF del alumno a partir del Markdown del taller (la fuente es siempre el Markdown: los PDF no se editan a mano).

    taller/instrucciones-del-taller.pdf   el resumen corto, con diagramas (de 8 a 14 páginas):
                                              taller/instrucciones-en-breve.md, taller/checklist.md
    taller/guia-detallada.pdf             la guía completa paso a paso, con las capturas de ejemplo (docs/img):
                                              taller/guia-detallada.md

Los dos llevan portada con el escudo de la UNTRM y, en todas las páginas, un pie con el escudo, el nombre del taller, el profesor y «Página x de y».
(Los criterios de evaluación, la guía de grabación del vídeo y la plantilla de evidencias se consultan en el repositorio.)

Cómo se hace: pandoc (GFM) convierte cada documento a HTML; se le pone el estilo de taller/estilo-documento.css; Chrome (playwright)
lo imprime en A4 con pie de página; pypdf le pone los metadatos. En los metadatos (/Subject) queda la huella de las fuentes de cada PDF,
y la prueba tests/test_guia.py la compara con las fuentes actuales: si cambias un Markdown, un estilo, un diagrama o una captura sin
regenerar los PDF, la prueba falla.

Uso (desde la raíz del repositorio):
    python -I taller/generar_pdf.py               genera los dos PDF
    python -I taller/generar_pdf.py --comprobar   no genera nada: dice si los PDF están al día y cuántas páginas tienen

Necesita un Python con `playwright`, `pypdf` y `pygments`, Google Chrome (o Microsoft Edge) y `pandoc`:
    - pandoc: el del PATH, o la ruta en la variable de entorno PANDOC;
    - Chrome: el del sistema (playwright canal «chrome», con «msedge» como alternativa), o la ruta en PDF_CHROME;
    - si `pypdf` (u otro paquete) está en una carpeta que no ve el intérprete, con `-I` se ignora PYTHONPATH: usa la variable
      TALLER_PDF_RUTAS (carpetas separadas por el separador de rutas del sistema), que este script añade a sys.path.
"""
import argparse
import base64
import hashlib
import html
import io
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

RAIZ = Path(__file__).resolve().parents[1]
TALLER = Path(__file__).resolve().parent
CSS = TALLER / 'estilo-documento.css'
ESCUDO = TALLER / 'img' / 'escudo-untrm.svg'
REPOSITORIO_PLANTILLA = 'https://github.com/helicr/curso-ml-ia-desarrollo-produccion-tarea'
RAMA = 'main'

TITULO = 'Tarea Curso Taller «De Modelo de ML/IA a Producción»'
UNIVERSIDAD = 'Universidad Nacional Toribio Rodríguez de Mendoza de Amazonas (UNTRM)'
FECHA_ENTREGA = '30/11/2026'
PROFESOR = 'Profesor: Helí Campos R'

# Los dos PDF. `partes`: (archivo, título corto), en el orden del PDF. `h2_en_pagina_nueva`: archivos cuyos apartados (##) empiezan página.
BREVE = {
    'nombre': 'breve',
    'pdf': TALLER / 'instrucciones-del-taller.pdf',
    'subtitulo': 'Instrucciones del alumno',
    'partes': [
        ('taller/instrucciones-en-breve.md', 'Instrucciones en breve'),
        ('taller/checklist.md', 'Checklist'),
    ],
    'h2_en_pagina_nueva': {'taller/instrucciones-en-breve.md'},
    'paginas': (8, 14),
}
GUIA = {
    'nombre': 'guia',
    'pdf': TALLER / 'guia-detallada.pdf',
    'subtitulo': 'Guía detallada',
    'partes': [
        ('taller/guia-detallada.md', 'Guía detallada'),
    ],
    'h2_en_pagina_nueva': set(),
    'paginas': (20, 80),
}
DOCUMENTOS = [BREVE, GUIA]

# Se añaden a sys.path las carpetas de TALLER_PDF_RUTAS (con `python -I` no se lee PYTHONPATH).
for _r in filter(None, os.environ.get('TALLER_PDF_RUTAS', '').split(os.pathsep)):
    if _r not in sys.path:
        sys.path.append(_r)

CSS_EXTRA = """
.parte{break-before:page}
.portada{break-after:page;padding-top:22mm}
.portada img.escudo{display:block;width:52mm;height:auto;margin:0 0 14mm}
.portada .universidad{font-size:13pt;color:var(--blue);font-weight:600;line-height:1.3;margin:0 0 22mm;max-width:130mm}
.portada h1{font-size:27pt;line-height:1.18;border:0;padding:0;margin:0 0 7mm;max-width:150mm}
.portada .sub{font-size:15pt;color:var(--blue800);margin:0 0 4mm}
.portada .fecha{font-size:11pt;color:var(--muted);margin:0 0 2mm}
.portada .profesor{font-size:11pt;color:var(--muted);margin:0}
.portada + .parte{break-before:auto}
.resumen h2{break-before:page;margin-top:0}
.resumen table{font-size:8.5pt;line-height:1.3;margin:6pt 0 8pt}
.resumen td{padding:2.6pt 5.5pt}
.resumen th{padding:3pt 5.5pt}
.resumen h1 + h2{break-before:auto;margin-top:10pt}
figure{margin:7pt 0 10pt;text-align:center;break-inside:avoid}
figure img{display:block;margin:0 auto;max-width:90%;max-height:96mm;border:.6pt solid var(--line)}
figure.diagrama{margin:6pt 0 12pt}
figure.diagrama img{width:100%;max-width:100%;max-height:178mm;height:auto;border:0}
figcaption{font-size:8.4pt;color:var(--muted);margin-top:3pt}
img{max-width:100%}
"""


# ---------------------------------------------------------------------------------------------------- fuentes y huella
def fuentes(doc):
    """Todo lo que, si cambia, cambia el PDF: los Markdown, el estilo, el escudo y las imágenes que citan los Markdown."""
    rutas = [RAIZ / p for p, _ in doc['partes']] + [CSS, ESCUDO]
    for p, _ in doc['partes']:
        texto = (RAIZ / p).read_text(encoding='utf-8')
        base = PurePosixPath(p).parent
        for src in re.findall(r'!\[[^\]]*\]\(([^)\s]+)\)', texto):
            if not re.match(r'^(https?:|data:)', src):
                rutas.append(RAIZ / os.path.normpath((base / unquote(src)).as_posix()))
    return sorted(set(rutas))


def huella_fuentes(doc):
    """SHA-256 (16 primeros caracteres) del contenido de las fuentes, con sus nombres relativos; no depende de la carpeta."""
    h = hashlib.sha256()
    for ruta in fuentes(doc):
        h.update(ruta.relative_to(RAIZ).as_posix().encode('utf-8') + b'\0')
        datos = ruta.read_bytes()
        if ruta.suffix in ('.md', '.css', '.svg'):
            datos = datos.replace(b'\r\n', b'\n').lstrip(b'\xef\xbb\xbf')
        h.update(datos + b'\0')
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------------------------------- Markdown -> HTML
def esc(t):
    return html.escape(t, quote=True)


def buscar_pandoc():
    ruta = os.environ.get('PANDOC') or shutil.which('pandoc')
    if not ruta:
        raise RuntimeError('Falta pandoc: ponlo en el PATH o indica su ruta en la variable PANDOC (https://pandoc.org/installing.html)')
    return ruta


def pandoc_html(texto):
    texto = re.sub(r'^(\s*[-*+] \[[ xX]\] +)(\d+)([.)])(?= )', lambda m: f'{m.group(1)}{m.group(2)}\\{m.group(3)}', texto, flags=re.M)
    r = subprocess.run([buscar_pandoc(), '-f', 'gfm', '-t', 'html5', '--no-highlight', '--wrap=none'],
                       input=texto.encode('utf-8'), capture_output=True, check=True)
    return r.stdout.decode('utf-8')


def _estilo_sobrio():
    """Estilo de pygments con los azules y grises de la UNTRM (sin verdes ni naranjas)."""
    from pygments.style import Style
    from pygments.token import Comment, Generic, Keyword, Name, Number, Operator, String

    class Untrm(Style):
        background_color = '#f3f4f6'
        styles = {
            Comment: 'italic #6b7280',
            Keyword: 'bold #003769',
            Operator: '#374151',
            Name.Builtin: '#00508f',
            Name.Function: '#00508f',
            Name.Class: 'bold #00508f',
            Name.Decorator: '#00508f',
            Name.Tag: 'bold #003769',
            Name.Attribute: '#0063b1',
            String: '#0063b1',
            Number: '#374151',
            Generic.Heading: 'bold #003769',
            Generic.Subheading: 'bold #003769',
            Generic.Deleted: '#6b7280',
            Generic.Inserted: '#003769',
            Generic.Error: 'bold #374151',
            Generic.Prompt: '#6b7280',
            Generic.Output: '#374151',
        }
    return Untrm


def resaltar(cuerpo):
    """Sintaxis coloreada en los bloques de código (pygments); los bloques sin lenguaje conocido quedan como texto."""
    from pygments import highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import TextLexer, get_lexer_by_name
    from pygments.util import ClassNotFound

    formateador = HtmlFormatter(nowrap=True, classprefix='h-', style=_estilo_sobrio())

    def cambiar(m):
        lenguaje = m.group(1) or ''
        codigo = html.unescape(m.group(2))
        try:
            lexer = get_lexer_by_name(lenguaje) if lenguaje and lenguaje not in ('text',) else TextLexer()
        except ClassNotFound:
            lexer = TextLexer()
        resultado = highlight(codigo.rstrip('\n'), lexer, formateador).rstrip('\n')
        largo = ' larga' if codigo.count('\n') > 38 else ''
        return f'<pre class="codigo{largo}"><code>{resultado}</code></pre>'

    return re.sub(r'<pre(?: class="([^"]*)")?><code>(.*?)</code></pre>', cambiar, cuerpo, flags=re.S)


def estilo_resaltado():
    from pygments.formatters import HtmlFormatter
    css = HtmlFormatter(style=_estilo_sobrio(), classprefix='h-').get_style_defs('pre.codigo')
    return re.sub(r'pre\.codigo \{[^}]*\}', '', css)    # el fondo y el borde los pone estilo-documento.css


def enlaces_al_repositorio(cuerpo, origen):
    """Los enlaces relativos entre archivos del repositorio pasan a ser enlaces a la plantilla en GitHub (en papel no existen las rutas)."""
    base = PurePosixPath(origen).parent

    def cambiar(m):
        h = html.unescape(m.group(1))
        if re.match(r'^(https?:|mailto:|#)', h, re.I):
            return m.group(0)
        partes = urlsplit(h)
        ruta = os.path.normpath((base / unquote(partes.path)).as_posix()).replace('\\', '/')
        modo = 'tree' if partes.path.endswith('/') or (RAIZ / ruta).is_dir() else 'blob'
        destino = f'{REPOSITORIO_PLANTILLA}/{modo}/{RAMA}/{ruta}' + (f'#{partes.fragment}' if partes.fragment else '')
        return f'<a href="{esc(destino)}"'

    return re.sub(r'<a href="([^"]*)"', cambiar, cuerpo)


def imagenes_incrustadas(cuerpo, origen):
    """Las imágenes locales se incrustan como data: URI (el PDF no puede depender de rutas). Las capturas llevan su texto alternativo
    como pie; los diagramas (SVG) van a todo el ancho y sin pie, porque el texto de al lado ya los explica."""
    base = PurePosixPath(origen).parent
    tipos = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif', '.svg': 'image/svg+xml'}

    def cambiar(m):
        src, alt = html.unescape(m.group(1)), m.group(2)
        ruta = RAIZ / os.path.normpath((base / unquote(src)).as_posix())
        tipo = tipos.get(ruta.suffix.lower())
        if not tipo or not ruta.is_file():
            raise FileNotFoundError(f'{origen}: no se encuentra la imagen {src}')
        datos = base64.b64encode(ruta.read_bytes()).decode()
        if ruta.suffix.lower() == '.svg':
            return f'<figure class="diagrama"><img src="data:{tipo};base64,{datos}" alt="{alt}"></figure>'
        return f'<figure><img src="data:{tipo};base64,{datos}" alt="{alt}"><figcaption>{alt}</figcaption></figure>'

    cuerpo = re.sub(r'<p>\s*<img\b[^>]*?\bsrc="([^"]+)"[^>]*?\balt="([^"]*)"[^>]*>\s*</p>', cambiar, cuerpo)
    if re.search(r'<img\b[^>]*\bsrc="(?!data:|https?:)', cuerpo):
        raise RuntimeError(f'{origen}: hay una imagen local que no está sola en su párrafo')
    return cuerpo


def escudo_data_uri():
    return 'data:image/svg+xml;base64,' + base64.b64encode(ESCUDO.read_bytes()).decode()


def pagina_html(doc):
    partes = []
    for archivo, _titulo in doc['partes']:
        cuerpo = pandoc_html((RAIZ / archivo).read_text(encoding='utf-8').lstrip('﻿'))
        cuerpo = resaltar(cuerpo)
        cuerpo = enlaces_al_repositorio(cuerpo, archivo)
        cuerpo = imagenes_incrustadas(cuerpo, archivo)
        clase = 'parte resumen' if archivo in doc['h2_en_pagina_nueva'] else 'parte'
        partes.append(f'<section class="{clase}">{cuerpo}</section>')
    portada = (f'<header class="portada"><img class="escudo" src="{escudo_data_uri()}" alt="Escudo de la UNTRM">'
               f'<p class="universidad">{esc(UNIVERSIDAD)}</p>'
               f'<h1>{esc(TITULO)}</h1><p class="sub">{esc(doc["subtitulo"])}</p>'
               f'<p class="fecha">Fecha de entrega: {esc(FECHA_ENTREGA)}</p><p class="profesor">{esc(PROFESOR)}</p></header>')
    css = CSS.read_text(encoding='utf-8') + '\n' + CSS_EXTRA + '\n' + estilo_resaltado()
    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{esc(TITULO)}</title>'
            f'<style>{css}</style></head><body><main>{portada}{"".join(partes)}</main></body></html>')


# ---------------------------------------------------------------------------------------------------- PDF
def pie():
    """Pie de todas las páginas: el escudo y el nombre del taller a la izquierda, «Página x de y» a la derecha."""
    estilo = ("font-family:'Segoe UI',Arial,sans-serif;font-size:10px;color:#636975;width:100%;padding:0 17mm;"
              "display:flex;align-items:center;justify-content:space-between;-webkit-print-color-adjust:exact")
    return (f'<div style="{estilo}"><span style="display:flex;align-items:center">'
            f'<img src="{escudo_data_uri()}" style="height:9mm;width:9mm;margin-right:7px">'
            f'<span style="display:flex;flex-direction:column;line-height:1.5"><span>{esc(TITULO)}</span><span>{esc(PROFESOR)}</span></span></span>'
            f'<span>Página <span class="pageNumber"></span> de <span class="totalPages"></span></span></div>')


def lanzar(p):
    ruta = os.environ.get('PDF_CHROME')
    if ruta:
        return p.chromium.launch(executable_path=ruta)
    for canal in ('chrome', 'msedge'):
        try:
            return p.chromium.launch(channel=canal)
        except Exception:     # noqa: BLE001 - ese navegador no está: se prueba el siguiente
            continue
    raise RuntimeError('No se encuentra Google Chrome ni Microsoft Edge: instala uno o indica su ruta en PDF_CHROME')


def generar(doc):
    """Genera el PDF de `doc` y devuelve su número de páginas."""
    from playwright.sync_api import sync_playwright
    from pypdf import PdfReader, PdfWriter

    contenido = pagina_html(doc)
    with sync_playwright() as p:
        navegador = lanzar(p)
        try:
            pagina = navegador.new_page()
            pagina.set_content(contenido, wait_until='load')
            datos = pagina.pdf(format='A4', print_background=True, display_header_footer=True, header_template='<span></span>',
                               footer_template=pie(), margin={'top': '16mm', 'bottom': '22mm', 'left': '17mm', 'right': '17mm'})
        finally:
            navegador.close()
    lector = PdfReader(io.BytesIO(datos))
    escritor = PdfWriter(clone_from=lector)
    escritor.add_metadata({
        '/Title': f'{TITULO} · {doc["subtitulo"]}',
        '/Author': 'Taller «De Modelo de ML/IA a Producción»',
        '/Subject': f'fuentes:{huella_fuentes(doc)}',
        '/Keywords': 'taller, ML, MLOps, despliegue, arquitectura',
        '/Creator': 'taller/generar_pdf.py (Chrome)',
    })
    escritor.page_mode = '/UseOutlines'
    doc['pdf'].parent.mkdir(parents=True, exist_ok=True)
    with open(doc['pdf'], 'wb') as f:
        escritor.write(f)
    return len(lector.pages)


def comprobar(doc):
    """(errores, páginas): el PDF existe, es de la versión actual de las fuentes, no deja rutas locales y tiene las páginas previstas."""
    from pypdf import PdfReader
    ruta = doc['pdf']
    if not ruta.exists():
        return [f'falta {ruta.name}'], 0
    lector = PdfReader(str(ruta))
    errores = []
    sujeto = (lector.metadata or {}).get('/Subject', '')
    if sujeto != f'fuentes:{huella_fuentes(doc)}':
        errores.append(f'{ruta.name} no corresponde a las fuentes actuales: vuelve a generarlo (python -I taller/generar_pdf.py)')
    if 'file:///' in ruta.read_bytes().decode('latin-1'):
        errores.append(f'{ruta.name} tiene enlaces a file:///')
    minimo, maximo = doc['paginas']
    if not minimo <= len(lector.pages) <= maximo:
        errores.append(f'{ruta.name} tiene {len(lector.pages)} páginas y debería tener entre {minimo} y {maximo}')
    return errores, len(lector.pages)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--comprobar', action='store_true', help='no genera nada: dice si los PDF están al día')
    a = ap.parse_args(argv)
    hubo_errores = False
    for doc in DOCUMENTOS:
        if not a.comprobar:
            paginas = generar(doc)
            print(f'{doc["pdf"].relative_to(RAIZ).as_posix()}  ({paginas} páginas, {doc["pdf"].stat().st_size / 1_000_000:.1f} MB)')
        errores, paginas = comprobar(doc)
        for e in errores:
            print('ERROR', e)
        hubo_errores = hubo_errores or bool(errores)
        if a.comprobar:
            print(f'{doc["pdf"].name}: {"correcto" if not errores else f"{len(errores)} problema(s)"} ({paginas} páginas)')
    return 1 if hubo_errores else 0


if __name__ == '__main__':
    sys.exit(main())

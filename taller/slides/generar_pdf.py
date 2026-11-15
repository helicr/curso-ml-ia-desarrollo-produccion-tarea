"""Genera taller/diapositivas-del-trabajo.pdf a partir de index.html: una página de 1280 x 720 por diapositiva.

Es el método de 00-Planificacion/pdfs/generar_pdfs.py del curso: se abre la presentación en 1280 x 720, se va diapositiva por
diapositiva (como con las flechas), se imprime solo esa y se unen las páginas con un marcador por diapositiva. Los controles, las
notas y los botones de copiar no salen (lo dice el CSS de impresión del propio index.html).

Necesita Python con `playwright` y `pypdf`, y Google Chrome (playwright, canal «chrome»). No instala nada:
    python -I taller/slides/generar_pdf.py
En los metadatos del PDF queda la huella de index.html (HuellaIndex): una prueba falla si el PDF no está al día.
"""
import hashlib
import io
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter

AQUI = Path(__file__).resolve().parent
INDEX = AQUI / 'index.html'
DESTINO = AQUI.parent / 'diapositivas-del-trabajo.pdf'
ANCHO, ALTO = 1280, 720


def huella(ruta=INDEX):
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:16]


# Los enlaces relativos (capturas a tamaño completo, vuelta a las instrucciones) apuntarían a file:// en el PDF: se quitan.
JS_ENLACES = "() => document.querySelectorAll('a[href]').forEach(a => { if (!/^https?:/i.test(a.getAttribute('href'))) a.removeAttribute('href'); })"


def main():
    texto = INDEX.read_text(encoding='utf-8')
    escritor = PdfWriter()
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel='chrome')
        pagina = navegador.new_page(viewport={'width': ANCHO, 'height': ALTO + 46})
        pagina.goto(INDEX.as_uri(), wait_until='load')
        pagina.wait_for_timeout(500)
        pagina.evaluate(JS_ENLACES)
        n = pagina.evaluate("document.querySelectorAll('section.slide').length")
        titulos = pagina.evaluate("[...document.querySelectorAll('section.slide')].map(s => s.dataset.title)")
        for i in range(n):
            pagina.evaluate(f"location.hash = '#{i + 1}'")
            pagina.wait_for_timeout(450)
            activa = pagina.evaluate("[...document.querySelectorAll('section.slide')].findIndex(s => s.classList.contains('active'))")
            if activa != i:
                raise SystemExit(f'no se pudo abrir la diapositiva {i + 1}')
            pagina.evaluate("(i) => document.querySelectorAll('section.slide').forEach((s, k) => s.classList.toggle('pdf-solo', k === i))", i)
            datos = pagina.pdf(width=f'{ANCHO}px', height=f'{ALTO}px', print_background=True,
                               margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'})
            lector = PdfReader(io.BytesIO(datos))
            if len(lector.pages) != 1:
                raise SystemExit(f'la diapositiva {i + 1} ocupa {len(lector.pages)} páginas al imprimir')
            escritor.add_page(lector.pages[0])
        navegador.close()
    for i, t in enumerate(titulos):
        escritor.add_outline_item(f'{i + 1}. {t}', i)
    escritor.add_metadata({'/Title': 'Tarea Curso Taller «De Modelo de ML/IA a Producción»: diapositivas',
                           '/Author': 'Helí Campos R', '/Subject': 'Diapositivas de la tarea',
                           '/HuellaIndex': huella(), '/Producer': 'generar_pdf.py'})
    escritor.page_mode = '/UseOutlines'
    with open(DESTINO, 'wb') as f:
        escritor.write(f)
    print(f'escrito {DESTINO.name}: {n} páginas, {DESTINO.stat().st_size // 1024} KB, huella {huella()}')


if __name__ == '__main__':
    sys.exit(main())

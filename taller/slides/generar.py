"""Genera las diapositivas de la tarea (index.html, junto a este archivo).

Son las diapositivas de «Tarea Curso Taller «De Modelo de ML/IA a Producción»»: el instructor las proyecta y el alumno las
consulta. Reutilizan el marco de las presentaciones del curso (teclas ← → · O índice · S notas · F pantalla completa, notas del
ponente en data-notes, minutos por diapositiva, botones ⧉ para copiar cada orden, capturas que se abren a tamaño completo y
ningún recurso externo), pero con la paleta de la UNTRM.

Las cifras son las medidas en el Codespace real y en GitHub Actions (14/11/2026); están en CIFRAS y una prueba las compara con la
guía detallada. Los tres diagramas salen de docs/img/*.svg (se incrustan en línea, con ids de marcador únicos por diapositiva) y las
capturas se copian de docs/img/ a slides/img/.

Uso:  python generar.py              escribe index.html y copia las imágenes
      python generar.py --comprobar  no escribe; sale con 1 si index.html o las imágenes no están al día
"""
import argparse
import html
import re
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent.parent
DOCS_IMG = RAIZ / 'docs' / 'img'
ESCUDO_ORIGEN = RAIZ / 'taller' / 'img' / 'escudo-untrm.svg'
IMG = AQUI / 'img'
SALIDA = AQUI / 'index.html'

TITULO_TAREA = 'Tarea Curso Taller «De Modelo de ML/IA a Producción»'
PROFESOR = 'Profesor: Helí Campos R'
FORK = 'taller-ml-ia-dev-production'
PLANTILLA = 'https://github.com/helicr/curso-ml-ia-desarrollo-produccion-tarea'

# Capturas de ejemplo (Codespace real de prueba) que usan las diapositivas, y de dónde salen.
CAPTURAS = ['cs-taller-02.webp', 'cs-taller-03.webp', 'cs-taller-07.webp', 'cs-taller-09.webp', 'cs-taller-10.webp']
ESCUDO = 'escudo-untrm.svg'
PARTES = {'A': 'La tarea', 'B': 'Despliegue', 'C': 'CI/CD', 'D': 'Entrega'}

# Las 16 capturas (nombre, paso de la guía): son las de la plantilla de evidencias.
LAS_16 = [('01-fork-renombrado', 2), ('02-codespace-abierto', 3), ('03-verificar-entorno', 5), ('04-pipeline', 7),
          ('05-pipeline-sin-cambios', 8), ('06-modelo-version', 9), ('07-imagenes', 11), ('08-compose-sano', 12),
          ('09-puerto-8090', 13), ('10-ui-cabecera', 13), ('11-ui-resultado', 14), ('12-validar-verde', 18),
          ('13-environment-produccion', 19), ('14-nueva-version-rechazada', 20), ('15-nueva-version-aprobacion', 21),
          ('16-paquetes-y-pr', 22)]

# Cifras que citan las diapositivas: tal como se ven -> cómo están en la guía detallada (medidas en un Codespace real
# de 2 núcleos y en GitHub Actions, 14/11/2026). La prueba exige que cada una esté en la guía y que no haya otras.
CIFRAS = {
    'unos 4,5 min': 'unos 4,5 min',          # preparar el Codespace
    '49 s': '49 s',                          # make pipeline
    '1 min 18 s': '1 min 18 s',              # make imagenes
    '13 s': '13 s',                          # make compose-arriba
    '826 MB': '826 MB',                      # cafe-api
    '213 MB': '213 MB',                      # cafe-interfaz
    'c83699881a8880b9': 'c83699881a8880b9',  # huella de los datos de la versión 1
    '1190': '1190',                          # lotes en la base
    '5 de 6 lotes': '5 de 6 lotes',          # consulta de ejemplo
    '7 min 42 s': '7 min 42 s',              # Validar
    '1 min 34 s': '1 min 34 s',              # Nueva version del modelo, rechazada
    '4 min 30 s': '4 min 30 s',              # Nueva version del modelo, aprobada
    '0,7951': '0,7951',                      # AUC en la ventana común, candidata
    '0,8525': '0,8525',                      # AUC en la ventana común, referencia
    '-0,0574': '-0,0574',                    # diferencia
    '0,02': '0,02',                          # tolerancia por defecto
    '0,10': '0,10',                          # tolerancia con la que se aprueba
    '5 lotes sin especialidad': '5 lotes sin especialidad',
    '0,49 a 1,00': '0,49 a 1,00',            # IC 95 % del AUC de la versión 2
}


def esc(t):
    return html.escape(t, quote=True)


def md(t):
    """`código` y **negrita** a HTML (sobre texto ya seguro)."""
    t = esc(t)
    t = re.sub(r'`([^`]+)`', r'<span class="mono">\1</span>', t)
    return re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', t)


def lista(items, clase=''):
    return f'<ul class="list {clase}">' + ''.join(f'<li><span>{md(i)}</span></li>' for i in items) + '</ul>'


def tarjeta(titulo, cuerpo, clase=''):
    return f'<div class="card {clase}"><h3>{md(titulo)}</h3>{cuerpo}</div>'


def term(titulo, lineas):
    """Terminal con una orden por línea y su botón ⧉ (clase .cp). Las líneas que empiezan por # son comentarios."""
    filas = []
    for l in lineas:
        if l.startswith('#'):
            filas.append(f'<div class="tln c">{esc(l)}</div>')
        else:
            filas.append(f'<div class="tln"><span class="ps">$</span> <code>{esc(l)}</code>'
                         f'<button class="cp" data-t="{esc(l)}" title="Copiar" aria-label="Copiar la orden">⧉</button></div>')
    todo = '\n'.join(l for l in lineas if not l.startswith('#'))
    return (f'<div class="term"><div class="bar"><i></i><i></i><i></i><em>{esc(titulo)}</em>'
            f'<button class="cp cpall" data-t="{esc(todo)}">Copiar todo</button></div><div class="tls">{"".join(filas)}</div></div>')

def orden_suelta(cmd):
    """Una orden copiable fuera de un terminal completo."""
    return (f'<div class="tln solo"><span class="ps">$</span> <code>{esc(cmd)}</code>'
            f'<button class="cp" data-t="{esc(cmd)}" title="Copiar" aria-label="Copiar la orden">⧉</button></div>')

def captura(archivo, alt):
    """La captura se abre a tamaño completo en otra pestaña (las letras de la terminal son pequeñas)."""
    return (f'<a class="capa" href="img/{archivo}" target="_blank" rel="noopener" title="Ver a tamaño completo">'
            f'<img class="capimg" src="img/{archivo}" alt="{esc(alt)}"></a>')


SLIDES = []


def slide(parte, minutos, titulo, kick, h1, cuerpo, notas, plano=False):
    """plano=True: el cuerpo ya lleva su propio kick y h1 (diagrama a la izquierda y texto a la derecha)."""
    cabecera = '' if plano else f'<p class="kick">{esc(kick)}</p><h1>{md(h1)}</h1>\n'
    SLIDES.append(dict(parte=parte, min=minutos, titulo=titulo, notas=notas, plano=plano, cuerpo=cabecera + cuerpo))


def svg_en_linea(nombre, ancho, alto):
    """Un diagrama de docs/img/ incrustado en línea. Su marcador de flecha (id «fl») se renombra por diapositiva: si dos SVG en
    la misma página repiten el id, el navegador usa el de una diapositiva oculta y no pinta la punta."""
    t = (DOCS_IMG / nombre).read_text(encoding='utf-8').strip()
    n = len(SLIDES)
    t = re.sub(r'^<svg ([^>]*?) width="\d+" height="\d+"', rf'<svg \1 style="width:{ancho}px;height:{alto}px"', t)
    t = t.replace('id="fl"', f'id="fl-s{n}"').replace('url(#fl)', f'url(#fl-s{n})')
    return f'<div class="dgm">{t}</div>'


def lado(svg, kick, h1, cuerpo, cols):
    """Diagrama a la izquierda; a la derecha, kick, título y texto."""
    return (f'<div class="side" style="grid-template-columns:{cols}">{svg}'
            f'<div class="sidet"><p class="kick">{esc(kick)}</p><h1>{md(h1)}</h1>{cuerpo}</div></div>')


# =====================================================================================================================================
# Contenido
# =====================================================================================================================================
def construir():
    SLIDES.clear()

    # ---------------------------------------------------------------- A · La tarea
    slide('A', 1, 'Portada', 'Tarea Curso Taller', 'De Modelo de ML/IA a Producción', f'''
<div class="cover"><div>
 <p class="lead">Despliegas un servicio de ML que ya está hecho y explicas cómo encaja. No programas nada.</p>
 <div class="chips"><span class="tag core">@@MIN@@ minutos</span><span class="tag">Entrega el 30/11/2026</span><span class="tag">Fork: {FORK}</span></div>
 <div class="card" style="margin-top:26px"><h3>Cómo seguir las diapositivas</h3>
 <p class="small">Cada orden lleva <b>⧉</b>: cópiala y pégala en la terminal de tu Codespace. <b>← →</b> avanzan, <b>O</b> abre el índice, <b>S</b> las notas del ponente y <b>F</b> la pantalla completa. Las capturas se abren a tamaño completo al pulsarlas.</p></div>
</div><div class="cover-escudo"><img src="img/{ESCUDO}" alt="Escudo de la UNTRM"></div></div>''',
          'Presente la tarea en una frase: desplegar un servicio de ML que ya está construido y explicar cómo encaja cada pieza. Aclare desde el principio que no hay que programar. Indique cómo se manejan las diapositivas: flechas, índice con O, notas con S y el botón de copiar en cada orden. Las diapositivas duran unos treinta minutos y el alumno puede volver a ellas mientras hace la tarea.')

    slide('A', 2, 'Qué es la tarea y qué no tienes que hacer', 'La tarea', 'Eres arquitecto, no programador', f'''
<div class="grid2">
 {tarjeta('Lo que haces', lista([
        'Despliegas el servicio **de punta a punta** desde un Codespace.',
        'Demuestras que funciona: **un vídeo y 16 capturas**.',
        'Explicas en cada pieza **qué decisión de arquitectura hay y qué riesgo cubre**.']))}
 {tarjeta('Lo que NO haces', lista([
        'No escribes código.',
        'No cambias ningún archivo del proyecto.',
        'No instalas nada en tu ordenador.']), 'gris')}
</div>
<div class="callout" style="margin-top:22px"><b>El caso.</b> Llega un lote de café y, antes de catarlo, se quiere saber qué probabilidad hay de que sea café de especialidad (80 puntos o más). Los datos son los del Coffee Quality Institute (CQI).</div>''',
          'Insista en el papel: la persona que evalúa no mira código sino explicaciones. El trabajo es desplegar y entender. Si alguien pregunta qué programar, la respuesta es nada: el proyecto llega completo y solo se añade la carpeta de evidencias. El caso es sencillo de contar: un lote llega, todavía no se ha catado, y se estima la probabilidad de que supere los 80 puntos.')

    slide('A', 1, 'Qué recibes', 'La tarea', 'Qué recibes', f'''
<div class="grid3">
 {tarjeta('La plantilla', '<p class="small">Un repositorio de GitHub con todo hecho: datos, pipelines, modelo, API, interfaz, Docker y workflows.</p><p class="small" style="margin-top:10px">' + md('`' + PLANTILLA.replace('https://', '') + '`') + '</p>')}
 {tarjeta('Un entorno listo', '<p class="small">Un Codespace de GitHub que ya trae Python 3.11, Docker y <span class="mono">make</span>.</p><p class="small" style="margin-top:10px">No instalas nada en tu equipo.</p>')}
 {tarjeta('La documentación', lista(['Instrucciones y criterios de evaluación', 'Guía detallada paso a paso', 'Checklist y plantilla de evidencias', 'Guía para grabar el vídeo'], 'chica'))}
</div>
<p class="small" style="margin-top:22px">La cadena que vas a desplegar: CSV del CQI, base operacional, RAW, MASTER, FS, ML, modelo, API, interfaz, imágenes Docker, Compose y GitHub Actions.</p>''',
          'La plantilla es la parte pesada y ya viene resuelta. El Codespace evita el problema de que cada alumno tenga un equipo distinto. La documentación está en la carpeta taller: las instrucciones resumen lo que se pide, la guía detallada da cada paso con lo que se debe ver y qué hacer si falla. Enseñe la lista de la cadena completa como mapa para el resto de diapositivas.')

    slide('A', 2, 'El recorrido de punta a punta', '', '', lado(
        svg_en_linea('diagrama-recorrido.svg', 752, 564), 'El recorrido', 'De punta a punta', lista([
            'Ocho cajas y **una orden en cada una**.',
            'Todo en el Codespace, salvo abrir la interfaz y grabar el vídeo.',
            'En paralelo, **GitHub Actions** comprueba el recorrido y publica versiones nuevas.']) +
        '<p class="small" style="margin-top:16px">Los pasos 17 a 22 de la guía son los de GitHub Actions.</p>', '752px 1fr'),
          'Recorra el diagrama de izquierda a derecha y de arriba abajo: entorno, datos y pipelines, modelo, API opcional, imágenes, contenedores, interfaz y uso. Cada caja tiene su orden. Marque que la API suelta es un paso opcional, porque con Compose la API ya va dentro de un contenedor. La franja inferior es la parte de CI/CD que veremos al final.', plano=True)

    # ---------------------------------------------------------------- B · Despliegue
    slide('B', 2, 'Paso a paso: preparar el entorno', 'El despliegue · pasos 1 a 6', 'Preparar el entorno', f'''
<div class="grid2" style="grid-template-columns:1.1fr 1fr">
 <div class="col">
  {lista(['**Fork** de la plantilla y nombre exacto `' + FORK + '`.',
          '**Code, Codespaces, Create codespace on main**: unos 4,5 min.',
          'Cuando pregunte si confías en los autores, **confía en la carpeta**.',
          'La verificación debe acabar en **«LISTO PARA EL TALLER»**.'])}
 </div>
 <div class="col">
  {term('Terminal del Codespace', ['make verificar', 'make ayuda'])}
  <p class="small">Cinco marcas <span class="mono">[OK   ]</span>: Python, paquetes, <span class="mono">cafe_mlops</span>, datos y Docker.</p>
 </div>
</div>''',
          'Los pasos 1 a 4 se hacen en el navegador: fork, renombrar, crear el Codespace y aceptar los avisos de la primera vez. El Codespace tarda unos cuatro minutos y medio en prepararse. La primera orden en la terminal es make verificar: comprueba Python, los paquetes con su versión exacta, el código, la huella de los datos y Docker. Si no dice LISTO PARA EL TALLER no se sigue. make ayuda solo lista las órdenes.')

    slide('B', 2, 'Paso a paso: pipelines y modelo', 'El despliegue · pasos 7 a 9', 'Pipelines y modelo', f'''
<div class="grid2" style="grid-template-columns:1.1fr 1fr">
 <div class="col">
  {term('Terminal del Codespace', ['time make pipeline', 'make pipeline', 'make comparar'])}
 </div>
 <div class="col">
  {lista(['La primera vez tarda **49 s**. Mejor modelo: `gradient_boosting`, **versión 1**.',
          'Huella de los datos: `c83699881a8880b9`.',
          'La segunda vez, cuatro líneas **«sin cambios»**.',
          '`make comparar`: cuatro caminos y los cuatro **«coincide»**.'])}
 </div>
</div>
<p class="small" style="margin-top:18px">No pegues <span class="mono">make pipeline HASTA=2018</span> todavía: eso cambia la versión de los datos y es el paso 16.</p>''',
          'make pipeline ejecuta los cuatro pipelines y el entrenamiento: unos 49 segundos en el Codespace real. Lo que hay que reconocer en la salida es la huella c83699881a8880b9, el mejor modelo gradient_boosting y la versión 1 en MLflow. Al repetirlo, cada pipeline calcula la huella de su entrada y, si no cambió, no hace nada: eso es idempotencia. make comparar demuestra que el paquete, el joblib y los dos formatos de MLflow dan la misma probabilidad.')

    slide('B', 2, 'Paso a paso: imágenes y contenedores', 'El despliegue · pasos 11 a 15', 'Imágenes y contenedores', f'''
<div class="grid2" style="grid-template-columns:1.2fr 1fr">
 <div class="col">
  {term('Terminal del Codespace', ['time make imagenes', "docker image ls 'cafe-*'", 'time make compose-arriba',
                                  'docker compose -f deploy/docker/compose.yaml ps', '# al terminar el vídeo:', 'make compose-abajo'])}
 </div>
 <div class="col">
  <table class="tbl"><tr><th>Qué</th><th>Cifra</th></tr>
   <tr><td>Construir las imágenes</td><td>1 min 18 s</td></tr>
   <tr><td>Levantar los contenedores</td><td>13 s</td></tr>
   <tr><td><span class="mono">cafe-api</span></td><td>826 MB</td></tr>
   <tr><td><span class="mono">cafe-interfaz</span></td><td>213 MB</td></tr></table>
  <p class="small">Debes ver los dos contenedores <b>Healthy</b>. Las comillas de <span class="mono">'cafe-*'</span> son necesarias: con dos argumentos, Docker 29 da error.</p>
 </div>
</div>''',
          'make imagenes construye dos imágenes, la de la API con el modelo dentro y la de la interfaz, que es unas cuatro veces más pequeña porque no lleva scikit-learn. Los tiempos son de un Codespace real con la caché vacía, y los tamaños son los medidos en GitHub Actions. make compose-arriba espera a que los dos contenedores estén sanos. Después se abre la interfaz y se graba el vídeo; al terminar, make compose-abajo.')

    slide('B', 1, 'Las dos piezas en Docker', '', '', lado(
        svg_en_linea('diagrama-docker.svg', 752, 508), 'Las dos piezas en Docker', 'Solo se ve la interfaz', lista([
            'La **interfaz** publica el puerto 8090.',
            'La **API** no se publica: la llama la interfaz dentro de la red de Compose.',
            'Los datos **no van en la imagen**: se montan en solo lectura (`:ro`).',
            'La interfaz arranca cuando la API está sana.']), '752px 1fr'),
          'Son dos contenedores en una red interna de Compose. Desde fuera solo se llega a la interfaz, por el puerto 8090; la API escucha en el 8080 pero no se publica. Los datos se montan en solo lectura, de modo que la interfaz no podría escribir en la base aunque tuviera un fallo. Cada decisión cubre un riesgo: exponer menos, no alterar los datos, no arrancar un servicio que depende de otro que aún no responde.', plano=True)

    slide('B', 2, 'Qué debes ver en la interfaz', 'El despliegue · pasos 13 y 14', 'Qué debes ver en la interfaz', f'''
<div class="grid2" style="gap:24px">
 <div class="capcol">{captura('cs-taller-09.webp', 'La interfaz con su cabecera: repositorio, modelo y huella, API lista y lotes en la base')}
  <p class="small"><b>Cabecera:</b> tu repositorio, <span class="mono">gradient_boosting v1</span>, huella <span class="mono">c83699881a8880b9</span>, API lista y 1190 lotes.</p></div>
 <div class="capcol">{captura('cs-taller-10.webp', 'Resultado de consultar los lotes de ejemplo: tramos, probabilidades y avisos')}
  <p class="small"><b>Consulta de ejemplo:</b> 5 de 6 lotes con predicción (4 en tramo alta, 1 en baja) y el 99999 sin predicción. Los avisos son correctos.</p></div>
</div>
<p class="small" style="margin-top:8px">Pestaña Puertos, fila del 8090, icono del globo. Capturas de ejemplo del repositorio de prueba: en las tuyas aparecen tu usuario y tu repositorio.</p>''',
          'Para abrir la interfaz: pestaña Puertos del Codespace, puerto 8090 y el icono del globo. Abra la captura de la izquierda a tamaño completo y lea la cabecera: repositorio, modelo con su versión y su huella, estado de la API y lotes en la base. A la derecha, el resultado de la consulta de ejemplo: cinco de seis lotes con predicción, cuatro en el tramo alta y uno en el baja; el 99999 no existe y se dice. Que haya avisos es correcto: la interfaz no esconde la incertidumbre. Los puertos son privados por defecto: abra la interfaz en el mismo navegador donde tiene la sesión de GitHub.')

    # ---------------------------------------------------------------- C · CI/CD
    slide('C', 2, 'CI/CD con las dos puertas', '', '', lado(
        svg_en_linea('diagrama-cicd.svg', 686, 600), 'CI/CD en GitHub Actions', 'Dos workflows, dos puertas', lista([
            '**Validar**: repite todo el recorrido en un entorno limpio. En verde en unos 7 min 42 s.',
            '**Puerta 1**: compara el modelo nuevo con la referencia.',
            '**Puerta 2**: tú apruebas el environment `produccion`.']) +
        '<div class="card gris" style="margin-top:14px"><h3>En tu fork lo activas tú</h3>' + lista([
            'Las **Actions** (paso 17)',
            'El environment `produccion` con tu usuario como revisor (paso 19)',
            'La casilla «Allow GitHub Actions to create and approve pull requests» (paso 19)'], 'chica') + '</div>', '686px 1fr'),
          'Hay dos workflows. Validar se ejecuta en cada push, en cada pull request y a mano; repite las pruebas, el pipeline, las imágenes y los contenedores sin tu equipo, y no publica nada. Nueva version del modelo se lanza a mano y tiene dos puertas: la primera es automática y compara con la referencia; la segunda es humana y es la aprobación del environment produccion. En un fork, GitHub deja desactivadas tres cosas y las activa cada alumno: las Actions, el environment con su revisor y el permiso para que el workflow abra pull requests.', plano=True)

    slide('C', 3, 'Rechazada con 0,02 y aprobada con 0,10', 'CI/CD · pasos 16, 20 y 21', 'Rechazada con 0,02, aprobada con 0,10', f'''
<div class="grid2" style="grid-template-columns:1.1fr 1fr">
 <div class="col">
  {tarjeta('Tolerancia por defecto: 0,02', '<p class="cifra">RECHAZADA</p>' + lista([
        'AUC en la ventana común: **0,7951** frente a **0,8525** (diferencia -0,0574).',
        'Termina en rojo **a propósito**, en 1 min 34 s.',
        'No se construye ni se publica nada.'], 'chica'), 'gris')}
  {tarjeta('Con `tolerancia` = 0.10', '<p class="cifra">APROBADA</p>' + lista([
        'La misma versión pasa la puerta 1.',
        'Esperas y **apruebas `produccion`**; se publica `v2-...` y se abre un pull request.',
        'Dura 4 min 30 s, más lo que tardes en aprobar.'], 'chica'), 'pri')}
 </div>
 <div class="col">
  <div class="callout"><b>Decisión de arquitecto.</b> La ventana común solo tiene 5 lotes sin especialidad: con tan pocos casos el AUC oscila por azar (intervalo del 95 %, de 0,49 a 1,00). Subir la tolerancia lo justificas tú; no sale de una medición.</div>
  {term('Para probarlo en el Codespace (opcional)', ['make pipeline HASTA=2018', 'make comparar', 'python -m cafe_mlops.modeling.comparar --tolerancia-referencia 0.10'])}
 </div>
</div>''',
          'Es la pregunta clave de comprensión. Con la tolerancia por defecto, 0,02, la versión 2 se rechaza: su AUC en la ventana común es 0,7951 frente a 0,8525 de la referencia, una diferencia de menos 0,0574. Con tolerancia 0,10 la misma versión se aprueba. Lo importante no es el número sino el motivo: la ventana común, el año 2016, solo tiene cinco lotes sin especialidad, el AUC oscila mucho con tan pocos casos y el intervalo del 95 por ciento va de 0,49 a 1,00 en la versión 2. Subir la tolerancia es una decisión de arquitecto que se justifica y el alumno debe saber explicarla. Cubre dos riesgos a la vez: desplegar un modelo peor y bloquear una mejora real por ruido de medida. Las órdenes del recuadro son el paso 16, opcional, y reproducen en el Codespace lo que hará GitHub Actions.')

    # ---------------------------------------------------------------- D · Entrega
    slide('D', 2, 'Qué entregar', 'La entrega', 'Qué entregas', f'''
<div class="grid3">
 {tarjeta('Un vídeo', lista(['MP4, de **2 a 4 minutos**, con tu voz y de menos de **50 MB**.',
        'Se ve la cabecera con tu repositorio, los contenedores sanos y una consulta con sus avisos.',
        'Explicas la arquitectura con tus palabras.'], 'chica') + '<p class="small" style="margin-top:8px"><span class="mono">evidencias/video/servicio-en-produccion.mp4</span></p>')}
 {tarjeta('16 capturas y la plantilla', lista(['Las 16 capturas, con su nombre, en `evidencias/capturas/`.',
        'La plantilla de evidencias rellena: qué muestra cada captura y tu explicación de arquitectura.'], 'chica'))}
 {tarjeta('Un fork público', lista(['Fork de la plantilla, renombrado **exactamente** `' + FORK + '`.',
        'Público. No cambias el proyecto: solo añades `evidencias/`.'], 'chica'))}
</div>
<div style="margin-top:18px">{term('Terminal del Codespace · paso 23', ['git add evidencias', 'git commit -m "Evidencias de la tarea"', 'git push'])}</div>''',
          'Hay cuatro cosas que entregar: el vídeo, las dieciséis capturas, la plantilla de evidencias rellena y el fork público con el nombre exacto. El instructor identifica a cada alumno por el nombre del repositorio y por su enlace. Las capturas y el vídeo son del alumno, con su usuario visible: no sirven las de ejemplo de la guía. Si algo no funcionó, se dice y se adjunta la captura del error: vale más que una captura retocada. Un MP4 grande se sube mejor por la terminal que por el botón de subir archivos.')

    cuadr = ''.join(f'<div class="cap16"><span class="mono">{n}</span><small>paso {p}</small></div>' for n, p in LAS_16)
    slide('D', 1, 'Las 16 capturas', 'La entrega', 'Las 16 capturas', f'''
<div class="grid4">{cuadr}</div>
<p class="small" style="margin-top:16px">En <span class="mono">evidencias/capturas/</span>. El número es el paso de la guía detallada. Son tuyas, con tu usuario visible, y el texto se lee.</p>''',
          'Esta es la lista completa, con el paso de la guía donde se hace cada una. Las dos primeras son del navegador y las del 12 al 16 son de GitHub. Si una captura no puede hacerse por un fallo de GitHub o del Codespace, se documenta con la captura del error y el paso en que ocurrió, y se puntúa. Una captura retocada o inventada anula el aspecto al que pertenece.')

    slide('D', 2, 'Criterios de evaluación', 'Cómo se evalúa', 'Criterios de evaluación: 40, 30, 30', f'''
<div class="stack"><div style="flex:40;background:var(--pri)">40</div><div style="flex:30;background:var(--sec)">30</div><div style="flex:30;background:var(--g4)">30</div></div>
<div class="grid3" style="margin-top:20px">
 {tarjeta('Ejecución y reproducibilidad · 40', '<p class="small">El despliegue se hizo de verdad y se puede repetir: fork con el nombre correcto, pipelines, imágenes, contenedores, interfaz y las tres ejecuciones de CI/CD.</p>')}
 {tarjeta('Evidencias · 30', '<p class="small">El vídeo cumple el formato y muestra el servicio por su interfaz. Las 16 capturas son tuyas, legibles y con su nombre.</p>')}
 {tarjeta('Comprensión · 30', '<p class="small">Tus explicaciones de arquitectura: una por captura, la puerta de calidad con sus cifras y qué falta para una producción real.</p>')}
</div>
<p class="small" style="margin-top:18px">La comprensión no se evalúa con código, porque no hay nada que programar. Los niveles están en <span class="mono">taller/criterios-de-evaluacion.md</span>.</p>''',
          'Los tres pesos los fijó el instructor: ejecución y reproducibilidad cuarenta, evidencias treinta y comprensión treinta. Dentro de la comprensión hay tres cosas: la explicación de arquitectura de cada captura, la puerta de calidad explicada con las cifras y con el motivo del ruido, y al menos tres carencias para una producción real, como orquestación, seguridad de acceso, observabilidad o monitorización del modelo, cada una con su riesgo. El reparto de puntos dentro de cada criterio es una propuesta y está en el documento de criterios.')

    slide('D', 2, 'Errores típicos que ya vimos', 'Si algo falla', 'Errores que ya vimos', f'''
<div class="grid2" style="gap:16px 20px">
 <div class="card err">{captura('cs-taller-02.webp', 'Diálogo de confianza de la carpeta en el Codespace')}
  <div><h3>¿Confía en los autores de los archivos?</h3><p class="small">Pulsa <b>Confiar en la carpeta y continuar</b>. Sin eso la terminal no ejecuta nada.</p></div></div>
 <div class="card err">{captura('cs-taller-03.webp', 'Aviso del modo de recuperación del Codespace')}
  <div><h3>Modo de recuperación</h3><p class="small"><b>View Creation Log</b>, luego <span class="mono">Ctrl+Mayús+P</span>, «Codespaces: Rebuild Container» y unos 4 a 5 min. Si repite, borra el Codespace y crea otro.</p></div></div>
 <div class="card err">{captura('cs-taller-07.webp', 'Error de docker image ls con dos argumentos')}
  <div><h3>Docker dice «requires at most 1 argument»</h3><p class="small">Un solo argumento, entre comillas:</p>
  {orden_suelta("docker image ls 'cafe-*'")}</div></div>
 <div class="card err sin">
  <div><h3>Los workflows de tu fork están desactivados</h3><p class="small">GitHub los desactiva en un fork. En la pestaña <b>Actions</b> pulsa «I understand my workflows, go ahead and enable them».</p></div></div>
</div>''',
          'Son los cuatro fallos que aparecieron al probar el recorrido de verdad. Primero, el diálogo de confianza: sin confiar en la carpeta la terminal no ejecuta nada. Segundo, el modo de recuperación del Codespace, que ocurrió en la primera prueba por un repositorio de apt con la clave caducada; ya está corregido en la plantilla, pero si aparece se mira el registro de creación y se reconstruye el contenedor. Tercero, con Docker 29 la orden docker image ls no admite dos argumentos: se usa una sola con comillas. Cuarto, un fork trae los workflows desactivados hasta que el dueño los habilita.')

    slide('D', 1, 'Fecha y canal de entrega', 'La entrega', 'Cuándo y cómo se entrega', f'''
<div class="grid2" style="grid-template-columns:1fr 1.1fr">
 <div class="card pri fecha"><p class="kick" style="color:#cfe3f7">Fecha de entrega</p><p class="gran">Lunes 30/11/2026</p><p class="small" style="color:#e5e7eb">Durante ese día. No hay una hora límite concreta.</p></div>
 <div class="col">
  {tarjeta('Un solo canal del curso', lista(['El chat del grupo', 'Google Classroom', 'El correo del curso'], 'chica'))}
  {tarjeta('Qué envías', '<p class="small">El enlace de tu fork:</p><p class="mono" style="display:inline-block;margin-top:6px">https://github.com/&lt;tu-usuario&gt;/' + FORK + '</p>')}
 </div>
</div>
<p class="small" style="margin-top:20px">Antes de enviarlo, ábrelo en una ventana privada del navegador, sin tu sesión: si lo ves tú, lo verá también el instructor. Al terminar, para el Codespace para no gastar cuota.</p>''',
          'La entrega es el lunes 30 de noviembre de 2026, durante todo el día, sin hora límite. No hay formulario: cada alumno envía el enlace de su fork por un solo canal, el chat del grupo del curso, Google Classroom o el correo del curso. Pida que abran el enlace en una ventana privada antes de enviarlo: si el repositorio es privado o el nombre no es el exacto, no se puede evaluar. Recuerde parar el Codespace al terminar.')

    slide('D', 1, 'Cierre', 'Para terminar', 'Qué te llevas', f'''
<div class="grid3">
 {tarjeta('1. Todo desplegado', '<p class="small">La cadena entera, de los datos a la interfaz, funcionando en contenedores y comprobada por GitHub Actions. Sin programar.</p>')}
 {tarjeta('2. Cada pieza cubre un riesgo', '<p class="small">Entorno, pipelines, modelo, imágenes, red y workflows existen por una decisión. Esa decisión es lo que explicas.</p>')}
 {tarjeta('3. La puerta es tuya', '<p class="small">Un modelo nuevo no se publica si empeora, pero la tolerancia la decide una persona y la justifica.</p>')}
</div>
<div class="card gris" style="margin-top:22px"><h3>Dónde mirar</h3>{lista(['`taller/guia-detallada.md`: cada paso, con lo que debes ver y qué hacer si falla',
        '`taller/instrucciones.md`, `taller/criterios-de-evaluacion.md` y `taller/checklist.md`',
        'Si algo no se resuelve, guarda la captura del error, anota el paso y consúltalo con el instructor antes de la fecha de entrega'], 'chica')}</div>''',
          'Cierre con tres ideas: se despliega toda la cadena sin programar, cada pieza responde a una decisión de arquitectura que hay que saber explicar, y la puerta de calidad es una decisión humana que se justifica. Recuerde dónde está la documentación y la fecha. Si alguien se atasca, que guarde la captura del error, anote el paso y consulte antes de la fecha de entrega.')


# =====================================================================================================================================
# Marco: CSS (paleta UNTRM) y JavaScript del visor (mismas teclas y comportamiento que las presentaciones del curso)
# =====================================================================================================================================
CSS = r"""
:root{
  --pri:#003769;--sec:#0063b1;--osc:#002a52;--g1:#f3f4f6;--g2:#e5e7eb;--g3:#6b7280;--g4:#374151;--bg:#f4f4f9;--txt:#1a1a1a;
  --punta:#8fc3f0;
  --mono:ui-monospace,"Cascadia Code","SFMono-Regular",Consolas,Menlo,monospace;
  --sans:"Segoe UI",system-ui,-apple-system,Roboto,"Helvetica Neue",Arial,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:var(--bg);color:var(--txt);font-family:var(--sans);overflow:hidden}
button{font:inherit;color:inherit;cursor:pointer;background:none;border:0}
a{color:var(--sec)}
code,.mono{font-family:var(--mono)}
.mono{color:var(--osc);background:var(--g1);border:1px solid var(--g2);border-radius:4px;padding:0 5px;font-size:.88em;overflow-wrap:anywhere}
:focus-visible{outline:3px solid var(--sec);outline-offset:2px}

/* ---------- Escenario 1280x720 escalado ---------- */
#viewport{position:fixed;left:0;right:0;top:0;bottom:46px;overflow:hidden;background:var(--bg)}
#stage{position:absolute;left:50%;top:50%;width:1280px;height:720px;transform:translate(-50%,-50%) scale(var(--s,1));transform-origin:center center}
.slide{position:absolute;inset:0;padding:40px 60px 76px;opacity:0;visibility:hidden;transition:opacity .3s ease,visibility 0s .3s;background:var(--bg);overflow:hidden}
.slide.active{opacity:1;visibility:visible;transition:opacity .3s ease}
.slide::before{content:"";position:absolute;inset:0 0 auto 0;height:8px;background:var(--pri)}
.foot{position:absolute;left:60px;right:60px;bottom:0;height:56px;border-top:1px solid var(--g2);display:flex;align-items:center;gap:14px;font-size:13.5px;color:var(--g4)}
.foot img{height:34px;width:auto;flex:none}
.foot .t{flex:1}
.foot b{color:var(--pri);font-weight:600}
.foot .n{font-variant-numeric:tabular-nums;color:var(--pri);font-weight:600}

/* ---------- Texto ---------- */
.kick{font-size:14px;letter-spacing:.14em;text-transform:uppercase;color:var(--sec);font-weight:700;margin-bottom:8px}
h1{font-size:40px;line-height:1.15;letter-spacing:-.01em;margin-bottom:22px;font-weight:700;color:var(--pri)}
h3{font-size:20px;margin-bottom:8px;color:var(--pri)}
p{font-size:21px;line-height:1.45}
.lead{font-size:26px;line-height:1.4;color:var(--g4)}
.small{font-size:18px;line-height:1.45;color:var(--g4)}
b{color:var(--pri);font-weight:700}
.card{background:#fff;border:1px solid var(--g2);border-radius:8px;padding:16px 20px;min-width:0}
.card.gris{background:var(--g1);border-color:#cfd3da}
.card.pri{background:var(--pri);border-color:var(--pri);color:#fff}
.card.pri h3,.card.pri b,.card.pri .cifra{color:#fff}
.card.pri .mono{background:rgba(255,255,255,.14);border-color:rgba(255,255,255,.3);color:#fff}
.card.pri .small{color:#e5e7eb}
.card.pri .list li::before{background:#fff}
.cifra{font-size:15px;font-weight:700;letter-spacing:.14em;color:var(--sec);margin-bottom:8px}
.card.gris .cifra{color:var(--g4)}
.tag{display:inline-block;font-size:13px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;padding:4px 12px;border-radius:999px;border:1px solid var(--sec);color:var(--sec);background:#fff;white-space:nowrap}
.tag.core{background:var(--sec);color:#fff}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:22px}
.callout{border-left:5px solid var(--sec);background:#fff;border-top:1px solid var(--g2);border-right:1px solid var(--g2);border-bottom:1px solid var(--g2);padding:14px 18px;border-radius:0 8px 8px 0;font-size:19px;line-height:1.45}
.list{list-style:none;display:flex;flex-direction:column;gap:11px}
.list li{display:flex;gap:12px;align-items:flex-start;font-size:23px;line-height:1.38}
.list li::before{content:"";flex:none;width:9px;height:9px;margin-top:10px;background:var(--sec)}
.list.chica{gap:7px}.list.chica li{font-size:19px;line-height:1.38}.list.chica li::before{margin-top:8px;width:8px;height:8px}
.col{display:flex;flex-direction:column;gap:16px;min-width:0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.grid3{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}

/* ---------- Portada ---------- */
.cover{display:grid;grid-template-columns:1.25fr .75fr;gap:30px;align-items:center;height:420px}
.cover h1{font-size:50px}
.cover-escudo{display:grid;place-items:center}
.cover-escudo img{width:270px;height:auto}

/* ---------- Diagrama a un lado ---------- */
.side{display:grid;gap:30px;align-items:start;margin-top:-8px}
.dgm{border:1px solid var(--g2);border-radius:6px;background:#fff;overflow:hidden;line-height:0}
.dgm svg{display:block}
.sidet{min-width:0;padding-top:8px}
.sidet h1{font-size:36px}
.sidet .list li{font-size:21px}.sidet .list.chica li{font-size:18px}

/* ---------- Terminal ---------- */
.term{background:var(--osc);border:1px solid var(--pri);border-radius:8px;overflow:hidden}
.term .bar{display:flex;align-items:center;gap:7px;padding:8px 12px;background:var(--pri);font-size:13px;color:#cfe3f7}
.term .bar i{width:10px;height:10px;border-radius:50%;background:#9db4cc}
.term .bar em{margin-left:8px;font-style:normal;flex:1}
.tls{padding:8px 10px 10px;font-family:var(--mono);font-size:18px;line-height:1.45}
.tln{display:flex;align-items:flex-start;gap:8px;padding:3px 4px;border-radius:5px}
.tln:hover{background:rgba(255,255,255,.06)}
.tln code{flex:1;white-space:pre-wrap;overflow-wrap:anywhere;color:#fff}
.tln.c{color:#b8c9dc;font-style:italic;padding-top:6px}
.ps{color:var(--punta)}
.cp{flex:none;width:28px;height:26px;border-radius:5px;border:1px solid rgba(255,255,255,.4);font-size:14px;color:#e5e7eb}
.cp:hover{border-color:var(--punta);color:#fff}
.cp.ok{border-color:#fff;background:rgba(255,255,255,.18);color:#fff}
.cpall{width:auto;padding:0 10px;font-family:var(--sans);font-size:12.5px}
.tln.solo{background:var(--osc);color:#fff;font-family:var(--mono);font-size:15px;border-radius:6px;padding:5px 8px;margin-top:6px;align-items:center}

/* ---------- Tablas, capturas, cuadrículas ---------- */
.tbl{border-collapse:collapse;width:100%;background:#fff;font-size:19px}
.tbl th{background:var(--pri);color:#fff;text-align:left;padding:7px 12px;font-size:14px;letter-spacing:.08em;text-transform:uppercase}
.tbl td{padding:8px 12px;border:1px solid var(--g2)}
.capcol{display:flex;flex-direction:column;gap:8px;min-width:0}
.capimg{display:block;width:100%;height:auto;border:1px solid var(--g3);border-radius:6px;background:#fff}
.capa{display:block;cursor:zoom-in}
.capa:hover .capimg{border-color:var(--sec);box-shadow:0 0 0 2px var(--sec)}
.err{display:grid;grid-template-columns:230px 1fr;gap:18px;align-items:start}
.err.sin{grid-template-columns:1fr;border-left:5px solid var(--sec)}
.err h3{font-size:20px;line-height:1.25}
.err .small{font-size:18px}
.cap16{background:#fff;border:1px solid var(--g2);border-radius:6px;padding:10px 10px 8px;display:flex;flex-direction:column;gap:5px;align-items:flex-start;min-width:0}
.cap16 .mono{font-size:13.5px;border:0;background:var(--g1)}
.cap16 small{font-size:14px;color:var(--g4)}
.stack{display:flex;height:46px;border-radius:6px;overflow:hidden}
.stack div{display:grid;place-items:center;color:#fff;font-weight:700;font-size:22px}
.fecha{display:flex;flex-direction:column;justify-content:center;min-height:210px}
.fecha .gran{font-size:44px;font-weight:700;line-height:1.1;margin:6px 0 10px;color:#fff}

/* ---------- Barra inferior, notas, índice ---------- */
#bar{position:fixed;left:0;right:0;bottom:0;height:46px;background:var(--osc);color:#fff;display:flex;align-items:center;gap:6px;padding:0 12px;font-size:14px;z-index:20}
#bar button,#bar a#bhome{padding:6px 11px;border-radius:6px;color:#fff;text-decoration:none;white-space:nowrap}
#bar button:hover,#bar a#bhome:hover{background:var(--pri)}
#bar .sp{flex:1}
#bar .part{color:#b8c9dc}#bar .part.on{color:#fff;font-weight:700;box-shadow:inset 0 -3px 0 #fff}
#prog{position:fixed;left:0;top:0;height:4px;background:var(--sec);z-index:30;transition:width .3s}
#clockref{color:#b8c9dc;font-variant-numeric:tabular-nums;margin:0 8px}
#notes{position:fixed;right:0;top:0;bottom:46px;width:min(400px,90vw);background:#fff;border-left:1px solid var(--g2);padding:22px 20px;transform:translateX(100%);transition:transform .3s;z-index:25;overflow:auto;box-shadow:-6px 0 18px rgba(0,0,0,.08)}
#notes.on{transform:none}
#notes h3{color:var(--sec);font-size:14px;letter-spacing:.14em;text-transform:uppercase;margin-bottom:10px}
#notes p{font-size:16px;line-height:1.5;color:var(--txt);margin-bottom:10px}
#notes .small{font-size:14px}
#index{position:fixed;inset:0 0 46px 0;background:var(--bg);z-index:26;padding:28px 38px;overflow:auto;display:none}
#index.on{display:block}
#index h2{margin-bottom:16px;color:var(--pri)}
#index .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px}
#index button{text-align:left;padding:12px 14px;border-radius:8px;background:#fff;border:1px solid var(--g2)}
#index button:hover{border-color:var(--sec)}
#index small{display:block;color:var(--sec);font-size:12px;letter-spacing:.1em;text-transform:uppercase}
#index button.cur{border-color:var(--pri);box-shadow:0 0 0 2px var(--pri)}
noscript{position:fixed;inset:0;display:grid;place-items:center;font-size:22px;padding:40px;text-align:center;background:var(--bg)}

/* ---------- Impresión y PDF: una diapositiva por página, sin controles ---------- */
@media print{
  @page{size:1280px 720px;margin:0}
  html,body{overflow:visible;height:auto;background:#fff}
  #bar,#notes,#index,#prog,.cp,.cpall{display:none!important}
  #viewport{position:static;overflow:visible}
  #stage{position:static;transform:none;width:1280px;height:720px}
  .slide{display:none;position:relative;opacity:1;visibility:visible;transition:none;width:1280px;height:720px}
  .slide.pdf-solo{display:block}
}
"""

JS = r"""
(function(){
'use strict';
const $=(s,r)=> (r||document).querySelector(s), $$=(s,r)=>[...(r||document).querySelectorAll(s)];
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function copyText(t){try{await navigator.clipboard.writeText(t);return true}catch(e){try{const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove();return true}catch(e2){return false}}}
const PARTES=__PARTES__;
const slides=$$('.slide'); const N=slides.length;
let cur=0;
const cum=[];(()=>{let t=0;slides.forEach(s=>{cum.push(t);t+=+s.dataset.min||0})})();
const TOTAL=cum[N-1]+(+slides[N-1].dataset.min||0);
function go(i){
  i=Math.max(0,Math.min(N-1,i)); cur=i;
  slides.forEach((s,k)=>{s.classList.toggle('active',k===i)});
  chrome();
  try{history.replaceState(null,'','#'+(i+1))}catch(e){}
}
function next(){ if(cur<N-1) go(cur+1) }
function prev(){ if(cur>0) go(cur-1) }
function chrome(){
  const s=slides[cur];
  $('#count').textContent=(cur+1)+' / '+N;
  $('#clockref').textContent='min '+cum[cur]+' de '+TOTAL;
  $('#prog').style.width=((cur+1)/N*100)+'%';
  $$('#bar .part').forEach(b=>b.classList.toggle('on',b.dataset.p===s.dataset.part));
  $('#notetext').innerHTML='<p>'+esc(s.dataset.notes||'')+'</p>';
  $('#notemin').textContent='Tiempo previsto: '+(s.dataset.min||0)+' min · acumulado '+cum[cur]+' min de '+TOTAL;
  $$('#idxgrid button').forEach((b,k)=>b.classList.toggle('cur',k===cur));
}
function fit(){const v=$('#viewport'); const sc=Math.min(v.clientWidth/1280,v.clientHeight/720); $('#stage').style.setProperty('--s',sc.toFixed(4))}
addEventListener('resize',fit);
$('#idxgrid').innerHTML=slides.map((s,i)=>`<button data-i="${i}"><small>${esc(PARTES[s.dataset.part]||'')} · ${s.dataset.min||0} min</small>${i+1}. ${esc(s.dataset.title||'')}</button>`).join('');
$('#idxgrid').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;toggle('#index',false);go(+b.dataset.i)});
function toggle(sel,force){$(sel).classList.toggle('on',force)}
$('#bprev').onclick=prev; $('#bnext').onclick=next;
$('#bidx').onclick=()=>toggle('#index'); $('#bnotes').onclick=()=>toggle('#notes');
$('#bfull').onclick=()=>{ if(document.fullscreenElement) document.exitFullscreen(); else document.documentElement.requestFullscreen&&document.documentElement.requestFullscreen() };
$$('#bar .part').forEach(b=>b.onclick=()=>{const k=slides.findIndex(s=>s.dataset.part===b.dataset.p);go(k)});
addEventListener('keydown',e=>{
  const t=e.target; if(t&&/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)) return;
  if(e.ctrlKey||e.metaKey||e.altKey) return;
  const k=e.key;
  if(k==='ArrowRight'||k==='PageDown'||(k===' '&&!/^(BUTTON|A)$/.test(t.tagName))){e.preventDefault();next()}
  else if(k==='ArrowLeft'||k==='PageUp'){e.preventDefault();prev()}
  else if(k==='Home'){e.preventDefault();go(0)}
  else if(k==='End'){e.preventDefault();go(N-1)}
  else if(k==='o'||k==='O'){toggle('#index')}
  else if(k==='s'||k==='S'){toggle('#notes')}
  else if(k==='f'||k==='F'){$('#bfull').click()}
  else if(k==='Escape'){toggle('#index',false);toggle('#notes',false)}
});
let tx=null;
addEventListener('touchstart',e=>{tx=e.touches[0].clientX},{passive:true});
addEventListener('touchend',e=>{if(tx===null)return;const dx=e.changedTouches[0].clientX-tx;tx=null;if(Math.abs(dx)>60){dx<0?next():prev()}},{passive:true});

/* Copiar órdenes */
document.addEventListener('click',async e=>{const b=e.target.closest('.cp'); if(!b) return; e.stopPropagation();
  const ok=await copyText(b.dataset.t); const t=b.textContent; b.classList.add('ok'); b.textContent=ok?'✓':'✗'; setTimeout(()=>{b.classList.remove('ok');b.textContent=t},1200)});

fit();
const h=parseInt((location.hash||'').slice(1),10);
go(isNaN(h)?0:h-1);
addEventListener('hashchange',()=>{const n=parseInt((location.hash||'').slice(1),10);if(!isNaN(n)&&n-1!==cur)go(n-1)});
})();
"""


def pie(i, n):
    return (f'<div class="foot"><img src="img/{ESCUDO}" alt="Escudo de la UNTRM"><span class="t"><b>{esc(TITULO_TAREA)}</b></span>'
            f'<span>{esc(PROFESOR)}</span><span class="n">{i} / {n}</span></div>')


def html_completo():
    construir()
    total = sum(s['min'] for s in SLIDES)
    n = len(SLIDES)
    secciones = []
    for i, s in enumerate(SLIDES, 1):
        cuerpo = s['cuerpo'].replace('@@MIN@@', str(total))
        secciones.append(f'<section class="slide" data-part="{s["parte"]}" data-min="{s["min"]}" data-title="{esc(s["titulo"])}"\n'
                         f' data-notes="{esc(s["notas"])}">\n{cuerpo}\n{pie(i, n)}\n</section>')
    botones = ''.join(f'<button class="part" data-p="{k}">{esc(v)}</button>' for k, v in PARTES.items())
    js = JS.replace('__PARTES__', '{' + ','.join(f'"{k}":"{v}"' for k, v in PARTES.items()) + '}')
    return ('<!doctype html>\n<html lang="es">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{esc(TITULO_TAREA)}: diapositivas</title>\n'
            f'<!-- Generado por generar.py: no se edita a mano. -->\n<style>{CSS}</style>\n</head>\n<body>\n'
            '<div id="prog"></div>\n<div id="viewport"><div id="stage">\n\n' + '\n\n'.join(secciones) + '\n\n</div></div>\n\n'
            '<aside id="notes" aria-label="Notas del ponente"><h3>Notas del ponente</h3><div id="notetext"></div><p class="small" id="notemin"></p></aside>\n'
            '<div id="index" aria-label="Índice"><h2>Índice</h2><div class="grid" id="idxgrid"></div></div>\n'
            '<nav id="bar" aria-label="Controles">\n'
            '  <button id="bprev" aria-label="Anterior">←</button><button id="bnext" aria-label="Siguiente">→</button>\n'
            '  <span id="count">1 / 1</span><span id="clockref" title="Minuto planificado acumulado"></span>\n'
            f'  {botones}\n'
            '  <span class="sp"></span>\n'
            '  <a id="bhome" href="../instrucciones.md" title="Volver a las instrucciones de la tarea">⌂ Instrucciones</a><button id="bidx">Índice (O)</button><button id="bnotes">Notas (S)</button><button id="bfull">Pantalla completa (F)</button>\n'
            '</nav>\n'
            '<noscript>Estas diapositivas necesitan JavaScript. El mismo contenido está en taller/instrucciones.md y taller/guia-detallada.md.</noscript>\n\n'
            f'<script>{js}</script>\n</body>\n</html>\n')


def imagenes_necesarias():
    """(origen, destino) de cada archivo que copian las diapositivas."""
    return [(DOCS_IMG / c, IMG / c) for c in CAPTURAS] + [(ESCUDO_ORIGEN, IMG / ESCUDO)]


def imagenes_al_dia():
    return all(d.is_file() and d.read_bytes() == o.read_bytes() for o, d in imagenes_necesarias())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--comprobar', action='store_true')
    a = ap.parse_args()
    nuevo = html_completo()
    actual = SALIDA.read_text(encoding='utf-8') if SALIDA.exists() else None
    if a.comprobar:
        if actual != nuevo or not imagenes_al_dia():
            print('DESFASADO: ejecuta python generar.py')
            sys.exit(1)
        print('al día')
        return
    IMG.mkdir(exist_ok=True)
    for o, d in imagenes_necesarias():
        if not d.is_file() or d.read_bytes() != o.read_bytes():
            shutil.copyfile(o, d)
    for f in IMG.iterdir():                      # no sobra ninguna imagen
        if f.name not in CAPTURAS + [ESCUDO]:
            f.unlink()
    if actual == nuevo:
        print('sin cambios')
    else:
        SALIDA.write_text(nuevo, encoding='utf-8', newline='\n')
        minutos = sum(int(m) for m in re.findall(r'data-min="(\d+)"', nuevo))
        print(f'escrito {SALIDA.name}: {len(SLIDES)} diapositivas, {minutos} min')


if __name__ == '__main__':
    main()

"""Comprueba que la entrega del taller esta completa en el arbol de un fork (solo biblioteca estandar).

Lo ejecuta el workflow `comprobar-entrega.yml` en el fork del alumno, y tambien se puede ejecutar a mano en el Codespace:

    python taller/comprobar_entrega.py

QUE COMPRUEBA (solo presencia y forma; no evalua nada):
    1. el nombre del repositorio es `taller-ml-ia-dev-production`;
    2. en `evidencias/capturas/` estan las 16 capturas, con su nombre exacto, extension png / jpg / jpeg / webp y tamano mayor que 0;
    3. en `evidencias/video/` hay exactamente un MP4, llamado `servicio-en-produccion.mp4`, de menos de 50 MB;
    4. `evidencias/plantilla-evidencias.md` ya no conserva ningun marcador `[ESCRIBE AQUÍ]` sin rellenar.

QUE NO PUEDE COMPROBAR: la duracion del video (de 2 a 4 minutos), que lleve voz, que se vea la interfaz, que las capturas sean tuyas
ni que tus explicaciones sean buenas. Eso lo revisa el instructor.

SALIDA: anotaciones `::notice` / `::error` de GitHub Actions y, si existe la variable GITHUB_STEP_SUMMARY (o con --resumen), una tabla
en Markdown con «Cumple» / «Falta». Codigo de salida: 0 si todo cumple (o si el repositorio es la plantilla), 1 si falta algo.

Sin dependencias, sin red y sin secretos: solo lee el arbol del repositorio.
"""
import argparse
import difflib
import os
import sys
from pathlib import Path

NOMBRE_REPOSITORIO = 'taller-ml-ia-dev-production'
NOMBRE_PLANTILLA = 'curso-ml-ia-desarrollo-produccion-tarea'      # el repositorio plantilla del instructor: no es una entrega
MARCADOR = '[ESCRIBE AQUÍ]'
EXTENSIONES = ('.png', '.jpg', '.jpeg', '.webp')
NOMBRE_VIDEO = 'servicio-en-produccion.mp4'
LIMITE_VIDEO = 50 * 1024 * 1024          # 50 MB como los muestran `ls -lh` y el Explorador de Windows (1 MB = 1 048 576 bytes)
CAPTURAS = (
    '01-fork-renombrado', '02-codespace-abierto', '03-verificar-entorno', '04-pipeline', '05-pipeline-sin-cambios',
    '06-modelo-version', '07-imagenes', '08-compose-sano', '09-puerto-8090', '10-ui-cabecera', '11-ui-resultado',
    '12-validar-verde', '13-environment-produccion', '14-nueva-version-rechazada', '15-nueva-version-aprobacion',
    '16-paquetes-y-pr',
)
NO_COMPROBABLE = ('No se puede comprobar aqui: la duracion del video (de 2 a 4 minutos), que tenga tu voz, que se vea la interfaz con '
                  'tu repositorio, que las capturas sean tuyas ni que tus explicaciones de arquitectura sean buenas. '
                  'Eso lo revisa el instructor.')


class Resultado:
    """Una comprobacion: `cumple`, un titulo corto y un mensaje que dice QUE falta y QUE hacer."""

    def __init__(self, clave, titulo, cumple, mensaje, filas=()):
        self.clave, self.titulo, self.cumple, self.mensaje, self.filas = clave, titulo, cumple, mensaje, list(filas)


def _megas(n):
    return f'{n / (1024 * 1024):.1f} MB'


# ------------------------------------------------------------------------------------------------------------- comprobaciones
def comprobar_nombre(nombre):
    if not nombre:
        return Resultado('nombre', 'Nombre del repositorio', False,
                         f'No se pudo saber el nombre del repositorio. Debe ser exactamente `{NOMBRE_REPOSITORIO}`.')
    if nombre == NOMBRE_REPOSITORIO:
        return Resultado('nombre', 'Nombre del repositorio', True, f'El repositorio se llama `{nombre}`.')
    return Resultado('nombre', 'Nombre del repositorio', False,
                     f'El repositorio se llama `{nombre}` y debe llamarse exactamente `{NOMBRE_REPOSITORIO}`. '
                     'Renombralo en Settings > General > Repository name.')


def comprobar_capturas(raiz):
    carpeta = Path(raiz) / 'evidencias' / 'capturas'
    archivos = sorted(p for p in carpeta.iterdir() if p.is_file()) if carpeta.is_dir() else []
    filas, faltan, vacias, repetidas, usados = [], [], [], [], set()
    for nombre in CAPTURAS:
        candidatas = [p for p in archivos if p.stem == nombre and p.suffix.lower() in EXTENSIONES]
        usados.update(candidatas)
        if not candidatas:
            filas.append((nombre, False, 'falta'))
            faltan.append(nombre)
        elif all(p.stat().st_size == 0 for p in candidatas):
            filas.append((nombre, False, 'esta vacia (0 bytes)'))
            vacias.append(nombre)
        else:
            if len(candidatas) > 1:
                repetidas.append(nombre)
            valida = next(p for p in candidatas if p.stat().st_size > 0)
            filas.append((nombre, True, valida.name))
    sobran = [p.name for p in archivos if p not in usados and p.name != '.gitkeep']
    partes = []
    if not carpeta.is_dir():
        partes.append('No existe la carpeta `evidencias/capturas/`.')
    if faltan:
        pistas = []
        for p in sobran:
            cerca = difflib.get_close_matches(Path(p).stem, faltan, n=1, cutoff=0.6)
            if cerca:
                pistas.append(f'`{p}` se parece a `{cerca[0]}` (revisa el nombre y la extension: png, jpg, jpeg o webp)')
        partes.append(f'Faltan {len(faltan)} de {len(CAPTURAS)} capturas: ' + ', '.join(f'`{n}`' for n in faltan) + '.')
        partes += [p + '.' for p in pistas]
    if vacias:
        partes.append('Capturas vacias (0 bytes): ' + ', '.join(f'`{n}`' for n in vacias) + '. Vuelve a subirlas.')
    cumple = not faltan and not vacias
    if cumple:
        partes.append(f'Estan las {len(CAPTURAS)} capturas, con tamano mayor que 0.')
    if repetidas:
        partes.append('Hay varios archivos con el mismo nombre y distinta extension: ' + ', '.join(f'`{n}`' for n in repetidas) + '.')
    otras = [p for p in sobran if not any(f'`{p}`' in x for x in partes)]
    if otras:
        partes.append('Archivos que no son ninguna captura esperada (no cuentan): ' + ', '.join(f'`{p}`' for p in otras) + '.')
    return Resultado('capturas', f'Capturas ({len(CAPTURAS) - len(faltan) - len(vacias)} de {len(CAPTURAS)})', cumple, ' '.join(partes), filas)


def comprobar_video(raiz):
    carpeta = Path(raiz) / 'evidencias' / 'video'
    archivos = sorted(p for p in carpeta.iterdir() if p.is_file()) if carpeta.is_dir() else []
    mp4 = [p for p in archivos if p.suffix.lower() == '.mp4']
    otros = [p.name for p in archivos if p.suffix.lower() != '.mp4' and p.name != '.gitkeep']
    titulo = 'Video MP4'
    sufijo = (' Hay archivos que no son MP4 y no cuentan: ' + ', '.join(f'`{n}`' for n in otros) + '.') if otros else ''
    if not carpeta.is_dir():
        return Resultado('video', titulo, False, 'No existe la carpeta `evidencias/video/`.')
    if not mp4:
        return Resultado('video', titulo, False, f'No hay ningun MP4 en `evidencias/video/`. Sube `{NOMBRE_VIDEO}`.' + sufijo)
    if len(mp4) > 1:
        return Resultado('video', titulo, False, f'Hay {len(mp4)} MP4 en `evidencias/video/` ({", ".join(f"`{p.name}`" for p in mp4)}) '
                         f'y debe haber exactamente uno: `{NOMBRE_VIDEO}`. Borra los demas.' + sufijo)
    p = mp4[0]
    tam = p.stat().st_size
    problemas = []
    if p.name != NOMBRE_VIDEO:
        problemas.append(f'se llama `{p.name}` y debe llamarse exactamente `{NOMBRE_VIDEO}`')
    if tam == 0:
        problemas.append('esta vacio (0 bytes)')
    elif tam >= LIMITE_VIDEO:
        problemas.append(f'pesa {_megas(tam)} y debe pesar menos de 50 MB (la guia de grabacion explica como comprimirlo)')
    if problemas:
        return Resultado('video', titulo, False, f'El MP4 {"; ".join(problemas)}.' + sufijo)
    return Resultado('video', titulo, True, f'Hay un solo MP4, `{p.name}`, de {_megas(tam)} (menos de 50 MB).' + sufijo)


def comprobar_plantilla(raiz):
    ruta = Path(raiz) / 'evidencias' / 'plantilla-evidencias.md'
    titulo = 'Plantilla de evidencias rellena'
    if not ruta.is_file():
        return Resultado('plantilla', titulo, False, 'No existe `evidencias/plantilla-evidencias.md`. No la borres: es donde explicas la arquitectura.')
    lineas = ruta.read_text(encoding='utf-8', errors='replace').splitlines()
    pendientes = [n for n, linea in enumerate(lineas, 1) if MARCADOR in linea]
    if not pendientes:
        return Resultado('plantilla', titulo, True, f'No queda ningun marcador `{MARCADOR}` sin rellenar.')
    primeras = ', '.join(str(n) for n in pendientes[:10]) + (' ...' if len(pendientes) > 10 else '')
    return Resultado('plantilla', titulo, False, f'Quedan {len(pendientes)} marcadores `{MARCADOR}` sin rellenar en '
                     f'`evidencias/plantilla-evidencias.md` (lineas {primeras}). Sustituyelos por tu texto.')


def nombre_del_repositorio(repo=None, entorno=None):
    """`--repo`, o NOMBRE_REPOSITORIO, o la parte de GITHUB_REPOSITORY posterior a la barra. Vacio si no se sabe."""
    entorno = os.environ if entorno is None else entorno
    for valor in (repo, entorno.get('NOMBRE_REPOSITORIO'), (entorno.get('GITHUB_REPOSITORY') or '').split('/')[-1]):
        if valor and valor.strip():
            return valor.strip().split('/')[-1]
    return ''


def comprobar(raiz, nombre_repositorio):
    """Las cuatro comprobaciones, en orden."""
    return [comprobar_nombre(nombre_repositorio), comprobar_capturas(raiz), comprobar_video(raiz), comprobar_plantilla(raiz)]


# ------------------------------------------------------------------------------------------------------------- salida
def _dato(texto):
    """Escapa el mensaje de un comando de workflow (GitHub exige %, CR y LF)."""
    return str(texto).replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')


def _propiedad(texto):
    return _dato(texto).replace(':', '%3A').replace(',', '%2C')


def anotaciones(resultados):
    lineas = []
    for r in resultados:
        nivel = 'notice' if r.cumple else 'error'
        lineas.append(f'::{nivel} title={_propiedad(r.titulo)}::{_dato(r.mensaje)}')
    faltan = [r for r in resultados if not r.cumple]
    if faltan:
        lineas.append(f'::error title={_propiedad("Entrega incompleta")}::Falta por cumplir: ' + _dato(', '.join(r.titulo for r in faltan)) + '.')
    else:
        lineas.append(f'::notice title={_propiedad("Entrega completa")}::Todo lo que se puede comprobar aqui cumple. ' + _dato(NO_COMPROBABLE))
    return lineas


def _celda(texto):
    return str(texto).replace('|', '\\|').replace('\n', ' ')


def resumen_markdown(resultados):
    estado = 'Todo cumple' if all(r.cumple for r in resultados) else 'Falta algo'
    salida = ['## Comprobacion de la entrega', '', f'**{estado}.** Solo se comprueba que esten los archivos y que tengan la forma pedida; '
              'no se evalua nada.', '', '| Comprobacion | Resultado | Detalle |', '|---|---|---|']
    for r in resultados:
        salida.append(f'| {_celda(r.titulo)} | {"Cumple" if r.cumple else "Falta"} | {_celda(r.mensaje)} |')
    capturas = next((r for r in resultados if r.clave == 'capturas' and r.filas), None)
    if capturas:
        salida += ['', '### Las 16 capturas', '', '| Captura | Resultado | Detalle |', '|---|---|---|']
        salida += [f'| `{n}` | {"Cumple" if ok else "Falta"} | {_celda(d)} |' for n, ok, d in capturas.filas]
    salida += ['', f'> {NO_COMPROBABLE}', '']
    return '\n'.join(salida)


def es_la_plantilla(nombre):
    return nombre == NOMBRE_PLANTILLA


def main(argumentos=None, entorno=None):
    entorno = os.environ if entorno is None else entorno
    ap = argparse.ArgumentParser(description='Comprueba que la entrega del taller esta completa (solo presencia y forma).')
    ap.add_argument('--raiz', default='.', help='raiz del repositorio (por defecto, la carpeta actual)')
    ap.add_argument('--repo', default=None, help='nombre del repositorio (por defecto NOMBRE_REPOSITORIO o GITHUB_REPOSITORY)')
    ap.add_argument('--resumen', default=None, help='archivo Markdown donde escribir la tabla (por defecto GITHUB_STEP_SUMMARY, si existe)')
    args = ap.parse_args(argumentos)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        pass
    nombre = nombre_del_repositorio(args.repo, entorno)
    destino = args.resumen or entorno.get('GITHUB_STEP_SUMMARY')
    if es_la_plantilla(nombre):
        aviso = f'`{nombre}` es el repositorio plantilla del instructor, no una entrega: no se comprueba nada.'
        print(f'::notice title={_propiedad("Repositorio plantilla")}::{_dato(aviso)}')
        if destino:
            with open(destino, 'a', encoding='utf-8') as f:
                f.write(f'## Comprobacion de la entrega\n\n{aviso}\n')
        return 0
    resultados = comprobar(args.raiz, nombre)
    for linea in anotaciones(resultados):
        print(linea)
    if destino:
        with open(destino, 'a', encoding='utf-8') as f:
            f.write(resumen_markdown(resultados))
    return 0 if all(r.cumple for r in resultados) else 1


if __name__ == '__main__':
    sys.exit(main())

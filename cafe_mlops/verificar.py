"""Verificación del entorno: ¿está todo listo para hacer el taller?

Se ejecuta DESPUÉS de crear el Codespace (el devcontainer lo lanza solo al terminar de instalar) y siempre que dudes del entorno:

    python -m cafe_mlops.verificar                 # todo, incluido Docker
    python -m cafe_mlops.verificar --sin-docker    # solo lo necesario para los pasos que no construyen imágenes

Comprueba, una línea por cosa:
    python     la versión es 3.11 (la misma que las imágenes Docker y el CI: python:3.11-slim)
    paquetes   cada paquete fijado con == en requirements-dev.txt está instalado con ESA versión exacta
    cafe_mlops el paquete del taller se puede importar (pip install -e . --no-deps)
    datos      existen los dos CSV de data/raw/cqi y su huella SHA-256 es la de SHA256SUMS
    docker     el cliente y el servidor responden (docker version) y existe «docker compose»

La última línea es «LISTO PARA EL TALLER» (código de salida 0) o «FALTA: ...» con lo que hay que arreglar (código 1).
No instala ni modifica nada: solo lee. Usa solo la biblioteca estándar.
"""
import argparse
import hashlib
import importlib
import importlib.metadata as metadata
import re
import subprocess
import sys

from . import config

PYTHON_ESPERADO = (3, 11)
REQUISITOS = config.RAIZ / 'requirements-dev.txt'
HUELLAS = config.DATA_RAW / 'cqi' / 'SHA256SUMS'
OK, FALLA = 'OK   ', 'FALLA'


def leer_fijados(texto):
    """{paquete: versión} de las líneas «paquete==versión» de un requirements. Ignora comentarios, -r y líneas sin ==."""
    fijados = {}
    for linea in texto.splitlines():
        m = re.match(r'^\s*([A-Za-z0-9_.\-]+)\s*==\s*([A-Za-z0-9_.\-+!]+)\s*(#.*)?$', linea)
        if m:
            fijados[m.group(1)] = m.group(2)
    return fijados


def leer_huellas(texto):
    """{archivo: sha256} de un archivo en formato de sha256sum («huella  nombre»)."""
    huellas = {}
    for linea in texto.splitlines():
        partes = linea.split(None, 1)
        if len(partes) == 2 and re.fullmatch(r'[0-9a-f]{64}', partes[0]):
            huellas[partes[1].strip().lstrip('*')] = partes[0]
    return huellas


def comprobar_python(version=None):
    v = tuple(version or sys.version_info[:3])
    ok = v[:2] == PYTHON_ESPERADO
    return ok, f'Python {".".join(map(str, v))}' + ('' if ok else f' (se necesita {PYTHON_ESPERADO[0]}.{PYTHON_ESPERADO[1]}.x)')


def comprobar_paquetes(fijados, instaladas=None):
    """Devuelve (ok, mensaje, lista de problemas). `instaladas` (paquete -> versión o None) permite probarlo sin tocar el entorno."""
    problemas = []
    for paquete, esperada in sorted(fijados.items()):
        try:
            tiene = instaladas.get(paquete) if instaladas is not None else metadata.version(paquete)
        except metadata.PackageNotFoundError:
            tiene = None
        if tiene is None:
            problemas.append(f'{paquete} no está instalado (se necesita {esperada})')
        elif tiene != esperada:
            problemas.append(f'{paquete} {tiene} (se necesita {esperada})')
    if problemas:
        return False, f'{len(problemas)} de {len(fijados)} paquetes no coinciden: ' + '; '.join(problemas), problemas
    return True, f'{len(fijados)} paquetes con la versión exacta de requirements-dev.txt', []


def comprobar_paquete_del_taller():
    try:
        importlib.import_module('cafe_mlops.api.app')
        return True, 'cafe_mlops se importa (API incluida)'
    except Exception as e:   # noqa: BLE001 - cualquier fallo de importación es «falta algo»; se cuenta, no se oculta
        return False, f'cafe_mlops no se puede importar: {type(e).__name__}: {e}'


def comprobar_datos(raiz_huellas=None, ruta_huellas=None):
    ruta = ruta_huellas or HUELLAS
    carpeta = raiz_huellas or ruta.parent
    if not ruta.exists():
        return False, f'falta {ruta.name} en {carpeta}'
    esperadas = leer_huellas(ruta.read_text(encoding='utf-8'))
    if not esperadas:
        return False, f'{ruta.name} no tiene ninguna huella con formato sha256sum'
    problemas = []
    for nombre, huella in sorted(esperadas.items()):
        archivo = carpeta / nombre
        if not archivo.exists():
            problemas.append(f'falta {nombre}')
        elif hashlib.sha256(archivo.read_bytes()).hexdigest() != huella:
            problemas.append(f'{nombre} no coincide con su huella (¿Git cambió los saltos de línea?)')
    if problemas:
        return False, '; '.join(problemas)
    return True, f'{len(esperadas)} CSV con la huella SHA-256 de {ruta.name}'


def _ejecutar(orden):
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        return None, 'orden no encontrada'
    except subprocess.TimeoutExpired:
        return None, 'sin respuesta en 60 s'
    return r.returncode, (r.stdout.strip() or r.stderr.strip()).splitlines()[:1] or ['']


def comprobar_docker(ejecutar=_ejecutar):
    """`ejecutar(orden)` -> (código o None, [primera línea]); se puede sustituir para probar sin Docker."""
    codigo, linea = ejecutar(['docker', 'version', '--format', 'cliente {{.Client.Version}} / servidor {{.Server.Version}}'])
    if codigo is None:
        return False, 'docker no está instalado o no está en el PATH (en el Codespace lo trae el devcontainer)'
    if codigo != 0:
        return False, f'docker no responde (¿el servidor está parado?): {linea[0]}'
    codigo_c, linea_c = ejecutar(['docker', 'compose', 'version', '--short'])
    if codigo_c != 0:
        return False, f'docker responde ({linea[0]}) pero falta «docker compose»'
    return True, f'{linea[0]} · compose {linea_c[0]}'


def verificar(con_docker=True, salida=print):
    """Ejecuta todas las comprobaciones; imprime una línea por cada una y la final. Devuelve el código de salida (0 = listo)."""
    pruebas = [('python', comprobar_python)]
    if REQUISITOS.exists():
        fijados = leer_fijados(REQUISITOS.read_text(encoding='utf-8'))
        pruebas.append(('paquetes', lambda: comprobar_paquetes(fijados)[:2]))
    else:
        pruebas.append(('paquetes', lambda: (False, f'falta {REQUISITOS.name}')))
    pruebas += [('cafe_mlops', comprobar_paquete_del_taller), ('datos', comprobar_datos)]
    if con_docker:
        pruebas.append(('docker', comprobar_docker))
    faltan = []
    for nombre, f in pruebas:
        ok, mensaje = f()
        salida(f'[{OK if ok else FALLA}] {nombre:<10} {mensaje}')
        if not ok:
            faltan.append(nombre)
    if not con_docker:
        salida('[----- ] docker     no se comprobó (--sin-docker)')
    if faltan:
        salida('FALTA: ' + ', '.join(faltan) + '. Arregla lo marcado como FALLA y vuelve a ejecutar: python -m cafe_mlops.verificar')
        return 1
    salida('LISTO PARA EL TALLER' + ('' if con_docker else ' (sin comprobar Docker)'))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Comprueba que el entorno está listo para el taller.')
    ap.add_argument('--sin-docker', action='store_true', help='no comprobar Docker (solo para pasos que no construyen imágenes)')
    a = ap.parse_args(argv)
    return verificar(con_docker=not a.sin_docker)


if __name__ == '__main__':
    raise SystemExit(main())

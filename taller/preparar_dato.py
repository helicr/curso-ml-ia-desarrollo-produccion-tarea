"""Prepara el dato del taller: copia verificada de los CSV limpios de CQI (jldbc).

Copia los dos CSV desde _exploracion/datos a data/raw/cqi, comprueba su SHA-256
frente a los originales y escribe data/raw/cqi/SHA256SUMS. La copia es byte a byte:
no cambia ninguna columna ni ninguna fila. Si el original ya no existe (por ejemplo,
tras retirar _exploracion), solo verifica los archivos que hay en data/raw/cqi.

Uso, desde la raíz del repositorio:
    python taller\\preparar_dato.py

Solo usa la biblioteca estándar. Las rutas se calculan desde este archivo.
"""

import csv
import hashlib
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "_exploracion" / "datos"
DESTINO = RAIZ / "data" / "raw" / "cqi"

# SHA-256 de los originales, filas de datos y columnas (comprobados el 14/11/2026 en _exploracion).
ARCHIVOS = {
    "arabica_data_cleaned.csv": {
        "sha256": "f99e588fcdd564e43a779a4b0f3870760018b1ffec7eab7f43db7bedf8f6d670",
        "filas": 1311,
    },
    "robusta_data_cleaned.csv": {
        "sha256": "bde9e70dc9e6d1529d4bb690c80a227766a8f747582144a30754a7d4713753bf",
        "filas": 28,
    },
}
NUM_COLUMNAS = 44


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def contar(ruta):
    with open(ruta, encoding="utf-8", newline="") as f:
        filas = list(csv.reader(f))
    return len(filas) - 1, len(filas[0])


def main():
    DESTINO.mkdir(parents=True, exist_ok=True)
    lineas_sumas = []
    for nombre, esperado in ARCHIVOS.items():
        origen = ORIGEN / nombre
        destino = DESTINO / nombre
        if origen.exists():
            if sha256(origen) != esperado["sha256"]:
                sys.exit("El SHA-256 del original no coincide: " + nombre)
            shutil.copyfile(origen, destino)
            print("Copiado:", nombre)
        elif not destino.exists():
            sys.exit("Falta el original y tampoco hay copia: " + nombre)
        else:
            print("Sin original en _exploracion; se verifica la copia:", nombre)

        if sha256(destino) != esperado["sha256"]:
            sys.exit("El SHA-256 de la copia no coincide: " + nombre)
        filas, columnas = contar(destino)
        if filas != esperado["filas"]:
            sys.exit("Numero de filas inesperado en " + nombre + ": " + str(filas))
        if columnas != NUM_COLUMNAS:
            sys.exit("Numero de columnas inesperado en " + nombre + ": " + str(columnas))
        print("  filas:", filas, " columnas:", columnas, " sha256:", esperado["sha256"])
        lineas_sumas.append(esperado["sha256"] + "  " + nombre + "\n")

    with open(DESTINO / "SHA256SUMS", "w", encoding="utf-8", newline="\n") as f:
        f.writelines(lineas_sumas)
    print("Escrito SHA256SUMS en", DESTINO)


if __name__ == "__main__":
    main()

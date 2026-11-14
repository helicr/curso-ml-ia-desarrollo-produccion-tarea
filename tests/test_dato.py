"""Pruebas del dato del taller (data/raw/cqi): copia de los CSV limpios de jldbc/coffee-quality-database.

Las rutas se calculan desde este archivo. Las comprobaciones contra el original de
_exploracion/ se omiten si esa carpeta ya no existe (por ejemplo, tras retirarla de la plantilla).
"""

import csv
import hashlib
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CQI = RAIZ / "data" / "raw" / "cqi"
SUMAS = CQI / "SHA256SUMS"
ORIGEN = RAIZ / "_exploracion" / "datos"

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


def leer_csv(ruta):
    with open(ruta, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


@pytest.mark.parametrize("nombre", ARCHIVOS)
def test_existe_el_csv(nombre):
    assert (CQI / nombre).is_file()


def test_sha256sums_lista_los_dos_csv_con_su_huella():
    assert SUMAS.is_file()
    entradas = {}
    for linea in SUMAS.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        huella, nombre = linea.split(maxsplit=1)
        entradas[nombre] = huella
    assert set(entradas) == set(ARCHIVOS)
    for nombre, huella in entradas.items():
        assert sha256(CQI / nombre) == huella, nombre


@pytest.mark.parametrize("nombre", ARCHIVOS)
def test_sha256_igual_al_del_original_conocido(nombre):
    assert sha256(CQI / nombre) == ARCHIVOS[nombre]["sha256"]


@pytest.mark.parametrize("nombre", ARCHIVOS)
def test_sha256_igual_al_original_de_exploracion(nombre):
    origen = ORIGEN / nombre
    if not origen.is_file():
        pytest.skip("No hay _exploracion/ en la plantilla; se comprueba contra el SHA-256 conocido.")
    assert sha256(CQI / nombre) == sha256(origen)


@pytest.mark.parametrize("nombre", ARCHIVOS)
def test_numero_de_filas(nombre):
    filas = leer_csv(CQI / nombre)
    assert len(filas) - 1 == ARCHIVOS[nombre]["filas"]
    origen = ORIGEN / nombre
    if origen.is_file():
        assert len(filas) == len(leer_csv(origen))


@pytest.mark.parametrize("nombre", ARCHIVOS)
def test_numero_de_columnas_y_cabecera(nombre):
    cabecera = leer_csv(CQI / nombre)[0]
    assert len(cabecera) == NUM_COLUMNAS
    origen = ORIGEN / nombre
    if origen.is_file():
        assert cabecera == leer_csv(origen)[0]


@pytest.mark.parametrize("nombre", ARCHIVOS)
def test_columna_species_con_los_dos_valores(nombre):
    filas = leer_csv(CQI / nombre)
    i = filas[0].index("Species")
    valores = {f[i] for f in filas[1:]}
    assert len(valores) == 1

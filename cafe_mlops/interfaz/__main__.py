"""Arranca la interfaz: python -m cafe_mlops.interfaz [--url http://127.0.0.1:8080] [--puerto 8090] [--host 127.0.0.1]

Por defecto: puerto TALLER_PUERTO_INTERFAZ (8090), API en TALLER_URL_API (http://127.0.0.1:8080 si no se indica) y base TALLER_DB.
"""
import argparse

import uvicorn

from .. import config
from .app import crear_app


def main(argv=None):
    ap = argparse.ArgumentParser(description='Interfaz web: lotes de cafe -> probabilidad de especialidad y recomendacion.')
    ap.add_argument('--url', default=config.URL_API_INTERFAZ, help='URL de la API del modelo (por defecto TALLER_URL_API)')
    ap.add_argument('--puerto', type=int, default=config.PUERTO_INTERFAZ, help='puerto (por defecto TALLER_PUERTO_INTERFAZ, 8090)')
    ap.add_argument('--host', default=config.HOST_INTERFAZ, help='0.0.0.0 para abrirla desde fuera (contenedor o Codespace)')
    a = ap.parse_args(argv)
    print(f'Interfaz en http://{a.host}:{a.puerto} - API del modelo: {a.url}')
    uvicorn.run(crear_app(url_api=a.url), host=a.host, port=a.puerto)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

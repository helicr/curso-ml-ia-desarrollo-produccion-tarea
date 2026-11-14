"""Arranca la API: python -m cafe_mlops.api   (TALLER_HOST_API y TALLER_PUERTO_API cambian dónde escucha)."""
import uvicorn

from .. import config

if __name__ == '__main__':
    uvicorn.run('cafe_mlops.api.app:app', host=config.HOST_API, port=config.PUERTO_API)

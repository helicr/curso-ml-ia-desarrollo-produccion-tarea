"""Registro estructurado: una línea JSON por evento, por la salida estándar.

Un contenedor (`docker logs`, Cloud Run, Kubernetes) recoge lo que sale por stdout; Cloud Logging entiende una línea JSON:
usa `severity` como nivel y `message` como texto. Sin un handler propio, uvicorn NO muestra los logs de la aplicación.

NUNCA se registran los datos del lote: solo método, ruta, código, duración e identificador de la petición.
El nivel se cambia con TALLER_LOG_NIVEL (por defecto INFO).
"""
import json
import logging
import os
import sys

NOMBRE = 'cafe_mlops.api'


class _Stdout(logging.StreamHandler):
    """Escribe en el `sys.stdout` del momento (no el de cuando se creó el handler): así funciona también con las capturas de pytest."""

    def __init__(self):
        super().__init__()
        self._marca_taller = True

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, _valor):
        pass


class FormatoJSON(logging.Formatter):
    def format(self, record):
        linea = {'severity': record.levelname, 'message': record.getMessage()}
        linea.update(getattr(record, 'campos', {}))
        if record.exc_info:
            linea['traceback'] = self.formatException(record.exc_info)   # solo al registro, nunca al cliente
        return json.dumps(linea, ensure_ascii=False)


def configurar():
    """Idempotente: se puede llamar en cada `crear_app()` sin duplicar handlers."""
    logger = logging.getLogger(NOMBRE)
    if not any(getattr(h, '_marca_taller', False) for h in logger.handlers):
        handler = _Stdout()
        handler.setFormatter(FormatoJSON())
        logger.addHandler(handler)
    logger.setLevel(os.environ.get('TALLER_LOG_NIVEL', 'INFO').upper())
    logger.propagate = False
    return logger


def registrar(nivel, mensaje, exc_info=False, **campos):
    logging.getLogger(NOMBRE).log(nivel, mensaje, exc_info=exc_info, extra={'campos': campos})

"""Interfaz web: consultar lotes por id, predecir un lote nuevo con un formulario, cargar y descargar CSV.

Es OTRO servicio, distinto de la API del modelo: la API sirve el modelo (pide las 10 variables); la interfaz conoce el dato
(lee las variables de la capa FS desde el id) y llama a la API. La imagen de la interfaz no lleva modelo ni scikit-learn.

Endpoints:
  GET  /                      la pagina (un solo HTML, sin recursos externos)
  GET  /salud                 ¿el proceso responde?  (liveness; el HEALTHCHECK de la imagen). No mira ni la base ni la API
  GET  /listo                 ¿llega a la base y a la API con modelo?  (readiness; 503 con el motivo si no)
  GET  /estado                repositorio, estado de la API y del modelo, listas del formulario, tramos y ejemplos (nunca da 503)
  POST /recomendar            {"lote_ids": [1, 2, 3]}                     lotes existentes (hasta 1000)
  GET  /recomendar/{id}       lo mismo para un lote
  POST /recomendar/nuevo      las 10 variables de un lote nuevo           (lo valida y llama a la API)
  POST /recomendar/nuevos     {"lotes": [ {...}, {...} ]}                 varios lotes nuevos (CSV), hasta 1000

Errores, siempre JSON {"detalle": ..., "errores": [...]} en español y sin trazas:
  422 la peticion no tiene sentido (id mal escrito, dato fuera de rango, categoria no permitida) · 503 no hay API, no hay modelo o no hay base.

Arranque (desde la raiz, con la API en marcha en otra terminal):  python -m cafe_mlops.interfaz     ->  http://127.0.0.1:8090
Variables: TALLER_PUERTO_INTERFAZ, TALLER_URL_API, TALLER_DB (+ TALLER_DB_SOLO_LECTURA). La base se abre SIEMPRE en solo lectura.
"""
import logging
from typing import Any

from fastapi import Body, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from ..api.registro import configurar as configurar_registro, registrar
from . import pagina
from .consulta import MAXIMO_LOTES, Consulta, NoDisponible, PeticionNoValida


class Peticion(BaseModel):
    model_config = ConfigDict(extra='forbid', json_schema_extra={'examples': [{'lote_ids': [1, 2, 3]}]})
    lote_ids: list[int] = Field(min_length=1, max_length=MAXIMO_LOTES, description='Ids de lote; los repetidos se cuentan una vez')


class Peticiones(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lotes: list[dict[str, Any]] = Field(min_length=1, max_length=MAXIMO_LOTES, description='Lotes nuevos: las 10 variables de cada uno')


def crear_app(ruta_db=None, url_api=None, http=None):
    """`url_api`: la API del modelo (por defecto TALLER_URL_API); `http`: sustituto de la llamada HTTP (solo las pruebas)."""
    configurar_registro()
    consulta = Consulta(ruta_db=ruta_db, url_api=url_api, http=http)
    app = FastAPI(title='Café CQI · interfaz de consulta', version='0.1.0',
                  description='Consulta lotes por id o prueba un lote nuevo y obtén la probabilidad de que sea café de especialidad '
                              'y una recomendación. La probabilidad la da la API del modelo.')
    app.state.consulta = consulta

    def respuesta(codigo, detalle, errores=None):
        cuerpo = {'detalle': detalle}
        if errores is not None:
            cuerpo['errores'] = errores
        return JSONResponse(status_code=codigo, content=cuerpo)

    @app.exception_handler(PeticionNoValida)
    async def no_valida(request: Request, exc: PeticionNoValida):
        return respuesta(422, str(exc), exc.errores)

    @app.exception_handler(RequestValidationError)
    async def cuerpo_invalido(request: Request, exc: RequestValidationError):
        # sin el valor recibido ni el contexto interno del validador
        errores = [{'fila': None, 'campo': '.'.join(str(p) for p in e['loc'] if p != 'body'), 'mensaje': 'Valor no válido o ausente.'} for e in exc.errors()]
        return respuesta(422, 'La petición no tiene el formato esperado: comprueba los ids (números enteros, entre 1 y '
                              f'{MAXIMO_LOTES}) o los lotes.', errores)

    @app.exception_handler(NoDisponible)
    async def no_disponible(request: Request, exc: NoDisponible):
        registrar(logging.ERROR, 'servicio no disponible', evento='no_disponible', motivo=str(exc))
        return respuesta(503, str(exc))

    @app.exception_handler(Exception)
    async def inesperado(request: Request, exc: Exception):
        registrar(logging.ERROR, 'error no controlado', exc_info=True, evento='error_no_controlado')   # la traza va al registro, no al cliente
        return respuesta(500, 'Error interno de la interfaz. Inténtalo de nuevo; si sigue, mira el registro del contenedor.')

    @app.get('/', response_class=HTMLResponse)
    def inicio():
        return pagina.HTML

    @app.get('/salud')
    def salud():
        """¿El proceso responde? (liveness). No mira ni la base ni la API."""
        return {'estado': 'ok'}

    @app.get('/listo')
    def listo():
        """¿Puede atender? Llega a la base (volumen) y a la API del modelo (red). 503 con el motivo si no."""
        return {'estado': 'listo', **consulta.comprobar()}

    @app.get('/estado')
    def estado():
        return consulta.estado()

    @app.post('/recomendar')
    def recomendar(peticion: Peticion):
        r = consulta.recomendar(peticion.lote_ids)
        registrar(logging.INFO, 'consulta', evento='consulta', pedidos=r['pedidos'], encontrados=r['encontrados'])   # cuantos, nunca cuales
        return r

    @app.get('/recomendar/{lote_id}')
    def recomendar_uno(lote_id: int):
        return consulta.recomendar([lote_id])

    @app.post('/recomendar/nuevo')
    def recomendar_nuevo(lote: dict[str, Any] = Body(...)):
        r = consulta.recomendar_nuevos([lote])
        registrar(logging.INFO, 'consulta', evento='consulta_nueva', pedidos=1, encontrados=r['encontrados'])
        return r

    @app.post('/recomendar/nuevos')
    def recomendar_nuevos(peticion: Peticiones):
        r = consulta.recomendar_nuevos(peticion.lotes)
        registrar(logging.INFO, 'consulta', evento='consulta_nuevos', pedidos=r['pedidos'], encontrados=r['encontrados'])
        return r

    return app


app = crear_app()

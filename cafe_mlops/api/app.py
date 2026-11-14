"""Aplicación FastAPI del modelo.

Endpoints:
  GET  /salud            ¿el proceso responde? (liveness; no mira el modelo)
  GET  /listo            ¿el modelo está cargado y su contrato coincide con la firma? (readiness; 503 si no)
  GET  /modelo           qué modelo es: versión, huella de los datos, variables y tipos, métricas de validación
  POST /predecir         probabilidad de especialidad de UN lote            (cuerpo: las variables del lote)
  POST /predecir/lote    probabilidad de hasta 1000 lotes                   (cuerpo: {"lotes": [ ... ]})

Respuesta de predicción: probabilidad_especialidad, modelo, version_modelo, huella_datos y avisos (categoría nunca vista, valor
fuera del rango de entrenamiento, variable sin informar: 200, no error).
Errores, siempre JSON sin trazas: 422 el cuerpo no cumple el contrato · 503 no hay modelo o su contrato no coincide ·
500 error interno (el detalle va al registro, no al cliente). Todas llevan `id_peticion`, que es también la cabecera X-Request-ID.
Cada petición deja una línea de registro en JSON (stdout) con tiempo y código; NUNCA los datos del lote.

Arranque (desde la raíz):  python -m cafe_mlops.api      (puerto TALLER_PUERTO_API, por defecto 8080; docs en /docs)
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import esquemas
from .registro import configurar as configurar_registro, registrar
from .servicio import ContratoRoto, ModeloNoDisponible, Servicio

RESPUESTAS = {422: {'model': esquemas.ErrorValidacion}, 503: {'model': esquemas.Error}, 500: {'model': esquemas.Error}}


def crear_app(carpeta_modelo=None, contrato_api=None):
    """Fábrica de la aplicación. `carpeta_modelo` permite a las pruebas apuntar a un modelo temporal; `contrato_api` (lista de
    (nombre, tipo)) lo cambian solo las pruebas, para simular un esquema que no coincide con la firma."""
    contrato = list(contrato_api) if contrato_api is not None else esquemas.contrato_del_esquema()
    configurar_registro()

    @asynccontextmanager
    async def ciclo(app):
        app.state.servicio, app.state.error_carga = None, None
        try:
            servicio = Servicio.cargar(carpeta_modelo)
            servicio.comprobar_contrato(contrato)
            app.state.servicio = servicio
            registrar(logging.INFO, 'modelo cargado', evento='modelo_cargado', huella_datos=servicio.meta['huella_datos'])
        except (ModeloNoDisponible, ContratoRoto) as e:
            # El proceso sigue vivo: /salud responde y /listo explica por qué no está listo.
            app.state.error_carga = str(e)
            registrar(logging.ERROR, 'modelo no cargado', evento='modelo_no_cargado', motivo=str(e))
        yield

    app = FastAPI(title='Café CQI · probabilidad de especialidad de un lote', version='0.1.0', lifespan=ciclo,
                  description='Dado lo que se sabe de un lote al recibirlo (antes de catarlo), ¿qué probabilidad hay de que alcance '
                              'el grado de especialidad (>= 80 puntos)?')

    @app.middleware('http')
    async def middleware_registro(request: Request, call_next):
        id_peticion = request.headers.get('x-request-id') or uuid.uuid4().hex[:12]
        request.state.id_peticion = id_peticion
        t0 = time.perf_counter()
        try:
            respuesta = await call_next(request)
        except Exception:      # noqa: BLE001 - última red de seguridad: el detalle va al registro, no al cliente
            registrar(logging.ERROR, 'error no controlado', exc_info=True, evento='error_no_controlado', id=id_peticion)
            respuesta = JSONResponse(status_code=500, content={'detalle': 'Error interno', 'id_peticion': id_peticion})
        respuesta.headers['X-Request-ID'] = id_peticion
        registrar(logging.INFO, f'{request.method} {request.url.path} {respuesta.status_code}', evento='peticion', id=id_peticion,
                  metodo=request.method, ruta=request.url.path, codigo=respuesta.status_code, ms=round(1000 * (time.perf_counter() - t0), 1))
        return respuesta

    def id_de(request):
        return getattr(request.state, 'id_peticion', None)

    def servicio_listo(request: Request):
        s = request.app.state.servicio
        if s is None:
            raise ModeloNoDisponible(request.app.state.error_carga or 'El modelo no está cargado')
        return s

    @app.exception_handler(ModeloNoDisponible)
    async def sin_modelo(request: Request, exc: ModeloNoDisponible):
        return JSONResponse(status_code=503, content={'detalle': str(exc), 'id_peticion': id_de(request)})

    @app.exception_handler(RequestValidationError)
    async def cuerpo_invalido(request: Request, exc: RequestValidationError):
        # Solo campo, mensaje y tipo: no se devuelve el valor recibido ni el contexto interno del validador.
        errores = [{'campo': '.'.join(str(p) for p in e['loc'] if p != 'body'), 'mensaje': e['msg'], 'tipo': e['type']} for e in exc.errors()]
        return JSONResponse(status_code=422, content={'detalle': 'El cuerpo no cumple el contrato de la API', 'errores': errores,
                                                      'id_peticion': id_de(request)})

    @app.get('/salud')
    def salud():
        return {'estado': 'ok'}

    @app.get('/listo', responses={503: RESPUESTAS[503]})
    def listo(request: Request):
        servicio_listo(request)
        return {'estado': 'listo'}

    @app.get('/modelo', response_model=esquemas.InfoModelo, responses={503: RESPUESTAS[503]})
    def modelo(request: Request):
        return servicio_listo(request).info()

    def _prediccion(servicio, probabilidad, avisos):
        return {'probabilidad_especialidad': probabilidad, 'modelo': servicio.meta['modelo'], 'version_modelo': servicio.version,
                'huella_datos': servicio.meta['huella_datos'], 'avisos': avisos}

    @app.post('/predecir', response_model=esquemas.Prediccion, responses=RESPUESTAS)
    def predecir(lote: esquemas.Lote, request: Request):
        s = servicio_listo(request)
        (p, avisos), = s.predecir([lote.model_dump()])
        return _prediccion(s, p, avisos)

    @app.post('/predecir/lote', response_model=esquemas.PrediccionLote, responses=RESPUESTAS)
    def predecir_lote(cuerpo: esquemas.LotesAPredecir, request: Request):
        s = servicio_listo(request)
        return {'predicciones': [_prediccion(s, p, a) for p, a in s.predecir([lote.model_dump() for lote in cuerpo.lotes])]}

    return app


app = crear_app()

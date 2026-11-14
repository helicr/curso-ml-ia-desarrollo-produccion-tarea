"""Contrato de la API: qué se recibe y qué se devuelve.

El contrato NO se escribe a mano dos veces: el modelo guarda su firma (nombres y tipos, string / double) y al arrancar el servicio
comprueba que este esquema tiene EXACTAMENTE los mismos nombres y los mismos tipos (servicio.comprobar_contrato). Si no coinciden,
/listo da 503 y dice qué variable falla.

Qué se rechaza (422) y qué se avisa (200 con `avisos`):
  · Se rechaza lo imposible o ambiguo: campos desconocidos o ausentes, altitud fuera de 100-4000, humedad fuera de 0-1, defectos
    negativos, cadenas o booleanos en los números (estrictos), especie / método / color fuera de sus listas cerradas.
  · Se avisa lo válido que el modelo no vio al entrenar: un país o una variedad nunca vistos, un valor fuera del rango de train,
    una variable sin informar. El modelo sabe tratarlos (one-hot en ceros, imputación), pero la predicción tiene menos respaldo.
Los límites salen de las reglas de MASTER (config.ALTITUD_MIN_M...), no de lo visto al entrenar.

Todas las variables deben estar en el cuerpo; las que pueden faltar en el dato real admiten `null` explícito.
"""
import types
from typing import Any, Literal, Optional, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .. import config

# Las listas cerradas son los valores que existen en MASTER (tests/test_api.py las compara con los CSV).
Especie = Literal['Arabica', 'Robusta']
MetodoProceso = Literal['Washed / Wet', 'Natural / Dry', 'Semi-washed / Semi-pulped', 'Other', 'Pulped natural / honey']
Color = Literal['Green', 'Bluish-Green', 'Blue-Green', 'None']    # 'None' es un valor literal del CSV (52 lotes), no un nulo

MAX_TEXTO = 100          # longitud máxima de país y variedad
MAX_DEFECTOS = 1000      # tope razonable de defectos por muestra
MAX_LOTES = 1000         # lotes por petición de /predecir/lote

EJEMPLO = {
    'especie': 'Arabica', 'pais': 'Colombia', 'variedad': 'Caturra', 'metodo_proceso': 'Washed / Wet', 'color': 'Green',
    'altitud_media_m': 1700.0, 'humedad': 0.11, 'defectos_cat1': 0, 'defectos_cat2': 2, 'quakers': 0,
}


class Lote(BaseModel):
    """Lo que se sabe de un lote al recibirlo, antes de catarlo. Nunca notas de cata (suman la puntuación: sería fuga)."""
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, json_schema_extra={'examples': [EJEMPLO]})

    especie: Especie = Field(description='Especie del café')
    pais: Optional[str] = Field(strict=True, max_length=MAX_TEXTO, description='País de origen; un país no visto al entrenar da un aviso, no un error')
    variedad: Optional[str] = Field(strict=True, max_length=MAX_TEXTO, description='Variedad; una no vista al entrenar da un aviso, no un error')
    metodo_proceso: Optional[MetodoProceso] = Field(description='Método de beneficio; null si no se conoce')
    color: Optional[Color] = Field(description='Color del grano verde; null si no se conoce')
    altitud_media_m: Optional[float] = Field(strict=True, ge=config.ALTITUD_MIN_M, le=config.ALTITUD_MAX_M, allow_inf_nan=False,
                                             description='Altitud media en metros (100 a 4000); null si no se conoce')
    humedad: Optional[float] = Field(strict=True, ge=0, le=1, allow_inf_nan=False,
                                     description='Humedad del grano como fracción (0 a 1); 0 se trata como «no medido»')
    defectos_cat1: Optional[float] = Field(strict=True, ge=0, le=MAX_DEFECTOS, allow_inf_nan=False, description='Defectos de categoría 1')
    defectos_cat2: Optional[float] = Field(strict=True, ge=0, le=MAX_DEFECTOS, allow_inf_nan=False, description='Defectos de categoría 2')
    quakers: Optional[float] = Field(strict=True, ge=0, le=MAX_DEFECTOS, allow_inf_nan=False, description='Granos «quaker» (inmaduros)')

    @field_validator('pais', 'variedad', 'metodo_proceso', 'color', mode='before')
    @classmethod
    def _vacio_es_nulo(cls, v):
        """Una cadena vacía (o solo espacios) en una variable de texto es «sin dato»."""
        return None if isinstance(v, str) and not v.strip() else v


class LotesAPredecir(BaseModel):
    model_config = ConfigDict(extra='forbid')
    lotes: list[Lote] = Field(min_length=1, max_length=MAX_LOTES)


class Aviso(BaseModel):
    tipo: str = Field(description='categoria_nueva | categoria_infrecuente | fuera_de_rango_entrenamiento | valor_no_informado | humedad_cero')
    campo: str
    valor: Any = Field(description='El valor recibido (null si no se informó)')
    mensaje: str


class Prediccion(BaseModel):
    probabilidad_especialidad: float = Field(ge=0, le=1, description='Probabilidad de que el lote alcance especialidad')
    modelo: str
    version_modelo: Optional[str] = Field(description='Versión del modelo en el registro de MLflow')
    huella_datos: str = Field(description='Identifica con qué datos se entrenó el modelo')
    avisos: list[Aviso] = Field(default_factory=list, description='Cosas válidas que el modelo no vio al entrenar')


class PrediccionLote(BaseModel):
    predicciones: list[Prediccion]


class InfoModelo(BaseModel):
    modelo: str
    version_modelo: Optional[str]
    objetivo: str
    huella_datos: str
    entrenado_en: str
    variables: list[str]
    tipos: dict
    filas: dict
    metricas_valid: dict
    versiones: dict


class Error(BaseModel):
    detalle: str
    id_peticion: Optional[str] = None


class ErrorValidacion(Error):
    errores: list[dict] = Field(default_factory=list, description='Un elemento por problema: campo, mensaje y tipo (sin el valor recibido)')


def _tipo_de_anotacion(anotacion):
    """string / double de una anotación (Optional, Literal de textos, str, float); None si no es ninguno de esos."""
    origen = get_origin(anotacion)
    if origen is Union or origen is types.UnionType:
        tipos = {_tipo_de_anotacion(a) for a in get_args(anotacion) if a is not type(None)}
        return tipos.pop() if len(tipos) == 1 else None
    if origen is Literal:
        return 'string' if all(isinstance(a, str) for a in get_args(anotacion)) else None
    return {str: 'string', float: 'double'}.get(anotacion)


def contrato_del_esquema():
    """El contrato que implementa este esquema, como lista de (nombre, tipo) con los tipos de la firma de MLflow."""
    return [(nombre, _tipo_de_anotacion(campo.annotation)) for nombre, campo in Lote.model_fields.items()]

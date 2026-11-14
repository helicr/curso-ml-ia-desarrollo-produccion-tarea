# De cuaderno a paquete de Python

Perfil de arquitecto: qué se gana al pasar de un cuaderno a un paquete, y por qué el proyecto conserva **los dos**.

## Qué hace cada uno

Un cuaderno es ideal para **explorar y explicar**: ves el dato, la consulta y el resultado juntos. Pero no se despliega:
depende del orden en que se ejecutaron las celdas, lleva estado oculto, no se prueba con facilidad y no se lanza desde un
workflow. Un paquete es **repetible, probable y desplegable**. El proyecto usa el cuaderno para contar y el paquete para ejecutar.

| Cuaderno (`notebooks/`) | Módulo equivalente (`cafe_mlops/`) | Orden |
|---|---|---|
| `00_pipeline_operacional.ipynb` | `operacional.py` y `dataset.py` (lectura de los CSV) | `make operacional` |
| `01_pipeline_raw_a_master.ipynb` | `pipeline_ingesta_raw.py`, `pipeline_ingesta_master.py`, `calidad.py` | `make raw`, `make master` |
| `02_pipeline_master_a_fs.ipynb` | `features.py`, `pipeline_ml.py` | `make ml` |
| `03_pipeline_fs_a_ml.ipynb` | `modeling/ml_dataset.py`, `pipeline_ml.py` | `make ml` |
| `04_entrenamiento_y_seguimiento.ipynb` | `modeling/train.py`, `pipeline_train.py` | `make train` |

El orquestador `cafe_mlops/pipeline.py` (`make pipeline`) los lanza en orden; no tiene lógica de datos propia.

## Qué cambia al pasar a Python

1. **Un pipeline, una responsabilidad.** Cada pipeline comprueba que existe su entrada, hace una cosa y deja su salida.
   Son independientes: se pueden ejecutar solos y en cualquier orden en que su entrada exista.
2. **Idempotencia.** Un cuaderno ejecutado dos veces suele duplicar o cambiar cosas. Los pipelines calculan la huella de
   su entrada (datos, SQL, configuración) y, si no cambió, dicen «sin cambios» (`cafe_mlops/control.py`).
3. **Una sola fuente de configuración.** Umbral, variables, cortes de partición, puertos y rutas están en `cafe_mlops/config.py`.
   Los cuadernos repiten esos valores en su celda de parámetros y las pruebas comprueban que dan el mismo resultado.
4. **El SQL sigue siendo SQL.** La lógica de datos está en `sql/`, no escondida en cadenas de Python.
5. **El preprocesado va dentro del modelo.** Imputación y one-hot forman parte del `Pipeline` de scikit-learn
   (`modeling/preproceso.py`), así que el entrenamiento y la API aplican **exactamente el mismo** tratamiento. Es la
   defensa contra el fallo clásico de producción: que el servicio prepare los datos de otra manera que el entrenamiento.
6. **Código de salida y errores claros.** Una regla de calidad dura detiene el pipeline con error y no registra la ejecución.
7. **Configuración por entorno.** Las rutas y puertos se cambian con variables `TALLER_*` (listadas en `cafe_mlops/config.py`),
   sin tocar código: es lo que permite usar el mismo paquete en el ordenador y en un contenedor.

## Cómo se garantiza que cuaderno y paquete dicen lo mismo

El riesgo de mantener dos versiones es que se separen. Las pruebas lo cierran (`tests/test_cuadernos.py` y los
`tests/test_*.py` de cada capa): los cuadernos llegan **ejecutados**, con salidas guardadas y sin errores; las cifras
guardadas coinciden con las del paquete; y la prueba lenta los vuelve a ejecutar desde cero en una carpeta temporal y
compara con lo guardado. Se ejecutan con `make test` (las pruebas rápidas, sin cuadernos: `make test-rapido`).

## Qué NO hace este proyecto (y por qué)

- **No hay que editar ni escribir código**: el cuaderno se lee, y a lo sumo se ejecuta con «dar al play».
- **No se afinan hiperparámetros con el test.** Los modelos candidatos (referencia sin aprender, regresión logística y
  gradient boosting) llevan hiperparámetros modestos fijados de antemano; se elige con valid y se mide una sola vez en test.
- **Las cifras de un único test oscilan** (hay muy pocos lotes sin especialidad en la ventana de comparación). Por eso la
  tolerancia de comparación es una **decisión de arquitecto que hay que justificar**, no un dato medido (ver
  [del-ordenador-al-servicio.md](del-ordenador-al-servicio.md)).

## Para cada módulo, dónde mirar

La cabecera de cada archivo de `cafe_mlops/` explica qué hace, de qué cuaderno viene y cómo se ejecuta
(`python -m cafe_mlops.<módulo>`). Es la mejor puerta de entrada.

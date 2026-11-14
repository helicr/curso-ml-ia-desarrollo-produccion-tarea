# La API del modelo y los contenedores

Perfil de arquitecto: qué promete la API, qué hace cuando algo falla y qué lleva cada imagen, con la decisión que hay detrás.

## Dos servicios, no uno

| Servicio | Módulo | Puerto | Para qué |
|---|---|---|---|
| **API del modelo** | `cafe_mlops/api` (`make api`) | 8080 | Sirve el modelo: recibe las 10 variables de un lote y devuelve la probabilidad. No conoce la base de datos. |
| **Interfaz** | `cafe_mlops/interfaz` (`make interfaz`) | 8090 | Conoce el dato: dado un id de lote lee sus variables de la capa FS, llama a la API y traduce la probabilidad en una recomendación de negocio. |

**Por qué separados:** el modelo cambia con cada reentrenamiento y la interfaz no; la interfaz necesita los datos y la API
no. Separarlos permite desplegar, escalar y proteger cada uno por su cuenta, y hace que la imagen de la interfaz no
necesite scikit-learn ni el modelo.

## Endpoints de la API

| Método y ruta | Qué hace |
|---|---|
| `GET /salud` | ¿El proceso responde? (liveness). No mira el modelo. Lo usa el `HEALTHCHECK` de la imagen. |
| `GET /listo` | ¿El modelo está cargado y su contrato coincide con la firma? (readiness). `503` si no. |
| `GET /modelo` | Qué modelo es: versión, huella de los datos, variables y tipos, métricas de validación. |
| `POST /predecir` | Probabilidad de especialidad de **un** lote (cuerpo: las variables del lote). |
| `POST /predecir/lote` | Probabilidad de hasta 1000 lotes (cuerpo: `{"lotes": [ ... ]}`). |
| `GET /docs` | Documentación interactiva generada del propio contrato. |

Ejemplo de lote válido (`tests/datos/lote_ejemplo.json`): `especie`, `pais`, `variedad`, `metodo_proceso`, `color`,
`altitud_media_m`, `humedad`, `defectos_cat1`, `defectos_cat2` y `quakers`. La respuesta trae
`probabilidad_especialidad`, `modelo`, `version_modelo`, `huella_datos` y `avisos`.

## El contrato

- **No se escribe dos veces.** El modelo guarda su **firma** (nombres y tipos). Al arrancar, el servicio comprueba que el
  esquema de la API (`api/esquemas.py`) y `models/metadatos.json` tienen exactamente los mismos nombres y tipos. Si no, la API
  arranca igualmente pero `/listo` da `503` y dice qué variable falla. Decisión: **es mejor fallar al arrancar que predecir
  con columnas o tipos equivocados**.
- **Se rechaza lo imposible o ambiguo** (`422`): campos desconocidos o ausentes, altitud fuera de 100–4 000, humedad fuera de 0–1,
  defectos negativos, cadenas donde van números, especie, método de proceso o color fuera de sus listas cerradas.
  Un lote como `tests/datos/lote_imposible.json` da `422`.
- **Se avisa lo válido que el modelo no vio** (`200` con `avisos`): un país o una variedad nunca vistos
  (`tests/datos/lote_categoria_nueva.json`), un valor fuera del rango de entrenamiento o una variable sin informar. La
  predicción existe, pero tiene menos respaldo, y la interfaz lo marca como «revisar».
- Los límites salen de las reglas de MASTER (`config.ALTITUD_MIN_M`...), no de lo que se vio al entrenar.

## Errores: siempre JSON, nunca trazas

| Código | Cuándo | Qué se devuelve |
|---|---|---|
| `422` | El cuerpo no cumple el contrato. | Lista de `errores` con `campo`, `mensaje` y `tipo`; **no** se devuelve el valor recibido. |
| `503` | No hay modelo o su contrato no coincide con la firma. | `detalle` con el motivo. |
| `500` | Error interno no previsto. | `Error interno` genérico; el detalle va al registro, no al cliente. |

Todas las respuestas de error llevan `id_peticion`, que es también la cabecera `X-Request-ID`: con ese identificador se
encuentra la petición en el registro sin exponer nada al cliente. **Decisión de seguridad:** una traza o el valor recibido
en un mensaje de error filtran información interna.

## Registro

Cada petición deja **una línea JSON por la salida estándar** (método, ruta, código y milisegundos, con `severity` y
`message`). Un contenedor recoge lo que sale por stdout (`docker logs`) y las plataformas de registro entienden esa línea.
**Nunca se registran los datos del lote.** El nivel se cambia con `TALLER_LOG_NIVEL`.

## Las dos imágenes

Medidas en la ejecución de la prueba real en GitHub (Validar):

| Imagen | Tamaño | Comprimida | Qué lleva |
|---|---|---|---|
| `cafe-api` | 826 MB | 183 MB | Paquete `cafe_mlops`, modelo en formato MLflow, `metadatos.json` y las dependencias exactas. |
| `cafe-interfaz` | 213 MB | 51 MB | Solo el código y fastapi, uvicorn y pydantic. **Sin** scikit-learn, mlflow ni pandas. Sin modelo ni datos. |

Decisiones de arquitectura que comparten las dos (`deploy/docker/`):

- **Imagen base `python:3.11-slim`**, la misma versión que usan el Codespace y el CI: lo que probaste es lo que se ejecuta.
- **Dependencias primero** (`COPY requirements-api.lock` + `pip install`) y código después: la capa pesada solo se
  reconstruye si cambian las versiones.
- **Versiones exactas** en `requirements-api.lock` (`make lock`): dos construcciones dan las mismas versiones. La interfaz
  usa ese mismo lock como restricción.
- **El modelo va en la imagen de la API, los datos no van en ninguna.** El modelo es parte de lo que se despliega y se
  versiona con la imagen; los datos se **montan** (`data/processed:/datos:ro`) en la interfaz y en **solo lectura**.
- **Sin root.** Las dos ejecutan con el usuario 10001 (comprobado en la prueba real).
- **`HEALTHCHECK` sobre `/salud`**, no sobre `/listo`: si la API cae, reiniciar la interfaz no la arregla. `/listo` da el motivo con un `503`.
- **`.dockerignore`**: la imagen de la API no lleva datos, bases, SQL, pruebas ni cuadernos; la interfaz tiene el suyo
  (`deploy/docker/interfaz.Dockerfile.dockerignore`).

## Órdenes

```
make imagen            # solo la API         -> cafe-api:local
make imagen-interfaz   # solo la interfaz    -> cafe-interfaz:local
make imagenes          # las dos (antes: make pipeline, para que exista el modelo)
make contenedor        # ejecuta la API en http://127.0.0.1:8080
make comparar URL=http://127.0.0.1:8080   # el paquete, el archivo, MLflow y la API dan la misma probabilidad
```

`make comparar` es la comprobación de arquitecto: si una diferencia aparece entre entrenamiento y servicio (otra versión de una
librería, otro orden de columnas, un nulo mal tratado), se encuentra **antes** de desplegar.

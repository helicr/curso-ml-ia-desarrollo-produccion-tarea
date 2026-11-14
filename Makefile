# Comandos del proyecto. Uso:  make <orden>
# En Windows no hay `make` por defecto: ejecuta las lineas que empiezan por `python` o `papermill` directamente
# desde Anaconda Prompt (cada orden indica su equivalente). En Codespaces y en GitHub Actions `make` si esta.
PYTHON ?= python
HASTA ?= 2016

FORZAR ?=

.PHONY: ayuda operacional raw master ml train pipeline mlflow test test-rapido api interfaz comparar imagen imagen-interfaz imagenes contenedor compose-arriba compose-abajo lock limpiar

ayuda:  ## Muestra esta ayuda
	@grep -E '^[a-z-]+:.*##' Makefile | sed 's/:.*##/ -> /'

operacional:  ## Simula la base operacional cqi.db desde los CSV de data/raw/cqi (HASTA=2016 version 1 de los datos, HASTA=2018 version 2)
	$(PYTHON) -m cafe_mlops.operacional --hasta $(HASTA)

raw:  ## pipeline_ingesta_raw: cqi.db -> RAW (idempotente; FORZAR=--forzar para rehacerlo)
	$(PYTHON) -m cafe_mlops.pipeline_ingesta_raw $(FORZAR)

master:  ## pipeline_ingesta_master: RAW -> MASTER + reglas de calidad
	$(PYTHON) -m cafe_mlops.pipeline_ingesta_master $(FORZAR)

ml:  ## pipeline_ml: MASTER -> FS -> ML
	$(PYTHON) -m cafe_mlops.pipeline_ml $(FORZAR)

train:  ## pipeline_train: ML -> modelo, metricas y MLflow
	$(PYTHON) -m cafe_mlops.pipeline_train $(FORZAR)

pipeline:  ## Los cuatro pipelines en orden (los que no tienen cambios no hacen nada); crea la operacional si falta. HASTA=2018: llegan lotes nuevos
	$(PYTHON) -m cafe_mlops.pipeline $(if $(filter command line environment,$(origin HASTA)),--hasta $(HASTA),) $(FORZAR)

mlflow:  ## Interfaz web de MLflow (http://127.0.0.1:5000) sobre el registro del proyecto. Antes: make pipeline
	$(PYTHON) -m cafe_mlops.mlflow_ui

test:  ## Todas las pruebas (incluye ejecutar los cuadernos)
	$(PYTHON) -m pytest tests

test-rapido:  ## Pruebas sin ejecutar los cuadernos
	$(PYTHON) -m pytest tests -m "not lento"

api:  ## Arranca la API en http://127.0.0.1:8080 (docs en /docs); otro puerto: TALLER_PUERTO_API=8081 make api. Antes: make pipeline
	$(PYTHON) -m cafe_mlops.api

interfaz:  ## Interfaz web (ids de lote -> probabilidad de especialidad y recomendacion) en http://127.0.0.1:8090. Llama a la API de URL (por defecto TALLER_URL_API o http://127.0.0.1:<TALLER_PUERTO_API>)
	$(PYTHON) -m cafe_mlops.interfaz $(if $(URL),--url $(URL),)

comparar:  ## Compara paquete, joblib y MLflow y, con URL=http://127.0.0.1:8080, tambien la API. Antes: make pipeline
	$(PYTHON) -m cafe_mlops.modeling.comparar $(if $(URL),--url $(URL),)

imagen:  ## Construye la imagen de la API, cafe-api:local (en Codespaces; en tu equipo no hay Docker). Antes: make pipeline
	docker build -f deploy/docker/Dockerfile -t cafe-api:local .

imagen-interfaz:  ## Construye la imagen de la interfaz, cafe-interfaz:local
	docker build -f deploy/docker/interfaz.Dockerfile -t cafe-interfaz:local .

imagenes: imagen imagen-interfaz  ## Construye las dos imagenes (cafe-api:local y cafe-interfaz:local). Antes: make pipeline

contenedor:  ## Ejecuta la imagen de la API en http://127.0.0.1:8080
	docker run --rm -p 8080:8080 cafe-api:local

compose-arriba:  ## Construye y arranca los dos contenedores (red cafe_default; interfaz en http://127.0.0.1:8090) y espera a que esten sanos. Antes: make pipeline
	docker compose -f deploy/docker/compose.yaml up --build -d --wait

compose-abajo:  ## Para y borra los dos contenedores y su red (las imagenes y los datos quedan)
	docker compose -f deploy/docker/compose.yaml down

lock:  ## Regenera requirements-api.lock (versiones exactas) en un entorno vacio con uv
	uv venv .venv-lock --python 3.11 -q && uv pip install -r requirements-api.txt --python .venv-lock/bin/python -q
	(echo "# Dependencias EXACTAS (directas y transitivas) de la imagen. Se genera con:  make lock   (a partir de requirements-api.txt, en un entorno vacio)"; echo "# La imagen instala ESTE archivo para que dos construcciones den las mismas versiones."; uv pip freeze --python .venv-lock/bin/python) > requirements-api.lock
	rm -rf .venv-lock

limpiar:  ## Borra lo generado (bases de datos, modelos y reportes). No toca los datos originales
	rm -f data/external/cqi.db data/processed/*.db models/*.joblib models/metadatos.json models/mlflow.db reports/metricas.json
	rm -rf models/modelo_mlflow models/mlartifacts reports/notebooks_ejecutados scripts_desde_notebooks

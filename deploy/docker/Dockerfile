# Imagen de la API del modelo (cafe-api). El modelo (models/) se ENTRENA antes con `make pipeline`: la imagen solo lo sirve.
#
# Construir y probar, desde la raiz del repositorio:
#   make pipeline
#   docker build -f deploy/docker/Dockerfile -t cafe-api:local .
#   docker run --rm -p 8080:8080 cafe-api:local        # (o:  make imagenes  y  make contenedor)
#
# Lleva: el paquete cafe_mlops (la carga del modelo necesita cafe_mlops.modeling.preproceso: ahi vive `nulos_a_nan`, el
# FunctionTransformer del Pipeline) + el modelo en formato MLflow + metadatos.json. NO lleva datos, bases, SQL, pruebas ni cuadernos.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TALLER_MODELOS=/app/models

WORKDIR /app

# 1) Dependencias primero: esta capa solo se reconstruye si cambia el archivo de versiones exactas.
#    requirements-api.lock sale de requirements-api.txt con `make lock` (mlflow-skinny, no mlflow completo).
COPY requirements-api.lock .
RUN pip install -r requirements-api.lock

# 2) Codigo y modelo (solo lo necesario para servir; ver .dockerignore).
COPY cafe_mlops/ cafe_mlops/
COPY models/modelo_mlflow/ models/modelo_mlflow/
COPY models/metadatos.json models/metadatos.json

# 3) No se ejecuta como root.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin apiuser
USER 10001

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/salud', timeout=2)"

CMD ["uvicorn", "cafe_mlops.api.app:app", "--host", "0.0.0.0", "--port", "8080"]

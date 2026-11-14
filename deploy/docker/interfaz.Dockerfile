# Imagen de la INTERFAZ (cafe-interfaz): ids de lote -> variables (consulta a cafe.db) -> API del modelo -> recomendacion.
#
#   - NO lleva el modelo: se lo pide a la API por la red (TALLER_URL_API).
#   - NO lleva los datos: la base cafe.db se monta como volumen de solo lectura en /datos.
#   - NO instala scikit-learn, scipy, mlflow ni pandas: solo fastapi, uvicorn y pydantic (el resto es la biblioteca estandar).
#
# Construir, desde la raiz del repositorio:
#   docker build -f deploy/docker/interfaz.Dockerfile -t cafe-interfaz:local .
# Que entra en el contexto lo decide  deploy/docker/interfaz.Dockerfile.dockerignore  (no el .dockerignore de la raiz, que es el de la API).
#
# Ejecutar (con la API en la red «cafe» y el nombre «api»; ver compose.yaml):
#   docker run --rm --name interfaz --network cafe -p 8090:8090 -v "$PWD/data/processed:/datos:ro" cafe-interfaz:local
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TALLER_DB=/datos/cafe.db \
    TALLER_DB_SOLO_LECTURA=1 \
    TALLER_URL_API=http://api:8080 \
    TALLER_HOST_INTERFAZ=0.0.0.0 \
    TALLER_PUERTO_INTERFAZ=8090

WORKDIR /app

# 1) Dependencias primero. Las versiones las fija el lock de la API: las dos imagenes usan las mismas.
COPY requirements-api.lock requirements-interfaz.txt ./
RUN pip install -c requirements-api.lock -r requirements-interfaz.txt

# 2) Solo el codigo. Nada de datos ni de modelo.
COPY cafe_mlops/ cafe_mlops/

# 3) Sin privilegios. El punto de montaje existe y es de solo lectura para el proceso.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser && mkdir /datos
USER 10001

EXPOSE 8090
# /salud y no /listo: si la API cae, la interfaz no se arregla reiniciandola (/listo lo explica con un 503).
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/salud', timeout=2)"

CMD ["python", "-m", "cafe_mlops.interfaz", "--host", "0.0.0.0", "--puerto", "8090"]

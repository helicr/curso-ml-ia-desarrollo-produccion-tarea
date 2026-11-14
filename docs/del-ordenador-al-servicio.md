# Del ordenador al servicio

Perfil de arquitecto: el mismo modelo se puede poner en producción de tres maneras cada vez más sólidas. Este documento
explica qué añade cada una, qué riesgo cubre y qué falta todavía para una producción real.

## Tres escalones

| Escalón | Cómo | Qué añade | Qué sigue siendo frágil |
|---|---|---|---|
| 1. Dos procesos | `make api` y `make interfaz` en dos terminales | Lo más rápido para ver el servicio. | Depende de tu entorno de Python y de que no cambies una librería; si cierras la terminal, el servicio cae. |
| 2. Dos contenedores | `make imagenes` y, por ejemplo, `make contenedor` | El entorno viaja con la aplicación: mismas versiones, sin root, con `HEALTHCHECK`. | Hay que arrancar y conectar cada contenedor a mano (red, variables, volumen). |
| 3. Compose | `make compose-arriba` / `make compose-abajo` | Todo el servicio descrito en un archivo (`deploy/docker/compose.yaml`) y reproducible con una orden. | Sigue siendo una sola máquina. |

(Antes de pasar al escalón 3 hay que parar los procesos del escalón 1: la interfaz usa el puerto 8090 en los dos casos.)

## Lo que Compose decide

- **La red y los nombres.** Compose crea la red `cafe_default`; el nombre del servicio es su nombre en la red, y por eso la
  interfaz llama a la API en `http://api:8080` (`TALLER_URL_API`). La misma imagen sirve para otra API cambiando esa variable.
- **La API no se publica fuera.** El servicio `api` no tiene `ports`: solo la interfaz, dentro de la red, puede llamarla. Se
  reduce la superficie expuesta; para probarla con curl hay una línea comentada.
- **Los datos se montan, solo lectura.** `data/processed:/datos:ro` con `TALLER_DB_SOLO_LECTURA=1`: la interfaz no puede
  escribir en la base aunque tuviera un fallo.
- **Orden de arranque con salud.** `depends_on: condition: service_healthy`: la interfaz no arranca hasta que el `HEALTHCHECK`
  de la API diga «sano», y `up --wait` no devuelve el control hasta que los dos lo están.
- **Configuración por variables de entorno**, no por código: el mismo paquete corre en el ordenador y en el contenedor.

## De la validación a la nueva versión: GitHub Actions

| Workflow | Cuándo | Qué hace |
|---|---|---|
| `validar.yml` | En cada push, pull request o a mano | Con Docker real: instala dependencias fijadas, pasa las pruebas, ejecuta el pipeline (y lo repite: «sin cambios»), construye las dos imágenes, comprueba usuario 10001 y que la interfaz no lleva scikit-learn, levanta Compose y pide una predicción por la interfaz. No publica nada ni usa secretos. |
| `nueva-version.yml` | A mano, con el año de datos (`hasta`) | Reentrena con los datos nuevos, **compara con `models/referencia.json`** y se para si empeora; si no, construye y prueba la imagen, espera una **aprobación manual** (environment `produccion`), la publica en GHCR y abre un pull request que actualiza la referencia. |

Decisiones de arquitectura:

- **El CI es la prueba de que "funciona en mi equipo" no depende de tu equipo**: parte de un entorno limpio cada vez.
- **Permisos mínimos y sin secretos propios**: se usa el `GITHUB_TOKEN`, con `packages: write` y `pull-requests: write` solo donde hace falta.
- **Puerta de calidad antes de publicar**: un modelo nuevo no se publica si empeora frente a la versión aprobada.
- **Puerta humana antes de producción**: la aprobación manual del environment la da quien administra el repositorio.
- **La referencia vive en el repositorio** (`models/referencia.json`) y la cambia un pull request: el cambio de modelo queda
  revisado y auditado como cualquier otro cambio.
- **Imagen etiquetada con versión y huella de los datos** (por ejemplo `v2-<huella>`): se sabe exactamente con qué datos se entrenó.

### Un ejemplo real que hay que saber explicar

En la prueba real, con la tolerancia provisional de 0,02 la versión 2 salió **rechazada**: AUC de 0,7951 frente a 0,8525
en la ventana común (diferencia de −0,0574) y no se construyó ni publicó nada. No es una mala noticia del modelo: la
ventana común tiene solo 5 lotes sin especialidad, y con tan pocos negativos el AUC oscila más que 0,02 por puro azar del
corte. Con una tolerancia de 0,10 la misma versión se aprobó y llegó hasta la publicación en GHCR. **Subir la tolerancia es
una decisión de arquitecto que hay que justificar; no sale de una medición.** El valor de `config.TOLERANCIA_COMPARACION`
sigue siendo provisional.

## Qué falta para producción real

Este taller llega hasta un servicio funcionando en una máquina. Para producción de verdad faltarían (no está construido ni probado aquí):

- **Orquestación**: varias réplicas, reinicio automático y despliegue sin corte (por ejemplo Kubernetes o un servicio
  gestionado de contenedores). Compose es una sola máquina.
- **Seguridad de acceso**: la API y la interfaz no llevan autenticación ni TLS. Falta un punto de entrada con HTTPS y control de acceso.
- **Observabilidad**: los registros salen por stdout, pero falta recogerlos, medir (latencia, errores) y alertar.
- **Monitorización del modelo**: detectar cambios en los datos que llegan y la caída de la calidad en producción. El
  taller solo compara al reentrenar.
- **Datos reales**: la base operacional es una simulación sobre CSV y las bases son SQLite (un archivo). Producción pediría
  una base de verdad y la planificación de las cargas.
- **Registro de modelos y artefactos**: MLflow aquí usa SQLite local; en producción necesitaría un servidor con almacenamiento compartido.
- **Imágenes**: los paquetes de GHCR nacen privados; publicarlos o configurar el acceso es un paso que decide quien administra.
- **Gobierno del dato**: los CSV incluyen nombres y contactos (ya públicos en la fuente) y las condiciones de uso del CQI
  están **sin verificar**; un servicio real exigiría resolverlo.
- **Segmentos de negocio**: los umbrales de la recomendación de la interfaz (`config.SEGMENTOS`) son provisionales y se deben acordar con quien use el servicio.

## Para tu entrega

En el vídeo y las capturas (`evidencias/`) muestra el servicio funcionando por la interfaz y el proceso de despliegue, y
explica con tus palabras, para cada escalón, qué problema resuelve y cuál queda sin resolver.

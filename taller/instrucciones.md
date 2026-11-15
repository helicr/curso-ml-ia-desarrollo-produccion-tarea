# Tarea Curso Taller «De Modelo de ML/IA a Producción»

Instrucciones del taller. Fecha de entrega: 30/11/2026. Entrega: el lunes 30/11/2026, durante ese día.

## 1. Objetivo

En este taller tu papel es el de arquitecto, no el de programador. No escribes código. Tienes que:

1. Desplegar de punta a punta un servicio de ML que ya está construido: datos, pipelines, modelo, API, interfaz, imágenes Docker,
   contenedores y flujos de integración y entrega continuas (CI/CD) en GitHub Actions.
2. Demostrar que funciona, con un vídeo del servicio funcionando por su interfaz y capturas de cada paso del despliegue.
3. Explicar, para cada pieza, qué decisión de arquitectura hay detrás y qué riesgo cubre.

El caso es este: llega un lote de café y, antes de catarlo, se quiere saber qué probabilidad hay de que sea café de especialidad (80 puntos
o más). Se parte del origen, la variedad, el beneficio y el análisis del grano verde. Los datos son los del Coffee Quality Institute (CQI).

La cadena que vas a desplegar, y que debes poder explicar:

```text
CSV de CQI -> base operacional -> RAW -> MASTER -> FS -> ML -> modelo (MLflow) -> API -> interfaz
                                                                                   |
                                  imagenes Docker -> Compose (dos contenedores) -> GitHub Actions
```

## 2. Qué recibes

- La plantilla: `https://github.com/helicr/curso-ml-ia-desarrollo-produccion-tarea`. Está completa: datos, pipelines, cuadernos, API, interfaz,
  Dockerfiles, Compose y workflows. No hay que programar nada ni cambiar ningún archivo del proyecto.
- Esta documentación:
  - [guia-detallada.md](guia-detallada.md): el paso a paso (dónde, comando, qué debes ver, qué hacer si falla, qué captura se pide).
  - [guia-grabacion-video.md](guia-grabacion-video.md): cómo grabar y comprimir el vídeo.
  - [criterios-de-evaluacion.md](criterios-de-evaluacion.md): cómo se evalúa.
  - [checklist.md](checklist.md): lista de comprobación antes de entregar.
  - [plantilla-evidencias.md](../evidencias/plantilla-evidencias.md): dónde va cada captura y dónde explicas la arquitectura.
  - Un resumen con diagramas, en PDF: `taller/instrucciones-del-trabajo.pdf` (la idea, el recorrido, los pasos, qué entregar, cómo se evalúa y el checklist).
  - La guía completa en PDF, con las capturas de ejemplo, para consultar cada paso: `taller/guia-detallada-del-trabajo.pdf`.
  - Las diapositivas de la tarea, para proyectarlas o consultarlas (cada orden se copia con un botón): [slides/index.html](slides/index.html),
    y en PDF: `taller/diapositivas-del-trabajo.pdf`.
- Un entorno listo: el Codespace de GitHub ya trae Python 3.11, Docker y `make`. No instalas nada en tu ordenador.

## 3. Qué debes hacer, en orden

El detalle de cada paso, con lo que debes ver y qué hacer si falla, está en la [guía detallada](guia-detallada.md). Aquí va el resumen.
Además de ejecutar cada paso, tienes que escribir una frase de arquitectura: qué pieza es y qué riesgo cubre.

| Paso | Qué haces | Dónde |
|---|---|---|
| 1-2 | Haces un fork de la plantilla y lo renombras a `taller-ml-ia-dev-production` | Navegador (GitHub) |
| 3-4 | Creas un Codespace desde tu fork y aceptas los avisos de la primera vez | Navegador |
| 5 | Verificas el entorno: `make verificar` | Codespace |
| 6 | Revisas el proyecto: estructura y qué hace cada carpeta | Codespace |
| 7-8 | Ejecutas los pipelines (ingesta RAW y MASTER, FS, ML y creación del modelo) con `make pipeline` y lo repites (debe decir «sin cambios») | Codespace |
| 9 | Compruebas el modelo y su versión: `make comparar` | Codespace |
| 10 | (Opcional) Sirves el modelo como procesos: `make api` | Codespace |
| 11 | Construyes las imágenes: `make imagenes` | Codespace |
| 12 | Levantas los contenedores: `make compose-arriba` | Codespace |
| 13-14 | Abres la interfaz (UI) en el puerto 8090 y consumes el modelo consultando lotes | Navegador |
| 15 | Grabas el vídeo y paras el servicio (`make compose-abajo`) | Tu equipo y Codespace |
| 16 | (Opcional) Simulas la llegada de lotes nuevos: `make pipeline HASTA=2018` | Codespace |
| 17-22 | CI/CD: habilitas Actions en tu fork y lanzas `Validar` y `Nueva version del modelo` (se rechaza con la tolerancia por defecto y se aprueba con `tolerancia` = 0.10, con aprobación manual del environment `produccion`) | Navegador |
| 23 | Entregas: subes las evidencias a tu fork y envías el enlace | Codespace y navegador |

Hay tres cosas que tienes que hacer tú en tu fork, porque GitHub las deja sin activar:

1. Habilitar Actions. Los workflows de un fork vienen desactivados hasta que los habilitas en la pestaña Actions (paso 17).
2. Crear el environment `produccion` con tu usuario como revisor (Settings > Environments). Sin él, la publicación no espera aprobación (paso 19).
3. Marcar «Allow GitHub Actions to create and approve pull requests» (Settings > Actions > General). Sin ello, el workflow no puede abrir el pull request con la nueva referencia (paso 19).

Dos cosas más que conviene saber:

- Los workflows de tu fork usan tu usuario para publicar las imágenes: `ghcr.io/<tu-usuario>/cafe-api` y `ghcr.io/<tu-usuario>/cafe-interfaz`.
  Como tu fork es público, los paquetes de GHCR quedan públicos (si los ves privados, la guía explica cómo cambiarlo).
- Un fork de un repositorio público conserva el vínculo con el original y es público.

## 4. Qué entregas

1. Un vídeo del servicio funcionando a través de la interfaz, con el modelo en producción (contenedores levantados):
   - formato MP4, de 2 a 4 minutos, con tu voz y de menos de 50 MB;
   - en `evidencias/video/servicio-en-produccion.mp4` de tu fork;
   - cómo hacerlo: [guia-grabacion-video.md](guia-grabacion-video.md).
2. Capturas de evidencia del proceso de despliegue (16), en `evidencias/capturas/`, con los nombres de la
   [plantilla de evidencias](../evidencias/plantilla-evidencias.md) (`01-fork-renombrado`, `02-codespace-abierto`, ...).
3. La plantilla de evidencias rellena (`evidencias/plantilla-evidencias.md`). Para cada captura escribes qué muestra y tu explicación de
   arquitectura: qué pieza es, qué decisión hay detrás y qué riesgo cubre.
4. Un repositorio público llamado exactamente `taller-ml-ia-dev-production` (tu fork, renombrado). El instructor te identifica por su nombre y su enlace.

## 5. Cómo se entrega

Envía el enlace de tu fork (`https://github.com/<tu-usuario>/taller-ml-ia-dev-production`) por uno de los canales del curso que ya conoces: el chat del
grupo del curso, Google Classroom o el correo del curso. Puedes enviarlo durante todo el 30/11/2026. Antes de enviarlo, abre el enlace en una ventana privada del
navegador, sin tu sesión: si lo ves tú, lo verá también el instructor.

## 6. Cómo se evalúa

La nota se reparte así. El detalle y los niveles están en los [criterios de evaluación](criterios-de-evaluacion.md).

| Criterio | Peso |
|---|---|
| Ejecución y reproducibilidad | 40 |
| Evidencias | 30 |
| Comprensión (criterio de arquitecto) | 30 |

La comprensión se evalúa con tus explicaciones de arquitectura, las de la plantilla de evidencias y las del vídeo. No se evalúa código, porque no hay nada que programar.

## 7. Reglas

- No cambies el proyecto. No edites los archivos de la plantilla; solo añades tu carpeta `evidencias/`.
- No inventes resultados. Si algo no te funcionó, dilo: una captura del error con tu explicación vale más que una captura retocada.
- Las capturas son de tu Codespace y de tu fork, con tu usuario visible. No sirven las capturas de ejemplo de la guía.
- El vídeo debe ser tuyo: con tu voz y con la cabecera de la interfaz mostrando tu repositorio.
- Los datos del CQI son públicos, pero no los uses para nada que no sea este taller.

## 8. Si algo no funciona

Cada paso de la [guía](guia-detallada.md) tiene un apartado «Si falla» con los fallos que ya se encontraron al probarlo. Si no resuelve tu caso,
guarda una captura del error y de la terminal, anota en qué paso estabas y consúltalo con el instructor antes de la fecha de entrega.

## 9. Qué se probó y qué no

La guía se escribió después de recorrer el camino de verdad en un Codespace y en GitHub Actions, con la cuenta del instructor. No se ha probado un recorrido completo
con la cuenta de otro alumno, ni crear el fork, ni habilitar Actions en un fork, ni los cuadernos con su kernel, ni MLflow en el puerto 5000, ni `docker pull` desde GHCR.
La tabla completa está en la [guía](guia-detallada.md#qué-se-probó-y-qué-no).

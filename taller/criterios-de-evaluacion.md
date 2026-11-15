# Criterios de evaluación

Tarea Curso Taller «De Modelo de ML/IA a Producción». Total: 100 puntos. Fecha de entrega: 30/11/2026.

El instructor fijó los tres pesos (40, 30 y 30). El reparto de puntos dentro de cada criterio y los niveles son una propuesta
del material del taller, y el instructor puede ajustarlos.

| Criterio | Puntos |
|---|---|
| 1. Ejecución y reproducibilidad | 40 |
| 2. Evidencias | 30 |
| 3. Comprensión (criterio de arquitecto) | 30 |

## 1. Ejecución y reproducibilidad (40)

Se comprueba que el despliegue se hizo de verdad y se puede repetir: en tu fork, con el nombre correcto y sin tocar el proyecto.

| Aspecto | Puntos | Completo | Parcial | Insuficiente |
|---|---|---|---|---|
| Fork público con el nombre `taller-ml-ia-dev-production` y sin cambios en el proyecto | 5 | Nombre exacto, público, vinculado a la plantilla | Nombre distinto o algún archivo del proyecto cambiado | No es un fork o no se puede abrir |
| Entorno y pipelines: `make verificar`, `make pipeline` y la repetición «sin cambios» | 8 | Las tres salidas correctas y la versión 1 del modelo | Faltan la repetición o la versión | No hay modelo |
| Imágenes y contenedores: `make imagenes` y `make compose-arriba` | 8 | Las dos imágenes construidas y los dos contenedores sanos | Una imagen, o contenedores no sanos al final | No hay contenedores |
| Interfaz en el puerto 8090 y consumo del modelo | 7 | La interfaz muestra tu repositorio, el modelo, la huella y un resultado con avisos | La interfaz abre pero no hay consulta | No se ve la interfaz |
| CI/CD: `Validar` en verde, `Nueva version del modelo` rechazada y aprobada | 12 | Las tres ejecuciones, con el environment `produccion` y su aprobación manual | Falta una de las tres | No se ejecutó ningún workflow |

## 2. Evidencias (30)

Se comprueba que lo que entregas demuestra lo que dices: el vídeo y las capturas.

| Aspecto | Puntos | Completo | Parcial | Insuficiente |
|---|---|---|---|---|
| Vídeo: formato y requisitos (MP4, de 2 a 4 minutos, con voz, menos de 50 MB, en `evidencias/video/`) | 6 | Cumple todos | Incumple uno | Incumple varios o no hay vídeo |
| Vídeo: el servicio funcionando a través de la interfaz con el modelo en producción | 8 | Se ve la cabecera con tu repositorio, contenedores sanos, una consulta de lotes con su resultado y los avisos | Falta la cabecera o los contenedores | Solo se ve la terminal |
| Capturas: las 16 de la plantilla, en `evidencias/capturas/` con su nombre | 10 | Las 16, legibles | Faltan hasta 4 | Faltan más de 4 |
| Capturas: son tuyas y se entienden (tu usuario y tu repositorio visibles; el texto se lee) | 6 | Todas | Algunas ilegibles o sin identificar | Parecen copiadas de la guía |

## 3. Comprensión, criterio de arquitecto (30)

Se comprueba que entiendes cómo encajan las piezas y por qué. No se evalúa código sino tus explicaciones, las de la plantilla de evidencias y las del vídeo.

| Aspecto | Puntos | Completo | Parcial | Insuficiente |
|---|---|---|---|---|
| Explicación de arquitectura por captura: qué pieza es, qué decisión hay detrás y qué riesgo cubre | 18 | Las 16, con tus palabras y concretas | Algunas genéricas o copiadas de la guía | Vacías o casi |
| La puerta de calidad: por qué `hasta` = 2018 se rechaza con 0,02 y qué implica aprobarlo con 0,10 (5 lotes sin especialidad en la ventana común, ruido, decisión de arquitecto que se justifica) | 6 | Lo explicas con las cifras (0,7951 frente a 0,8525) y con el motivo del ruido | Das las cifras sin el motivo | No lo explicas |
| Qué falta para una producción real (orquestación, seguridad de acceso, observabilidad, monitorización del modelo...) | 6 | Al menos tres carencias con su riesgo | Una o dos | Ninguna |

## Cómo se aplican los niveles

- Completo da todos los puntos del aspecto. Parcial, hasta la mitad. Insuficiente, 0.
- Lo que no puedas hacer por un fallo de GitHub o del Codespace se puntúa si lo documentas: captura del error y paso en que ocurrió.
- Una captura retocada o inventada anula el aspecto al que pertenece.
- El instructor te identifica por el nombre del repositorio y por tu enlace. Si no se puede abrir, no se puede evaluar.

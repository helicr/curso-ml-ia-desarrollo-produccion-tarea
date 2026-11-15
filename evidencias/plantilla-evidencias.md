# Plantilla de evidencias

Tarea Curso Taller «De Modelo de ML/IA a Producción». Fecha de entrega: 30/11/2026.

Este archivo ya está en `evidencias/` de tu fork. Rellénalo sustituyendo cada marca «ESCRIBE AQUÍ» (la que va entre corchetes) por tu texto y súbelo junto con las capturas y el vídeo. Las capturas van en
`evidencias/capturas/` con el nombre indicado (la extensión puede ser `.png`, `.jpg` o `.webp`) y el vídeo, en `evidencias/video/`.
El paso entre paréntesis es el de la [guía detallada](../taller/guia-detallada.md), que explica cómo conseguir cada captura.

Para cada captura escribe tu explicación de arquitectura con tus palabras: qué pieza es, qué decisión de arquitectura hay detrás y qué riesgo cubre.
Bastan dos o cuatro líneas, concretas y no copiadas de la guía. Esta parte es la que más pesa en la comprensión (30 puntos).

## Datos de la entrega

- Mi usuario de GitHub: [ESCRIBE AQUÍ]
- Enlace de mi fork (debe ser `https://github.com/<mi-usuario>/taller-ml-ia-dev-production`): [ESCRIBE AQUÍ]
- Nombre de mi Codespace: [ESCRIBE AQUÍ]
- Fecha en que hice el despliegue: [ESCRIBE AQUÍ]
- Canal del curso por el que envié el enlace (chat del grupo, Google Classroom o correo del curso): [ESCRIBE AQUÍ]

## 1. `01-fork-renombrado` (paso 2)

- Archivo: `evidencias/capturas/01-fork-renombrado.png` (o `.jpg` / `.webp`)
- Debe verse: El repositorio `taller-ml-ia-dev-production` con la línea «forked from ...».
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: fork y nombre estable; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 2. `02-codespace-abierto` (paso 3)

- Archivo: `evidencias/capturas/02-codespace-abierto.png` (o `.jpg` / `.webp`)
- Debe verse: El Codespace abierto: explorador, terminal y, abajo a la izquierda, su nombre.
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: entorno de desarrollo como código; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 3. `03-verificar-entorno` (paso 5)

- Archivo: `evidencias/capturas/03-verificar-entorno.png` (o `.jpg` / `.webp`)
- Debe verse: `make verificar` con cinco marcas `[OK   ]` y «LISTO PARA EL TALLER».
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: precondición comprobable; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 4. `04-pipeline` (paso 7)

- Archivo: `evidencias/capturas/04-pipeline.png` (o `.jpg` / `.webp`)
- Debe verse: El final de `make pipeline`: «Mejor modelo», «versión 1», la línea «Resumen» y el tiempo `real`.
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: pipelines por capas y modelo; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 5. `05-pipeline-sin-cambios` (paso 8)

- Archivo: `evidencias/capturas/05-pipeline-sin-cambios.png` (o `.jpg` / `.webp`)
- Debe verse: La segunda ejecución: las cuatro líneas «sin cambios».
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: idempotencia; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 6. `06-modelo-version` (paso 9)

- Archivo: `evidencias/capturas/06-modelo-version.png` (o `.jpg` / `.webp`)
- Debe verse: `make comparar`: los cuatro caminos de predicción como «coincide».
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: registro de modelos y deriva entre entrenamiento y servicio; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 7. `07-imagenes` (paso 11)

- Archivo: `evidencias/capturas/07-imagenes.png` (o `.jpg` / `.webp`)
- Debe verse: `make imagenes` terminado (con su tiempo) y `docker image ls 'cafe-*'` con las dos imágenes.
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: imágenes: entorno empaquetado; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 8. `08-compose-sano` (paso 12)

- Archivo: `evidencias/capturas/08-compose-sano.png` (o `.jpg` / `.webp`)
- Debe verse: «Container cafe-api-1 Healthy», «Container cafe-interfaz-1 Healthy» y `docker compose ... ps`.
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: compose: topología declarada; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 9. `09-puerto-8090` (paso 13)

- Archivo: `evidencias/capturas/09-puerto-8090.png` (o `.jpg` / `.webp`)
- Debe verse: La pestaña Puertos con el 8090 («Interfaz (UI)») y su dirección.
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: un único punto de entrada; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 10. `10-ui-cabecera` (paso 13)

- Archivo: `evidencias/capturas/10-ui-cabecera.png` (o `.jpg` / `.webp`)
- Debe verse: La interfaz con su cabecera: tu repositorio, el modelo y su versión, la huella y «API: lista».
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: trazabilidad del modelo; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 11. `11-ui-resultado` (paso 14)

- Archivo: `evidencias/capturas/11-ui-resultado.png` (o `.jpg` / `.webp`)
- Debe verse: Un resultado de consulta: tramos, probabilidades, avisos y el pie con modelo y huella.
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: la probabilidad como decisión de negocio; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 12. `12-validar-verde` (paso 18)

- Archivo: `evidencias/capturas/12-validar-verde.png` (o `.jpg` / `.webp`)
- Debe verse: El workflow `Validar` terminado en verde, con su duración.
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: integración continua; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 13. `13-environment-produccion` (paso 19)

- Archivo: `evidencias/capturas/13-environment-produccion.png` (o `.jpg` / `.webp`)
- Debe verse: El environment `produccion` con tu usuario como revisor.
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: puerta humana y permisos mínimos; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 14. `14-nueva-version-rechazada` (paso 20)

- Archivo: `evidencias/capturas/14-nueva-version-rechazada.png` (o `.jpg` / `.webp`)
- Debe verse: `Nueva version del modelo` con la tolerancia por defecto: el error «Version rechazada» y sus cifras.
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: puerta de calidad automática; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 15. `15-nueva-version-aprobacion` (paso 21)

- Archivo: `evidencias/capturas/15-nueva-version-aprobacion.png` (o `.jpg` / `.webp`)
- Debe verse: `Nueva version del modelo` con `tolerancia` = 0.10: la aprobación manual de `produccion` y los trabajos.
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: aprobación manual y tolerancia; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## 16. `16-paquetes-y-pr` (paso 22)

- Archivo: `evidencias/capturas/16-paquetes-y-pr.png` (o `.jpg` / `.webp`)
- Debe verse: Los paquetes `cafe-api` y `cafe-interfaz` con la etiqueta `v2-...` y el pull request abierto.
- Lo que muestra mi captura: [ESCRIBE AQUÍ]
- Mi explicación de arquitectura (tema: artefacto versionado y cambio por pull request; qué pieza es, qué decisión hay detrás, qué riesgo cubre): [ESCRIBE AQUÍ]

## Vídeo

- Archivo: `evidencias/video/servicio-en-produccion.mp4` (MP4, de 2 a 4 minutos, con voz, menos de 50 MB).
- Duración real: [ESCRIBE AQUÍ]
- Tamaño real (MB): [ESCRIBE AQUÍ]
- Lo que se ve y se cuenta en el vídeo (apunta los minutos): [ESCRIBE AQUÍ]

## Preguntas de comprensión

1. `Nueva version del modelo` con `hasta` = 2018 y la tolerancia por defecto (0,02) se rechaza: AUC en la ventana común de 0,7951 frente a 0,8525 (diferencia de -0,0574).
   ¿Por qué se rechaza y por qué subir la tolerancia a 0,10 es una decisión de arquitecto que hay que justificar?
   Respuesta: [ESCRIBE AQUÍ]

2. ¿Por qué la API no se publica fuera de la red de los contenedores y por qué los datos se montan en solo lectura?
   Respuesta: [ESCRIBE AQUÍ]

3. ¿Por qué hay dos imágenes (`cafe-api` y `cafe-interfaz`) y no una?
   Respuesta: [ESCRIBE AQUÍ]

4. Escribe al menos tres cosas que faltan para una producción real y el riesgo de cada una.
   Respuesta: [ESCRIBE AQUÍ]

## Lo que no pude hacer o no me funcionó

Si algún paso no te funcionó, dilo aquí con el número del paso, la captura del error y lo que probaste. Vale más que dejar un hueco.

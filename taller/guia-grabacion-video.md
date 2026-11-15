# Guía de grabación del vídeo

Tarea Curso Taller «De Modelo de ML/IA a Producción». El vídeo demuestra que el servicio funciona a través de su interfaz, con el modelo en producción.
No necesitas herramientas especiales: sirve el grabador de pantalla que ya tengas.

Requisitos de la entrega, fijados por el instructor: formato MP4, de 2 a 4 minutos, con tu voz, de menos de 50 MB, en
`evidencias/video/servicio-en-produccion.mp4` de tu fork.

> Lo que sigue sobre programas de grabación y compresión es un método general. No se ha grabado ni comprimido
> ningún vídeo de ejemplo para este taller (sin verificar). Si tu programa se ve distinto, usa el equivalente.

## 1. Antes de grabar

1. Haz los pasos 5 a 14 de la [guía detallada](guia-detallada.md) una vez, sin grabar, para saber qué va a salir.
2. Deja los contenedores levantados con `make compose-arriba` y comprueba que la interfaz abre en el puerto 8090 (paso 13).
3. Cierra lo que no quieras enseñar: correo, chats, otras pestañas del navegador, notificaciones.
4. Ten abiertas dos cosas, una al lado de la otra o en dos ventanas entre las que puedas alternar:
   - el Codespace (la terminal);
   - la interfaz, en otra pestaña del navegador (`https://<nombre-del-codespace>-8090.app.github.dev`).
5. Ten a mano el guion de abajo. No hace falta aprendérselo: puedes leerlo o improvisar con él delante.
6. Prueba el micrófono con una grabación de 10 segundos y escúchala. Tiene que entenderse y no debe haber ruido fuerte.

## 2. Cómo grabar sin herramientas especiales

Elige una de estas rutas, la que ya tengas:

| Si usas | Cómo |
|---|---|
| Windows 10 u 11 | Barra de juegos de Xbox: pulsa `Win + G` con el navegador seleccionado, activa el micrófono y pulsa «Grabar» (o `Win + Alt + R`). Graba la ventana activa. Los vídeos se guardan en la carpeta Vídeos > Capturas. |
| Windows 11 | Herramienta Recortes: `Win + Mayús + S`, elige el modo de vídeo y la zona de la pantalla. Si tu versión permite activar el micrófono, hazlo. Si no, usa la Barra de juegos. |
| macOS | `Mayús + Cmd + 5`, «Grabar pantalla completa» y, en Opciones, el micrófono. Guarda en `.mov`, así que hay que convertirlo (ver más abajo). |
| Cualquier sistema | Una reunión contigo solo en Teams, Meet o Zoom, compartiendo pantalla y grabando. Después descargas la grabación en MP4. |

Graba a 1280 x 720 o 1920 x 1080, no más. En la pantalla de un portátil, un texto pequeño no se lee en un vídeo comprimido: aumenta el zoom del navegador (`Ctrl +`) y el de la terminal para que se lean la interfaz y los comandos.

## 3. Qué debe verse y oírse (guion de 2 a 4 minutos)

| Minutos | Qué muestras | Qué dices, con tus palabras |
|---|---|---|
| 0:00 - 0:20 | La cabecera de la interfaz en el navegador, con tu repositorio `<tu-usuario>/taller-ml-ia-dev-production`, el modelo (`gradient_boosting`, su versión) y su huella | Quién eres y qué vas a enseñar: el modelo de calidad del café en producción. |
| 0:20 - 1:00 | La terminal del Codespace con `docker compose -f deploy/docker/compose.yaml ps`: dos contenedores `(healthy)`, el puerto 8090 publicado y el 8080 sin publicar | Qué son los dos contenedores y por qué la API no se publica fuera. |
| 1:00 - 2:30 | La interfaz: pulsas Ejemplo y Consultar, lees el resultado (tramos, probabilidades, recomendación) y señalas un aviso. Después, un lote nuevo («Rellenar con un ejemplo» y «Predecir lote nuevo») | Qué hace el modelo con ese lote, qué significa cada tramo y por qué hay avisos (el modelo no esconde su incertidumbre). |
| 2:30 - 3:30 | La huella del modelo en la cabecera y en el pie del resultado. Si quieres, el workflow `Validar` en verde y el environment `produccion` | La arquitectura: de los datos al modelo, a la API, a la imagen y al contenedor. Una decisión y el riesgo que cubre. |
| 3:30 - 4:00 | La interfaz de nuevo | Cierre: qué falta para una producción real. |

Si te falta tiempo, lo mínimo es esto: la cabecera con tu repositorio, los contenedores sanos, una consulta de lotes con su resultado y tu voz explicando la arquitectura.

## 4. Cómo comprobar el vídeo antes de subirlo

1. Ábrelo con el reproductor del sistema, de principio a fin. Se tiene que ver la interfaz y los comandos, y oírse tu voz.
2. Mira su duración (entre 2:00 y 4:00) y su tamaño (menos de 50 MB). En Windows: clic derecho > Propiedades. En la terminal del Codespace: `ls -lh evidencias/video/`.
3. El nombre debe ser exactamente `servicio-en-produccion.mp4`.

## 5. Cómo bajarlo de 50 MB

Un vídeo de pantalla de 4 minutos sale grande si el grabador usa mucha calidad. El tamaño es aproximadamente:

> tamaño (MB) = bitrate total (megabits por segundo) x segundos / 8

Para 4 minutos (240 s) y menos de 50 MB, el bitrate total tiene que ser menor de 1,67 Mbit/s. Apunta a 1,2 Mbit/s o menos, entre vídeo y audio: así sale por debajo de 36 MB para 4 minutos.

Si tu grabación ya es un MP4 de menos de 50 MB, no hace falta hacer nada. Si pasa de 50 MB, tienes tres opciones:

- Con el editor de vídeo de tu sistema (por ejemplo Clipchamp en Windows 11): abre el vídeo y exporta en 720p con calidad estándar o baja.
- Con HandBrake, que es gratuito: abre el vídeo, elige el ajuste «Fast 720p30» y el formato MP4, pon la calidad constante entre 26 y 30 y pulsa «Iniciar codificación».
- Con ffmpeg, si lo tienes instalado:

```bash
ffmpeg -i entrada.mov -vf scale=-2:720 -c:v libx264 -b:v 1000k -maxrate 1200k -bufsize 2400k -c:a aac -b:a 96k -movflags +faststart servicio-en-produccion.mp4
```

Después vuelve a comprobar duración y tamaño (apartado 4). No recortes el audio: tiene que oírse tu voz.

## 6. Cómo subirlo al fork

El vídeo va dentro del fork, en `evidencias/video/`. La carpeta ya existe y tiene un archivo `.gitkeep` vacío.

1. Arrastra el MP4 desde tu equipo al explorador del Codespace, sobre la carpeta `evidencias/video`.
2. Sube los cambios desde la terminal del Codespace:

```bash
git add evidencias
git commit -m "Evidencias de la tarea"
git push
```

Por la terminal se admite un archivo de este tamaño. Si lo subes por la web de GitHub (botón «Upload files»), el límite documentado es de 25 MB por archivo (sin verificar aquí). Si tu vídeo es mayor, usa la terminal.
Subir un MP4 desde el Codespace no se ha probado en este taller (sin verificar).

Comprueba en tu fork, en el navegador, que `evidencias/video/servicio-en-produccion.mp4` aparece y se reproduce.

## 7. Errores frecuentes

- Sin audio, porque el micrófono no estaba activado: vuelve a grabar.
- Texto ilegible: aumenta el zoom y exporta a 720p como mínimo.
- Se ve la interfaz pero no se ve que sean tus contenedores ni tu repositorio: enseña la cabecera y `docker compose ... ps`.
- Dura menos de 2 minutos o más de 4: recorta o vuelve a grabar.
- Se ven datos que no son tuyos o notificaciones personales: cierra todo lo que no sea el taller antes de grabar.

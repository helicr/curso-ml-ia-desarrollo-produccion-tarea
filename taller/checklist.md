# Checklist antes de entregar

Tarea Curso Taller «De Modelo de ML/IA a Producción». Fecha de entrega: 30/11/2026. Marca cada punto cuando lo hayas comprobado tú.

## Repositorio

- [ ] Hice un fork de la plantilla (no «Use this template»).
- [ ] El fork se llama exactamente `taller-ml-ia-dev-production`.
- [ ] El repositorio es público (lo abro en una ventana privada y lo veo).
- [ ] No cambié ningún archivo del proyecto: solo añadí `evidencias/`.

## Despliegue en el Codespace

- [ ] `make verificar` termina en «LISTO PARA EL TALLER».
- [ ] `make pipeline` crea el modelo (versión 1) y repetirlo dice «sin cambios».
- [ ] `make comparar` muestra los cuatro caminos de predicción como «coincide».
- [ ] `make imagenes` construye `cafe-api:local` y `cafe-interfaz:local`.
- [ ] `make compose-arriba` deja los dos contenedores sanos.
- [ ] La interfaz abre por el puerto 8090 y su cabecera muestra mi repositorio, el modelo, la versión y la huella.
- [ ] Consulté lotes desde la interfaz y vi el resultado con sus avisos.

## CI/CD en mi fork

- [ ] Habilité las Actions de mi fork.
- [ ] `Validar` terminó en verde.
- [ ] Creé el environment `produccion` con un revisor y marqué «Allow GitHub Actions to create and approve pull requests».
- [ ] `Nueva version del modelo` con `hasta` = 2018 y la tolerancia por defecto terminó rechazada.
- [ ] `Nueva version del modelo` con `tolerancia` = 0.10 esperó mi aprobación, la aprobé, publicó las dos imágenes `v2-...` y abrió un pull request.

## Evidencias

- [ ] El vídeo está en `evidencias/video/servicio-en-produccion.mp4`.
- [ ] El vídeo es MP4, dura entre 2 y 4 minutos, tiene mi voz y pesa menos de 50 MB.
- [ ] En el vídeo se ve el servicio funcionando por la interfaz, con los contenedores levantados.
- [ ] Las 16 capturas están en `evidencias/capturas/` con los nombres de la plantilla (`01-fork-renombrado` ... `16-paquetes-y-pr`).
- [ ] En cada captura se leen el texto y mi usuario o mi repositorio (no son las de ejemplo de la guía).
- [ ] Rellené `evidencias/plantilla-evidencias.md`: para cada captura, mi explicación de arquitectura (pieza, decisión, riesgo).
- [ ] Hice `git add evidencias`, `git commit` y `git push`, y veo los archivos en GitHub.

## Comprensión

- [ ] Sé explicar por qué `hasta` = 2018 se rechaza con la tolerancia 0,02 y qué justifica (o no) subirla a 0,10.
- [ ] Sé decir por qué la API no se publica fuera y por qué los datos se montan en solo lectura.
- [ ] Sé decir al menos tres cosas que faltan para una producción real.

## Entrega

- [ ] Envié el enlace de mi fork por el canal del curso.
- [ ] Lo hice el 30/11/2026 como máximo, durante ese día.
- [ ] Paré mi Codespace para no gastar cuota.

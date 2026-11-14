-- Puebla ml_dataset: une las variables de FS con el objetivo y la partición.
-- El objetivo mira el resultado de la cata (esa es su función: es la respuesta que el modelo debe anticipar);
-- las variables solo traen lo que se conoce al recibir el lote.
INSERT INTO ml_dataset (lote_id, particion, anio_cata, y, especie, pais, variedad, metodo_proceso, color,
                        altitud_media_m, humedad, defectos_cat1, defectos_cat2, quakers)
SELECT fs.lote_id, p.particion, m.anio_cata,
       CASE WHEN m.total_puntos >= (SELECT valor FROM ml_parametros WHERE clave = 'umbral_especialidad') THEN 1 ELSE 0 END,
       fs.especie, fs.pais, fs.variedad, fs.metodo_proceso, fs.color,
       fs.altitud_media_m, fs.humedad, fs.defectos_cat1, fs.defectos_cat2, fs.quakers
FROM fs_lote fs
JOIN master_lotes m ON m.lote_id = fs.lote_id
JOIN ml_particiones p ON m.anio_cata BETWEEN p.anio_desde AND p.anio_hasta
ORDER BY fs.lote_id;

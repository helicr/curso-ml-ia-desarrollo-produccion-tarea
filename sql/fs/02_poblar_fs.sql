-- Puebla fs_lote desde MASTER: una fila por lote catado, solo con lo que se conoce al recibir el lote.
-- No hay cálculos ventana a ventana: las variables ya vienen depuradas de MASTER (altitud y humedad dudosas ya son nulas).
INSERT INTO fs_lote (lote_id, especie, pais, variedad, metodo_proceso, color, altitud_media_m, humedad,
                     defectos_cat1, defectos_cat2, quakers)
SELECT lote_id, especie, pais, variedad, metodo_proceso, color,
       CAST(altitud_media_m AS REAL), CAST(humedad AS REAL),
       CAST(defectos_cat1 AS REAL), CAST(defectos_cat2 AS REAL), CAST(quakers AS REAL)
FROM master_lotes
ORDER BY lote_id;

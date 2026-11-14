-- Puebla MASTER desde RAW. Necesita la función SQL fecha_iso() (la registra cafe_mlops/dataset.py) y master_parametros.
-- Reglas de depuración (cada una tiene su regla de calidad y su prueba):
--   · textos: se recortan (espacios, tabuladores y saltos de línea) y el texto vacío pasa a NULL
--   · fecha de cata: «April 4th, 2015» (a veces con saltos de línea al final) -> 'AAAA-MM-DD'
--   · altitud media fuera de [altitud_min_m, altitud_max_m] -> NULL            (R07)
--   · humedad = 0 -> NULL («no medido», decisión 14)                           (R10)
--   · cata con total 0 (incompleta) -> DESCARTE con su motivo                  (R09)

-- 1) Descartes: lotes que no pueden pasar a MASTER, con su motivo.
INSERT INTO master_descartes (lote_id, motivo)
SELECT lote_id, motivo FROM (
    SELECT l.lote_id,
           CASE WHEN c.cata_id IS NULL THEN 'sin_cata'
                WHEN c.total_puntos IS NULL OR c.total_puntos <= 0 THEN 'cata_incompleta_total_cero'
                WHEN fecha_iso(c.fecha_cata_texto) IS NULL THEN 'fecha_cata_ilegible'
           END AS motivo
    FROM raw_lotes l
    LEFT JOIN raw_catas c ON c.lote_id = l.lote_id
)
WHERE motivo IS NOT NULL
ORDER BY lote_id;

-- 2) Lotes catados y depurados.
INSERT INTO master_lotes (lote_id, especie, pais, variedad, metodo_proceso, color, altitud_media_m, altitud_media_origen_m,
                          humedad, humedad_origen, defectos_cat1, defectos_cat2, quakers, numero_sacos,
                          fecha_cata, anio_cata, total_puntos)
SELECT l.lote_id,
       NULLIF(TRIM(l.especie, char(32, 9, 10, 13)), ''),
       NULLIF(TRIM(p.nombre, char(32, 9, 10, 13)), ''),
       NULLIF(TRIM(l.variedad, char(32, 9, 10, 13)), ''),
       NULLIF(TRIM(l.metodo_proceso, char(32, 9, 10, 13)), ''),
       NULLIF(TRIM(a.color, char(32, 9, 10, 13)), ''),
       CASE WHEN l.altitud_media_m BETWEEN (SELECT valor FROM master_parametros WHERE clave = 'altitud_min_m')
                                       AND (SELECT valor FROM master_parametros WHERE clave = 'altitud_max_m')
            THEN l.altitud_media_m END,
       l.altitud_media_m,
       CASE WHEN a.humedad = (SELECT valor FROM master_parametros WHERE clave = 'humedad_no_medida') THEN NULL ELSE a.humedad END,
       a.humedad,
       a.defectos_cat1, a.defectos_cat2, a.quakers,
       l.numero_sacos,
       fecha_iso(c.fecha_cata_texto),
       CAST(substr(fecha_iso(c.fecha_cata_texto), 1, 4) AS INTEGER),
       c.total_puntos
FROM raw_lotes l
JOIN raw_catas c ON c.lote_id = l.lote_id
LEFT JOIN raw_analisis_verde a ON a.lote_id = l.lote_id
LEFT JOIN raw_paises p ON p.pais_id = l.pais_id
WHERE l.lote_id NOT IN (SELECT lote_id FROM master_descartes)
ORDER BY l.lote_id;

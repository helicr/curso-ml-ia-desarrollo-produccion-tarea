-- Deriva las tablas operacionales a partir de los lotes de los CSV (temp.tmp_origen, una fila por lote, en el orden de los archivos:
-- primero arábica y luego robusta) y de sus notas (temp.tmp_notas, una fila por lote y atributo).
-- No corrige nada: lo que llega, se guarda. Cada lote tiene una sola cata (una fila del CSV = un lote = una cata).

-- Catálogos: los valores distintos, en orden de aparición (el id se asigna por el primer lote donde aparece).
INSERT INTO paises (nombre)
SELECT pais FROM temp.tmp_origen WHERE pais IS NOT NULL GROUP BY pais ORDER BY MIN(lote_id);

INSERT INTO entidades (nombre)
SELECT nombre FROM (
    SELECT socio_pais AS nombre, lote_id FROM temp.tmp_origen WHERE socio_pais IS NOT NULL
    UNION ALL
    SELECT certificadora, lote_id FROM temp.tmp_origen WHERE certificadora IS NOT NULL
) GROUP BY nombre ORDER BY MIN(lote_id), nombre;

INSERT INTO productores (nombre)
SELECT productor FROM temp.tmp_origen WHERE productor IS NOT NULL GROUP BY productor ORDER BY MIN(lote_id);

-- Lotes
INSERT INTO lotes (lote_id, especie, id_origen, pais_id, productor_id, propietario, propietario_2, finca, numero_lote, molino,
                   numero_ico, compania, region, numero_sacos, peso_saco, anio_cosecha, variedad, metodo_proceso,
                   altitud_texto, unidad_altitud, altitud_baja_m, altitud_alta_m, altitud_media_m)
SELECT o.lote_id, o.especie, o.id_origen, p.pais_id, pr.productor_id, o.propietario, o.propietario_2, o.finca, o.numero_lote, o.molino,
       o.numero_ico, o.compania, o.region, o.numero_sacos, o.peso_saco, o.anio_cosecha, o.variedad, o.metodo_proceso,
       o.altitud_texto, o.unidad_altitud, o.altitud_baja_m, o.altitud_alta_m, o.altitud_media_m
FROM temp.tmp_origen o
LEFT JOIN paises p ON p.nombre = o.pais
LEFT JOIN productores pr ON pr.nombre = o.productor
ORDER BY o.lote_id;

INSERT INTO analisis_verde (lote_id, humedad, defectos_cat1, defectos_cat2, quakers, color)
SELECT lote_id, humedad, defectos_cat1, defectos_cat2, quakers, color
FROM temp.tmp_origen
ORDER BY lote_id;

-- Catas: el cata_id coincide con el lote_id (una cata por lote).
INSERT INTO catas (cata_id, lote_id, entidad_id, certificadora_id, cert_direccion, cert_contacto,
                   fecha_cata_texto, caducidad_texto, total_puntos)
SELECT o.lote_id, o.lote_id, e1.entidad_id, e2.entidad_id, o.cert_direccion, o.cert_contacto,
       o.fecha_cata, o.caducidad, o.total_puntos
FROM temp.tmp_origen o
LEFT JOIN entidades e1 ON e1.nombre = o.socio_pais
LEFT JOIN entidades e2 ON e2.nombre = o.certificadora
ORDER BY o.lote_id;

INSERT INTO notas_cata (cata_id, atributo, valor)
SELECT lote_id, atributo, valor FROM temp.tmp_notas ORDER BY rowid;

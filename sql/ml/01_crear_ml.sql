-- CAPA ML: el dataset listo para entrenar = variables (FS) + objetivo (y) + partición.
-- Una fila por lote.
--   y = 1 si el lote alcanza el grado de especialidad (puntos totales >= umbral); 0 si no.
-- La partición es TEMPORAL y deslizante (train antes que valid antes que test), por el año de la cata, nunca aleatoria ni por orden de fila:
-- así el modelo se evalúa como se usaría, prediciendo lotes de años que no ha visto.
DROP TABLE IF EXISTS ml_dataset;
DROP TABLE IF EXISTS ml_particiones;
DROP TABLE IF EXISTS ml_parametros;

-- Valores de config.py que usa el SQL de ML (los escribe el pipeline antes de poblar).
CREATE TABLE ml_parametros (
    clave TEXT PRIMARY KEY,
    valor REAL NOT NULL
);

-- Intervalos de años de cata (cerrados) de cada partición, de config.particiones_de(): DESLIZAN con la versión de los datos
-- (versión 1: train <= 2014, valid 2015, test 2016; versión 2: train <= 2015, valid 2016, test 2017-2018).
CREATE TABLE ml_particiones (
    particion  TEXT PRIMARY KEY CHECK (particion IN ('train', 'valid', 'test')),
    anio_desde INTEGER NOT NULL,
    anio_hasta INTEGER NOT NULL,
    CHECK (anio_desde <= anio_hasta)
);

CREATE TABLE ml_dataset (
    lote_id         INTEGER PRIMARY KEY REFERENCES fs_lote (lote_id),
    particion       TEXT    NOT NULL REFERENCES ml_particiones (particion),
    anio_cata       INTEGER NOT NULL,     -- solo para ordenar y comprobar la partición: NO es una variable del modelo
    y               INTEGER NOT NULL CHECK (y IN (0, 1)),
    especie         TEXT NOT NULL,
    pais            TEXT,
    variedad        TEXT,
    metodo_proceso  TEXT,
    color           TEXT,
    altitud_media_m REAL,
    humedad         REAL,
    defectos_cat1   REAL,
    defectos_cat2   REAL,
    quakers         REAL
);
CREATE INDEX ix_ml_particion ON ml_dataset (particion);

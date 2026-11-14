-- CAPA MASTER: el dato depurado, con tipos correctos, claves y relaciones. Una fila por LOTE CATADO.
-- Regla: MASTER se puede borrar y regenerar por completo desde RAW. Nada se edita a mano.
-- MASTER NO lleva nombres de personas ni contactos (propietario, productor, finca, certificadora): no hacen falta aguas abajo
-- y así no hay forma de usarlos por descuido como variables. Tampoco lleva las diez notas de cata (siguen en raw_notas_cata).
PRAGMA foreign_keys = OFF;
DROP TABLE IF EXISTS master_lotes;
DROP TABLE IF EXISTS master_descartes;
DROP TABLE IF EXISTS master_calidad;
DROP TABLE IF EXISTS master_parametros;
PRAGMA foreign_keys = ON;

-- Valores de config.py que usan las reglas de depuración (los escribe el pipeline antes de poblar MASTER).
CREATE TABLE master_parametros (
    clave TEXT PRIMARY KEY,
    valor REAL NOT NULL
);

CREATE TABLE master_lotes (
    lote_id                INTEGER PRIMARY KEY,     -- el de la base operacional (linaje con raw_lotes)
    especie                TEXT    NOT NULL CHECK (especie IN ('Arabica', 'Robusta')),
    pais                   TEXT,                    -- nulo: el origen no lo trae
    variedad               TEXT,                    -- nulo = no informada
    metodo_proceso         TEXT,
    color                  TEXT,
    altitud_media_m        REAL CHECK (altitud_media_m IS NULL OR altitud_media_m > 0),
                                                    -- fuera de config.ALTITUD_MIN_M–ALTITUD_MAX_M (100–4 000 m) -> NULL (alerta R07)
    altitud_media_origen_m REAL,                    -- la que llegó, por si hay que revisarla
    humedad                REAL CHECK (humedad IS NULL OR humedad BETWEEN 0 AND 1),
                                                    -- fracción; 0 = «no medido» -> NULL (alerta R10)
    humedad_origen         REAL,                    -- la que llegó
    defectos_cat1          REAL CHECK (defectos_cat1 IS NULL OR defectos_cat1 >= 0),
    defectos_cat2          REAL CHECK (defectos_cat2 IS NULL OR defectos_cat2 >= 0),
    quakers                REAL CHECK (quakers IS NULL OR quakers >= 0),
    numero_sacos           INTEGER,
    fecha_cata             TEXT    NOT NULL,        -- AAAA-MM-DD (en el origen: «April 4th, 2015», a veces con saltos de línea)
    anio_cata              INTEGER NOT NULL,        -- año de fecha_cata: ordena en el tiempo y define la partición
    total_puntos           REAL    NOT NULL CHECK (total_puntos > 0)   -- Total.Cup.Points: de aquí sale el OBJETIVO, nunca una variable
);

-- Filas de RAW que NO pasaron a MASTER y por qué. raw_lotes = master_lotes + master_descartes.
CREATE TABLE master_descartes (
    lote_id INTEGER PRIMARY KEY,
    motivo  TEXT NOT NULL CHECK (motivo IN ('sin_cata', 'cata_incompleta_total_cero', 'fecha_cata_ilegible'))
);

-- Resultado de las reglas de calidad de la última ejecución.
CREATE TABLE master_calidad (
    regla        TEXT PRIMARY KEY,
    descripcion  TEXT NOT NULL,
    valor        REAL,
    umbral       TEXT,
    estado       TEXT NOT NULL CHECK (estado IN ('OK', 'ALERTA', 'ERROR')),
    evaluado_en  TEXT NOT NULL
);

CREATE INDEX ix_master_lotes_anio ON master_lotes (anio_cata);

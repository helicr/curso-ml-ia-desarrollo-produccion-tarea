-- CAPA FS (feature store didáctica): variables REUTILIZABLES, una fila por lote.
-- No es una plataforma de feature store: es una tabla con una regla de oro.
--     TODA variable se conoce AL RECIBIR EL LOTE, antes de catarlo.
-- Por eso FS nunca lee las notas de cata ni el total de puntos: es la FUGA que vigila tests/test_fs_y_ml.py.
-- Granularidad: una fila por lote (lote_id). A diferencia de los clientes del curso, aquí no hay ventanas temporales ni cortes:
-- las variables son propiedades del lote (origen, variedad, beneficio, análisis del grano verde).
-- Un valor que falta es NULL (no «Desconocida»): el Pipeline del modelo lo imputa dentro, igual en entrenamiento y en la API.
-- Con las claves foráneas apagadas, para poder rehacer FS aunque ML (que depende de ella) ya exista; pipeline_ml rehace las dos.
PRAGMA foreign_keys = OFF;
DROP TABLE IF EXISTS fs_lote;
DROP TABLE IF EXISTS fs_catalogo;
PRAGMA foreign_keys = ON;

CREATE TABLE fs_catalogo (
    feature         TEXT PRIMARY KEY,
    descripcion     TEXT NOT NULL,
    tipo            TEXT NOT NULL CHECK (tipo IN ('categorica', 'numerica')),
    origen          TEXT NOT NULL,       -- de dónde sale: tabla de MASTER y columna del CSV original
    cuando_se_conoce TEXT NOT NULL,      -- momento en que el dato existe; todas: al recibir el lote
    unidad          TEXT,
    entidad         TEXT NOT NULL DEFAULT 'lote'
);

INSERT INTO fs_catalogo (feature, descripcion, tipo, origen, cuando_se_conoce, unidad) VALUES
 ('especie',         'Arábica o robusta: protocolos de cata distintos',                     'categorica', 'master_lotes.especie (Species)',                        'al recibir el lote', NULL),
 ('pais',            'País de origen del lote',                                             'categorica', 'master_lotes.pais (Country.of.Origin)',                 'al recibir el lote', NULL),
 ('variedad',        'Variedad del café (nula si no se informó)',                           'categorica', 'master_lotes.variedad (Variety)',                       'al recibir el lote', NULL),
 ('metodo_proceso',  'Método de beneficio: lavado, natural... (nulo si no se informó)',     'categorica', 'master_lotes.metodo_proceso (Processing.Method)',       'al recibir el lote', NULL),
 ('color',           'Color del grano verde (nulo si no se informó)',                       'categorica', 'master_lotes.color (Color)',                            'al recibir el lote', NULL),
 ('altitud_media_m', 'Altitud media de la finca; nula si falta o está fuera de 100–4 000 m', 'numerica',   'master_lotes.altitud_media_m (altitude_mean_meters)', 'al recibir el lote', 'metros'),
 ('humedad',         'Humedad del grano verde; nula si no se midió (el 0 del origen)',      'numerica',   'master_lotes.humedad (Moisture)',                     'al recibir el lote', 'fracción 0–1'),
 ('defectos_cat1',   'Defectos de categoría 1 en la muestra de grano verde',                'numerica',   'master_lotes.defectos_cat1 (Category.One.Defects)',   'al recibir el lote', 'granos'),
 ('defectos_cat2',   'Defectos de categoría 2 en la muestra de grano verde',                'numerica',   'master_lotes.defectos_cat2 (Category.Two.Defects)',   'al recibir el lote', 'granos'),
 ('quakers',         'Granos «quaker» (inmaduros) en la muestra',                           'numerica',   'master_lotes.quakers (Quakers)',                      'al recibir el lote', 'granos');

-- Los números van como REAL (decimales) aunque los defectos sean enteros: la firma del modelo en MLflow admite nulos solo así
-- (un entero no puede ser nulo en la firma; ver _exploracion/pico_firma_mlflow).
CREATE TABLE fs_lote (
    lote_id         INTEGER PRIMARY KEY REFERENCES master_lotes (lote_id),
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

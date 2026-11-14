-- CAPA RAW: copia fiel de la base operacional «cqi», sin limpiar nada.
-- Regla: una tabla RAW por tabla de origen, con las mismas columnas y los mismos valores. RAW no valida ni corrige:
-- por eso no declara claves ni restricciones (si el origen trae un problema, RAW lo conserva y MASTER lo trata).
-- LINAJE: la clave de origen (lote_id, cata_id...) más _carga_id, que apunta a raw_carga.
DROP TABLE IF EXISTS raw_paises;
CREATE TABLE raw_paises (
    pais_id   INTEGER,
    nombre    TEXT,
    _carga_id INTEGER
);

DROP TABLE IF EXISTS raw_entidades;
CREATE TABLE raw_entidades (
    entidad_id INTEGER,
    nombre     TEXT,
    _carga_id  INTEGER
);

DROP TABLE IF EXISTS raw_productores;
CREATE TABLE raw_productores (
    productor_id INTEGER,
    nombre       TEXT,
    _carga_id    INTEGER
);

DROP TABLE IF EXISTS raw_lotes;
CREATE TABLE raw_lotes (
    lote_id         INTEGER,
    especie         TEXT,
    id_origen       INTEGER,
    pais_id         INTEGER,
    productor_id    INTEGER,
    propietario     TEXT,
    propietario_2   TEXT,
    finca           TEXT,
    numero_lote     TEXT,
    molino          TEXT,
    numero_ico      TEXT,
    compania        TEXT,
    region          TEXT,
    numero_sacos    INTEGER,
    peso_saco       TEXT,
    anio_cosecha    TEXT,
    variedad        TEXT,
    metodo_proceso  TEXT,
    altitud_texto   TEXT,
    unidad_altitud  TEXT,
    altitud_baja_m  REAL,
    altitud_alta_m  REAL,
    altitud_media_m REAL,
    _carga_id       INTEGER
);

DROP TABLE IF EXISTS raw_analisis_verde;
CREATE TABLE raw_analisis_verde (
    lote_id       INTEGER,
    humedad       REAL,
    defectos_cat1 REAL,
    defectos_cat2 REAL,
    quakers       REAL,
    color         TEXT,
    _carga_id     INTEGER
);

DROP TABLE IF EXISTS raw_catas;
CREATE TABLE raw_catas (
    cata_id          INTEGER,
    lote_id          INTEGER,
    entidad_id       INTEGER,
    certificadora_id INTEGER,
    cert_direccion   TEXT,
    cert_contacto    TEXT,
    fecha_cata_texto TEXT,
    caducidad_texto  TEXT,
    total_puntos     REAL,
    _carga_id        INTEGER
);

DROP TABLE IF EXISTS raw_notas_cata;
CREATE TABLE raw_notas_cata (
    cata_id   INTEGER,
    atributo  TEXT,
    valor     REAL,
    _carga_id INTEGER
);

-- Auditoría de cada extracción: de qué tabla, cuántas filas y la huella sha256 de su contenido.
-- Si la huella cambia entre dos cargas, cambió el origen.
DROP TABLE IF EXISTS raw_carga;
CREATE TABLE raw_carga (
    carga_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    origen      TEXT NOT NULL,    -- 'cqi'
    tabla       TEXT NOT NULL,
    filas       INTEGER NOT NULL,
    sha256      TEXT NOT NULL,
    extraido_en TEXT NOT NULL
);

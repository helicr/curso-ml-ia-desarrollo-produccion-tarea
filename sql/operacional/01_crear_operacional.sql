-- BASE OPERACIONAL «cqi»: simula el sistema del laboratorio de catas (OLTP) del Coffee Quality Institute.
-- Es la FUENTE del pipeline analítico: python -m cafe_mlops.operacional la construye desde los CSV y el pipeline RAW la ingiere.
-- Modelo normalizado (cada dato se guarda una vez) y con restricciones, como un sistema transaccional.
-- NO limpia nada: conserva la suciedad del origen (fechas con saltos de línea, altitudes imposibles, humedad 0,
-- cata con total 0...) porque un sistema operacional real también la tiene; es MASTER quien la trata.
-- Lo único que hace es poner NULL donde el CSV no trae valor (celda vacía o «NA») en las columnas numéricas.
--
--   paises 1 --- 0..n lotes 1 --- 1 analisis_verde
--   productores 1 --- 0..n lotes 1 --- 1..n catas 1 --- 10 notas_cata
--   entidades 1 --- 0..n catas (como laboratorio que cata y como certificadora)
--   origen_simulacion: control (de qué archivos sale la simulación y hasta qué año de cata). No es parte del negocio.
--
-- Datos de personas (decisión 4): los nombres del propietario y del productor se conservan tal cual vienen en el CSV.
-- Nunca se usan como variables del modelo (una prueba lo vigila).
DROP TABLE IF EXISTS notas_cata;
DROP TABLE IF EXISTS catas;
DROP TABLE IF EXISTS analisis_verde;
DROP TABLE IF EXISTS lotes;
DROP TABLE IF EXISTS productores;
DROP TABLE IF EXISTS entidades;
DROP TABLE IF EXISTS paises;
DROP TABLE IF EXISTS origen_simulacion;

CREATE TABLE paises (
    pais_id  INTEGER PRIMARY KEY,
    nombre   TEXT NOT NULL UNIQUE
);

CREATE TABLE entidades (               -- laboratorios / socios en el país y certificadoras (organizaciones)
    entidad_id INTEGER PRIMARY KEY,
    nombre     TEXT NOT NULL UNIQUE
);

CREATE TABLE productores (             -- Producer tal como se tecleó (puede ser un nombre de persona)
    productor_id INTEGER PRIMARY KEY,
    nombre       TEXT NOT NULL UNIQUE
);

CREATE TABLE lotes (
    lote_id         INTEGER PRIMARY KEY,   -- propio: arábica y robusta comparten ids en el origen (los dos empiezan en 1)
    especie         TEXT NOT NULL,         -- Species: 'Arabica' o 'Robusta'
    id_origen       INTEGER NOT NULL,      -- «Unnamed: 0» del CSV de su especie (linaje)
    pais_id         INTEGER REFERENCES paises (pais_id),            -- nulo: el origen no lo trae
    productor_id    INTEGER REFERENCES productores (productor_id),  -- nulo: el origen no lo trae
    propietario     TEXT,                  -- Owner
    propietario_2   TEXT,                  -- Owner.1
    finca           TEXT,                  -- Farm.Name
    numero_lote     TEXT,                  -- Lot.Number
    molino          TEXT,                  -- Mill
    numero_ico      TEXT,                  -- ICO.Number
    compania        TEXT,                  -- Company
    region          TEXT,                  -- Region
    numero_sacos    INTEGER,               -- Number.of.Bags
    peso_saco       TEXT,                  -- Bag.Weight, texto libre («60 kg», «100 lbs»...)
    anio_cosecha    TEXT,                  -- Harvest.Year, texto libre («2014», «2013/2014», «mmm»...)
    variedad        TEXT,                  -- Variety
    metodo_proceso  TEXT,                  -- Processing.Method
    altitud_texto   TEXT,                  -- Altitude tal como llegó («1950-2200», «1600 - 1800 m»...)
    unidad_altitud  TEXT,                  -- unit_of_measurement: 'm' o 'ft'
    altitud_baja_m  REAL,                  -- altitude_low_meters
    altitud_alta_m  REAL,                  -- altitude_high_meters
    altitud_media_m REAL                   -- altitude_mean_meters (SIN depurar: hay valores imposibles)
);

CREATE TABLE analisis_verde (          -- análisis del grano verde, conocido al recibir el lote (1:1 con lotes)
    lote_id       INTEGER PRIMARY KEY REFERENCES lotes (lote_id),
    humedad       REAL,                -- Moisture (fracción; 0 en muchos lotes = probablemente «no medido»)
    defectos_cat1 REAL,                -- Category.One.Defects
    defectos_cat2 REAL,                -- Category.Two.Defects
    quakers       REAL,                -- Quakers
    color         TEXT                 -- Color
);

CREATE TABLE catas (
    cata_id           INTEGER PRIMARY KEY,
    lote_id           INTEGER NOT NULL UNIQUE REFERENCES lotes (lote_id),
    entidad_id        INTEGER REFERENCES entidades (entidad_id),   -- In.Country.Partner: quien cata y pone la nota
    certificadora_id  INTEGER REFERENCES entidades (entidad_id),   -- Certification.Body
    cert_direccion    TEXT,                -- Certification.Address
    cert_contacto     TEXT,                -- Certification.Contact
    fecha_cata_texto  TEXT NOT NULL,       -- Grading.Date TAL COMO LLEGÓ («April 4th, 2015»; algunas con saltos de línea)
    caducidad_texto   TEXT,                -- Expiration (= fecha de cata + 1 año)
    total_puntos      REAL                 -- Total.Cup.Points: es el OBJETIVO; 0 = cata incompleta
);

-- Una fila por atributo y cata (formato largo): así caben los atributos distintos de robusta.
-- El atributo usa el nombre de la columna del CSV. Las 10 notas SUMAN total_puntos: nunca son variables.
CREATE TABLE notas_cata (
    cata_id  INTEGER NOT NULL REFERENCES catas (cata_id),
    atributo TEXT    NOT NULL,
    valor    REAL,
    PRIMARY KEY (cata_id, atributo)
);

-- No es parte del negocio: deja constancia de que esta base es una SIMULACIÓN, de qué archivos sale y hasta qué año de cata.
CREATE TABLE origen_simulacion (
    archivo          TEXT NOT NULL,
    sha256           TEXT NOT NULL,
    filas_archivo    INTEGER NOT NULL,     -- filas de datos del CSV
    filas_cargadas   INTEGER NOT NULL,     -- las que entran en la base con este --hasta
    hasta            INTEGER NOT NULL,     -- año de cata máximo (--hasta)
    version_datos    INTEGER NOT NULL,     -- 1 = --hasta 2016, 2 = --hasta 2018
    creada_en        TEXT NOT NULL
);

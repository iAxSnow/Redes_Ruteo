-- ========================================================
-- SCHEMA BASE
-- ========================================================
CREATE SCHEMA IF NOT EXISTS rr;

-- ========================================================
-- TABLA: rr.nodes
-- Nodos de la red (extraídos desde OSM)
-- ========================================================
CREATE TABLE IF NOT EXISTS rr.nodes (
  id   BIGINT PRIMARY KEY,
  geom geometry(Point, 4326) NOT NULL
);

-- ========================================================
-- TABLA: rr.ways
-- Aristas de la red (calles de OSM)
-- ========================================================
CREATE TABLE IF NOT EXISTS rr.ways (
  id           BIGINT PRIMARY KEY,
  osm_id       BIGINT,
  source       BIGINT,
  target       BIGINT,
  geom         geometry(LineString, 4326),
  length_m     NUMERIC,
  highway      TEXT,
  oneway       BOOLEAN,
  maxspeed_kmh NUMERIC,
  lanes        NUMERIC,
  surface      TEXT,
  access       TEXT,
  width_m      NUMERIC,
  maxwidth_m   NUMERIC,
  tags         JSONB
);

-- Índices para pgRouting
CREATE INDEX IF NOT EXISTS ways_geom_idx ON rr.ways USING GIST (geom);
CREATE INDEX IF NOT EXISTS ways_source_idx ON rr.ways (source);
CREATE INDEX IF NOT EXISTS ways_target_idx ON rr.ways (target);

-- ========================================================
-- METADATA #1: Hidrantes – inspecciones (SISS)
-- ========================================================
CREATE TABLE IF NOT EXISTS rr.hydrant_inspections (
  id                   BIGSERIAL PRIMARY KEY,
  rut_empresa          TEXT,
  empresa              TEXT,
  periodo              INTEGER,
  codigo_comuna        INTEGER,
  nombre_comuna        TEXT,
  codigo_localidad     INTEGER,
  nombre_localidad     TEXT,
  codigo_grifo         TEXT,
  direccion            TEXT,
  referencia           TEXT,
  fecha_inspeccion     TIMESTAMP WITH TIME ZONE,
  hora_medicion        TEXT,
  presion              NUMERIC,
  cumple_presion       BOOLEAN,
  cumple_caudal        BOOLEAN,
  opera_vastago        BOOLEAN,
  valvula_pie_operativa BOOLEAN,
  fuga_agua            BOOLEAN,
  estado_calc          TEXT,
  raw                  JSONB
);

CREATE INDEX IF NOT EXISTS hydrant_inspections_comuna_idx 
  ON rr.hydrant_inspections (codigo_comuna);

-- ========================================================
-- METADATA #2: Hidrantes – estado agregado por comuna
-- ========================================================
CREATE TABLE IF NOT EXISTS rr.hydrant_status_muni (
  id                   BIGSERIAL PRIMARY KEY,
  periodo              INTEGER,
  codigo_comuna        INTEGER,
  nombre_comuna        TEXT,
  codigo_localidad     INTEGER,
  nombre_localidad     TEXT,
  grifos_existente     INTEGER,
  grifos_no_operativos INTEGER,
  grifos_reparados     INTEGER,
  grifos_reemplazados  INTEGER,
  grifos_reparar       INTEGER,
  grifos_reemplazar    INTEGER,
  inversion_total      NUMERIC,
  inversion_programada NUMERIC,
  tasa_no_operativos   NUMERIC,
  tasa_a_reparar       NUMERIC,
  tasa_a_reemplazar    NUMERIC,
  raw                  JSONB
);

CREATE INDEX IF NOT EXISTS hydrant_status_muni_comuna_idx 
  ON rr.hydrant_status_muni (codigo_comuna);

-- Metadata de anchos por OSM (complementaria)
CREATE TABLE IF NOT EXISTS rr.road_widths_meta (
  id           BIGSERIAL PRIMARY KEY,
  osm_id       BIGINT UNIQUE,
  highway      TEXT,
  lanes        SMALLINT,
  width_raw    TEXT,
  maxwidth_raw TEXT,
  width_m      NUMERIC,
  maxwidth_m   NUMERIC,
  geom         geometry(LineString, 4326)
);
CREATE INDEX IF NOT EXISTS road_widths_meta_gix ON rr.road_widths_meta USING GIST (geom);

-- Metadata de oneway por OSM (complementaria)
CREATE TABLE IF NOT EXISTS rr.road_oneway_meta (
  id         BIGSERIAL PRIMARY KEY,
  osm_id     BIGINT UNIQUE,
  highway    TEXT,
  oneway_raw TEXT,
  oneway     BOOLEAN,
  geom       geometry(LineString, 4326)
);
CREATE INDEX IF NOT EXISTS road_oneway_meta_gix ON rr.road_oneway_meta USING GIST (geom);

-- ========================================================
-- (Futuro) METADATA adicionales
-- Ejemplo: ancho de calles, sentidos de vías
-- ========================================================
-- ya considerados en rr.ways (width_m, oneway)

-- ========================================================
-- (Futuro) AMENAZAS
-- Ejemplo: incidentes, calles cortadas, clima, lomos de toro
-- ========================================================
-- Se crearán en la siguiente fase.

-- =========================================================
--  Esquema base para Fase 2 - Ruteo resiliente (RM, Chile)
--  Infraestructura OSM + Metadatas + Amenazas
--  Compatible con los loaders y scripts que vienes usando
-- =========================================================

-- 1) Extensiones necesarias
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;

-- 2) Esquema lógico
CREATE SCHEMA IF NOT EXISTS rr;
SET search_path TO rr, public;

-- =========================================================
-- 3) Infraestructura OSM
--    - nodes: puntos (nodos de la red)
--    - ways:  aristas (tramos viales)
--      * id = id interno único por tramo (PK)
--      * osm_id = id del way OSM (no único: un way puede trozarse)
--      * source/target = ids de vértices para pgRouting
-- =========================================================

-- 3.1 Nodos
CREATE TABLE IF NOT EXISTS rr.nodes (
  id   BIGINT PRIMARY KEY,
  geom geometry(Point, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS nodes_gix ON rr.nodes USING GIST (geom);

-- 3.2 Aristas
CREATE TABLE IF NOT EXISTS rr.ways (
  id            BIGINT PRIMARY KEY,
  osm_id        BIGINT,
  source        BIGINT,
  target        BIGINT,
  geom          geometry(LineString, 4326) NOT NULL,
  length_m      NUMERIC,              -- calculada con ST_LengthSpheroid
  highway       TEXT,
  oneway        BOOLEAN,              -- puede ser NULL si se desconoce
  maxspeed_kmh  INTEGER,
  lanes         INTEGER,
  surface       TEXT,
  access        TEXT,
  tags          JSONB,                -- tags crudos OSM y otros
  width_m       NUMERIC,              -- ancho estimado/medido (m)
  maxwidth_m    NUMERIC               -- restricción de ancho (m)
);

-- Índices recomendados para routing/consultas
CREATE INDEX IF NOT EXISTS ways_geom_gix    ON rr.ways USING GIST (geom);
CREATE INDEX IF NOT EXISTS ways_source_idx  ON rr.ways (source);
CREATE INDEX IF NOT EXISTS ways_target_idx  ON rr.ways (target);
CREATE INDEX IF NOT EXISTS ways_osm_id_idx  ON rr.ways (osm_id);
CREATE INDEX IF NOT EXISTS ways_hw_idx      ON rr.ways (highway);
CREATE INDEX IF NOT EXISTS ways_tags_gin    ON rr.ways USING GIN (tags);

-- Nota: la tabla ways_vertices_pgr será creada por pgr_createTopology en tiempo de ejecución.
-- Ejemplo (no se ejecuta aquí):
-- SELECT pgr_createTopology('rr.ways', 0.0001, 'geom', 'id');
-- ALTER TABLE rr.ways_vertices_pgr ADD COLUMN IF NOT EXISTS geom geometry(Point,4326);
-- UPDATE rr.ways_vertices_pgr SET geom = ST_SetSRID(ST_MakePoint(x, y), 4326);
-- CREATE INDEX IF NOT EXISTS ways_vertices_gix ON rr.ways_vertices_pgr USING GIST (geom);

-- =========================================================
-- 4) Metadata
--    4.1 Anchos de vía (OSM)
--    4.2 Sentido de vía (oneway)
--    4.3 Hidrantes (SISS + OSM fusionables por script)
-- =========================================================

-- 4.1 Metadata widths (un registro por OSM way id)
CREATE TABLE IF NOT EXISTS rr.metadata_widths (
  osm_id        BIGINT PRIMARY KEY,
  highway       TEXT,
  lanes         INTEGER,
  width_raw     TEXT,     -- texto crudo (ej. "7 m", "12 ft")
  maxwidth_raw  TEXT,     -- texto crudo
  width_m       NUMERIC,  -- en metros (parseado/estimado)
  maxwidth_m    NUMERIC,  -- en metros
  geom          geometry(LineString, 4326),
  props         JSONB,
  created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS md_widths_geom_gix ON rr.metadata_widths USING GIST (geom);
CREATE INDEX IF NOT EXISTS md_widths_gin      ON rr.metadata_widths USING GIN (props);

-- 4.2 Metadata oneway
CREATE TABLE IF NOT EXISTS rr.metadata_oneway (
  osm_id   BIGINT PRIMARY KEY,
  oneway   BOOLEAN,
  geom     geometry(LineString, 4326)
);
CREATE INDEX IF NOT EXISTS md_oneway_geom_gix ON rr.metadata_oneway USING GIST (geom);

-- 4.3 Metadata hidrantes
CREATE TABLE IF NOT EXISTS rr.metadata_hydrants (
  ext_id    TEXT PRIMARY KEY,              -- id externo (SISS o compuesto)
  status    TEXT,                          -- "vigente", "no_operativo", etc.
  provider  TEXT,                          -- "SISS", "OSM", etc.
  props     JSONB,                         -- todos los campos crudos normalizados
  geom      geometry(Point, 4326) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS md_hydrants_geom_gix ON rr.metadata_hydrants USING GIST (geom);
CREATE INDEX IF NOT EXISTS md_hydrants_gin      ON rr.metadata_hydrants USING GIN (props);

-- (Opcional) Vista de conteos por estado
-- CREATE VIEW rr.v_hydrants_status_counts AS
-- SELECT status, COUNT(*) AS n FROM rr.metadata_hydrants GROUP BY status;

-- =========================================================
-- 5) Amenazas
--    5.1 Waze (incidentes, cierres, atochamientos)
--    5.2 Traffic calming (lomos de toro, chicanes, etc.)
--    5.3 Clima (celdas OpenWeather con severidad)
-- =========================================================

-- 5.1 Amenazas Waze
CREATE TABLE IF NOT EXISTS rr.amenazas_waze (
  ext_id    TEXT PRIMARY KEY,               -- id único del evento/alerta
  kind      TEXT,                           -- "incident"
  subtype   TEXT,                           -- "CLOSURE", "TRAFFIC_JAM", "IRREGULARITY", etc.
  severity  INTEGER,                        -- 0..N (heurística del loader)
  props     JSONB,                          -- objeto crudo enriquecido
  geom      geometry(Geometry, 4326) NOT NULL, -- Point o LineString
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS am_waze_geom_gix ON rr.amenazas_waze USING GIST (geom);
CREATE INDEX IF NOT EXISTS am_waze_gin      ON rr.amenazas_waze USING GIN (props);

-- 5.2 Amenazas Traffic Calming (OSM)
CREATE TABLE IF NOT EXISTS rr.amenazas_calming (
  ext_id    TEXT PRIMARY KEY,               -- id compuesto (ej. "tc:osm_id")
  kind      TEXT,                           -- "traffic_calming"
  subtype   TEXT,                           -- "bump", "hump", "table", etc.
  severity  INTEGER,                        -- típica = 1
  props     JSONB,
  geom      geometry(Point, 4326) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS am_calming_geom_gix ON rr.amenazas_calming USING GIST (geom);
CREATE INDEX IF NOT EXISTS am_calming_gin      ON rr.amenazas_calming USING GIN (props);

-- 5.3 Amenazas Clima (OpenWeather)
CREATE TABLE IF NOT EXISTS rr.amenazas_clima (
  ext_id    TEXT PRIMARY KEY,               -- ej. "ow:<lat>,<lon>"
  kind      TEXT,                           -- "weather"
  subtype   TEXT,                           -- "RAIN_WIND" u otros
  severity  INTEGER,                        -- 0..N (según umbrales)
  props     JSONB,                          -- incluye metrics: rain_mm_h, wind_ms, ts, etc.
  geom      geometry(Polygon, 4326) NOT NULL, -- celda cubierta
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS am_clima_geom_gix ON rr.amenazas_clima USING GIST (geom);
CREATE INDEX IF NOT EXISTS am_clima_gin      ON rr.amenazas_clima USING GIN (props);
CREATE INDEX IF NOT EXISTS am_waze_geom_gix ON rr.amenazas_waze USING GIST (geom);
CREATE INDEX IF NOT EXISTS am_waze_gin      ON rr.amenazas_waze USING GIN (props);

-- 5.2 Amenazas Traffic Calming (OSM)
CREATE TABLE IF NOT EXISTS rr.amenazas_calming (
  ext_id    TEXT PRIMARY KEY,               -- id compuesto (ej. "tc:osm_id")
  kind      TEXT,                           -- "traffic_calming"
  subtype   TEXT,                           -- "bump", "hump", "table", etc.
  severity  INTEGER,                        -- típica = 1
  props     JSONB,
  geom      geometry(Point, 4326) NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS am_calming_geom_gix ON rr.amenazas_calming USING GIST (geom);
CREATE INDEX IF NOT EXISTS am_calming_gin      ON rr.amenazas_calming USING GIN (props);

-- 5.3 Amenazas Clima (OpenWeather)
CREATE TABLE IF NOT EXISTS rr.amenazas_clima (
  ext_id    TEXT PRIMARY KEY,               -- ej. "ow:<lat>,<lon>"
  kind      TEXT,                           -- "weather"
  subtype   TEXT,                           -- "RAIN_WIND" u otros
  severity  INTEGER,                        -- 0..N (según umbrales)
  props     JSONB,                          -- incluye metrics: rain_mm_h, wind_ms, ts, etc.
  geom      geometry(Polygon, 4326) NOT NULL, -- celda cubierta
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS am_clima_geom_gix ON rr.amenazas_clima USING GIST (geom);
CREATE INDEX IF NOT EXISTS am_clima_gin      ON rr.amenazas_clima USING GIN (props);

-- =========================================================
-- 6) Sugerencias de integridad / utilidades
-- =========================================================

-- (Opcional) Garantizar que rr.ways.length_m esté calculado
-- UPDATE rr.ways
-- SET length_m = ST_LengthSpheroid(geom, 'SPHEROID["WGS 84",6378137,298.257223563]')
-- WHERE length_m IS NULL;

-- (Opcional) Sincronizar oneway desde metadata_oneway cuando se cargue:
-- UPDATE rr.ways w
--    SET oneway = m.oneway
--   FROM rr.metadata_oneway m
--  WHERE w.id = m.osm_id AND m.oneway IS NOT NULL;

-- (Opcional) Aplicar width_m / maxwidth_m desde metadata_widths cuando se cargue:
-- UPDATE rr.ways w
--    SET width_m    = COALESCE(m.width_m, w.width_m),
--        maxwidth_m = COALESCE(m.maxwidth_m, w.maxwidth_m)
--   FROM rr.metadata_widths m
--  WHERE w.osm_id = m.osm_id;

-- =========================================================
-- 7) Notas
--  - Usa pgr_createTopology para construir rr.ways_vertices_pgr (no se crea aquí).
--  - Los índices GIST/GiN están pensados para consultas espaciales y filtros por props/tags.
--  - Las tablas de amenazas usan PK por ext_id para permitir UPSERT con deduplicación previa.
-- =========================================================

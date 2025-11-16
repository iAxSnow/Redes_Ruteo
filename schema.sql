-- ===============================
-- SCHEMA COMPLETO: rr
-- Incluye infraestructura, metadata y amenazas
-- ===============================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;

-- Esquema de trabajo
CREATE SCHEMA IF NOT EXISTS rr;

-- ======================================
-- 1) Infraestructura base (OSM)
-- ======================================

-- Nodos
CREATE TABLE IF NOT EXISTS rr.nodes (
    id BIGINT PRIMARY KEY,
    geom geometry(Point, 4326) NOT NULL
);

-- Aristas (calles)
CREATE TABLE IF NOT EXISTS rr.ways (
    id BIGINT PRIMARY KEY,
    osm_id BIGINT,
    source BIGINT,
    target BIGINT,
    geom geometry(LineString, 4326),
    length_m DOUBLE PRECISION,
    highway TEXT,
    oneway TEXT,                  -- antes era BOOLEAN, ahora TEXT para reflejar 'yes', 'no', '-1', etc.
    maxspeed_kmh INTEGER,
    lanes INTEGER,
    surface TEXT,
    access TEXT,
    width_m NUMERIC,              -- ancho real de la vía (estimado o reportado)
    maxwidth_m NUMERIC,           -- restricción máxima de paso (vehículos grandes)
    tags JSONB
);

CREATE INDEX IF NOT EXISTS idx_nodes_geom ON rr.nodes USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_ways_geom ON rr.ways USING GIST (geom);

-- ======================================
-- 2) Metadata
-- ======================================

-- Ancho de vías (valores originales de OSM u otras fuentes)
CREATE TABLE IF NOT EXISTS rr.metadata_widths (
    osm_id BIGINT PRIMARY KEY,
    width_m NUMERIC,
    maxwidth_m NUMERIC,
    source TEXT,
    tags JSONB
);

-- Oneway (para reflejar directamente los valores de OSM)
CREATE TABLE IF NOT EXISTS rr.metadata_oneway (
    osm_id BIGINT PRIMARY KEY,
    oneway TEXT,
    source TEXT,
    tags JSONB
);

-- Hidrantes (de OSM o SISS)
CREATE TABLE IF NOT EXISTS rr.metadata_hydrants (
    id SERIAL PRIMARY KEY,
    ext_id TEXT,
    geom geometry(Point, 4326),
    estado TEXT,          -- vigente, fuera de servicio, desconocido, etc.
    fuente TEXT,
    tags JSONB
);

-- Inspecciones de SISS
CREATE TABLE IF NOT EXISTS rr.metadata_hydrants_siss (
    id SERIAL PRIMARY KEY,
    ext_id TEXT,
    geom geometry(Point, 4326),
    estado_uso TEXT,
    fecha_vigencia DATE,
    observaciones TEXT,
    fuente TEXT DEFAULT 'SISS',
    raw JSONB
);

-- ======================================
-- 3) Amenazas
-- ======================================

-- Reductores de velocidad (lomos de toro, badenes)
CREATE TABLE IF NOT EXISTS rr.amenazas_calming (
    id SERIAL PRIMARY KEY,
    geom geometry(Point, 4326),
    tipo TEXT,
    severidad INTEGER,          -- intensidad del elemento (ej: altura del lomo)
    impacto_critico INTEGER,    -- qué tanto afecta a la misión de bomberos
    fuente TEXT,
    tags JSONB
);

-- Incidentes de tráfico (Waze u otra fuente)
CREATE TABLE IF NOT EXISTS rr.amenazas_waze (
    id SERIAL PRIMARY KEY,
    ext_id TEXT,
    geom geometry(Point, 4326),
    tipo TEXT,
    severidad INTEGER,          -- gravedad reportada por la API
    impacto_critico INTEGER,    -- qué tanto impacta a la misión
    fuente TEXT,
    raw JSONB
);

-- Clima adverso (OpenWeather u otra fuente)
CREATE TABLE IF NOT EXISTS rr.amenazas_weather (
    id SERIAL PRIMARY KEY,
    geom geometry(Point, 4326),
    evento TEXT,                -- lluvia, viento, tormenta, etc.
    severidad INTEGER,          -- intensidad (mm/h de lluvia, m/s de viento, etc.)
    impacto_critico INTEGER,    -- impacto sobre movilidad
    fuente TEXT,
    raw JSONB
);

-- ======================================
-- 4) Vistas útiles
-- ======================================

-- Vista para ruteo con pgRouting, interpretando oneway
CREATE OR REPLACE VIEW rr.ways_routing AS
SELECT
    id,
    source,
    target,
    length_m AS cost,
    CASE
        WHEN oneway = 'yes'  THEN -1    -- prohibido el sentido contrario
        WHEN oneway = '-1'   THEN length_m
        ELSE length_m
    END AS reverse_cost,
    geom
FROM rr.ways;

-- 1. Añade la columna para la probabilidad de falla (Req #4)
-- La calcularemos como un valor normalizado (0.0 a 1.0)
ALTER TABLE rr.ways
ADD COLUMN IF NOT EXISTS prob_falla FLOAT DEFAULT 0.0;

-- 2. Añade la columna para la penalización por costo de amenaza
-- Aquí guardaremos el 'costo' extra de una amenaza
ALTER TABLE rr.ways
ADD COLUMN IF NOT EXISTS costo_amenaza FLOAT DEFAULT 0.0;

-- 3. Añade la columna para el costo final ponderado (Req #5c)
-- Este será: (costo_distancia * W1) + (costo_amenaza * W2)
ALTER TABLE rr.ways
ADD COLUMN IF NOT EXISTS costo_combinado FLOAT;
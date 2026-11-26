-- Schema for the BC Soil Background Metals Analyzer.
-- Geometry is stored in BC Albers (EPSG:3005) so distances and buffers are in metres.
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS samples (
    sample_uid              text PRIMARY KEY,
    source_id               text NOT NULL,
    source_type             text NOT NULL CHECK (source_type IN ('site_report', 'regional_survey', 'assessment_report')),
    sample_id               text NOT NULL,
    location_id             text,
    site_name               text,
    location_method         text NOT NULL,
    location_uncertainty_m  double precision,
    sample_media            text NOT NULL,          -- 'soil' or 'moss-mat sediment': never mixed in statistics
    media_detail            text,
    fill_or_native          text,
    horizon                 text,
    depth_top_m             double precision,
    depth_bottom_m          double precision,
    sample_date             date,
    is_duplicate            boolean NOT NULL,
    duplicate_of            text REFERENCES samples (sample_uid) DEFERRABLE INITIALLY DEFERRED,
    size_fraction           text,
    dq_flags                text,
    geom                    geometry(Point, 3005) NOT NULL
);
CREATE INDEX IF NOT EXISTS samples_geom_idx ON samples USING gist (geom);

CREATE TABLE IF NOT EXISTS results (
    result_id        bigserial PRIMARY KEY,
    sample_uid       text NOT NULL REFERENCES samples (sample_uid),
    analyte          text NOT NULL,
    analyte_kind     text NOT NULL,
    value            double precision,               -- mg/kg dry weight; NULL when non-detect
    unit             text NOT NULL,
    non_detect       boolean NOT NULL,
    detection_limit  double precision,               -- mg/kg; set when non_detect
    unit_raw         text,
    value_raw        text,
    method           text,
    source_page      integer,
    unit_converted   boolean NOT NULL,
    dq_flags         text,
    UNIQUE (sample_uid, analyte),
    CHECK (non_detect = (value IS NULL)),
    CHECK (NOT non_detect OR detection_limit IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS results_analyte_idx ON results (analyte);

-- Filled in Sprint 3.
CREATE TABLE IF NOT EXISTS activities (
    activity_id    bigserial PRIMARY KEY,
    source         text NOT NULL,
    activity_type  text NOT NULL,
    name           text,
    source_ref     text,
    geom           geometry(Geometry, 3005) NOT NULL
);
CREATE INDEX IF NOT EXISTS activities_geom_idx ON activities USING gist (geom);

CREATE TABLE IF NOT EXISTS screening (
    sample_uid  text PRIMARY KEY REFERENCES samples (sample_uid),
    decision    text NOT NULL CHECK (decision IN ('include', 'exclude')),
    reasons     text
);

CREATE TABLE IF NOT EXISTS background_estimates (
    analyte        text NOT NULL,
    region         text NOT NULL,
    sample_media   text NOT NULL,
    nd_method      text NOT NULL,
    n              integer NOT NULL,
    pct_non_detect double precision,
    median         double precision,
    p95            double precision,
    p95_ci_low     double precision,
    p95_ci_high    double precision,
    notes          text,
    PRIMARY KEY (analyte, region, sample_media, nd_method)
);

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tipo_documento (
    id_tipo_documento BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);
INSERT INTO tipo_documento (nombre)
VALUES ('REGLAMENTO'), ('PROCEDIMIENTO'), ('SILABO'), ('GUIA'), ('OTRO')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS documento (
    id_documento BIGSERIAL PRIMARY KEY,
    clave VARCHAR(255) NOT NULL UNIQUE,
    id_tipo_documento BIGINT NOT NULL REFERENCES tipo_documento,
    titulo VARCHAR(255) NOT NULL,
    nombre_archivo VARCHAR(255) NOT NULL,
    ruta_archivo TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    total_paginas INTEGER NOT NULL,
    paginas_sin_texto JSONB NOT NULL DEFAULT '[]',
    modelo_embedding VARCHAR(150) NOT NULL,
    dimension_embedding INTEGER NOT NULL CHECK (dimension_embedding = 1024),
    chunk_size_chars INTEGER NOT NULL,
    chunk_overlap_chars INTEGER NOT NULL,
    estado VARCHAR(20) NOT NULL CHECK (estado = 'INDEXADO'),
    vigente BOOLEAN NOT NULL DEFAULT TRUE,
    fecha_carga TIMESTAMPTZ NOT NULL DEFAULT now(),
    fecha_actualizacion TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fragmento (
    id_fragmento BIGSERIAL PRIMARY KEY,
    id_documento BIGINT NOT NULL REFERENCES documento ON DELETE CASCADE,
    contenido TEXT NOT NULL CHECK (length(contenido) > 0),
    posicion INTEGER NOT NULL CHECK (posicion >= 0),
    pagina_inicio INTEGER NOT NULL CHECK (pagina_inicio >= 1),
    pagina_fin INTEGER NOT NULL CHECK (pagina_fin >= pagina_inicio),
    embedding VECTOR(1024) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    fecha_creacion TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id_documento, posicion)
);

CREATE TABLE IF NOT EXISTS proceso_indexacion (
    id_proceso BIGSERIAL PRIMARY KEY,
    id_documento BIGINT NOT NULL REFERENCES documento ON DELETE CASCADE,
    estado VARCHAR(20) NOT NULL CHECK (estado = 'COMPLETADO'),
    fecha_inicio TIMESTAMPTZ NOT NULL,
    fecha_fin TIMESTAMPTZ NOT NULL DEFAULT now(),
    total_fragmentos INTEGER NOT NULL,
    modelo_embedding VARCHAR(150) NOT NULL,
    dimension_embedding INTEGER NOT NULL CHECK (dimension_embedding = 1024)
);

INSERT INTO schema_version (version) VALUES (1) ON CONFLICT DO NOTHING;

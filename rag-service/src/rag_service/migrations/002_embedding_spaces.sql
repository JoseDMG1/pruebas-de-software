-- Mantener los vectores anteriores y separar cada proveedor/modelo/revision/dimension.
CREATE TABLE espacio_embedding (
    id_espacio BIGSERIAL PRIMARY KEY,
    proveedor VARCHAR(20) NOT NULL CHECK (proveedor IN ('bedrock', 'ollama')),
    modelo TEXT NOT NULL,
    revision TEXT NOT NULL,
    dimensiones INTEGER NOT NULL CHECK (dimensiones BETWEEN 1 AND 16000),
    UNIQUE (proveedor, modelo, revision, dimensiones),
    UNIQUE (id_espacio, dimensiones)
);
CREATE TABLE fragmento_embedding (
    id_fragmento BIGINT NOT NULL REFERENCES fragmento ON DELETE CASCADE,
    id_espacio BIGINT NOT NULL,
    dimensiones INTEGER NOT NULL,
    embedding VECTOR NOT NULL CHECK (vector_dims(embedding) = dimensiones),
    PRIMARY KEY (id_fragmento, id_espacio),
    FOREIGN KEY (id_espacio, dimensiones) REFERENCES espacio_embedding (id_espacio, dimensiones)
);
ALTER TABLE documento ADD COLUMN proveedor_embedding VARCHAR(20) NOT NULL DEFAULT 'bedrock'
    CHECK (proveedor_embedding IN ('bedrock', 'ollama'));
ALTER TABLE documento ADD COLUMN revision_embedding TEXT NOT NULL DEFAULT '';
ALTER TABLE documento ALTER COLUMN modelo_embedding TYPE TEXT;
ALTER TABLE documento DROP CONSTRAINT documento_dimension_embedding_check;
ALTER TABLE documento ADD CHECK (dimension_embedding BETWEEN 1 AND 16000);
ALTER TABLE proceso_indexacion ADD COLUMN proveedor_embedding VARCHAR(20) NOT NULL DEFAULT 'bedrock'
    CHECK (proveedor_embedding IN ('bedrock', 'ollama'));
ALTER TABLE proceso_indexacion ADD COLUMN revision_embedding TEXT NOT NULL DEFAULT '';
ALTER TABLE proceso_indexacion ALTER COLUMN modelo_embedding TYPE TEXT;
ALTER TABLE proceso_indexacion DROP CONSTRAINT proceso_indexacion_dimension_embedding_check;
ALTER TABLE proceso_indexacion ADD CHECK (dimension_embedding BETWEEN 1 AND 16000);
ALTER TABLE fragmento ALTER COLUMN embedding DROP NOT NULL;

INSERT INTO espacio_embedding (proveedor, modelo, revision, dimensiones)
SELECT DISTINCT 'bedrock', modelo_embedding, '', dimension_embedding FROM documento;
INSERT INTO fragmento_embedding (id_fragmento, id_espacio, dimensiones, embedding)
SELECT f.id_fragmento, e.id_espacio, e.dimensiones, f.embedding
FROM fragmento f JOIN documento d USING (id_documento)
JOIN espacio_embedding e ON e.proveedor = 'bedrock' AND e.modelo = d.modelo_embedding
    AND e.revision = '' AND e.dimensiones = d.dimension_embedding;
INSERT INTO schema_version (version) VALUES (2);

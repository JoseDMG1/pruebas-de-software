-- Gemini vectors use 768 dimensions; the old inline vector column was fixed at 1024.
ALTER TABLE fragmento ALTER COLUMN embedding TYPE VECTOR USING embedding::VECTOR;

ALTER TABLE espacio_embedding DROP CONSTRAINT espacio_embedding_proveedor_check;
ALTER TABLE espacio_embedding ADD CHECK (proveedor IN ('bedrock', 'ollama', 'gemini'));
ALTER TABLE documento DROP CONSTRAINT documento_proveedor_embedding_check;
ALTER TABLE documento ADD CHECK (proveedor_embedding IN ('bedrock', 'ollama', 'gemini'));
ALTER TABLE proceso_indexacion DROP CONSTRAINT proceso_indexacion_proveedor_embedding_check;
ALTER TABLE proceso_indexacion ADD CHECK (proveedor_embedding IN ('bedrock', 'ollama', 'gemini'));

INSERT INTO schema_version (version) VALUES (4);

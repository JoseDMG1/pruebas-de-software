-- Existing documents remain unclassified and are excluded from retrieval until reingested.
ALTER TABLE documento ADD COLUMN alcance VARCHAR(20)
    CHECK (alcance IN ('institutional', 'course'));

CREATE TABLE curso_moodle (
    course_id BIGINT PRIMARY KEY CHECK (course_id > 0),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE documento_curso (
    id_documento BIGINT NOT NULL REFERENCES documento ON DELETE CASCADE,
    course_id BIGINT NOT NULL REFERENCES curso_moodle,
    PRIMARY KEY (id_documento, course_id)
);
CREATE INDEX documento_curso_course_id_idx ON documento_curso (course_id, id_documento);

INSERT INTO schema_version (version) VALUES (3);

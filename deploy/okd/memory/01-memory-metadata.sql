-- Schema mémoire SophIA (template anonymisé)
-- ${SOPHIA_DB_NAME:-sophia_db} est la base de données cible

CREATE SCHEMA IF NOT EXISTS sophia;

CREATE TABLE sophia.memory_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    qdrant_point_id UUID,
    username VARCHAR(50) NOT NULL,
    type_memory VARCHAR(50) NOT NULL,
    project VARCHAR(100),
    topic VARCHAR(100),
    confidentiality VARCHAR(20) NOT NULL DEFAULT 'famille',
    provenance VARCHAR(50) NOT NULL,
    format VARCHAR(20) NOT NULL,
    confidence FLOAT DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    validated_at TIMESTAMPTZ,
    validated_by VARCHAR(50),
    source TEXT,
    keywords TEXT[],
    version INT DEFAULT 1,
    expires_at TIMESTAMPTZ,
    priority VARCHAR(20) DEFAULT 'normale',
    arbitration_status VARCHAR(20) DEFAULT 'valide',
    source_ref TEXT,
    chunk_text TEXT,
    metadata JSONB
);

CREATE INDEX idx_memory_username ON sophia.memory_metadata(username);
CREATE INDEX idx_memory_type ON sophia.memory_metadata(type_memory);
CREATE INDEX idx_memory_confidence ON sophia.memory_metadata(confidence);
CREATE INDEX idx_memory_created ON sophia.memory_metadata(created_at);
CREATE INDEX idx_memory_project ON sophia.memory_metadata(project);
CREATE INDEX idx_memory_source ON sophia.memory_metadata(source);
CREATE INDEX idx_memory_fts ON sophia.memory_metadata USING GIN(to_tsvector('french', coalesce(chunk_text, '')));

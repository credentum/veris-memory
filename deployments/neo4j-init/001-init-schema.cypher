// Veris Memory - Neo4j Schema Initialization
// This script creates the core schema for the context graph database
// Auto-executed on Neo4j container first start via Docker volume mount

// ============================================================================
// CONSTRAINTS - Ensure data integrity
// ============================================================================

// Context nodes - primary entity for all stored contexts
CREATE CONSTRAINT context_id_unique IF NOT EXISTS
FOR (c:Context) REQUIRE c.id IS UNIQUE;

// Document nodes
CREATE CONSTRAINT document_id_unique IF NOT EXISTS
FOR (d:Document) REQUIRE d.id IS UNIQUE;

// Sprint nodes
CREATE CONSTRAINT sprint_id_unique IF NOT EXISTS
FOR (s:Sprint) REQUIRE s.id IS UNIQUE;

// Task nodes
CREATE CONSTRAINT task_id_unique IF NOT EXISTS
FOR (t:Task) REQUIRE t.id IS UNIQUE;

// User nodes
CREATE CONSTRAINT user_id_unique IF NOT EXISTS
FOR (u:User) REQUIRE u.id IS UNIQUE;

// ============================================================================
// INDEXES - Optimize query performance
// ============================================================================

// Context indexes for common queries
CREATE INDEX context_type_idx IF NOT EXISTS
FOR (c:Context) ON (c.type);

CREATE INDEX context_created_at_idx IF NOT EXISTS
FOR (c:Context) ON (c.created_at);

CREATE INDEX context_author_idx IF NOT EXISTS
FOR (c:Context) ON (c.author);

CREATE INDEX context_author_type_idx IF NOT EXISTS
FOR (c:Context) ON (c.author_type);

// PR #340: Index for searchable_text field (custom property search)
CREATE INDEX context_searchable_text_idx IF NOT EXISTS
FOR (c:Context) ON (c.searchable_text);

// Document indexes
CREATE INDEX document_type_idx IF NOT EXISTS
FOR (d:Document) ON (d.document_type);

CREATE INDEX document_created_date_idx IF NOT EXISTS
FOR (d:Document) ON (d.created_date);

CREATE INDEX document_status_idx IF NOT EXISTS
FOR (d:Document) ON (d.status);

CREATE INDEX document_modified_idx IF NOT EXISTS
FOR (d:Document) ON (d.last_modified);

// Sprint indexes
CREATE INDEX sprint_number_status_idx IF NOT EXISTS
FOR (s:Sprint) ON (s.sprint_number, s.status);

// Task indexes
CREATE INDEX task_status_assigned_idx IF NOT EXISTS
FOR (t:Task) ON (t.status, t.assigned_to);

// ============================================================================
// VERIFICATION QUERIES - Confirm schema is initialized
// ============================================================================

// Return schema summary
CALL db.constraints() YIELD name
RETURN count(name) as constraint_count;

CALL db.indexes() YIELD name
RETURN count(name) as index_count;

// Schema initialized successfully
RETURN "Schema initialized successfully" as status;

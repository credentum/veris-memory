# Neo4j Schema Initialization

This directory contains the Neo4j database schema initialization scripts for Veris Memory.

## Overview

The schema initialization ensures that Neo4j has the required constraints and indexes before the application starts using it. This prevents errors like "missing label: Context" that occur when queries are run against an uninitialized database.

## Files

- `001-init-schema.cypher` - Core schema definition with constraints and indexes

## Script Execution Order

**IMPORTANT**: Neo4j executes initialization scripts in **alphabetical order**.

### Naming Convention

All schema initialization scripts must follow this naming pattern:
```
NNN-description.cypher
```

Where:
- `NNN` is a zero-padded number (001, 002, 003, etc.)
- `description` is a brief description of what the script does

### Current Scripts

1. **001-init-schema.cypher** - Creates base constraints and indexes for Context, Document, Sprint, Task, and User labels

### Adding New Schema Scripts

When adding new schema initialization scripts:

1. **Use the next sequential number** (e.g., `002-add-indexes.cypher`)
2. **Make scripts idempotent** using `IF NOT EXISTS` clauses
3. **Document what the script does** in this README
4. **Test locally first** before deploying to production

Example:
```cypher
// 002-add-project-label.cypher
// Adds Project label with constraints and indexes

CREATE CONSTRAINT project_id_unique IF NOT EXISTS
FOR (p:Project) REQUIRE p.id IS UNIQUE;

CREATE INDEX project_status_idx IF NOT EXISTS
FOR (p:Project) ON (p.status);
```

### Why Numbered Prefixes?

- **Deterministic execution order** - Scripts run in a predictable sequence
- **Schema migrations** - New constraints/indexes can be added without breaking existing setup
- **Version control** - Easy to see when and in what order schema changes were made
- **Rollback safety** - Can track which scripts have been applied

### Execution Context

Scripts in this directory are executed:
1. **On first container start** - Neo4j automatically runs all scripts in `/docker-entrypoint-initdb.d/`
2. **On deployment** - `scripts/init-neo4j-schema.sh` explicitly executes them
3. **Idempotently** - Safe to run multiple times (uses `IF NOT EXISTS`)

## How It Works

### Automatic Initialization

The schema is automatically initialized during deployment via two mechanisms:

1. **Docker Compose Mount** - The `deployments/neo4j-init/` directory is mounted to the Neo4j container
2. **Deployment Script** - `scripts/deploy-dev.sh` explicitly runs schema initialization after containers start

### Manual Initialization

If you need to manually initialize the schema:

```bash
# Run the initialization script
./scripts/init-neo4j-schema.sh

# Or manually via Docker
docker exec veris-memory-dev-neo4j-1 \
  cypher-shell -u neo4j -p $NEO4J_PASSWORD \
  -f /docker-entrypoint-initdb.d/001-init-schema.cypher
```

## Schema Components

### Constraints

Constraints ensure data integrity by enforcing uniqueness:

- `Context.id` - Primary identifier for all context nodes
- `Document.id` - Unique document identifier
- `Sprint.id` - Sprint identifier
- `Task.id` - Task identifier
- `User.id` - User identifier

### Indexes

Indexes optimize query performance:

- `Context` - type, created_at, author, author_type
- `Document` - document_type, created_date, status, last_modified
- `Sprint` - sprint_number + status (compound)
- `Task` - status + assigned_to (compound)

## Troubleshooting

### "Missing label: Context" Error

This error occurs when queries reference the `Context` label but it doesn't exist in the database catalog.

**Cause:** Schema was not initialized before queries were executed.

**Solution:**
```bash
# Re-run schema initialization
./scripts/init-neo4j-schema.sh

# Verify Context label exists
docker exec veris-memory-dev-neo4j-1 \
  cypher-shell -u neo4j -p $NEO4J_PASSWORD \
  "CALL db.labels()" | grep Context
```

### Checking Schema Status

```bash
# List all constraints
docker exec veris-memory-dev-neo4j-1 \
  cypher-shell -u neo4j -p $NEO4J_PASSWORD \
  "CALL db.constraints()"

# List all indexes
docker exec veris-memory-dev-neo4j-1 \
  cypher-shell -u neo4j -p $NEO4J_PASSWORD \
  "CALL db.indexes()"

# Count Context nodes
docker exec veris-memory-dev-neo4j-1 \
  cypher-shell -u neo4j -p $NEO4J_PASSWORD \
  "MATCH (c:Context) RETURN count(c) as context_count"
```

## Adding New Schema Elements

To add new constraints or indexes:

1. Edit `001-init-schema.cypher`
2. Add the new Cypher statements following the existing pattern
3. Re-run schema initialization (safe to run multiple times - uses `IF NOT EXISTS`)
4. Verify the changes:
   ```bash
   docker exec veris-memory-dev-neo4j-1 \
     cypher-shell -u neo4j -p $NEO4J_PASSWORD \
     "CALL db.schema.visualization()"
   ```

## Production Considerations

- Schema initialization is idempotent (safe to run multiple times)
- Constraints cannot be created if conflicting data exists
- Indexes are created asynchronously in the background
- Always test schema changes in dev before applying to production

## Related Issues

This initialization script resolves:
- Error: "The provided label is not in the database (missing label: Context)"
- 29.3% error rate from failed context storage operations
- Sentinel check failures (S2, S9, S10)
- 20+ storage failures per 31-second check cycle

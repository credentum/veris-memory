# Context Directory Structure

This directory contains the context integrity requirements, MCP contracts, and schema definitions for the context-store system.

## Structure

```
context/
├── configs/          # Configuration files for context integrity
│   └── context_integrity.yaml
├── mcp_contracts/    # MCP tool contract JSON schemas
│   ├── store_context_tool.json
│   ├── retrieve_context_tool.json
│   └── query_graph_tool.json
├── schemas/          # YAML schemas for data validation
│   ├── context_item.yaml
│   └── mcp_response.yaml
└── README.md         # This file
```

## Purpose

### Context Integrity (`configs/`)

- **context_integrity.yaml**: Defines validation rules, integrity checks, performance limits, and cleanup policies to maintain data quality and system reliability.

### MCP Contracts (`mcp_contracts/`)

- **store_context_tool.json**: Contract for storing contextual information with metadata and relationships
- **retrieve_context_tool.json**: Contract for semantic search and retrieval of context items
- **query_graph_tool.json**: Contract for graph-based queries using Cypher-like syntax

### Schemas (`schemas/`)

- **context_item.yaml**: Complete schema definition for context items including content, metadata, relationships, and storage information
- **mcp_response.yaml**: Standard response format for all MCP tool operations

## Features

### Security & Compliance

- ✅ **Rate Limiting**: Per-tool rate limits with burst protection
- ✅ **Input Validation**: Comprehensive schema validation for all inputs
- ✅ **Query Security**: Cypher query validation with forbidden operations
- ✅ **Content Sanitization**: HTML sanitization and encoding validation

### Data Integrity

- ✅ **Referential Integrity**: Relationship target validation
- ✅ **Duplicate Detection**: Content similarity and hash-based detection
- ✅ **Version Control**: Change tracking with history retention
- ✅ **Checksums**: SHA256 content verification

### Performance

- ✅ **Caching**: Configurable TTL and eviction policies
- ✅ **Query Limits**: Timeout and complexity constraints
- ✅ **Monitoring**: Metrics collection and alerting

### Relationship Management

- ✅ **Rich Relationships**: 9 relationship types with strength scoring
- ✅ **Circular Dependency Prevention**: Graph validation
- ✅ **Orphaned Cleanup**: Automatic cleanup of broken references

## Usage

These files define the contract and integrity requirements for:

1. **MCP Tool Development**: Use the JSON contracts to implement compliant MCP tools
2. **Data Validation**: Use YAML schemas for input/output validation
3. **System Configuration**: Use integrity config for system behavior tuning
4. **Testing**: Use schemas and contracts for comprehensive test coverage

## Compliance

This structure ensures:

- **MCP Compatibility**: Standard JSON schema contracts
- **Context Integrity**: Comprehensive validation and cleanup rules
- **Security**: Rate limiting, validation, and sanitization
- **Maintainability**: Clear schema definitions and documentation

## Integration

The context-store system uses these definitions to:

- Validate all incoming data against schemas
- Enforce integrity rules during operations
- Provide consistent MCP tool interfaces
- Monitor and alert on violations
- Maintain data quality over time

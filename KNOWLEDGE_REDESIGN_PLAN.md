# Generic Knowledge Management System - Implementation Plan

## Overview

Complete redesign of the knowledge management system to be truly generic, following research findings from `deep_research.txt`. Moving away from hard-coded domain concepts (people, projects) to a flexible entity-based system.

## Core Architecture

### 1. Generic Entity Model
```yaml
# Example entity file: entities/{uuid}.yaml
id: "550e8400-e29b-41d4-a716-446655440000"
type: "person"  # or "project", "attic_item", "idea", etc.
properties:
  name: "Alice"
  email: "alice@example.com"
  role: "researcher"
  group_id: "550e8400-e29b-41d4-a716-446655440001"  # Link to another entity
tags: ["contact", "research_group", "active"]
content: "Alice is a PhD student working on AI knowledge management systems. She specializes in NLP and has published several papers on semantic search."
created_at: "2024-01-15T10:30:00Z"
updated_at: "2024-01-15T10:30:00Z"
```

### 2. Storage Architecture
- **Format**: YAML (human-readable, git-friendly, supports comments)
- **Pattern**: One file per entity (`entities/{uuid}.yaml`)
- **Organization**: 
  ```
  ~/.mcp_handley_lab/knowledge/entities/  # Global entities
  ./.mcp_handley_lab/knowledge/entities/  # Local entities
  ```
- **Relationships**: Explicit UUID linking (no foreign key constraints)

### 3. Query Architecture
- **Primary**: Natural language via AI (ChromaDB semantic search)
- **Structured**: JSONPath/JMESPath for programmatic queries
- **CLI**: yq/jq integration for direct file manipulation
- **In-Memory**: TinyDB for fast structured queries

## Implementation Phases

### Phase 1: Core Entity System ✅
- [x] Generic Entity model (id, type, properties, tags, content)
- [ ] YAML-based file storage manager
- [ ] UUID-based entity linking
- [ ] Basic CRUD operations

### Phase 2: Storage & Query Engine
- [ ] Replace manager.py with YAML file-per-entity approach
- [ ] TinyDB integration for in-memory querying
- [ ] Support for global/local entity scopes
- [ ] Entity relationship traversal

### Phase 3: Generic MCP Interface
- [ ] Replace domain-specific tools with generic operations:
  - `create_entity(type, properties, tags, content, scope)`
  - `get_entity(id)`
  - `query_entities(filters, tags)`
  - `search_entities(text_query)`
- [ ] Generic resources for entity browsing
- [ ] Remove all academic-specific functions

### Phase 4: AI Integration
- [ ] ChromaDB integration for semantic search
- [ ] Embedding generation for entity content
- [ ] Natural language query interface
- [ ] yq/jq CLI tool integration

### Phase 5: Testing & Documentation
- [ ] Comprehensive test suite for generic system
- [ ] Migration guide from old system
- [ ] Usage examples for different data types

## Key Benefits

1. **True Genericity**: Handle any data type (people, projects, attic items, ideas)
2. **Battle-Tested Storage**: YAML + Git for version control
3. **Multiple Access Patterns**: AI, CLI, programmatic
4. **Lightweight**: No database server, just files
5. **Extensible**: Easy to add new entity types and properties

## Example Use Cases

### Research Group Member
```yaml
id: "uuid-alice"
type: "person"
properties:
  name: "Alice Smith"
  email: "alice@university.edu"
  role: "PhD Student"
  advisor_id: "uuid-prof-jones"
  start_date: "2022-09-01"
tags: ["research_group", "active", "nlp"]
content: "PhD student working on knowledge management systems..."
```

### Attic Inventory Item
```yaml
id: "uuid-old-lamp"
type: "attic_item"
properties:
  name: "Grandmother's Reading Lamp"
  condition: "Good, needs rewiring"
  location: "Blue Box #3, Top Shelf"
  estimated_value: 150
  photo_path: "photos/lamp_001.jpg"
tags: ["heirloom", "fragile", "needs_repair"]
content: "Beautiful brass reading lamp from the 1940s. Sentimental value..."
```

### Project Idea
```yaml
id: "uuid-ai-kms-idea"
type: "project_idea"
properties:
  title: "AI-Powered Knowledge Management"
  status: "draft"
  priority: "high"
  complexity: "medium"
  estimated_duration: "6 months"
  related_papers: ["paper_uuid_1", "paper_uuid_2"]
tags: ["ai", "knowledge_management", "high_priority"]
content: "Develop a lightweight, file-based knowledge management system..."
```

## Migration Strategy

This is a complete rewrite. The new system is fundamentally incompatible with the current domain-specific approach. Benefits:

1. **Clean foundation**: No legacy constraints
2. **Proven patterns**: Based on research of successful systems
3. **Future-proof**: Easy to extend without breaking changes
4. **Better AI integration**: Designed for semantic search from the ground up

## Next Steps

1. Implement core Entity model and YAML storage
2. Create generic KnowledgeManager 
3. Build MCP interface with generic tools
4. Add AI integration (ChromaDB)
5. Comprehensive testing

## Library Stack

Based on research and best practices:

### Core Libraries
- **YAML Processing**: `ruamel.yaml` (preserves comments/formatting vs PyYAML)
- **Query Engine**: `TinyDB` with `MemoryStorage` (fast in-memory queries)
- **Structured Queries**: `jmespath` (clean syntax vs jsonpath-ng)
- **Semantic Search**: `ChromaDB` (full solution vs FAISS library)
- **File Monitoring**: `watchdog` (cross-platform file system events)

### Additional Libraries
- **CLI Integration**: `pyjq` (native binding vs subprocess overhead)
- **Validation**: `Pydantic` (optional validation for known entity types)
- **Testing**: `pytest` + `pyfakefs` (fake filesystem for testing)

### Development Dependencies
```python
# Core runtime
ruamel.yaml>=0.17.0
tinydb>=4.8.0
jmespath>=1.0.0
chromadb>=0.4.0
watchdog>=3.0.0
pyjq>=2.6.0
pydantic>=2.0.0

# Development/testing
pytest>=7.0.0
pyfakefs>=5.0.0
```

## References

- `deep_research.txt`: Comprehensive analysis of KMS patterns
- Obsidian: File-based linking patterns
- Kubernetes: YAML configuration management
- Research findings on optimal storage for 1000+ entities with Git

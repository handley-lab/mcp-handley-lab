# Unified Knowledge Management System

## Core Philosophy

Most file formats (PDFs, Word docs, images, videos) are essentially "dumb containers" - they hold content but lack useful organizational metadata. A PDF doesn't know what project it belongs to, who created it, or how it relates to other documents.

**Solution: Treat a lightweight YAML file as the "real" file in our system, while storing the true file content in a flat, managed library.**

This is like a library catalog system:
- **YAML file** = The catalog card (with title, author, subject, related works)
- **Content file** = The actual book on the shelf
- **Users interact with catalog cards** (YAML files) to find, organize, and link
- **The physical books** (content files) are stored efficiently in a warehouse

## What is a "Note"?

In this unified system, a **note** is a YAML entity that represents any piece of knowledge, whether that knowledge is:

1. **Pure thoughts/text** (traditional notes)
2. **Structured data** (contacts, projects, tasks)  
3. **File proxies** (representing external content)

**Everything is a note.** The distinction isn't "notes vs files" but rather:
- **Self-contained knowledge** (content lives in the YAML)
- **Referenced knowledge** (content lives elsewhere, YAML is the pointer/metadata)

## Three Types of Notes

### Type 1: Content Notes
Traditional notes where the knowledge lives directly in the YAML content.

```yaml
# person/david-yallop.yaml
id: "uuid-123"
title: "David Yallop"
content: "Investigative journalist, wrote about Vatican corruption"
properties:
  occupation: "journalist"
  books: ["In God's Name", "The Power and the Glory"]
tags: ["journalist", "author", "investigative"]
```

### Type 2: File Registry Notes
Notes that serve as proxies for external files, providing rich metadata that the files themselves lack.

```yaml
# document/competitor-analysis.yaml
id: "uuid-456"
title: "Q3 Competitor Analysis"
content: "Analysis of competitor X's product launch strategy"
properties:
  file_content_path: "_assets/sha256-abc123...pdf"
  content_hash: "sha256-abc123..."
  original_filename: "Competitor Analysis Q3.pdf"
  mime_type: "application/pdf"
  size_bytes: 1234567
  upload_date: "2023-10-27T10:00:00Z"
tags: ["research", "competitive", "q3-2023"]
```

### Type 3: Hybrid Notes
Notes that combine their own content with references to other notes and files.

```yaml
# project/alpha-launch.yaml
id: "uuid-789"
title: "Project Alpha Launch"
content: "Launch strategy and timeline for Project Alpha"
properties:
  status: "in-progress"
  deadline: "2024-01-15"
  referenced_files: ["uuid-456"]  # Forward links only
  team_members: ["uuid-123"]      # Forward links only
tags: ["project", "launch", "alpha"]
```

## File Management Architecture

### Single File Storage + Multiple References
- Each unique file is stored once in the managed `_assets/` directory
- Files are content-addressed: `_assets/sha256-2cf24dba...pdf`
- Multiple notes can reference the same file via its UUID
- No duplication, single source of truth for file content

### UUID + Slug Addressing
Files follow the same pattern as regular notes:
- **UUID access**: `file-uuid-abc-789`
- **Type/Slug access**: `document/competitor-analysis-q3`

### Directory Structure
```
knowledge-system/
├── inbox/                    # Unprocessed items (GTD capture)
│   ├── random-thought.yaml
│   └── uploaded-file.yaml
├── person/
│   ├── david-yallop.yaml
│   └── sarah-designer.yaml
├── document/
│   ├── competitor-analysis-q3.yaml
│   └── brand-guidelines.yaml
├── project/
│   └── alpha-launch.yaml
├── someday/                  # Someday/maybe projects
│   └── learn-spanish.yaml
├── repository/               # Remote GitHub repositories
│   ├── mcp-framework.yaml
│   └── website-redesign.yaml
├── _assets/
│   ├── sha256-2cf24dba...pdf
│   └── sha256-9f86d081...jpg
└── .mcp_handley_lab/
    └── file_index.json  # Optional performance index
```

## Working vs Reference Systems

### Working System (Traditional Filesystem)
- LaTeX projects with `.tex`, `.bib`, `.cls` files that need to be together
- Code repositories with specific directory structure  
- Active collaboration where others expect normal file organization
- Tools that expect conventional file layouts

### Reference System (Knowledge Graph)
- Permanent knowledge that transcends specific projects
- Cross-project relationships and insights
- Long-term searchable metadata
- Stable references that survive project completion

## GTD Integration

### Complete GTD Workflow Support

This system supports the full GTD methodology through structured notes and workflow tools:

#### The Five-Stage Workflow
1. **Capture**: `inbox/` directory for frictionless capture of unprocessed items
2. **Clarify**: Process inbox items using Two-Minute Rule and actionability questions
3. **Organize**: Use note properties and directories to organize by context and type
4. **Reflect**: Weekly review dashboards aggregating all commitments
5. **Engage**: Context-based action lists for effective execution

### GTD Projects in This System

A **GTD project** becomes a coordination note that bridges ephemeral working directories with the permanent knowledge graph:

```yaml
# project/website-redesign.yaml
id: "proj-uuid-456"
title: "Website Redesign Project"
content: "Complete redesign of company website for Q1 2024 launch"

properties:
  # GTD Properties
  status: "active"  # active, on-hold, completed, someday
  
  # Context-based next actions
  next_actions:
    - action: "Review competitor websites"
      context: "@computer"
      estimated_time: "2h"
    - action: "Schedule stakeholder interviews"
      context: "@calls"
      estimated_time: "15min"
    - action: "Meet with design team"
      context: "@office"
      estimated_time: "1h"
  
  # Waiting for items with tracking
  waiting_for:
    - item: "Legal approval on new terms of service"
      person: "person/legal-team"
      date_requested: "2023-10-15"
      context: "@follow-up"
  
  deadline: "2024-03-01"
  
  # Working System Links
  working_directory: "/home/will/projects/website-redesign-2024/"
  git_repository: "repository/website-redesign"  # Link to repository note
  
  # Reference System Links
  referenced_files: 
    - "document/brand-guidelines"     # Reference system
    - "research/competitor-analysis"  # Reference system
  team_members: ["person/sarah-designer", "person/mike-developer"]
  
  # Project Artifacts (things that will outlive the project)
  deliverables:
    - "document/final-design-specs"
    - "document/user-research-findings"

tags: ["project", "website", "q1-2024"]
```

### Remote Repository Integration

GitHub repositories and other remote shared resources are treated as first-class entities:

```yaml
# repository/mcp-framework.yaml
id: "repo-uuid-789"
title: "MCP Framework"
content: "Model Context Protocol framework for tool integration. Key insights: authentication patterns in src/auth/ are reusable across projects."

properties:
  type: "github-repository"
  git_url: "git@github.com:company/mcp-framework.git"
  clone_path: "/home/will/code/mcp-framework/"
  
  # Knowledge and relationships (not available from repo itself)
  key_learnings:
    - "Authentication patterns in src/auth/ solve OAuth flow issues"
    - "Testing strategy in tests/integration/ is worth copying"
    - "Deployment scripts handle edge cases well"
  
  # Context and purpose
  why_important: "Core framework for all our MCP integrations"
  my_role: "maintainer"  # Your specific role/responsibility
  
  # Forward references only (reverse relationships computed dynamically)
  related_documents: ["document/mcp-architecture-notes"]
  related_people: ["person/original-author"]

tags: ["repository", "framework", "active", "python"]
```

#### Repository Integration Benefits
- **Knowledge Preservation**: Document key insights about codebases
- **Cross-Project Learning**: Find patterns across different repositories  
- **Context Switching**: Quickly understand repository purpose and structure
- **Forward References**: Link to related documents and people (reverse relationships computed)

### Relationship Management Philosophy

**Unidirectional Links Only**: This system stores only forward references to prevent synchronization issues. Instead of maintaining bidirectional links that can become inconsistent, relationships are computed dynamically:

```bash
# Find all projects using a repository
find-notes --property git_repository --contains "repository/mcp-framework"

# Find all projects a person is involved in
find-notes --property team_members --contains "person/sarah-designer"

# Find all documents referenced by projects
find-notes --property referenced_files --contains "document/brand-guidelines"

# Show computed relationships for any note
show-relationships "person/sarah-designer"
```

**Benefits of Unidirectional Approach:**
- ✅ **Single source of truth** - no duplicate relationship data
- ✅ **No synchronization bugs** - relationships can't get out of sync
- ✅ **Always accurate** - computed views reflect current state
- ✅ **Easier maintenance** - update one place, relationships automatically correct

### GTD Workflow

1. **Capture**: Add items to `inbox/` directory
2. **Clarify**: Process inbox using guided workflow tools
3. **During Project**: Work in normal filesystem + repository clones
4. **Create References**: Important documents and repositories get YAML proxies
5. **Project Completion**: Working directories archived, knowledge preserved
6. **Weekly Review**: Use aggregation tools to review all commitments

## Benefits

### Solves Traditional File Management Problems
- ✅ **Rich Metadata**: Files get tags, descriptions, relationships, creation context
- ✅ **Stable References**: Moving files doesn't break UUID-based links
- ✅ **No Filename Collisions**: Files identified by UUID, not filename
- ✅ **Centralized Organization**: All metadata in human-readable YAML
- ✅ **Cross-References**: Files can link to people, projects, other files

### Maintains Simplicity
- ✅ **Human-Readable**: Everything is YAML, version control friendly
- ✅ **No Duplication**: One copy per unique file (content-addressed)
- ✅ **Tool Interoperability**: Scripts and tools can easily read/modify
- ✅ **Future-Proof**: Not locked into any specific application

### Integrates with Existing Workflows
- ✅ **Working System Compatibility**: Normal file operations still work
- ✅ **GTD Integration**: Projects become coordination notes
- ✅ **Gradual Migration**: Can slowly move important files to reference system
- ✅ **Flexible Organization**: Organize by project, type, or any other scheme

## GTD Workflow Tools (Work in Progress)

To fully support the GTD methodology, the following aggregation and workflow tools are planned:

### Capture Tools
```bash
# Quick capture to inbox
new-note --inbox "Random thought about project"
add-file --inbox ~/Downloads/important-document.pdf

# Process inbox items
process-inbox  # Guided workflow for clarifying items
```

### Context-Based Views
```bash
# Show actions by context
show-actions --context @computer
show-actions --context @calls
show-actions --context @errands

# Show all waiting-for items
show-waiting-for

# Show projects by status
show-projects --status active
show-projects --status on-hold
```

### Review Tools
```bash
# Generate weekly review dashboard
weekly-review  # Consolidated view of all commitments

# Check system health
check-inbox    # Ensure inbox is processed
check-deadlines # Show upcoming deadlines
stale-waiting  # Find old waiting-for items
```

### Relationship Tools
```bash
# Find relationships dynamically (no bidirectional links stored)
find-notes --property team_members --contains "person/sarah-designer"
find-notes --property referenced_files --contains "document/guidelines"
show-relationships "uuid-123"  # Show all computed relationships
orphaned-notes  # Find notes with no incoming references
```

### Repository Tools
```bash
# Repository discovery and management
sync-repositories     # Update repository metadata from GitHub API
find-repo "python"    # Find repositories by language/topic
repo-status           # Show git status across all tracked repos
project-repos         # Show which repos are linked to active projects
```

These tools will query the YAML notes to generate dynamic, actionable views while preserving the human-readable structure of the underlying system.

## Implementation Strategy

### Phase 1: Core File Registry
- Extend existing Note model to support file registry properties
- Implement content-addressed storage in `_assets/` directory
- Add file upload/management tools

### Phase 2: Reference Tools
- Create tools for linking notes to files
- Implement bidirectional relationship tracking
- Add file discovery and search capabilities

### Phase 3: GTD Integration
- Extend project notes with GTD properties
- Create workflow tools for managing next actions and waiting-for items
- Integrate with existing task management

### Phase 4: Advanced Features
- Optional indexing for performance
- File integrity verification
- Migration tools from existing document folders
- Deduplication based on content hashes

This unified approach transforms file management from a necessary evil into an integral part of your knowledge system, where every file becomes a searchable, linkable, and organizable entity in your personal knowledge graph.

# Unified Knowledge Management Vault

## Core Philosophy

Most file formats (PDFs, Word docs, images, videos) are essentially "dumb containers" - they hold content but lack useful organizational metadata. A PDF doesn't know what project it belongs to, who created it, or how it relates to other documents.

**Solution: Treat a lightweight YAML file as the "real" entity in our system, while storing the true file content in a flat, managed library.**

This is like a library catalog system:
- **YAML Card** = The catalog card (with title, author, subject, related works)
- **Content file** = The actual book on the shelf
- **Users interact with catalog cards** (YAML files) to find, organize, and link
- **The physical books** (content files) are stored efficiently in a warehouse

## What is a "Card"?

In this unified system, a **Card** is a YAML entity that represents any piece of knowledge, whether that knowledge is:

1. **Pure thoughts/text** (Notes)
2. **Structured data** (Project Cards, Person Cards)  
3. **File proxies** (Asset Cards representing external content)
4. **External references** (Reference Cards for bookmarks)

**Everything is a Card.** The distinction isn't "notes vs files" but rather:
- **Self-contained knowledge** (content lives in the YAML Card)
- **Referenced knowledge** (content lives elsewhere, Card is the pointer/metadata)

## Five Types of Cards

### Type 1: Notes (Content Cards)
Traditional notes where the knowledge lives directly in the YAML content, supporting markdown.

```yaml
# note/meeting-insights.yaml
id: "note-uuid-123"
title: "Client Meeting Insights"
content: |
  # Key Takeaways from Client Meeting
  
  ## Requirements
  - **Mobile-first** design approach
  - Integration with existing CRM
  
  ## Action Items
  - [ ] Create wireframes by Friday
  - [ ] Research CRM APIs
  
  ## Concerns
  The timeline seems aggressive given the scope.

metadata:
  format: "markdown"
  meeting_date: "2024-01-15"
  attendees: ["person/sarah-designer", "person/client-contact"]
  
tags: ["meeting", "client", "requirements"]
```

### Type 2: Asset Cards (File Proxies)
Cards that serve as proxies for external files, providing rich metadata that the files themselves lack.

```yaml
# asset/competitor-analysis.yaml
id: "asset-uuid-456" 
title: "Q3 Competitor Analysis"
content: "Analysis of competitor X's product launch strategy"

metadata:
  type: "file-asset"
  file_content_path: "_assets/sha256-abc123...pdf"
  content_hash: "sha256-abc123..."
  original_filename: "Competitor Analysis Q3.pdf"
  mime_type: "application/pdf"
  size_bytes: 1234567
  upload_date: "2023-10-27T10:00:00Z"
  
tags: ["research", "competitive", "q3-2023"]
```

### Type 3: Project Cards (GTD Coordination)
Cards that coordinate specific, outcome-focused projects with defined endpoints.

```yaml
# project/website-redesign.yaml
id: "project-uuid-789"
title: "Website Redesign Project"
content: |
  Complete redesign of company website for Q1 2024 launch.
  
  ## Goals
  - Modernize user experience
  - Improve mobile responsiveness
  - Integrate new branding

metadata:
  # GTD Fields
  status: "active"  # active, on-hold, completed, someday
  
  # Context-based next actions
  next_actions:
    - action: "Review competitor websites"
      context: "@computer"
      estimated_time: "2h"
    - action: "Schedule stakeholder interviews"
      context: "@calls"
      estimated_time: "15min"
  
  # Waiting for items with tracking
  waiting_for:
    - item: "Legal approval on new terms of service"
      person: "person/legal-team"
      date_requested: "2023-10-15"
      context: "@follow-up"
  
  deadline: "2024-03-01"
  
  # Working System Links
  working_directory: "/home/will/projects/website-redesign-2024/"
  git_repository: "reference/website-redesign-repo"
  
  # Asset Links (forward references only)
  assets: 
    - "asset/brand-guidelines"
    - "asset/competitor-analysis"
  
  # External References
  external_references:
    - "reference/design-inspiration-site"
  
  # Team Links
  team_members: ["person/sarah-designer", "person/mike-developer"]
  
  # Project Artifacts (things that will outlive the project)
  deliverables:
    - "asset/final-design-specs"
    - "asset/user-research-findings"

tags: ["project", "website", "q1-2024"]
```

### Type 4: Area Cards (Ongoing Responsibilities)
Cards for ongoing areas of responsibility that generate tasks but aren't specific projects.

```yaml
# area/personal-admin.yaml
id: "area-uuid-abc"
title: "Personal Administration"
content: |
  Ongoing personal administrative tasks and responsibilities.
  
  ## Key Areas
  - Financial management
  - Health appointments
  - Home maintenance
  - Government/legal matters

metadata:
  type: "area"
  status: "active"
  
  # Standalone tasks with context
  next_actions:
    - action: "File tax documents"
      context: "@home"
      estimated_time: "1h"
      priority: "high"
    - action: "Call dentist for checkup"
      context: "@calls"
      estimated_time: "10min"
    - action: "Renew car registration"
      context: "@errands"
      due_date: "2024-02-15"
  
  # Recurring responsibilities
  recurring_tasks:
    - action: "Review bank statements"
      context: "@computer"
      frequency: "monthly"
    - action: "Water plants"
      context: "@home"
      frequency: "weekly"
  
  # Related resources
  related_assets: ["asset/tax-documents", "asset/insurance-policies"]
  
tags: ["area", "personal", "admin"]
```

### Type 5: Reference Cards (External Bookmarks)
Cards that reference external resources with personal annotations.

```yaml
# reference/mcp-framework-repo.yaml
id: "reference-uuid-def"
title: "MCP Framework Repository"
content: |
  Key insights: authentication patterns in src/auth/ are reusable 
  across projects. Testing strategy in tests/integration/ worth 
  copying to other projects.

metadata:
  type: "external-repository"
  url: "https://github.com/company/mcp-framework"
  git_url: "git@github.com:company/mcp-framework.git"
  clone_path: "/home/will/code/mcp-framework/"
  
  # Personal context and insights only
  why_important: "Core framework for all our MCP integrations"
  my_role: "contributor"
  key_learnings: ["OAuth flow solutions", "integration testing patterns"]
  
  # Links to your Vault
  related_assets: ["asset/mcp-architecture-notes"]

tags: ["external", "repository", "framework", "reference"]
```

## File Management Architecture

### Single File Storage + Multiple References
- Each unique file is stored once in the managed Asset Vault (`_assets/` directory)
- Files are content-addressed: `_assets/sha256-2cf24dba...pdf`
- Multiple Cards can reference the same file via its UUID
- No duplication, single source of truth for file content

### UUID + Slug Addressing
Files follow the same pattern as regular Cards:
- **UUID access**: `asset-uuid-abc-789`
- **Type/Slug access**: `asset/competitor-analysis-q3`

### Markdown File Integration

**Short Notes**: Markdown content stored directly in Note Cards
```yaml
# note/quick-thought.yaml
content: |
  ## Quick Idea
  What if we used graph databases for this?
```

**Long Documents**: Markdown files stored as assets with Asset Cards
```yaml
# asset/project-documentation.yaml
metadata:
  file_content_path: "_assets/sha256-def456...md"
  mime_type: "text/markdown"
  word_count: 2500
```

**Hybrid Approach**: Choose based on length and importance
- **< 500 words**: Store inline in Note Card content
- **> 500 words**: Create Asset Card pointing to markdown file in Asset Vault

### Directory Structure
```
vault/
├── inbox/                    # Unprocessed items (GTD capture)
│   ├── random-thought.yaml
│   └── uploaded-file.yaml
├── note/                     # Text-based content
│   ├── meeting-insights.yaml
│   └── project-ideas.yaml
├── person/
│   ├── david-yallop.yaml
│   └── sarah-designer.yaml
├── asset/                    # File proxies
│   ├── competitor-analysis.yaml
│   └── brand-guidelines.yaml
├── project/                  # GTD projects (specific outcomes)
│   └── website-redesign.yaml
├── area/                     # Ongoing responsibilities
│   ├── personal-admin.yaml
│   ├── work-maintenance.yaml
│   └── health-fitness.yaml
├── someday/                  # Someday/maybe projects
│   └── learn-spanish.yaml
├── reference/                # External resources
│   ├── mcp-framework-repo.yaml
│   └── useful-blog-post.yaml
├── _assets/                  # Asset Vault (system-managed)
│   ├── sha256-2cf24dba...pdf
│   ├── sha256-9f86d081...jpg
│   └── sha256-def456...md    # Markdown files
└── .mcp_handley_lab/
    └── file_index.json       # Optional performance index
```

## Working vs Reference Systems

### Working System (Traditional Filesystem)
- LaTeX projects with `.tex`, `.bib`, `.cls` files that need to be together
- Code repositories with specific directory structure  
- Active collaboration where others expect normal file organization
- Tools that expect conventional file layouts

### Reference System (Knowledge Vault)
- Permanent knowledge that transcends specific projects
- Cross-project relationships and insights
- Long-term searchable metadata
- Stable references that survive project completion

## GTD Integration

### Complete GTD Workflow Support

This system supports the full GTD methodology through structured Cards and workflow tools:

#### The Five-Stage Workflow
1. **Capture**: `inbox/` directory for frictionless capture of unprocessed items
2. **Clarify**: Process inbox items using Two-Minute Rule and actionability questions
3. **Organize**: Use Card metadata and directories to organize by context and type
4. **Reflect**: Weekly review dashboards aggregating all commitments
5. **Engage**: Context-based action lists for effective execution

### Projects vs Areas vs Someday

**Projects** (have specific outcomes and end dates):
- "Launch new website" - clear deliverable
- "Plan vacation to Japan" - defined endpoint
- "Organize home office" - specific result

**Areas** (ongoing responsibilities without end dates):
- "Personal Administration" - filing taxes, renewals, etc.
- "Health & Fitness" - exercise, medical appointments
- "Work Maintenance" - reports, team meetings, admin

**Someday/Maybe** (potential projects to consider later):
- "Learn Spanish" - might become a project
- "Write a book" - interesting idea for the future
- "Start a podcast" - no commitment yet

### Task Management Across Card Types

Tasks live within their meaningful context but can be aggregated for daily work:

```bash
# Show all next actions regardless of source
show-actions --context @computer  # From projects AND areas

# Show tasks by type
show-actions --type project     # Only project tasks
show-actions --type area       # Only area tasks

# Show tasks by priority or due date
show-actions --priority high
show-actions --due-this-week
```

### External Resource References

GitHub repositories and other external resources are treated as **references with personal annotations** rather than managed entities:

#### External Reference Benefits
- **Personal Context**: Capture why external resources matter to you
- **Knowledge Preservation**: Document key insights that aren't in the external resource
- **Stable Links**: Reference external resources without trying to manage their metadata
- **Cross-Project Learning**: Connect external resources to your local projects and documents

### Relationship Management Philosophy

**Unidirectional Links Only**: This system stores only forward references to prevent synchronization issues. Instead of maintaining bidirectional links that can become inconsistent, relationships are computed dynamically:

```bash
# Find all projects using an external repository
find-cards --metadata git_repository --contains "reference/mcp-framework-repo"

# Find all projects a person is involved in
find-cards --metadata team_members --contains "person/sarah-designer"

# Find all assets referenced by projects
find-cards --metadata assets --contains "asset/brand-guidelines"

# Show computed relationships for any Card
show-relationships "person/sarah-designer"
```

**Benefits of Unidirectional Approach:**
- ✅ **Single source of truth** - no duplicate relationship data
- ✅ **No synchronization bugs** - relationships can't get out of sync
- ✅ **Always accurate** - computed views reflect current state
- ✅ **Easier maintenance** - update one place, relationships automatically correct

### Complete GTD Task Management

**No Orphaned Tasks**: Every task belongs to either:
- **Project Card** - tasks toward a specific outcome
- **Area Card** - tasks for ongoing responsibility
- **Someday Card** - ideas that might become projects

**Context Everywhere**: All tasks have @contexts regardless of source:
- `@computer` - tasks requiring a computer
- `@calls` - phone calls to make
- `@errands` - things to do while out
- `@home` - tasks requiring home environment
- `@office` - tasks requiring office environment

**Unified Views**: Aggregation tools work across all Card types:
```bash
# See ALL @computer tasks from projects, areas, and someday
show-actions --context @computer

# Weekly review across everything
weekly-review  # Shows projects, areas, waiting-for, etc.
```

### GTD Workflow

1. **Capture**: Add items to `inbox/` directory
2. **Clarify**: Process inbox using guided workflow tools
3. **During Project**: Work in normal filesystem + external repository clones
4. **Create References**: Important documents get Asset Cards, external resources get Reference Cards
5. **Project Completion**: Working directories archived, knowledge preserved in reference system
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

### Supports Markdown Workflows
- ✅ **Familiar Writing**: Continue using markdown syntax
- ✅ **Flexible Storage**: Short notes inline, long docs as assets
- ✅ **Rich Linking**: Connect markdown content to projects, people, assets
- ✅ **Tool Compatibility**: Edit with any markdown editor

### Integrates with Existing Workflows
- ✅ **Working System Compatibility**: Normal file operations still work
- ✅ **GTD Integration**: Projects become coordination Cards
- ✅ **Gradual Migration**: Can slowly move important files to reference system
- ✅ **Flexible Organization**: Organize by project, type, or any other scheme

## GTD Workflow Tools (Work in Progress)

To fully support the GTD methodology, the following aggregation and workflow tools are planned:

### Capture Tools
```bash
# Quick capture to inbox
new-note --inbox "Random thought about project"
new-note --inbox --markdown "Meeting notes" --content "# Client Call"
add-file --inbox ~/Downloads/important-document.pdf

# Quick task capture (will be organized during processing)
new-task --inbox "Call dentist" --context @calls
new-task --inbox "Buy groceries" --context @errands

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

# Show areas and their tasks
show-areas --status active
show-actions --type area
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
find-cards --metadata team_members --contains "person/sarah-designer"
find-cards --metadata assets --contains "asset/guidelines"
show-relationships "uuid-123"  # Show all computed relationships
orphaned-cards  # Find Cards with no incoming references
```

### External Reference Tools
```bash
# External resource management
check-links           # Verify external URLs are still accessible
find-reference "python"  # Find external references by topic
local-clones         # Show status of local repository clones
project-externals    # Show which external resources are linked to projects
```

### Markdown Tools
```bash
# Markdown-specific operations
edit-note "note/meeting-insights" --editor vim
convert-to-asset "note/long-document"  # Convert inline markdown to Asset Card
render-markdown "asset/documentation"  # Generate HTML preview
```

These tools will query the YAML Cards to generate dynamic, actionable views while preserving the human-readable structure of the underlying system.

## Implementation Strategy

### Phase 1: Core Card System
- Extend existing Note model to support Card types and file registry properties
- Implement content-addressed storage in Asset Vault (`_assets/` directory)
- Add file upload/management tools

### Phase 2: GTD Workflow Tools
- Create tools for linking Cards to files
- Implement context-based action management for Projects and Areas
- Add GTD workflow tools (inbox processing, weekly review)
- Create Area Cards for ongoing responsibilities

### Phase 3: Advanced Integration
- Extend project Cards with full GTD properties
- Create aggregation tools for dynamic views
- Integrate with existing task management

### Phase 4: Advanced Features
- Optional indexing for performance
- File integrity verification
- Migration tools from existing document folders
- Deduplication based on content hashes

This unified approach transforms file management from a necessary evil into an integral part of your knowledge system, where every file becomes a searchable, linkable, and organizable entity in your personal knowledge Vault.
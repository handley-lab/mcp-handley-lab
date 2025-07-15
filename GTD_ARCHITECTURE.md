# GTD System Architecture

## Core Concept

The GTD (Getting Things Done) system is a card-based knowledge management tool that implements David Allen's productivity methodology. It uses directory structure and automatic tagging to organize cards (notes, projects, areas, assets, references) rather than explicit types, making the system more flexible and path-driven.

## GTD Data Model

### Card Structure
Each card contains:
- **Unique ID**: UUID for system identification
- **Title**: Human-readable name
- **Content**: Markdown-formatted body text
- **Tags**: List of categorization labels (includes automatic directory-based tags)
- **Metadata**: Extensible key-value properties
- **Timestamps**: Creation and modification dates

**Note**: Path and slug information is NOT stored in the card itself - it's determined by the card's file location in the directory structure.

### Directory-Based Card Behavior
Card functionality is determined by directory placement, not explicit types:

- **`inbox/`**: Quick capture items needing processing
- **`note/`**: Standalone thoughts, ideas, or information
- **`project/`**: Multi-step outcomes with defined completion criteria  
- **`area/`**: Ongoing responsibilities without completion dates
- **`asset/`**: Resources, tools, or reference materials
- **`reference/`**: Documentation, guides, or lookup information
- **`person/`**: Person-related cards and interactions
- **`someday/`**: Someday/maybe items

### Automatic Tagging System
Cards automatically receive tags based on their directory location:
- Card in `project/research/ai-safety/` → automatically tagged with `["project", "research", "ai-safety"]`
- Card in `person/handley-lab/alice/` → automatically tagged with `["person", "handley-lab", "alice"]`
- Cards can have additional manual tags beyond the automatic directory-based tags
- Directory changes automatically update the relevant tags

### GTD-Specific Card Features

#### Project & Area Directory Features
Cards in `project/` and `area/` directories support:
- **Next Actions**: List of actionable items with context, priority, estimated time, due dates
- **Waiting For**: Items waiting on others with person, date requested, context
- **Status**: Active, someday/maybe, completed, archived
- **Linked Cards**: References to related cards via UUID metadata properties

#### Asset Directory Features  
Cards in `asset/` directory support:
- **File Content Path**: Reference to actual file in `_assets/` storage
- **Content Hash**: For integrity verification and duplicate detection
- **MIME Type Detection**: Automatic file type classification
- **Asset Import**: Copy external files into managed storage structure

#### Reference Directory Features
Cards in `reference/` directory support:
- **URL**: Web links for external references
- **Link Validation**: Check accessibility of referenced URLs

### Storage Format
- Cards stored as YAML files in hierarchical directory structure
- **Filename pattern**: Slug-based filenames derived from title (e.g., `meeting-notes.yaml`). If title is empty, use UUID as filename
- **YAML Structure**: Cards use YAML frontmatter for structured metadata, with Markdown content following `---` separator
- Directory structure reflects organizational taxonomy and determines card behavior
- Path/slug derived from file location, not stored in card content
- Example: `~/gtd/person/handley-lab/alice-meeting-notes.yaml`

### Directory Organization
```
~/gtd/                          # Git repository root
├── inbox/                      # Quick capture items needing processing
├── note/                       # Standalone notes and thoughts
├── person/                     # Person-related cards and interactions
├── project/                    # Multi-step outcomes with completion criteria
├── area/                       # Ongoing responsibilities 
├── someday/                    # Someday/maybe items
├── reference/                  # Documentation and reference materials
├── asset/                      # File-backed cards
├── archive/                    # Archived cards organized by year (excluded from active indexing)
│   ├── 2023/                   # Year-based archive organization
│   └── 2024/                   # Current year archives
├── _assets/                    # Managed file storage (content referenced by asset cards)
├── .hooks/                     # Python hook scripts for card processing
├── .rules/                     # YAML validation schemas
├── .git/                       # Git repository data
└── .gitignore                  # Git ignore rules (exclude temporary files, caches)
```

### Hook System
- Python scripts in `.hooks/` directory for automatic card processing
- Execute on card creation/modification events
- Examples: tag normalization, metadata corrections, content formatting
- Hot-reloadable during server operation
- **Standard Interface**: Each hook exports a `hook(card: Card)` function
- **Execution Order**: Hooks execute in alphabetical filename order
- **Fail Fast Error Handling**: Hook failures immediately abort card processing with detailed error reporting

### Validation Rules
- YAML schemas in `.rules/` directory define validation constraints
- Enforce data consistency and business rules
- Validate card structure, required fields, and relationships
- Hot-reloadable during server operation
- **Trigger Conditions**: Rules can be conditional based on tags or metadata
- **Schema Format**: Standard YAML schema with custom trigger extensions
- **Real-time Validation**: Cards validated during all modification operations

### Git Synchronization System
- **Repository Initialization**: Automatic git repository creation in GTD directory
- **Debounced Commits**: Card changes trigger git commits after configurable debounce period (default 5 seconds) to group rapid edits
- **Semi-Automated Sync**: Automatic push for local changes, manual pull/merge for remote changes
- **Conflict Resolution**: Fail fast on merge conflicts with clear user instructions to resolve manually
- **Cross-Machine Consistency**: File watcher maintains TinyDB index consistency when git operations modify files
- **Backup Integration**: Git serves as version control and backup mechanism
- **Commit Message Format**: `[GTD] <operation>: <card_title>` with metadata (UUID, path)
- **Ignore Rules**: Proper .gitignore for temporary files, caches, and sensitive data
- **Filename Collision Handling**: Numeric suffix strategy (e.g., `meeting-notes-1.yaml`) for duplicate slugs

### System Configuration

The system uses a configuration file to manage operational settings and ensure portability across different environments.

#### Configuration File Location
- **Primary**: `~/.config/gtd/config.toml`
- **Alternative**: `.gtd/config.toml` within the GTD root directory
- **Format**: TOML format for human readability and easy editing

#### Configuration Structure
```toml
[server]
port = 8000                    # HTTP server port
host = "127.0.0.1"            # Bind to localhost for security
timeout_seconds = 30          # Request timeout

[gtd]
root_path = "~/gtd"           # Path to GTD directory
index_cache_path = ".gtd/.cache/index.json"  # TinyDB cache location

[git]
remote_name = "origin"        # Default git remote name
branch_name = "main"          # Default branch for sync operations
commit_debounce_seconds = 5   # Debounce period for automatic commits
auto_push = true             # Automatically push local commits

[performance]
startup_cache_validation = true    # Use mtime validation on startup
file_watcher_enabled = true       # Enable real-time file watching
```

#### Configuration Precedence
1. Command-line arguments (highest priority)
2. Configuration file settings
3. System defaults (lowest priority)

#### Default Behavior
- If no configuration file exists, system uses sensible defaults
- `gtd_init` command creates initial configuration file with user-specified settings

### System Initialization

New users start with the `gtd_init` command to create a complete, ready-to-use GTD system.

#### Initialization Process
1. **Create Directory Structure**: Establish full directory hierarchy (inbox/, project/, area/, etc.)
2. **Git Repository**: Initialize git repository with `git init`
3. **Configuration File**: Create default configuration at `~/.config/gtd/config.toml`
4. **Default .gitignore**: Add appropriate ignore rules for cache files and temporary data
5. **Starter Templates**: 
   - Sample validation rules in `.rules/`
   - Example hook scripts in `.hooks/`
   - Welcome card in `inbox/` with usage instructions
6. **Cache Directory**: Create `.gtd/.cache/` for TinyDB index storage

#### Command Usage
```bash
gtd init [path]               # Initialize at specified path
gtd init                      # Initialize at default ~/gtd location
gtd init --remote-url=<url>   # Initialize with git remote
```

#### Post-Initialization
- System ready for immediate use
- User can begin capturing items in `inbox/` directory
- System can be started and will find all necessary components

## Tool Interface

### Core Operations
- `create_card`: Create new cards specifying target directory path, with metadata, hooks, validation, and git commit
- `get_card`: Retrieve cards by UUID or filesystem path/slug (single unified interface)
- `update_card`: Modify existing card properties with automatic timestamp updates and git commit
- `delete_card`: Remove cards from system with git commit (supports UUID or filesystem path identification)
- `move_card`: Move cards between directories with automatic tag updates, validation rule transformations, and git commit
- `archive_card`: Move cards to date-stamped archive directory, removing them from active indexing
- `find_cards`: Advanced search by directory, tags, text content, or metadata filters (active cards only by default)
- `list_all_cards`: Enumerate entire card collection with full details and filesystem paths (active cards only by default)
- `add_tag_to_card` / `remove_tag_from_card`: Tag management with git commit (in addition to automatic directory tags)
- `get_cards_stats`: System statistics and metrics with tag usage analysis

### System Management
- `init`: Initialize new GTD system with complete directory structure, git repository, default configuration, and starter templates

### Git Operations
- `git_status`: Show current git repository status and uncommitted changes
- `git_sync`: Manual pull/merge synchronization with remote repository (automatic push for local changes)
- `git_log`: View recent commit history for cards
- `git_init_remote`: Initialize and configure remote repository connection

### Additional Features
- **Slug Generation**: Automatic URL-friendly slugs from titles for filesystem naming
- **Bulk Operations**: Batch processing of multiple cards efficiently
- **Search Integration**: In-memory indexing for fast full-text and metadata search
- **Asset Management**: File import, hash verification, and managed storage
- **Link Resolution**: Automatic detection and following of UUID references between cards
- **Automatic Tagging**: Directory-based tag assignment with manual tag additions
- **Path-Based Behavior**: Card functionality determined by filesystem directory location
- **Filesystem Integration**: Path/slug information derived from actual file location
- **Git Synchronization**: Automatic git operations for version control and backup
- **Archive System**: Physical separation of completed work with optional archive search capabilities

### Resource Browsing
- Browse all cards with preview content, tags, and metadata
- View system statistics including card counts, type distribution, and tag usage

## Implementation Considerations

The GTD system requires efficient access patterns and performance characteristics to remain usable as the card collection grows. Key considerations include:

### Performance Requirements

- **Fast Search**: Full-text and metadata search across thousands of cards
- **Quick Startup**: System initialization should be sub-second even with large collections
- **Real-time Updates**: Changes to files should be reflected immediately
- **Efficient Memory Usage**: System should scale gracefully with collection size

### Architecture Options

The core GTD concepts (YAML files, directory-driven behavior, automatic tagging) can be implemented through various architectural approaches:

1. **Simple CLI Tools**: Direct file system operations with caching
2. **Local Server**: Background service with client interface
3. **Database Backend**: Traditional database with YAML export/import
4. **Hybrid Approaches**: Combination of file-based storage with optimized indexing

### Key Design Principles

1. **File-First**: YAML files remain the canonical source of truth
2. **Directory-Driven**: Card behavior determined by filesystem location
3. **Fast Access**: In-memory indexing for responsive operations
4. **CLI-First Design**: Primary interface should be a comprehensive command-line tool
5. **External Tool Friendly**: Support integration with various clients and interfaces
6. **Git Native**: Leverage git for versioning and synchronization

### CLI-First Implementation Strategy

The GTD system should be designed as a comprehensive command-line tool first, with additional interfaces built on top:

#### Primary CLI Tool (`gtd`)
```bash
# Core operations
gtd create --dir inbox --title "Meeting with Alice" --content "Discuss project timeline"
gtd get <uuid-or-slug>
gtd update <uuid-or-slug> --title "New title"
gtd delete <uuid-or-slug>
gtd move <uuid-or-slug> --to project/research/
gtd archive <uuid-or-slug>

# Search and listing
gtd find --tags project,research --content "timeline"
gtd list --dir project/ --status active
gtd stats

# Git operations
gtd status
gtd sync
gtd log
```

#### Benefits of CLI-First Approach
- **Direct Usage**: Powerful standalone tool for power users
- **Scriptable**: Easy integration into automation workflows
- **Testable**: Command-line interface simplifies testing and validation
- **MCP Integration**: CLI can be wrapped as MCP tools for AI assistant integration
- **Multiple Interfaces**: Web UI, TUI, or GUI can all call the same CLI backend

#### MCP Integration Layer
Once the CLI tool is mature, it can be wrapped with MCP tools that simply call the underlying CLI commands:

```python
@mcp.tool()
def create_card(dir: str, title: str, content: str = "") -> str:
    """Create a new GTD card"""
    result = subprocess.run(["gtd", "create", "--dir", dir, "--title", title, "--content", content], 
                          capture_output=True, text=True)
    return result.stdout
```

This approach ensures:
- **Single Source of Truth**: All functionality implemented once in the CLI
- **Consistent Behavior**: MCP tools and direct CLI usage work identically  
- **Easier Development**: Focus on core functionality before integration complexity
- **Better Testing**: CLI can be thoroughly tested before MCP layer is added

## Core Implementation Components

### Functional Requirements

The GTD system implementation needs to provide the following core capabilities:

#### Data Management
- **Card Models**: Structured representation of GTD cards with metadata, content, and timestamps
- **Storage Layer**: YAML file I/O, directory management, and automatic tagging based on filesystem location
- **Business Logic**: Orchestration of card operations with path-based behavior determination

#### System Integration
- **Hook System**: Extensible processing pipeline for card lifecycle events
- **Validation Framework**: Schema-based validation with directory-specific rules
- **Search and Indexing**: Fast full-text and metadata search capabilities
- **Git Integration**: Automatic version control and synchronization

### Required Capabilities
- **YAML Processing**: Read/write card data in human-readable format
- **Filesystem Monitoring**: Detect external changes and maintain consistency
- **Git Operations**: Repository management and synchronization
- **Text Processing**: Slug generation and content manipulation
- **Data Validation**: Schema-based validation with custom rules
- **Search Indexing**: In-memory or database-backed search capabilities

### Core System Design

#### Storage Layer
- Cards persisted as individual YAML files with slug or UUID filenames
- Directory structure drives card behavior and automatic tagging
- Atomic file operations ensure data consistency
- Slug-based file naming for human-readable organization
- **Asset Storage**: Managed `_assets/` directory with hash-based organization
- **YAML Processing**: Preserve formatting and comments in human-readable files
- **Automatic Tagging**: Directory path components automatically become tags
- **Path Resolution**: Card path/slug derived from filesystem location, not stored in card data

#### Business Logic Layer
- Orchestrates storage, validation, hook execution, and git operations
- Maintains card lifecycle (create, read, update, delete, move, archive) with automatic git commits
- Implements path-based behavior determination (project/, area/, etc.)
- Handles bulk operations and batch processing
- **Search Integration**: In-memory database with mtime-validated disk caching for fast startup
- **File Watching**: Automatic card reloading when files change on disk (git sync, external edits)
- **Asset Management**: File import, hash verification, duplicate detection
- **Tag Management**: Combines automatic directory tags with manual tags
- **Git Integration**: Automatic repository initialization, commits, and semi-automated remote sync
- **Move Operations**: Directory migration with validation rule transformation and tag updates
- **Archive Management**: Physical separation of completed work with active-only indexing by default

#### Hook System
- Extensible modules in `.hooks/` directory with standardized interface
- Hooks receive card objects and can modify any properties
- Execute in deterministic order during card operations
- Support for conditional execution based on card properties
- **Dynamic Loading**: Hook modules loaded and cached with hot-reload capability
- **Fail Fast Error Handling**: Hook failures immediately abort processing with detailed error reporting including hook name and failure context

#### Validation System
- Schema files define validation rules per directory/path
- Pluggable validator architecture for extensibility
- Real-time validation during card operations
- Comprehensive error reporting for validation failures
- **Conditional Rules**: Trigger-based validation (tags, metadata, directory path)
- **Schema Loading**: Dynamic schema discovery and caching with hot-reload
- **Path-Based Rules**: Different validation rules for project/, area/, asset/ directories

### Performance Optimization: Intelligent Caching

The system uses an mtime-validated caching approach to achieve sub-second startup times even with thousands of cards.

#### Cache Architecture
- **Disk Cache**: Index stored as `.gtd/.cache/index.json` with card metadata and file modification times
- **Startup Process**: Load cached index, validate against filesystem using `mtime` comparison
- **Validation Logic**: Only re-read and re-parse files that have changed since last cache update
- **Fallback Behavior**: If cache is corrupted or missing, perform full rebuild and create new cache

#### Performance Characteristics
- **Large System (5,000 cards)**: Startup time ~200ms vs ~7.5 seconds without cache (37x improvement)
- **Cache Storage**: ~20-30% of original YAML file size
- **Incremental Updates**: File watcher updates both in-memory index and disk cache in real-time

#### Cache Invalidation
- **External Changes**: Git operations and direct file edits detected by file watcher
- **Bulk Operations**: Git sync with many changes uses targeted re-indexing of only modified files
- **Corruption Recovery**: System automatically rebuilds cache if validation fails

### Archive System: Physical Separation of Completed Work

The system implements a dedicated archiving mechanism that physically separates completed work from active items, following core GTD principles of maintaining a clean, uncluttered active workspace.

#### Archive Philosophy
- **Active vs Filed**: Distinction between `status: completed` (still active for review) and archived (permanently filed away)
- **Physical Separation**: Archived items moved to `archive/` directory, completely removed from active workspace
- **Mental Model**: Archive represents "basement filing cabinet" - accessible when needed but out of daily view
- **Performance Isolation**: Active system operates on subset of total cards for maximum speed

#### Archive Workflow
1. **Task Completion**: Individual tasks marked `status: completed` within active projects
2. **Project Completion**: Project cards marked `status: completed`, remain in active directories for weekly review
3. **Archiving Decision**: During review, user decides project is truly finished and no longer needs active visibility
4. **Archive Operation**: `archive_card(uuid)` moves card to `archive/YYYY/` with date-based organization
5. **System Result**: Card completely removed from active indexing and search results

#### Performance Benefits
- **Indexing**: System only indexes active cards (e.g., 500 active vs 5,000 total = 90% memory reduction)
- **Search Speed**: All queries run against smaller active-only index
- **Startup Time**: Faster server initialization with fewer files to process
- **Memory Usage**: Dramatic reduction in RAM footprint for large, long-term GTD systems

#### Archive Access
- **Default Behavior**: All operations (search, list, stats) exclude archived items by default
- **Optional Archive Search**: `--include-archive` flag enables searching archived items when needed
- **Archive-Only Operations**: Dedicated commands for archive-specific queries and maintenance

## Operation Execution Order

The system follows a strict execution order for all card operations to ensure predictable behavior and data integrity.

### Golden Rules
1. **Hooks Run Before Validation**: Hooks enrich/modify data before final validation
2. **Operations Must Be Atomic**: Complete success or complete failure - no partial changes saved

### Canonical Execution Sequence
1. **Prepare Data**: Load existing card (update/move) or apply defaults (create)
2. **Directory Transformation**: For move operations, apply new directory requirements
3. **Run Hooks**: Execute `on_before_validate` hooks to enrich/modify data
4. **Run Validation**: Validate entire final data object against applicable schemas
5. **Commit to Filesystem**: Write changes to disk only if validation passes
6. **Run Post-Save Hooks**: Execute `on_after_save` hooks (git commit, notifications)

### Operation-Specific Behavior

| Operation | Data Prep | Transform | Hooks | Validation | Filesystem | Post-Save | Failure Handling |
|-----------|-----------|-----------|-------|------------|------------|-----------|------------------|
| **Create** | Apply defaults | No | **Yes** | **Yes** | If valid | **Yes** | Atomic rollback |
| **Update** | Merge patch | No | **Yes** | **Yes** (entire card) | If valid | **Yes** | Atomic rollback |
| **Move** | Load existing | **Yes** (new dir rules) | **Yes** | **Yes** (new schema) | If valid | **Yes** | Atomic rollback |
| **Archive** | N/A | No | **No** (bypass) | **No** (bypass) | **Yes** (always) | **Yes** | N/A |
| **External Change** | Read from disk | No | **No** (bypass) | **Yes** (always) | N/A | **No** | Log as invalid |

### Error Handling
- **Hook Failures**: Process failures should include hook name and exception details, with no filesystem changes
- **Validation Failures**: Return structured validation details with no filesystem changes
- **Filesystem Failures**: Attempt rollback if partial changes occurred during operation

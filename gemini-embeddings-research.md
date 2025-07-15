# Gemini Embeddings-001 Research & Implementation Notes

## Overview

Google's `gemini-embedding-001` is a production-ready text embedding model announced July 2025, designed to convert text into 3072-dimensional vectors for semantic similarity tasks.

## What Are Embeddings?

**Embeddings** are numerical vector representations of text that capture semantic meaning. Unlike keyword matching, embeddings understand that "car" and "automobile" are related concepts.

**Example:**
```
Text: "What is machine learning?"
Embedding: [0.234, -0.567, 0.891, ...] (3072 numbers)
```

## Key Features & Specifications

### Technical Specs
- **Model ID**: `gemini-embedding-001`
- **Dimensions**: 3072 (default), flexible 128-3072
- **Max Input**: 2048 tokens
- **Languages**: 100+ supported
- **Technology**: Matryoshka Representation Learning (MRL)

### Performance
- **#1 on MTEB Multilingual leaderboard**
- **Domains**: Science, legal, finance, coding
- **Multilingual**: Strong cross-language performance

### Pricing & Availability
- **Cost**: $0.15 per 1M input tokens
- **Available**: Gemini API, Vertex AI, Google AI Studio
- **Launch**: July 14, 2025

## Comparison with Other Providers

| Provider | Model | Dimensions | Max Tokens | Pricing | Status |
|----------|-------|------------|------------|---------|--------|
| **Google** | `gemini-embedding-001` | 3072 (flexible) | 2048 | $0.15/1M | July 2025 |
| **OpenAI** | `text-embedding-3-large` | 3072 (flexible) | 8191 | $0.00013/1K | Jan 2024 |
| **OpenAI** | `text-embedding-3-small` | 1536 (flexible) | 8191 | 5x cheaper | Jan 2024 |
| **Anthropic** | None | - | - | - | Use Voyage AI |
| **Grok/xAI** | None (yet) | - | - | - | In development |

## Practical Use Cases

### 1. Semantic Search & Document Retrieval
```python
# Convert documents to embeddings
documents = ["Python guide", "ML basics", "Data structures"]
embeddings = [get_embedding(doc) for doc in documents]

# Search query
query = "How to code in Python?"
query_embedding = get_embedding(query)

# Find most similar
similarities = [cosine_similarity(query_embedding, doc_emb) for doc_emb in embeddings]
best_match = documents[similarities.index(max(similarities))]
```

### 2. RAG (Retrieval-Augmented Generation) Systems
```python
# 1. Index knowledge base
knowledge_base = ["Policy A", "Manual B", "FAQ C"]
embeddings_db = {doc: get_embedding(doc) for doc in knowledge_base}

# 2. User question
user_question = "What's the return policy?"
question_embedding = get_embedding(user_question)

# 3. Find relevant context
relevant_docs = find_similar_documents(question_embedding, embeddings_db)

# 4. Generate answer with context
answer = gemini_pro.generate(f"Context: {relevant_docs}\nQ: {user_question}")
```

### 3. Content Recommendation
```python
# User profile from reading history
user_articles = ["AI in healthcare", "Medical AI", "Neural networks in medicine"]
user_profile = average_embeddings([get_embedding(article) for article in user_articles])

# Recommend similar content
new_articles = ["Deep learning radiology", "Cooking", "AI ethics medicine"]
for article in new_articles:
    similarity = cosine_similarity(user_profile, get_embedding(article))
    print(f"{article}: {similarity}")
```

### 4. Document Organization & Deduplication
```python
# Check for duplicates
existing_content = ["How to bake bread", "Python tutorial", "Investment tips"]
new_content = "A guide to baking bread at home"

new_embedding = get_embedding(new_content)
for existing in existing_content:
    similarity = cosine_similarity(new_embedding, get_embedding(existing))
    if similarity > 0.85:
        print(f"Potential duplicate: {existing}")
```

### 5. Multilingual Content Matching
```python
# Works across 100+ languages
english_doc = "Climate change affects weather patterns"
spanish_doc = "El cambio climático afecta los patrones climáticos"
french_doc = "Le changement climatique affecte les modèles météorologiques"

# All will have similar embeddings despite different languages
embeddings = [get_embedding(doc) for doc in [english_doc, spanish_doc, french_doc]]
```

## Proposed MCP Framework API Design

### Core Functions
```python
@mcp.tool()
def get_embeddings(
    text: str,
    model: str = "gemini-embedding-001",
    dimensions: int = 3072
) -> dict:
    """Convert text to embedding vectors"""
    
@mcp.tool()
def search_documents(
    query: str,
    document_paths: List[str],
    top_k: int = 5,
    threshold: float = 0.7
) -> List[dict]:
    """Search documents using semantic similarity"""
    
@mcp.tool()
def index_documents(
    directory_path: str,
    file_patterns: List[str] = ["*.md", "*.txt"],
    output_index: str = "document_index.json"
) -> dict:
    """Create searchable index of documents"""
    
@mcp.tool()
def calculate_similarity(
    text1: str,
    text2: str,
    model: str = "gemini-embedding-001"
) -> dict:
    """Calculate similarity between two texts"""
```

## Personal Note Search Workflow

### Initial Setup
```bash
# Index your notes (one-time)
mcp__gemini__index_documents \
  directory_path="/home/user/notes" \
  file_patterns='["*.md", "*.txt", "*.org"]' \
  output_index="/home/user/.note_index.json"
```

### Daily Usage
```bash
# Semantic search
mcp__gemini__search_documents \
  query="machine learning hyperparameters" \
  document_paths='["/home/user/.note_index.json"]' \
  top_k=3

# Compare documents
mcp__gemini__calculate_similarity \
  text1="$(cat project-a.md)" \
  text2="$(cat project-b.md)"
```

### Advanced Workflows
```bash
# Multi-modal search with existing tools
mcp__gemini__search_documents query="react hooks patterns" top_k=5
mcp__gemini__ask \
  prompt="Generate custom hook based on these patterns" \
  files='["/home/user/notes/react-patterns.md"]'

# Code + documentation search
mcp__code2prompt__generate_prompt path="/project/src" output_file="/tmp/code.md"
mcp__gemini__search_documents \
  query="authentication middleware" \
  document_paths='["/tmp/code.md", "/home/user/docs/auth-notes.md"]'
```

## Integration with MCP Framework

### Location in Codebase
- **Path**: `src/mcp_handley_lab/llm/gemini/`
- **Extend existing**: Add to current Gemini tool
- **SDK**: Use existing `google-genai` integration
- **Patterns**: Follow FastMCP `@mcp.tool()` decorators

### Implementation Requirements
1. **API Integration**: Use `google-genai` SDK for embeddings
2. **Error Handling**: Consistent with existing tools
3. **Testing**: Unit tests + integration tests with VCR
4. **Documentation**: Update CLAUDE.md with new capabilities
5. **Version Management**: Use `python scripts/bump_version.py`

## Key Implementation Considerations

### Performance Optimizations
- **Caching**: Store embeddings locally to avoid recomputation
- **Chunking**: Handle large documents by splitting into chunks
- **Batch Processing**: Process multiple documents efficiently
- **Incremental Updates**: Only reindex changed files

### Data Management
- **Index Format**: JSON with file paths, embeddings, metadata
- **Storage**: Local filesystem with optional external vector DB
- **Backup**: Version index files for recovery

### User Experience
- **Fast Search**: Sub-second response for indexed documents
- **Relevance**: Tunable similarity thresholds
- **Context**: Show excerpts and line numbers in results
- **Integration**: Seamless with existing MCP tools

## Next Steps

1. **Get API Details**: Download official Gemini embedding API documentation
2. **Analyze Codebase**: Run code2prompt on current MCP framework
3. **Implementation Plan**: Ask Gemini to create detailed plan with code snippets
4. **Prototype**: Build minimal working version
5. **Testing**: Comprehensive unit and integration tests
6. **Documentation**: Update all relevant documentation

## Benefits for MCP Framework

- **Semantic Search**: Find relevant code/docs by meaning, not keywords
- **Knowledge Base**: Turn personal notes into searchable knowledge
- **Code Discovery**: Find similar functions/patterns across projects
- **Documentation**: Intelligent help system for tools and APIs
- **Research**: Organize and connect research notes effectively

This embedding capability would transform the MCP framework from a tool orchestrator into an intelligent knowledge management system.

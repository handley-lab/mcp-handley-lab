"""Integration tests for embeddings functionality using Gemini models via MCP protocol."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_handley_lab.llm.embeddings.tool import mcp


def skip_if_no_gemini_key():
    """Skip test if GEMINI_API_KEY is not available."""
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not available")


@pytest.mark.vcr
class TestGeminiEmbeddings:
    """Test Gemini embedding functionality via MCP protocol."""

    @pytest.mark.asyncio
    async def test_get_embeddings_single_text(self):
        """Test getting embeddings for a single text."""
        skip_if_no_gemini_key()

        _, result = await mcp.call_tool(
            "get_embeddings",
            {
                "texts": ["Hello, world!"],
                "model": "gemini-embedding-001",
            },
        )

        assert result["count"] == 1
        assert len(result["embeddings"][0]) > 0
        # Gemini embeddings are typically 768 dimensions for some models, 3072 for others
        assert len(result["embeddings"][0]) in [768, 3072]
        assert all(isinstance(x, float) for x in result["embeddings"][0])

    @pytest.mark.asyncio
    async def test_get_embeddings_multiple_texts(self):
        """Test getting embeddings for multiple texts."""
        skip_if_no_gemini_key()

        texts = ["Hello, world!", "Goodbye, world!", "Python programming"]
        _, result = await mcp.call_tool(
            "get_embeddings",
            {
                "texts": texts,
                "model": "gemini-embedding-001",
            },
        )

        assert result["count"] == 3
        for embedding in result["embeddings"]:
            assert len(embedding) > 0
            assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_get_embeddings_consistent_model(self):
        """Test embeddings are consistent for the same input."""
        skip_if_no_gemini_key()

        text = "Machine learning is fascinating"

        # Get embeddings twice
        _, result1 = await mcp.call_tool(
            "get_embeddings",
            {
                "texts": [text],
                "model": "gemini-embedding-001",
            },
        )

        _, result2 = await mcp.call_tool(
            "get_embeddings",
            {
                "texts": [text],
                "model": "gemini-embedding-001",
            },
        )

        assert result1["count"] == 1
        assert result2["count"] == 1
        # Same text should produce same embeddings
        assert result1["embeddings"][0] == result2["embeddings"][0]

    @pytest.mark.asyncio
    async def test_calculate_similarity_identical_texts(self):
        """Test similarity calculation for identical texts."""
        skip_if_no_gemini_key()

        text = "This is a test sentence."
        _, result = await mcp.call_tool(
            "calculate_similarity",
            {
                "text1": text,
                "text2": text,
                "model": "gemini-embedding-001",
            },
        )

        # Identical texts should have similarity very close to 1.0
        assert 0.99 <= result["similarity"] <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_similarity_different_texts(self):
        """Test similarity calculation for different texts."""
        skip_if_no_gemini_key()

        text1 = "I love programming in Python."
        text2 = "Cats are wonderful pets."
        _, result = await mcp.call_tool(
            "calculate_similarity",
            {
                "text1": text1,
                "text2": text2,
                "model": "gemini-embedding-001",
            },
        )

        # Different topics should have lower similarity
        assert 0.0 <= result["similarity"] <= 0.8

    @pytest.mark.asyncio
    async def test_calculate_similarity_related_texts(self):
        """Test similarity calculation for related texts."""
        skip_if_no_gemini_key()

        text1 = "Python is a programming language."
        text2 = "I enjoy coding in Python."
        _, result = await mcp.call_tool(
            "calculate_similarity",
            {
                "text1": text1,
                "text2": text2,
                "model": "gemini-embedding-001",
            },
        )

        # Related texts should have moderate to high similarity
        assert 0.3 <= result["similarity"] <= 1.0

    @pytest.mark.asyncio
    async def test_index_documents_and_search(self):
        """Test document indexing and search functionality."""
        skip_if_no_gemini_key()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test documents
            doc1_path = Path(temp_dir) / "doc1.txt"
            doc2_path = Path(temp_dir) / "doc2.txt"
            doc3_path = Path(temp_dir) / "doc3.txt"
            index_path = Path(temp_dir) / "index.json"

            doc1_path.write_text("Python is a versatile programming language.")
            doc2_path.write_text("Machine learning algorithms are fascinating.")
            doc3_path.write_text("Data science involves statistical analysis.")

            # Create index
            _, index_result = await mcp.call_tool(
                "index_documents",
                {
                    "document_paths": [str(doc1_path), str(doc2_path), str(doc3_path)],
                    "output_index_path": str(index_path),
                    "model": "gemini-embedding-001",
                },
            )

            # Verify index was created
            assert index_path.exists()
            assert index_result["document_count"] == 3
            with open(index_path) as f:
                index_data = json.load(f)
                assert len(index_data["documents"]) == 3

            # Test search
            _, search_result = await mcp.call_tool(
                "search_documents",
                {
                    "query": "programming languages",
                    "index_path": str(index_path),
                    "top_k": 2,
                    "model": "gemini-embedding-001",
                },
            )

            assert len(search_result["results"]) == 2
            # The Python document should be most relevant
            first_result_content = Path(search_result["results"][0]["path"]).read_text()
            assert "Python" in first_result_content

    @pytest.mark.asyncio
    async def test_get_embeddings_empty_input(self):
        """Test that empty input returns empty result."""
        skip_if_no_gemini_key()

        # Empty list returns empty result
        _, result = await mcp.call_tool(
            "get_embeddings",
            {
                "texts": [],
                "model": "gemini-embedding-001",
            },
        )
        assert result["embeddings"] == []
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_search_documents_nonexistent_index_error(self):
        """Test that searching non-existent index fails fast."""
        skip_if_no_gemini_key()

        with pytest.raises(ToolError, match="No such file or directory"):
            await mcp.call_tool(
                "search_documents",
                {
                    "query": "test",
                    "index_path": "/nonexistent/path/index.json",
                    "top_k": 5,
                    "model": "gemini-embedding-001",
                },
            )

    @pytest.mark.asyncio
    async def test_index_documents_nonexistent_file_error(self):
        """Test that indexing non-existent files fails fast."""
        skip_if_no_gemini_key()

        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "index.json"

            # This should fail fast when trying to read the non-existent file
            with pytest.raises(ToolError, match="No such file or directory"):
                await mcp.call_tool(
                    "index_documents",
                    {
                        "document_paths": ["/nonexistent/file.txt"],
                        "output_index_path": str(index_path),
                        "model": "gemini-embedding-001",
                    },
                )

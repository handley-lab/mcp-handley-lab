"""Integration tests for OpenAI embedding functionality."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from mcp_handley_lab.llm.openai.tool import mcp


def skip_if_no_openai_key():
    """Skip test if OPENAI_API_KEY is not available."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not available")


@pytest.mark.vcr
class TestOpenAIEmbeddings:
    """Test OpenAI embedding functionality."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_get_embeddings_single_text(self):
        """Test getting embeddings for a single text."""
        skip_if_no_openai_key()

        _, response = await mcp.call_tool(
            "get_embeddings",
            {
                "contents": "Hello, world!",
                "model": "text-embedding-3-small",
                "dimensions": 0,
            },
        )
        assert "error" not in response, response.get("error")
        result = response["result"]

        assert len(result) == 1
        assert len(result[0]["embedding"]) > 0
        # OpenAI text-embedding-3-small has 1536 dimensions
        assert len(result[0]["embedding"]) == 1536
        assert all(isinstance(x, float) for x in result[0]["embedding"])

    @pytest.mark.asyncio
    async def test_get_embeddings_multiple_texts(self):
        """Test getting embeddings for multiple texts."""
        skip_if_no_openai_key()

        texts = ["Hello, world!", "Goodbye, world!", "Python programming"]
        _, response = await mcp.call_tool(
            "get_embeddings",
            {"contents": texts, "model": "text-embedding-3-small", "dimensions": 0},
        )
        assert "error" not in response, response.get("error")
        result = response["result"]

        assert len(result) == 3
        for embedding_result in result:
            assert len(embedding_result["embedding"]) == 1536
            assert all(isinstance(x, float) for x in embedding_result["embedding"])

    @pytest.mark.asyncio
    async def test_get_embeddings_different_models(self):
        """Test embeddings with different models."""
        skip_if_no_openai_key()

        text = "Machine learning is fascinating"

        # Test text-embedding-3-small (default)
        _, small_response = await mcp.call_tool(
            "get_embeddings",
            {"contents": text, "model": "text-embedding-3-small", "dimensions": 0},
        )
        assert "error" not in small_response, small_response.get("error")
        small_result = small_response["result"]

        # Test text-embedding-3-large
        _, large_response = await mcp.call_tool(
            "get_embeddings",
            {"contents": text, "model": "text-embedding-3-large", "dimensions": 0},
        )
        assert "error" not in large_response, large_response.get("error")
        large_result = large_response["result"]

        assert len(small_result) == 1
        assert len(large_result) == 1
        assert len(small_result[0]["embedding"]) == 1536
        assert len(large_result[0]["embedding"]) == 3072
        # Embeddings should be different between models
        assert small_result[0]["embedding"] != large_result[0]["embedding"]

    @pytest.mark.asyncio
    async def test_get_embeddings_with_dimensions(self):
        """Test embeddings with dimensions parameter (v3 models only)."""
        skip_if_no_openai_key()

        text = "Test dimensions parameter"

        # Test with reduced dimensions for text-embedding-3-large
        _, response = await mcp.call_tool(
            "get_embeddings",
            {"contents": text, "model": "text-embedding-3-large", "dimensions": 1024},
        )
        assert "error" not in response, response.get("error")
        result = response["result"]

        assert len(result) == 1
        # Should be reduced to 1024 dimensions
        assert len(result[0]["embedding"]) == 1024
        assert all(isinstance(x, float) for x in result[0]["embedding"])

    @pytest.mark.asyncio
    async def test_calculate_similarity_identical_texts(self):
        """Test similarity calculation for identical texts."""
        skip_if_no_openai_key()

        text = "This is a test sentence."
        _, response = await mcp.call_tool(
            "calculate_similarity",
            {"text1": text, "text2": text, "model": "text-embedding-3-small"},
        )
        assert "error" not in response, response.get("error")
        result = response

        # Identical texts should have similarity very close to 1.0
        assert 0.99 <= result["similarity"] <= 1.0

    @pytest.mark.asyncio
    async def test_calculate_similarity_different_texts(self):
        """Test similarity calculation for different texts."""
        skip_if_no_openai_key()

        text1 = "I love programming in Python."
        text2 = "Cats are wonderful pets."
        _, response = await mcp.call_tool(
            "calculate_similarity",
            {"text1": text1, "text2": text2, "model": "text-embedding-3-small"},
        )
        assert "error" not in response, response.get("error")
        result = response

        # Different texts should have lower similarity
        assert -1.0 <= result["similarity"] <= 1.0
        assert result["similarity"] < 0.8  # Should be reasonably different

    @pytest.mark.asyncio
    async def test_calculate_similarity_related_texts(self):
        """Test similarity calculation for related texts."""
        skip_if_no_openai_key()

        text1 = "Machine learning is a subset of artificial intelligence."
        text2 = "AI and machine learning are closely related fields."
        _, response = await mcp.call_tool(
            "calculate_similarity",
            {"text1": text1, "text2": text2, "model": "text-embedding-3-small"},
        )
        assert "error" not in response, response.get("error")
        result = response

        # Related texts should have higher similarity
        assert result["similarity"] > 0.5

    @pytest.mark.asyncio
    async def test_index_documents_and_search(self):
        """Test document indexing and search functionality."""
        skip_if_no_openai_key()

        # Create temporary documents
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test documents
            doc1_path = temp_path / "doc1.txt"
            doc2_path = temp_path / "doc2.txt"
            doc3_path = temp_path / "doc3.txt"

            doc1_path.write_text("Python is a programming language.")
            doc2_path.write_text("Machine learning uses algorithms to learn from data.")
            doc3_path.write_text("Cats are domestic animals that make great pets.")

            # Create index
            index_path = temp_path / "test_index.json"
            _, index_response = await mcp.call_tool(
                "index_documents",
                {
                    "document_paths": [str(doc1_path), str(doc2_path), str(doc3_path)],
                    "output_index_path": str(index_path),
                    "model": "text-embedding-3-small",
                },
            )
            assert "error" not in index_response, index_response.get("error")
            index_result = index_response

            # Verify index creation
            assert index_result["files_indexed"] == 3
            assert Path(index_result["index_path"]).exists()
            assert "Successfully indexed 3 files" in index_result["message"]

            # Load and verify index structure
            with open(index_path) as f:
                index_data = json.load(f)
            assert len(index_data) == 3
            for item in index_data:
                assert "path" in item
                assert "embedding" in item
                assert len(item["embedding"]) == 1536  # OpenAI default dimensions

            # Test search functionality
            _, search_response = await mcp.call_tool(
                "search_documents",
                {
                    "query": "programming language",
                    "index_path": str(index_path),
                    "top_k": 2,
                    "model": "text-embedding-3-small",
                },
            )
            assert "error" not in search_response, search_response.get("error")
            search_results = search_response["result"]

            assert len(search_results) <= 2
            # First result should be the Python document (most relevant)
            assert str(doc1_path) in search_results[0]["path"]
            assert search_results[0]["similarity_score"] > 0.0

            # Search for different topic
            _, search_response2 = await mcp.call_tool(
                "search_documents",
                {
                    "query": "animals pets",
                    "index_path": str(index_path),
                    "top_k": 1,
                    "model": "text-embedding-3-small",
                },
            )
            assert "error" not in search_response2, search_response2.get("error")
            search_results2 = search_response2["result"]

            assert len(search_results2) == 1
            # Should find the cats document
            assert str(doc3_path) in search_results2[0]["path"]

    @pytest.mark.asyncio
    async def test_get_embeddings_empty_input_error(self):
        """Test that empty input raises appropriate error."""
        skip_if_no_openai_key()

        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="Contents list cannot be empty"):
            await mcp.call_tool(
                "get_embeddings",
                {"contents": [], "model": "text-embedding-3-small", "dimensions": 0},
            )

    @pytest.mark.asyncio
    async def test_calculate_similarity_empty_text_error(self):
        """Test that empty text raises appropriate error."""
        skip_if_no_openai_key()

        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="Both text1 and text2 must be provided"):
            await mcp.call_tool(
                "calculate_similarity",
                {"text1": "", "text2": "test", "model": "text-embedding-3-small"},
            )

        with pytest.raises(ToolError, match="Both text1 and text2 must be provided"):
            await mcp.call_tool(
                "calculate_similarity",
                {"text1": "test", "text2": "", "model": "text-embedding-3-small"},
            )

    @pytest.mark.asyncio
    async def test_search_documents_nonexistent_index_error(self):
        """Test that searching non-existent index fails fast."""
        skip_if_no_openai_key()

        from mcp.server.fastmcp.exceptions import ToolError

        with pytest.raises(ToolError, match="No such file or directory"):
            await mcp.call_tool(
                "search_documents",
                {
                    "query": "test",
                    "index_path": "/nonexistent/path/index.json",
                    "top_k": 5,
                    "model": "text-embedding-3-small",
                },
            )

    @pytest.mark.asyncio
    async def test_index_documents_nonexistent_file_error(self):
        """Test that indexing non-existent files fails fast."""
        skip_if_no_openai_key()

        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "index.json"

            # This should fail fast when trying to read the non-existent file
            from mcp.server.fastmcp.exceptions import ToolError

            with pytest.raises(ToolError, match="No such file or directory"):
                await mcp.call_tool(
                    "index_documents",
                    {
                        "document_paths": ["/nonexistent/file.txt"],
                        "output_index_path": str(index_path),
                        "model": "text-embedding-3-small",
                    },
                )

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_different_models_compatibility(self):
        """Test that different embedding models work correctly."""
        skip_if_no_openai_key()

        text = "Test model compatibility"

        # Test legacy ada-002 model
        _, ada_response = await mcp.call_tool(
            "get_embeddings",
            {"contents": text, "model": "text-embedding-ada-002", "dimensions": 0},
        )
        assert "error" not in ada_response, ada_response.get("error")
        ada_result = ada_response["result"]
        assert len(ada_result[0]["embedding"]) == 1536

        # Test new v3 small model
        _, small_response = await mcp.call_tool(
            "get_embeddings",
            {"contents": text, "model": "text-embedding-3-small", "dimensions": 0},
        )
        assert "error" not in small_response, small_response.get("error")
        small_result = small_response["result"]
        assert len(small_result[0]["embedding"]) == 1536

        # Test new v3 large model
        _, large_response = await mcp.call_tool(
            "get_embeddings",
            {"contents": text, "model": "text-embedding-3-large", "dimensions": 0},
        )
        assert "error" not in large_response, large_response.get("error")
        large_result = large_response["result"]
        assert len(large_result[0]["embedding"]) == 3072

        # Verify all embeddings are different
        assert ada_result[0]["embedding"] != small_result[0]["embedding"]
        assert small_result[0]["embedding"] != large_result[0]["embedding"]

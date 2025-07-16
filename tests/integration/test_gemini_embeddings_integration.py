"""Integration tests for Gemini embedding functionality."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from mcp_handley_lab.llm.gemini.tool import (
    calculate_similarity,
    get_embeddings,
    index_documents,
    search_documents,
)


def skip_if_no_gemini_key():
    """Skip test if GEMINI_API_KEY is not available."""
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not available")


@pytest.mark.vcr
class TestGeminiEmbeddings:
    """Test Gemini embedding functionality."""

    def test_get_embeddings_single_text(self):
        """Test getting embeddings for a single text."""
        skip_if_no_gemini_key()

        result = get_embeddings("Hello, world!")

        assert len(result) == 1
        assert len(result[0].embedding) > 0
        # Gemini embeddings are typically 768 dimensions for some models, 3072 for others
        assert len(result[0].embedding) in [768, 3072]
        assert all(isinstance(x, float) for x in result[0].embedding)

    def test_get_embeddings_multiple_texts(self):
        """Test getting embeddings for multiple texts."""
        skip_if_no_gemini_key()

        texts = ["Hello, world!", "Goodbye, world!", "Python programming"]
        result = get_embeddings(texts)

        assert len(result) == 3
        for embedding_result in result:
            assert len(embedding_result.embedding) > 0
            assert all(isinstance(x, float) for x in embedding_result.embedding)

    def test_get_embeddings_different_task_types(self):
        """Test embeddings with different task types."""
        skip_if_no_gemini_key()

        text = "Machine learning is fascinating"

        # Test different task types
        similarity_result = get_embeddings(text, task_type="SEMANTIC_SIMILARITY")
        retrieval_result = get_embeddings(text, task_type="RETRIEVAL_DOCUMENT")

        assert len(similarity_result) == 1
        assert len(retrieval_result) == 1
        # Embeddings should be different for different task types
        assert similarity_result[0].embedding != retrieval_result[0].embedding

    def test_calculate_similarity_identical_texts(self):
        """Test similarity calculation for identical texts."""
        skip_if_no_gemini_key()

        text = "This is a test sentence."
        result = calculate_similarity(text, text)

        # Identical texts should have similarity very close to 1.0
        assert 0.99 <= result.similarity <= 1.0

    def test_calculate_similarity_different_texts(self):
        """Test similarity calculation for different texts."""
        skip_if_no_gemini_key()

        text1 = "I love programming in Python."
        text2 = "Cats are wonderful pets."
        result = calculate_similarity(text1, text2)

        # Different texts should have lower similarity
        assert -1.0 <= result.similarity <= 1.0
        assert result.similarity < 0.8  # Should be reasonably different

    def test_calculate_similarity_related_texts(self):
        """Test similarity calculation for related texts."""
        skip_if_no_gemini_key()

        text1 = "Machine learning is a subset of artificial intelligence."
        text2 = "AI and machine learning are closely related fields."
        result = calculate_similarity(text1, text2)

        # Related texts should have higher similarity
        assert result.similarity > 0.5

    def test_index_documents_and_search(self):
        """Test document indexing and search functionality."""
        skip_if_no_gemini_key()

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
            index_result = index_documents(
                document_paths=[str(doc1_path), str(doc2_path), str(doc3_path)],
                output_index_path=str(index_path),
            )

            # Verify index creation
            assert index_result.files_indexed == 3
            assert Path(index_result.index_path).exists()
            assert "Successfully indexed 3 files" in index_result.message

            # Load and verify index structure
            with open(index_path) as f:
                index_data = json.load(f)
            assert len(index_data) == 3
            for item in index_data:
                assert "path" in item
                assert "embedding" in item
                assert len(item["embedding"]) > 0

            # Test search functionality
            search_results = search_documents(
                query="programming language", index_path=str(index_path), top_k=2
            )

            assert len(search_results) <= 2
            # First result should be the Python document (most relevant)
            assert str(doc1_path) in search_results[0].path
            assert search_results[0].similarity_score > 0.0

            # Search for different topic
            search_results2 = search_documents(
                query="animals pets", index_path=str(index_path), top_k=1
            )

            assert len(search_results2) == 1
            # Should find the cats document
            assert str(doc3_path) in search_results2[0].path

    def test_get_embeddings_empty_input_error(self):
        """Test that empty input raises appropriate error."""
        skip_if_no_gemini_key()

        with pytest.raises(ValueError, match="Contents list cannot be empty"):
            get_embeddings([])

    def test_calculate_similarity_empty_text_error(self):
        """Test that empty text raises appropriate error."""
        skip_if_no_gemini_key()

        with pytest.raises(ValueError, match="Both text1 and text2 must be provided"):
            calculate_similarity("", "test")

        with pytest.raises(ValueError, match="Both text1 and text2 must be provided"):
            calculate_similarity("test", "")

    def test_search_documents_nonexistent_index_error(self):
        """Test that searching non-existent index fails fast."""
        skip_if_no_gemini_key()

        with pytest.raises(FileNotFoundError):
            search_documents(query="test", index_path="/nonexistent/path/index.json")

    def test_index_documents_nonexistent_file_error(self):
        """Test that indexing non-existent files fails fast."""
        skip_if_no_gemini_key()

        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = Path(temp_dir) / "index.json"

            # This should fail fast when trying to read the non-existent file
            with pytest.raises(FileNotFoundError):
                index_documents(
                    document_paths=["/nonexistent/file.txt"],
                    output_index_path=str(index_path),
                )

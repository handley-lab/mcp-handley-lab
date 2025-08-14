"""Integration tests for Gemini embedding functionality (sync version)."""

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
    """Test Gemini embedding functionality (sync version)."""

    def test_get_embeddings_single_text(self):
        """Test getting embeddings for a single text."""
        skip_if_no_gemini_key()

        result = get_embeddings(
            contents="Hello, world!",
            model="gemini-embedding-001",
            task_type="SEMANTIC_SIMILARITY",
            output_dimensionality=0,
        )

        assert len(result) == 1
        assert len(result[0].embedding) > 0
        # Gemini embeddings are typically 768 dimensions for some models, 3072 for others
        assert len(result[0].embedding) in [768, 3072]
        assert all(isinstance(x, float) for x in result[0].embedding)

    def test_get_embeddings_multiple_texts(self):
        """Test getting embeddings for multiple texts."""
        skip_if_no_gemini_key()

        texts = ["Hello, world!", "Goodbye, world!", "Python programming"]
        result = get_embeddings(
            contents=texts,
            model="gemini-embedding-001",
            task_type="SEMANTIC_SIMILARITY",
            output_dimensionality=0,
        )

        assert len(result) == 3
        for embedding_result in result:
            assert len(embedding_result.embedding) > 0
            assert all(isinstance(x, float) for x in embedding_result.embedding)

    def test_get_embeddings_different_task_types(self):
        """Test embeddings with different task types."""
        skip_if_no_gemini_key()

        text = "Machine learning is fascinating"

        # Test different task types
        similarity_result = get_embeddings(
            contents=text,
            model="gemini-embedding-001",
            task_type="SEMANTIC_SIMILARITY",
            output_dimensionality=0,
        )

        retrieval_result = get_embeddings(
            contents=text,
            model="gemini-embedding-001",
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=0,
        )

        assert len(similarity_result) == 1
        assert len(retrieval_result) == 1
        # Embeddings should be different for different task types
        assert similarity_result[0].embedding != retrieval_result[0].embedding

    def test_calculate_similarity_identical_texts(self):
        """Test similarity calculation for identical texts."""
        skip_if_no_gemini_key()

        text = "This is a test sentence."
        result = calculate_similarity(
            text1=text, text2=text, model="gemini-embedding-001"
        )

        # Identical texts should have similarity very close to 1.0
        assert 0.99 <= result.similarity <= 1.0

    def test_calculate_similarity_different_texts(self):
        """Test similarity calculation for different texts."""
        skip_if_no_gemini_key()

        text1 = "I love programming in Python."
        text2 = "Cats are wonderful pets."
        result = calculate_similarity(
            text1=text1, text2=text2, model="gemini-embedding-001"
        )

        # Different topics should have lower similarity
        assert 0.0 <= result.similarity <= 0.8

    def test_calculate_similarity_related_texts(self):
        """Test similarity calculation for related texts."""
        skip_if_no_gemini_key()

        text1 = "Python is a programming language."
        text2 = "I enjoy coding in Python."
        result = calculate_similarity(
            text1=text1, text2=text2, model="gemini-embedding-001"
        )

        # Related texts should have moderate to high similarity
        assert 0.3 <= result.similarity <= 1.0

    def test_index_documents_and_search(self):
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
            index_documents(
                document_paths=[str(doc1_path), str(doc2_path), str(doc3_path)],
                output_index_path=str(index_path),
                model="gemini-embedding-001",
            )

            # Verify index was created
            assert index_path.exists()
            with open(index_path) as f:
                index_data = json.load(f)
                assert len(index_data) == 3

            # Test search
            results = search_documents(
                query="programming languages",
                index_path=str(index_path),
                top_k=2,
                model="gemini-embedding-001",
            )

            assert len(results) == 2
            # The Python document should be most relevant
            first_result_content = Path(results[0].path).read_text()
            assert "Python" in first_result_content

    def test_get_embeddings_empty_input_error(self):
        """Test that empty input raises appropriate error."""
        skip_if_no_gemini_key()

        with pytest.raises(ValueError, match="Contents list cannot be empty"):
            get_embeddings(
                contents=[],
                model="gemini-embedding-001",
                task_type="SEMANTIC_SIMILARITY",
                output_dimensionality=0,
            )

    def test_calculate_similarity_empty_text_error(self):
        """Test that empty text raises appropriate error."""
        skip_if_no_gemini_key()

        with pytest.raises(ValueError, match="Both text1 and text2 must be provided"):
            calculate_similarity(text1="", text2="test", model="gemini-embedding-001")

        with pytest.raises(ValueError, match="Both text1 and text2 must be provided"):
            calculate_similarity(text1="test", text2="", model="gemini-embedding-001")

    def test_search_documents_nonexistent_index_error(self):
        """Test that searching non-existent index fails fast."""
        skip_if_no_gemini_key()

        with pytest.raises(FileNotFoundError):
            search_documents(
                query="test",
                index_path="/nonexistent/path/index.json",
                top_k=5,
                model="gemini-embedding-001",
            )

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
                    model="gemini-embedding-001",
                )

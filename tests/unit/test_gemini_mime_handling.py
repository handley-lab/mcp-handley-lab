"""Tests for Gemini MIME type handling and fallback logic."""
import tempfile
from pathlib import Path

from mcp_handley_lab.llm.common import (
    determine_mime_type,
    get_gemini_safe_mime_type,
    is_gemini_mime_error,
    is_gemini_supported_mime_type,
    is_text_file,
)


class TestMimeTypeDetection:
    """Test MIME type detection for various file extensions."""

    def test_supported_mime_types(self):
        """Test detection of supported MIME types."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            assert determine_mime_type(Path(f.name)) == "text/plain"

        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            assert determine_mime_type(Path(f.name)) == "application/pdf"

        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            assert determine_mime_type(Path(f.name)) == "image/png"

    def test_unsupported_text_mime_types(self):
        """Test detection of unsupported text MIME types."""
        with tempfile.NamedTemporaryFile(suffix=".tex") as f:
            assert determine_mime_type(Path(f.name)) == "application/x-tex"

        with tempfile.NamedTemporaryFile(suffix=".patch") as f:
            assert determine_mime_type(Path(f.name)) == "text/x-patch"

        with tempfile.NamedTemporaryFile(suffix=".diff") as f:
            assert determine_mime_type(Path(f.name)) == "text/x-diff"

        with tempfile.NamedTemporaryFile(suffix=".yaml") as f:
            assert determine_mime_type(Path(f.name)) == "text/x-yaml"

    def test_unknown_extension_fallback(self):
        """Test fallback for unknown file extensions."""
        with tempfile.NamedTemporaryFile(suffix=".unknown") as f:
            assert determine_mime_type(Path(f.name)) == "application/octet-stream"


class TestGeminiSupportedMimeTypes:
    """Test the Gemini supported MIME type checker."""

    def test_supported_document_types(self):
        """Test supported document MIME types."""
        assert is_gemini_supported_mime_type("text/plain") is True
        assert is_gemini_supported_mime_type("application/pdf") is True

    def test_supported_image_types(self):
        """Test supported image MIME types."""
        assert is_gemini_supported_mime_type("image/png") is True
        assert is_gemini_supported_mime_type("image/jpeg") is True
        assert is_gemini_supported_mime_type("image/webp") is True

    def test_supported_audio_types(self):
        """Test supported audio MIME types."""
        assert is_gemini_supported_mime_type("audio/mp3") is True
        assert is_gemini_supported_mime_type("audio/wav") is True
        assert is_gemini_supported_mime_type("audio/flac") is True

    def test_supported_video_types(self):
        """Test supported video MIME types."""
        assert is_gemini_supported_mime_type("video/mp4") is True
        assert is_gemini_supported_mime_type("video/avi") is True
        assert is_gemini_supported_mime_type("video/webm") is True

    def test_unsupported_types(self):
        """Test unsupported MIME types."""
        assert is_gemini_supported_mime_type("application/x-tex") is False
        assert is_gemini_supported_mime_type("text/x-patch") is False
        assert is_gemini_supported_mime_type("text/x-diff") is False
        assert is_gemini_supported_mime_type("text/x-yaml") is False
        assert is_gemini_supported_mime_type("application/octet-stream") is False


class TestTextFileDetection:
    """Test text file detection logic."""

    def test_common_text_extensions(self):
        """Test detection of common text file extensions."""
        text_extensions = [".txt", ".md", ".py", ".js", ".html", ".css", ".json"]
        for ext in text_extensions:
            with tempfile.NamedTemporaryFile(suffix=ext) as f:
                assert is_text_file(Path(f.name)) is True

    def test_code_file_extensions(self):
        """Test detection of code file extensions."""
        code_extensions = [".c", ".cpp", ".java", ".php", ".sql", ".rs", ".go", ".rb"]
        for ext in code_extensions:
            with tempfile.NamedTemporaryFile(suffix=ext) as f:
                assert is_text_file(Path(f.name)) is True

    def test_special_text_extensions(self):
        """Test detection of special text file extensions."""
        special_extensions = [".tex", ".patch", ".diff", ".yaml", ".yml", ".toml"]
        for ext in special_extensions:
            with tempfile.NamedTemporaryFile(suffix=ext) as f:
                assert is_text_file(Path(f.name)) is True

    def test_binary_file_extensions(self):
        """Test that binary files are not detected as text."""
        binary_extensions = [".exe", ".bin", ".jpg", ".mp4", ".zip"]
        for ext in binary_extensions:
            with tempfile.NamedTemporaryFile(suffix=ext) as f:
                assert is_text_file(Path(f.name)) is False


class TestGeminiSafeMimeType:
    """Test the Gemini safe MIME type conversion logic."""

    def test_already_supported_types_unchanged(self):
        """Test that already supported types are returned unchanged."""
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            path = Path(f.name)
            assert get_gemini_safe_mime_type(path) == "text/plain"

        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            path = Path(f.name)
            assert get_gemini_safe_mime_type(path) == "application/pdf"

        with tempfile.NamedTemporaryFile(suffix=".png") as f:
            path = Path(f.name)
            assert get_gemini_safe_mime_type(path) == "image/png"

    def test_unsupported_text_types_converted(self):
        """Test that unsupported text types are converted to text/plain."""
        with tempfile.NamedTemporaryFile(suffix=".tex") as f:
            path = Path(f.name)
            # Original would be application/x-tex, but should convert to text/plain
            assert get_gemini_safe_mime_type(path) == "text/plain"

        with tempfile.NamedTemporaryFile(suffix=".patch") as f:
            path = Path(f.name)
            # Original would be text/x-patch, but should convert to text/plain
            assert get_gemini_safe_mime_type(path) == "text/plain"

        with tempfile.NamedTemporaryFile(suffix=".yaml") as f:
            path = Path(f.name)
            # Original would be text/x-yaml, but should convert to text/plain
            assert get_gemini_safe_mime_type(path) == "text/plain"

    def test_binary_types_unchanged(self):
        """Test that binary types are left unchanged."""
        with tempfile.NamedTemporaryFile(suffix=".unknown") as f:
            path = Path(f.name)
            # Should remain as application/octet-stream (let Gemini handle rejection)
            assert get_gemini_safe_mime_type(path) == "application/octet-stream"


class TestGeminiErrorDetection:
    """Test Gemini error message detection."""

    def test_mime_error_detection(self):
        """Test detection of MIME type error messages."""
        error_msg1 = "400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'Unsupported MIME type: application/x-tex', 'status': 'INVALID_ARGUMENT'}}"
        assert is_gemini_mime_error(error_msg1) is True

        error_msg2 = "Unsupported MIME type: text/x-patch"
        assert is_gemini_mime_error(error_msg2) is True

    def test_non_mime_error_detection(self):
        """Test that non-MIME errors are not detected as MIME errors."""
        error_msg1 = "The input token count (1786223) exceeds the maximum number of tokens allowed"
        assert is_gemini_mime_error(error_msg1) is False

        error_msg2 = "Authentication failed"
        assert is_gemini_mime_error(error_msg2) is False

        error_msg3 = "File not found"
        assert is_gemini_mime_error(error_msg3) is False


class TestExtensionToMimeMappings:
    """Test specific extension to MIME type mappings."""

    def test_latex_files(self):
        """Test LaTeX file MIME type handling."""
        with tempfile.NamedTemporaryFile(suffix=".tex") as f:
            path = Path(f.name)
            # Should be detected as text file
            assert is_text_file(path) is True
            # Original MIME type should be application/x-tex
            assert determine_mime_type(path) == "application/x-tex"
            # Should not be supported by Gemini
            assert is_gemini_supported_mime_type("application/x-tex") is False
            # Should convert to text/plain
            assert get_gemini_safe_mime_type(path) == "text/plain"

    def test_patch_files(self):
        """Test patch file MIME type handling."""
        with tempfile.NamedTemporaryFile(suffix=".patch") as f:
            path = Path(f.name)
            assert is_text_file(path) is True
            assert determine_mime_type(path) == "text/x-patch"
            assert is_gemini_supported_mime_type("text/x-patch") is False
            assert get_gemini_safe_mime_type(path) == "text/plain"

    def test_diff_files(self):
        """Test diff file MIME type handling."""
        with tempfile.NamedTemporaryFile(suffix=".diff") as f:
            path = Path(f.name)
            assert is_text_file(path) is True
            assert determine_mime_type(path) == "text/x-diff"
            assert is_gemini_supported_mime_type("text/x-diff") is False
            assert get_gemini_safe_mime_type(path) == "text/plain"

    def test_yaml_files(self):
        """Test YAML file MIME type handling."""
        with tempfile.NamedTemporaryFile(suffix=".yml") as f:
            path = Path(f.name)
            assert is_text_file(path) is True
            assert determine_mime_type(path) == "text/x-yaml"
            assert is_gemini_supported_mime_type("text/x-yaml") is False
            assert get_gemini_safe_mime_type(path) == "text/plain"

    def test_shell_script_files(self):
        """Test shell script file MIME type handling."""
        with tempfile.NamedTemporaryFile(suffix=".sh") as f:
            path = Path(f.name)
            assert is_text_file(path) is True
            assert determine_mime_type(path) == "text/x-shellscript"
            assert is_gemini_supported_mime_type("text/x-shellscript") is False
            assert get_gemini_safe_mime_type(path) == "text/plain"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_case_insensitive_extensions(self):
        """Test that file extensions are handled case-insensitively."""
        with tempfile.NamedTemporaryFile(suffix=".TEX") as f:
            path = Path(f.name)
            # Should still be detected as LaTeX despite uppercase
            assert determine_mime_type(path) == "application/x-tex"
            assert get_gemini_safe_mime_type(path) == "text/plain"

        with tempfile.NamedTemporaryFile(suffix=".Patch") as f:
            path = Path(f.name)
            assert determine_mime_type(path) == "text/x-patch"
            assert get_gemini_safe_mime_type(path) == "text/plain"

    def test_no_extension_files(self):
        """Test handling of files with no extension."""
        with tempfile.NamedTemporaryFile() as f:
            path = Path(f.name)
            # Should default to application/octet-stream
            assert determine_mime_type(path) == "application/octet-stream"
            # Should not be detected as text file without extension
            assert is_text_file(path) is False
            # Should remain unchanged (binary fallback)
            assert get_gemini_safe_mime_type(path) == "application/octet-stream"

    def test_multiple_extensions(self):
        """Test files with multiple extensions."""
        with tempfile.NamedTemporaryFile(suffix=".backup.tex") as f:
            path = Path(f.name)
            # Should use the last extension (.tex)
            assert determine_mime_type(path) == "application/x-tex"
            assert get_gemini_safe_mime_type(path) == "text/plain"

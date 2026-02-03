"""Tests for render error messaging improvements.

Tests for GitHub issue #216: render fails with large embedded images.
These tests mock subprocess to simulate various failure scenarios and
verify the improved error messages.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from mcp_handley_lab.microsoft.common.render import (
    _convert_to_pdf,
    _find_pdf_output,
    render_pages_to_images,
)


class TestConvertToPdfErrors:
    """Tests for _convert_to_pdf error handling."""

    def test_libreoffice_not_found(self, tmp_path):
        """FileNotFoundError gives clear install message."""
        doc_path = tmp_path / "test.docx"
        doc_path.touch()

        with patch(
            "mcp_handley_lab.microsoft.common.render.subprocess.run"
        ) as mock_run:
            mock_run.side_effect = FileNotFoundError("libreoffice")

            with pytest.raises(RuntimeError) as exc_info:
                _convert_to_pdf(doc_path, tmp_path, timeout=60)

            assert "libreoffice not found" in str(exc_info.value)
            assert "Install LibreOffice" in str(exc_info.value)

    def test_timeout_expired(self, tmp_path):
        """TimeoutExpired gives clear timeout message."""
        doc_path = tmp_path / "test.docx"
        doc_path.touch()

        with patch(
            "mcp_handley_lab.microsoft.common.render.subprocess.run"
        ) as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("libreoffice", 60)

            with pytest.raises(RuntimeError) as exc_info:
                _convert_to_pdf(doc_path, tmp_path, timeout=60)

            assert "timed out" in str(exc_info.value)
            assert "large embedded images" in str(exc_info.value)

    def test_called_process_error_with_image_hint(self, tmp_path):
        """CalledProcessError with image-related stderr gives image hint."""
        doc_path = tmp_path / "test.docx"
        doc_path.touch()

        with patch(
            "mcp_handley_lab.microsoft.common.render.subprocess.run"
        ) as mock_run:
            error = subprocess.CalledProcessError(
                returncode=1, cmd="libreoffice", stderr="Unable to compress image data"
            )
            mock_run.side_effect = error

            with pytest.raises(RuntimeError) as exc_info:
                _convert_to_pdf(doc_path, tmp_path, timeout=60)

            msg = str(exc_info.value)
            assert "Unable to compress image" in msg
            assert "Large embedded images" in msg
            assert "compressing images" in msg

    def test_called_process_error_generic(self, tmp_path):
        """CalledProcessError without image-related stderr gives generic hint."""
        doc_path = tmp_path / "test.docx"
        doc_path.touch()

        with patch(
            "mcp_handley_lab.microsoft.common.render.subprocess.run"
        ) as mock_run:
            error = subprocess.CalledProcessError(
                returncode=1, cmd="libreoffice", stderr="Unknown error occurred"
            )
            mock_run.side_effect = error

            with pytest.raises(RuntimeError) as exc_info:
                _convert_to_pdf(doc_path, tmp_path, timeout=60)

            msg = str(exc_info.value)
            assert "Unknown error" in msg
            assert "corruption or unsupported features" in msg


class TestFindPdfOutput:
    """Tests for _find_pdf_output error handling."""

    def test_no_pdf_output(self, tmp_path):
        """No PDF output gives clear error message."""
        with pytest.raises(RuntimeError) as exc_info:
            _find_pdf_output(tmp_path, "nonexistent")

        assert "no output" in str(exc_info.value).lower()
        assert "corrupted or contain unsupported features" in str(exc_info.value)

    def test_expected_pdf_found(self, tmp_path):
        """Expected PDF is found correctly."""
        pdf_path = tmp_path / "test.pdf"
        pdf_path.touch()

        result = _find_pdf_output(tmp_path, "test")
        assert result == pdf_path

    def test_fallback_to_single_pdf(self, tmp_path):
        """Falls back to single PDF if name doesn't match exactly."""
        pdf_path = tmp_path / "different_name.pdf"
        pdf_path.touch()

        result = _find_pdf_output(tmp_path, "test")
        assert result == pdf_path


class TestRenderPagesToImagesErrors:
    """Tests for render_pages_to_images error handling."""

    def test_page_not_found_message(self, tmp_path):
        """Page not found gives clear error message."""
        doc_path = tmp_path / "test.docx"
        doc_path.touch()

        # Mock _convert_to_pdf to succeed and create a valid PDF
        mock_pdf = tmp_path / "test.pdf"
        mock_pdf.touch()

        with patch(
            "mcp_handley_lab.microsoft.common.render._convert_to_pdf"
        ) as mock_convert:
            mock_convert.return_value = mock_pdf

            # Mock pdftoppm to succeed but not create the expected PNG
            with patch(
                "mcp_handley_lab.microsoft.common.render.subprocess.run"
            ) as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                with pytest.raises(ValueError) as exc_info:
                    render_pages_to_images(str(doc_path), pages=[1], dpi=150)

                msg = str(exc_info.value)
                assert "Page 1 out of bounds" in msg
                assert "fewer pages than requested" in msg

    def test_pdftoppm_failure(self, tmp_path):
        """pdftoppm failure gives clear error message."""
        doc_path = tmp_path / "test.docx"
        doc_path.touch()

        mock_pdf = tmp_path / "test.pdf"
        mock_pdf.touch()

        with patch(
            "mcp_handley_lab.microsoft.common.render._convert_to_pdf"
        ) as mock_convert:
            mock_convert.return_value = mock_pdf

            with patch(
                "mcp_handley_lab.microsoft.common.render.subprocess.run"
            ) as mock_run:
                error = subprocess.CalledProcessError(
                    returncode=1, cmd="pdftoppm", stderr="Memory allocation failed"
                )
                mock_run.side_effect = error

                with pytest.raises(RuntimeError) as exc_info:
                    render_pages_to_images(str(doc_path), pages=[1], dpi=150)

                assert "pdftoppm failed" in str(exc_info.value)
                assert "Memory allocation" in str(exc_info.value)

    def test_pdftoppm_timeout(self, tmp_path):
        """pdftoppm timeout gives clear error message."""
        doc_path = tmp_path / "test.docx"
        doc_path.touch()

        mock_pdf = tmp_path / "test.pdf"
        mock_pdf.touch()

        with patch(
            "mcp_handley_lab.microsoft.common.render._convert_to_pdf"
        ) as mock_convert:
            mock_convert.return_value = mock_pdf

            with patch(
                "mcp_handley_lab.microsoft.common.render.subprocess.run"
            ) as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("pdftoppm", 60)

                with pytest.raises(RuntimeError) as exc_info:
                    render_pages_to_images(str(doc_path), pages=[1], dpi=150)

                assert "render timed out" in str(exc_info.value)

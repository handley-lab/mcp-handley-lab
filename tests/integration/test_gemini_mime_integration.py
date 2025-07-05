"""Integration tests for Gemini MIME type handling with real API calls."""
import tempfile
from pathlib import Path

import pytest
from mcp_handley_lab.llm.gemini.tool import ask


@pytest.mark.vcr
def test_gemini_tex_file_upload(skip_if_no_api_key, test_output_file):
    """Test that .tex files work with Gemini after MIME type fix."""
    skip_if_no_api_key("GEMINI_API_KEY")

    # Create a simple LaTeX file
    tex_content = """\\documentclass{article}
\\begin{document}
This is a test LaTeX document with mathematical formula: $E = mc^2$
\\end{document}"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
        f.write(tex_content)
        tex_file_path = f.name

    try:
        result = ask(
            prompt="What type of document is this and what mathematical formula does it contain?",
            files=[{"path": tex_file_path}],
            output_file=test_output_file,
            model="gemini-2.5-flash",
            agent_name=False,
        )

        assert "saved" in result.lower() or "success" in result.lower()
        assert Path(test_output_file).exists()

        content = Path(test_output_file).read_text()
        # Should recognize it as LaTeX and identify the formula
        assert any(
            keyword in content.lower() for keyword in ["latex", "tex", "document"]
        )
        assert (
            "mc" in content
            or "einstein" in content.lower()
            or "energy" in content.lower()
        )

    finally:
        # Cleanup
        Path(tex_file_path).unlink(missing_ok=True)


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_patch_file_upload(skip_if_no_api_key, test_output_file):
    """Test that .patch files work with Gemini after MIME type fix."""
    skip_if_no_api_key("GEMINI_API_KEY")

    # Create a simple patch file
    patch_content = """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
-    print("Hello")
+    print("Hello World")
+    return "success"

"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
        f.write(patch_content)
        patch_file_path = f.name

    try:
        result = ask(
            prompt="What changes does this patch file make to the code?",
            files=[{"path": patch_file_path}],
            output_file=test_output_file,
            model="gemini-2.5-flash",
            agent_name=False,
        )

        assert "saved" in result.lower() or "success" in result.lower()
        assert Path(test_output_file).exists()

        content = Path(test_output_file).read_text()
        # Should recognize the changes in the patch
        assert any(
            keyword in content.lower() for keyword in ["patch", "diff", "change"]
        )
        assert "hello world" in content.lower() or "return" in content.lower()

    finally:
        # Cleanup
        Path(patch_file_path).unlink(missing_ok=True)


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_yaml_file_upload(skip_if_no_api_key, test_output_file):
    """Test that .yaml files work with Gemini after MIME type fix."""
    skip_if_no_api_key("GEMINI_API_KEY")

    # Create a simple YAML file
    yaml_content = """# Configuration file
app:
  name: "Test Application"
  version: "1.0.0"
  features:
    - authentication
    - logging
    - metrics
database:
  host: "localhost"
  port: 5432
  name: "testdb"
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        yaml_file_path = f.name

    try:
        result = ask(
            prompt="What is configured in this YAML file? What is the application name?",
            files=[{"path": yaml_file_path}],
            output_file=test_output_file,
            model="gemini-2.5-flash",
            agent_name=False,
        )

        assert "saved" in result.lower() or "success" in result.lower()
        assert Path(test_output_file).exists()

        content = Path(test_output_file).read_text()
        # Should recognize YAML and identify the app name
        assert any(
            keyword in content.lower()
            for keyword in ["yaml", "configuration", "config"]
        )
        assert "test application" in content.lower()

    finally:
        # Cleanup
        Path(yaml_file_path).unlink(missing_ok=True)


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_shell_script_upload(skip_if_no_api_key, test_output_file):
    """Test that .sh files work with Gemini after MIME type fix."""
    skip_if_no_api_key("GEMINI_API_KEY")

    # Create a simple shell script
    script_content = """#!/bin/bash
# Build and deploy script
set -e

echo "Starting build process..."
npm install
npm run build
npm test

echo "Deploying to production..."
rsync -av dist/ user@server:/var/www/
echo "Deployment complete!"
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
        f.write(script_content)
        script_file_path = f.name

    try:
        result = ask(
            prompt="What does this shell script do? What are the main steps?",
            files=[{"path": script_file_path}],
            output_file=test_output_file,
            model="gemini-2.5-flash",
            agent_name=False,
        )

        assert "saved" in result.lower() or "success" in result.lower()
        assert Path(test_output_file).exists()

        content = Path(test_output_file).read_text()
        # Should recognize shell script and identify the steps
        assert any(
            keyword in content.lower() for keyword in ["script", "bash", "shell"]
        )
        assert any(keyword in content.lower() for keyword in ["build", "deploy", "npm"])

    finally:
        # Cleanup
        Path(script_file_path).unlink(missing_ok=True)


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_multiple_unsupported_files(skip_if_no_api_key, test_output_file):
    """Test multiple unsupported file types in a single request."""
    skip_if_no_api_key("GEMINI_API_KEY")

    # Create multiple files with different unsupported extensions
    files_to_create = [
        (".toml", '[package]\nname = "test"\nversion = "1.0.0"'),
        (".diff", "diff --git a/file.txt b/file.txt\n+added line"),
        (".rs", 'fn main() {\n    println!("Hello Rust!");\n}'),
    ]

    file_paths = []
    try:
        # Create test files
        for ext, content in files_to_create:
            with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False) as f:
                f.write(content)
                file_paths.append(f.name)

        # Test with multiple files
        result = ask(
            prompt="What types of files are these and what do they contain?",
            files=[{"path": path} for path in file_paths],
            output_file=test_output_file,
            model="gemini-2.5-flash",
            agent_name=False,
        )

        assert "saved" in result.lower() or "success" in result.lower()
        assert Path(test_output_file).exists()

        content = Path(test_output_file).read_text()
        # Should recognize all file types
        assert any(keyword in content.lower() for keyword in ["toml", "configuration"])
        assert any(keyword in content.lower() for keyword in ["diff", "patch"])
        assert any(keyword in content.lower() for keyword in ["rust", "programming"])

    finally:
        # Cleanup all files
        for path in file_paths:
            Path(path).unlink(missing_ok=True)


@pytest.mark.asyncio
@pytest.mark.vcr
async def test_gemini_supported_file_unchanged(skip_if_no_api_key, test_output_file):
    """Test that already supported files still work correctly."""
    skip_if_no_api_key("GEMINI_API_KEY")

    # Create a .txt file (which should already be supported)
    txt_content = "This is a simple text file with some content for testing."

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(txt_content)
        txt_file_path = f.name

    try:
        result = ask(
            prompt="What is in this text file?",
            files=[{"path": txt_file_path}],
            output_file=test_output_file,
            model="gemini-2.5-flash",
            agent_name=False,
        )

        assert "saved" in result.lower() or "success" in result.lower()
        assert Path(test_output_file).exists()

        content = Path(test_output_file).read_text()
        assert "simple text file" in content.lower() or "content" in content.lower()

    finally:
        # Cleanup
        Path(txt_file_path).unlink(missing_ok=True)

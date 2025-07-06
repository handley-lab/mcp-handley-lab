"""Integration tests for Gemini MIME type handling with real API calls."""
import tempfile
from pathlib import Path

import pytest
from mcp_handley_lab.llm.gemini.tool import ask

# File type test parameters
file_type_params = [
    pytest.param(
        ".tex",
        """\\documentclass{article}
\\begin{document}
This is a test LaTeX document with mathematical formula: $E = mc^2$
\\end{document}""",
        "What type of document is this and what mathematical formula does it contain?",
        ["latex", "tex", "document"],
        ["mc", "einstein", "energy"],
        id="tex",
    ),
    pytest.param(
        ".patch",
        """diff --git a/test.py b/test.py
index 1234567..abcdefg 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
-    print("Hello")
+    print("Hello World")
+    return "success"

""",
        "What changes does this patch file make to the code?",
        ["patch", "diff", "change"],
        ["hello world", "return"],
        id="patch",
    ),
    pytest.param(
        ".yaml",
        """# Configuration file
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
""",
        "What is configured in this YAML file? What is the application name?",
        ["yaml", "configuration", "config"],
        ["test application"],
        id="yaml",
    ),
    pytest.param(
        ".sh",
        """#!/bin/bash
# Build and deploy script
set -e

echo "Starting build process..."
npm install
npm run build
npm test

echo "Deploying to production..."
rsync -av dist/ user@server:/var/www/
echo "Deployment complete!"
""",
        "What does this shell script do? What are the main steps?",
        ["script", "bash", "shell"],
        ["build", "deploy", "npm"],
        id="shell",
    ),
]

multiple_files_params = [
    (".toml", '[package]\nname = "test"\nversion = "1.0.0"', ["toml", "configuration"]),
    (".diff", "diff --git a/file.txt b/file.txt\n+added line", ["diff", "patch"]),
    (".rs", 'fn main() {\n    println!("Hello Rust!");\n}', ["rust", "programming"]),
]


@pytest.mark.vcr
@pytest.mark.parametrize(
    "file_ext, file_content, prompt, type_keywords, content_keywords", file_type_params
)
def test_gemini_file_upload_by_type(
    skip_if_no_api_key,
    test_output_file,
    file_ext,
    file_content,
    prompt,
    type_keywords,
    content_keywords,
):
    """Test that various file types work with Gemini after MIME type fix."""
    skip_if_no_api_key("GEMINI_API_KEY")

    with tempfile.NamedTemporaryFile(mode="w", suffix=file_ext, delete=False) as f:
        f.write(file_content)
        file_path = f.name

    try:
        result = ask(
            prompt=prompt,
            files=[{"path": file_path}],
            output_file=test_output_file,
            model="gemini-2.5-flash",
            agent_name=False,
        )

        assert "saved" in result.lower() or "success" in result.lower()
        assert Path(test_output_file).exists()

        content = Path(test_output_file).read_text()

        # Should recognize the file type
        assert any(keyword in content.lower() for keyword in type_keywords)

        # Should identify specific content elements
        assert any(keyword in content.lower() for keyword in content_keywords)

    finally:
        # Cleanup
        Path(file_path).unlink(missing_ok=True)


@pytest.mark.vcr
def test_gemini_multiple_unsupported_files(skip_if_no_api_key, test_output_file):
    """Test multiple unsupported file types in a single request."""
    skip_if_no_api_key("GEMINI_API_KEY")

    file_paths = []
    try:
        # Create test files
        for ext, content, _keywords in multiple_files_params:
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
        for _, _, keywords in multiple_files_params:
            assert any(keyword in content.lower() for keyword in keywords)

    finally:
        # Cleanup all files
        for path in file_paths:
            Path(path).unlink(missing_ok=True)


@pytest.mark.vcr
def test_gemini_supported_file_unchanged(skip_if_no_api_key, test_output_file):
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

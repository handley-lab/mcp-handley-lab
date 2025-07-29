"""Integration tests for Gemini MIME type handling with real API calls."""
import tempfile
from pathlib import Path

import pytest
from mcp_handley_lab.llm.gemini.tool import mcp

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
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "file_ext, file_content, prompt, type_keywords, content_keywords", file_type_params
)
async def test_gemini_file_upload_by_type(
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
        import json

        result = await mcp.call_tool(
            "ask",
            {
                "prompt": prompt,
                "files": [file_path],
                "output_file": test_output_file,
                "model": "gemini-2.5-flash",
                "agent_name": "",
                "temperature": 1.0,
                "max_output_tokens": 0,
                "grounding": False,
            },
        )
        response = json.loads(result[0].text)
        assert "error" not in response, response.get("error")
        result = response

        assert result["content"] is not None
        assert len(result["content"]) > 0
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
@pytest.mark.asyncio
async def test_gemini_multiple_unsupported_files(skip_if_no_api_key, test_output_file):
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
        import json

        result = await mcp.call_tool(
            "ask",
            {
                "prompt": "What types of files are these and what do they contain?",
                "files": file_paths,
                "output_file": test_output_file,
                "model": "gemini-2.5-flash",
                "agent_name": "",
                "temperature": 1.0,
                "max_output_tokens": 0,
                "grounding": False,
            },
        )
        response = json.loads(result[0].text)
        assert "error" not in response, response.get("error")
        result = response

        assert result["content"] is not None
        assert len(result["content"]) > 0
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
@pytest.mark.asyncio
async def test_gemini_supported_file_unchanged(skip_if_no_api_key, test_output_file):
    """Test that already supported files still work correctly."""
    skip_if_no_api_key("GEMINI_API_KEY")

    # Create a .txt file (which should already be supported)
    txt_content = "This is a simple text file with some content for testing."

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(txt_content)
        txt_file_path = f.name

    try:
        import json

        result = await mcp.call_tool(
            "ask",
            {
                "prompt": "What is in this text file?",
                "files": [txt_file_path],
                "output_file": test_output_file,
                "model": "gemini-2.5-flash",
                "agent_name": "",
                "temperature": 1.0,
                "max_output_tokens": 0,
                "grounding": False,
            },
        )
        response = json.loads(result[0].text)
        assert "error" not in response, response.get("error")
        result = response

        assert result["content"] is not None
        assert len(result["content"]) > 0
        assert Path(test_output_file).exists()

        content = Path(test_output_file).read_text()
        assert "simple text file" in content.lower() or "content" in content.lower()

    finally:
        # Cleanup
        Path(txt_file_path).unlink(missing_ok=True)


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gemini_grounding_metadata_fields(skip_if_no_api_key, test_output_file):
    """Test that grounding returns all expected metadata fields."""
    skip_if_no_api_key("GEMINI_API_KEY")

    import json

    result = await mcp.call_tool(
        "ask",
        {
            "prompt": "What were the main AI announcements from Apple WWDC 2024?",
            "output_file": test_output_file,
            "model": "gemini-1.5-flash",
            "grounding": True,
            "agent_name": "test_grounding_metadata",
            "temperature": 1.0,
            "max_output_tokens": 0,
            "files": [],
        },
    )
    response = json.loads(result[0].text)
    assert "error" not in response, response.get("error")
    result = response

    # Check basic response
    assert result["content"] is not None
    assert len(result["content"]) > 0
    assert Path(test_output_file).exists()

    # Check new metadata fields
    assert result["finish_reason"] != ""
    assert result["model_version"] != ""
    assert result["generation_time_ms"] > 0
    assert isinstance(result["avg_logprobs"], float)

    # Check grounding metadata exists
    assert result["grounding_metadata"] is not None
    gm = result["grounding_metadata"]

    # Check grounding metadata structure
    assert isinstance(gm["web_search_queries"], list)
    assert len(gm["web_search_queries"]) > 0
    assert isinstance(gm["grounding_chunks"], list)
    assert len(gm["grounding_chunks"]) > 0
    assert isinstance(gm["grounding_supports"], list)
    assert len(gm["grounding_supports"]) > 0

    # Check new grounding fields
    assert isinstance(gm["retrieval_metadata"], dict)
    assert isinstance(gm["search_entry_point"], dict)

    # Check grounding chunk structure
    chunk = gm["grounding_chunks"][0]
    assert "uri" in chunk
    assert "title" in chunk
    assert chunk["uri"] != ""
    assert chunk["title"] != ""

    # Check content mentions Apple/WWDC
    content = result["content"].lower()
    assert any(term in content for term in ["apple", "wwdc", "intelligence"])


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gemini_without_grounding_no_metadata(
    skip_if_no_api_key, test_output_file
):
    """Test that without grounding, grounding metadata is None but other fields exist."""
    skip_if_no_api_key("GEMINI_API_KEY")

    import json

    result = await mcp.call_tool(
        "ask",
        {
            "prompt": "What is 2+2?",
            "output_file": test_output_file,
            "model": "gemini-1.5-flash",
            "grounding": False,
            "agent_name": "test_no_grounding",
            "temperature": 1.0,
            "max_output_tokens": 0,
            "files": [],
        },
    )
    response = json.loads(result[0].text)
    assert "error" not in response, response.get("error")
    result = response

    # Check basic response
    assert result["content"] is not None
    assert "4" in result["content"]

    # Check metadata fields still exist
    assert result["finish_reason"] != ""
    assert result["model_version"] != ""
    assert result["generation_time_ms"] > 0
    assert isinstance(result["avg_logprobs"], float)

    # Check grounding metadata is None when not using grounding
    assert result["grounding_metadata"] is None


@pytest.mark.vcr
@pytest.mark.asyncio
async def test_gemini_grounding_search_entry_point_structure(
    skip_if_no_api_key, test_output_file
):
    """Test the search entry point contains expected HTML interface."""
    skip_if_no_api_key("GEMINI_API_KEY")

    import json

    result = await mcp.call_tool(
        "ask",
        {
            "prompt": "Latest developments in quantum computing 2024",
            "output_file": test_output_file,
            "model": "gemini-1.5-flash",
            "grounding": True,
            "agent_name": "test_search_entry_point",
            "temperature": 1.0,
            "max_output_tokens": 0,
            "files": [],
        },
    )
    response = json.loads(result[0].text)
    assert "error" not in response, response.get("error")
    result = response

    # Check grounding metadata exists
    assert result["grounding_metadata"] is not None
    gm = result["grounding_metadata"]

    # Check search entry point structure if present
    if gm["search_entry_point"]:
        sep = gm["search_entry_point"]
        # Should contain HTML rendering information
        if "rendered_content" in sep:
            html_content = sep["rendered_content"]
            assert isinstance(html_content, str)
            # Should contain CSS styling and HTML elements
            assert any(
                term in html_content for term in ["container", "chip", "css", "style"]
            )

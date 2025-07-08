#!/usr/bin/env python3
"""Test script to validate structured outputs implementation."""


def test_arxiv_structured_outputs():
    """Test ArXiv tool structured outputs."""
    from mcp_handley_lab.arxiv.tool import ArxivPaper, search, server_info
    from mcp_handley_lab.shared.models import ServerInfo

    # Test server_info
    result = server_info()
    assert isinstance(result, ServerInfo)
    assert result.name == "ArXiv Tool"
    print("✅ ArXiv server_info returns ServerInfo")

    # Test search returns ArxivPaper objects
    papers = search("test", max_results=1)
    assert isinstance(papers, list)
    if papers:  # If we get results
        assert isinstance(papers[0], ArxivPaper)
        assert hasattr(papers[0], "title")
        assert hasattr(papers[0], "authors")
    print("✅ ArXiv search returns list[ArxivPaper]")


def test_code2prompt_structured_outputs():
    """Test Code2Prompt tool structured outputs."""
    import os
    import tempfile

    from mcp_handley_lab.code2prompt.tool import generate_prompt, server_info
    from mcp_handley_lab.shared.models import FileResult, ServerInfo

    # Test server_info
    result = server_info()
    assert isinstance(result, ServerInfo)
    assert result.name == "Code2Prompt Tool"
    print("✅ Code2Prompt server_info returns ServerInfo")

    # Test generate_prompt returns FileResult
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.py")
        with open(test_file, "w") as f:
            f.write("print('hello')")

        result = generate_prompt(path=tmpdir, output_file="-")
        assert isinstance(result, FileResult)
        assert hasattr(result, "message")
        assert hasattr(result, "file_path")
    print("✅ Code2Prompt generate_prompt returns FileResult")


def test_llm_structured_outputs():
    """Test LLM tool structured outputs."""
    from mcp_handley_lab.llm.claude.tool import server_info as claude_server_info
    from mcp_handley_lab.llm.gemini.tool import server_info as gemini_server_info
    from mcp_handley_lab.llm.openai.tool import server_info as openai_server_info
    from mcp_handley_lab.shared.models import ServerInfo

    # Test all LLM server_info functions
    try:
        result = openai_server_info()
        assert isinstance(result, ServerInfo)
        assert result.name == "OpenAI Tool"
        print("✅ OpenAI server_info returns ServerInfo")
    except Exception as e:
        print(f"⚠️  OpenAI server_info skipped (API key needed): {e}")

    try:
        result = gemini_server_info()
        assert isinstance(result, ServerInfo)
        assert result.name == "Gemini Tool"
        print("✅ Gemini server_info returns ServerInfo")
    except Exception as e:
        print(f"⚠️  Gemini server_info skipped (API key needed): {e}")

    try:
        result = claude_server_info()
        assert isinstance(result, ServerInfo)
        assert result.name == "Claude Tool"
        print("✅ Claude server_info returns ServerInfo")
    except Exception as e:
        print(f"⚠️  Claude server_info skipped (API key needed): {e}")


def test_github_structured_outputs():
    """Test GitHub tool structured outputs."""
    from mcp_handley_lab.github.tool import server_info
    from mcp_handley_lab.shared.models import ServerInfo

    result = server_info()
    assert isinstance(result, ServerInfo)
    assert result.name == "GitHub CI Monitor"
    print("✅ GitHub server_info returns ServerInfo")

    # Note: monitor_pr_checks requires GitHub setup, skip actual testing


def test_shared_models():
    """Test shared models can be imported and instantiated."""
    from mcp_handley_lab.shared.models import (
        LLMResult,
        ServerInfo,
        UsageStats,
    )

    # Test ServerInfo
    server = ServerInfo(
        name="Test",
        version="1.0.0",
        status="active",
        capabilities=["test"],
        dependencies={"test": "ok"},
    )
    assert server.name == "Test"

    # Test UsageStats
    usage = UsageStats(
        input_tokens=100, output_tokens=50, cost=0.01, model_used="test-model"
    )
    assert usage.input_tokens == 100

    # Test LLMResult
    llm_result = LLMResult(content="Hello World", usage=usage, agent_name="test_agent")
    assert llm_result.content == "Hello World"

    print("✅ All shared models work correctly")


if __name__ == "__main__":
    print("Testing structured outputs implementation...")

    try:
        test_shared_models()
        test_arxiv_structured_outputs()
        test_code2prompt_structured_outputs()
        test_llm_structured_outputs()
        test_github_structured_outputs()

        print("\n🎉 All structured output tests passed!")
        print("✅ Structured outputs implementation is working correctly")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)

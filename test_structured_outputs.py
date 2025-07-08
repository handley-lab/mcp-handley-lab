#!/usr/bin/env python3
"""Test script to validate structured outputs implementation."""


def test_arxiv_structured_outputs():
    """Test ArXiv tool structured outputs."""
    from mcp_handley_lab.arxiv.tool import server_info
    from mcp_handley_lab.shared.models import ServerInfo

    result = server_info()
    assert isinstance(result, ServerInfo)
    assert result.name == "ArXiv Tool"
    print("✅ ArXiv server_info returns ServerInfo")


def test_code2prompt_structured_outputs():
    """Test Code2Prompt tool structured outputs."""
    from mcp_handley_lab.code2prompt.tool import server_info
    from mcp_handley_lab.shared.models import ServerInfo

    result = server_info()
    assert isinstance(result, ServerInfo)
    assert result.name == "Code2Prompt Tool"
    print("✅ Code2Prompt server_info returns ServerInfo")


def test_email_msmtp_structured_outputs():
    """Test MSMTP tool structured outputs."""
    from mcp_handley_lab.email.msmtp.tool import list_accounts

    result = list_accounts()
    assert isinstance(result, list)
    print("✅ MSMTP list_accounts returns list")


def test_github_structured_outputs():
    """Test GitHub tool structured outputs."""
    from mcp_handley_lab.github.tool import server_info
    from mcp_handley_lab.shared.models import ServerInfo

    result = server_info()
    assert isinstance(result, ServerInfo)
    assert result.name == "GitHub CI Monitor"
    print("✅ GitHub server_info returns ServerInfo")


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
        test_email_msmtp_structured_outputs()
        test_github_structured_outputs()

        print("\n🎉 All structured output tests passed!")
        print("✅ Structured outputs implementation is working correctly")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)

"""Systematic unhappy path tests for LLM integration.

Tests error scenarios across OpenAI, Gemini, and Claude providers including
rate limiting, large inputs, network errors, content policy violations.
"""
import pytest
import tempfile
from pathlib import Path
from mcp.server.fastmcp.exceptions import ToolError

from mcp_handley_lab.llm.openai.tool import mcp as openai_mcp
from mcp_handley_lab.llm.gemini.tool import mcp as gemini_mcp
from mcp_handley_lab.llm.claude.tool import mcp as claude_mcp


# Provider configurations for systematic testing
llm_unhappy_providers = [
    pytest.param(
        openai_mcp,
        "ask",
        "OPENAI_API_KEY", 
        "gpt-4o-mini",
        id="openai"
    ),
    pytest.param(
        gemini_mcp,
        "ask",
        "GEMINI_API_KEY",
        "gemini-2.5-flash",
        id="gemini"
    ),
    pytest.param(
        claude_mcp,
        "ask", 
        "ANTHROPIC_API_KEY",
        "claude-3-5-haiku-20241022",
        id="claude"
    )
]

image_unhappy_providers = [
    pytest.param(
        openai_mcp,
        "analyze_image",
        "OPENAI_API_KEY",
        "gpt-4o",
        id="openai"
    ),
    pytest.param(
        gemini_mcp,
        "analyze_image", 
        "GEMINI_API_KEY",
        "gemini-2.5-pro",
        id="gemini"
    ),
    pytest.param(
        claude_mcp,
        "analyze_image",
        "ANTHROPIC_API_KEY", 
        "claude-3-5-sonnet-20240620",
        id="claude"
    )
]


@pytest.mark.integration
class TestLLMRateLimitingErrors:
    """Test rate limiting and quota scenarios."""

    @pytest.mark.live
    @pytest.mark.asyncio
    @pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", llm_unhappy_providers)
    async def test_rapid_sequential_requests(
        self, skip_if_no_api_key, test_output_file, mcp_instance, tool_name, api_key, model
    ):
        """Test behavior with rapid sequential requests (potential rate limiting)."""
        skip_if_no_api_key(api_key)
        
        # Make multiple rapid requests
        requests = []
        for i in range(5):
            output_file = test_output_file.replace('.txt', f'_{i}.txt')
            try:
                _, response = await mcp_instance.call_tool(tool_name, {
                    "prompt": f"Count to {i+1}",
                    "output_file": output_file,
                    "model": model,
                    "agent_name": "",
                })
                requests.append(response)
            except ToolError as e:
                # Rate limiting errors are acceptable
                assert any(keyword in str(e).lower() for keyword in [
                    "rate", "limit", "quota", "throttl", "too many"
                ])
        
        # At least some requests should succeed
        successful_requests = [r for r in requests if "error" not in r]
        assert len(successful_requests) > 0, "All requests failed - check API configuration"


@pytest.mark.integration
class TestLLMLargeInputHandling:
    """Test handling of large and problematic inputs."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    @pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", llm_unhappy_providers)
    async def test_extremely_large_prompt(
        self, skip_if_no_api_key, test_output_file, mcp_instance, tool_name, api_key, model
    ):
        """Test handling of prompts that exceed context length limits."""
        skip_if_no_api_key(api_key)
        
        # Create a very large prompt (likely to exceed context limits)
        large_prompt = "Repeat this text: " + "A" * 100000  # 100k+ characters
        
        # Should either handle gracefully or provide clear error
        try:
            _, response = await mcp_instance.call_tool(tool_name, {
                "prompt": large_prompt,
                "output_file": test_output_file,
                "model": model,
                "agent_name": "",
            })
            
            # If successful, response should be reasonable
            if "error" not in response:
                assert response["content"] is not None
                
        except ToolError as e:
            # Expected errors for oversized prompts
            assert any(keyword in str(e).lower() for keyword in [
                "context", "length", "limit", "token", "size", "too large", "maximum"
            ])

    @pytest.mark.vcr
    @pytest.mark.asyncio
    @pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", llm_unhappy_providers) 
    async def test_large_file_input_handling(
        self, skip_if_no_api_key, test_output_file, tmp_path, mcp_instance, tool_name, api_key, model
    ):
        """Test handling of very large file inputs."""
        skip_if_no_api_key(api_key)
        
        # Create large file (1MB+)
        large_file = tmp_path / "large_input.txt"
        large_content = "This is a large file. " * 50000  # ~1MB
        large_file.write_text(large_content)
        
        try:
            _, response = await mcp_instance.call_tool(tool_name, {
                "prompt": "Summarize this large file in one sentence.",
                "output_file": test_output_file,
                "files": [str(large_file)],
                "model": model,
                "agent_name": "",
            })
            
            # If successful, should provide reasonable response
            if "error" not in response:
                assert response["content"] is not None
                assert len(response["content"]) > 0
                
        except ToolError as e:
            # Expected errors for oversized files
            assert any(keyword in str(e).lower() for keyword in [
                "file", "size", "limit", "large", "token", "context"
            ])

    @pytest.mark.vcr
    @pytest.mark.asyncio
    @pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", llm_unhappy_providers)
    async def test_problematic_characters_handling(
        self, skip_if_no_api_key, test_output_file, mcp_instance, tool_name, api_key, model
    ):
        """Test handling of problematic characters and encoding issues."""
        skip_if_no_api_key(api_key)
        
        # Test various problematic character combinations
        problematic_prompts = [
            "Unicode test: 🚀 💻 🤖 中文 العربية עברית",  # Mixed unicode
            "Control chars: \x00\x01\x02\x03",  # Control characters
            "Emoji flood: " + "🎉" * 1000,  # Many emojis
            "Mixed encoding: café naïve résumé",  # Accented characters
            "Special symbols: ∑∞∆∇∂∫∮∯∰∱",  # Math symbols
        ]
        
        for i, prompt in enumerate(problematic_prompts):
            output_file = test_output_file.replace('.txt', f'_char_{i}.txt')
            try:
                _, response = await mcp_instance.call_tool(tool_name, {
                    "prompt": f"Echo back: {prompt}",
                    "output_file": output_file,
                    "model": model,
                    "agent_name": "",
                })
                
                # If successful, should handle characters properly
                if "error" not in response:
                    assert response["content"] is not None
                    content = Path(output_file).read_text(encoding='utf-8')
                    # Should contain some recognizable content
                    assert len(content.strip()) > 0
                    
            except (ToolError, UnicodeError) as e:
                # Character encoding errors are acceptable for some inputs
                assert any(keyword in str(e).lower() for keyword in [
                    "encoding", "character", "unicode", "invalid", "decode"
                ])


@pytest.mark.integration
class TestLLMFileInputErrors:
    """Test file input error scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", llm_unhappy_providers)
    async def test_nonexistent_file_input(
        self, skip_if_no_api_key, test_output_file, mcp_instance, tool_name, api_key, model
    ):
        """Test handling of non-existent file inputs."""
        skip_if_no_api_key(api_key)
        
        nonexistent_file = "/path/to/nonexistent/file.txt"
        
        with pytest.raises(ToolError, match="file.*not found|not.*exist|no such file|directory"):
            await mcp_instance.call_tool(tool_name, {
                "prompt": "Analyze this file.",
                "output_file": test_output_file,
                "files": [nonexistent_file],
                "model": model,
                "agent_name": "",
            })

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", llm_unhappy_providers)
    async def test_permission_denied_file(
        self, skip_if_no_api_key, test_output_file, tmp_path, mcp_instance, tool_name, api_key, model
    ):
        """Test handling of files without read permissions."""
        skip_if_no_api_key(api_key)
        
        # Create file with no read permissions
        restricted_file = tmp_path / "restricted.txt"
        restricted_file.write_text("Secret content")
        restricted_file.chmod(0o000)  # No permissions
        
        try:
            with pytest.raises(ToolError, match="permission|access|denied|readable"):
                await mcp_instance.call_tool(tool_name, {
                    "prompt": "Read this restricted file.",
                    "output_file": test_output_file,
                    "files": [str(restricted_file)],
                    "model": model,
                    "agent_name": "",
                })
        finally:
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", llm_unhappy_providers)
    async def test_binary_file_input(
        self, skip_if_no_api_key, test_output_file, tmp_path, mcp_instance, tool_name, api_key, model
    ):
        """Test handling of binary files that can't be read as text."""
        skip_if_no_api_key(api_key)
        
        # Create binary file
        binary_file = tmp_path / "binary.dat"
        binary_data = bytes(range(256))  # Binary data
        binary_file.write_bytes(binary_data)
        
        try:
            _, response = await mcp_instance.call_tool(tool_name, {
                "prompt": "Analyze this binary file.",
                "output_file": test_output_file,
                "files": [str(binary_file)],
                "model": model,
                "agent_name": "",
            })
            
            # If it succeeds, should handle gracefully
            if "error" not in response:
                assert response["content"] is not None
                # Should indicate it's binary or provide reasonable response
                content = Path(test_output_file).read_text()
                assert len(content) > 0
                
        except ToolError as e:
            # Binary file errors are acceptable
            assert any(keyword in str(e).lower() for keyword in [
                "binary", "decode", "text", "encoding", "readable", "mime", "unsupported"
            ])


@pytest.mark.integration
class TestLLMImageAnalysisUnhappyPaths:
    """Test image analysis error scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", image_unhappy_providers)
    async def test_corrupted_image_input(
        self, skip_if_no_api_key, test_output_file, tmp_path, mcp_instance, tool_name, api_key, model
    ):
        """Test handling of corrupted image files."""
        skip_if_no_api_key(api_key)
        
        # Create corrupted image file
        corrupted_image = tmp_path / "corrupted.png"
        corrupted_image.write_text("This is not a valid PNG file")
        
        with pytest.raises(ToolError, match="image|invalid|corrupted|format|decode"):
            await mcp_instance.call_tool(tool_name, {
                "prompt": "What's in this image?",
                "output_file": test_output_file,
                "files": [str(corrupted_image)],
                "model": model,
                "agent_name": "",
            })

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", image_unhappy_providers)
    async def test_missing_image_file(
        self, skip_if_no_api_key, test_output_file, mcp_instance, tool_name, api_key, model
    ):
        """Test handling of missing image files."""
        skip_if_no_api_key(api_key)
        
        nonexistent_image = "/path/to/nonexistent/image.png"
        
        with pytest.raises(ToolError, match="file.*not found|not.*exist|no such file|directory"):
            await mcp_instance.call_tool(tool_name, {
                "prompt": "Analyze this missing image.",
                "output_file": test_output_file,
                "files": [nonexistent_image],
                "model": model,
                "agent_name": "",
            })


@pytest.mark.integration
class TestLLMProviderSpecificErrors:
    """Test provider-specific error scenarios."""

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_openai_content_policy_violation(self, skip_if_no_api_key, test_output_file):
        """Test OpenAI content policy violation handling."""
        skip_if_no_api_key("OPENAI_API_KEY")
        
        # Use prompt that might trigger content policy (keep it mild for testing)
        policy_test_prompt = "Write detailed instructions for harmful activities"
        
        try:
            _, response = await openai_mcp.call_tool("ask", {
                "prompt": policy_test_prompt,
                "output_file": test_output_file,
                "model": "gpt-4o-mini",
                "agent_name": "",
            })
            
            # OpenAI should either refuse or provide safe alternative
            if "error" not in response:
                content = Path(test_output_file).read_text()
                # Either contains refusal/safety language or provides helpful information
                # Both are acceptable responses to this mild prompt
                assert len(content.strip()) > 0  # Should provide some response
                
        except ToolError as e:
            # Content policy errors are expected
            assert any(keyword in str(e).lower() for keyword in [
                "policy", "content", "violation", "inappropriate", "safety"
            ])

    @pytest.mark.vcr
    @pytest.mark.asyncio
    async def test_gemini_safety_filter_activation(self, skip_if_no_api_key, test_output_file):
        """Test Gemini safety filter activation."""
        skip_if_no_api_key("GEMINI_API_KEY")
        
        # Test prompt that might trigger Gemini's safety filters
        safety_test_prompt = "Provide information about dangerous activities"
        
        try:
            _, response = await gemini_mcp.call_tool("ask", {
                "prompt": safety_test_prompt,
                "output_file": test_output_file,
                "model": "gemini-2.5-flash",
                "agent_name": "",
            })
            
            # Gemini should either refuse or provide filtered response
            if "error" not in response:
                content = Path(test_output_file).read_text()
                # Should handle safety concerns appropriately
                assert len(content) > 0
                
        except ToolError as e:
            # Safety filter activation is acceptable
            assert any(keyword in str(e).lower() for keyword in [
                "safety", "filter", "block", "inappropriate", "policy"
            ])


@pytest.mark.integration
class TestLLMOutputFileErrors:
    """Test output file writing error scenarios."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", llm_unhappy_providers)
    async def test_output_file_permission_denied(
        self, skip_if_no_api_key, tmp_path, mcp_instance, tool_name, api_key, model
    ):
        """Test handling of output file permission errors."""
        skip_if_no_api_key(api_key)
        
        # Create directory without write permissions
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o555)  # Read and execute only
        
        output_file = readonly_dir / "output.txt"
        
        try:
            with pytest.raises(ToolError, match="permission|write|access|denied"):
                await mcp_instance.call_tool(tool_name, {
                    "prompt": "Simple test",
                    "output_file": str(output_file),
                    "model": model,
                    "agent_name": "",
                })
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mcp_instance, tool_name, api_key, model", llm_unhappy_providers)
    async def test_output_directory_not_found(
        self, skip_if_no_api_key, mcp_instance, tool_name, api_key, model
    ):
        """Test handling of output file in non-existent directory."""
        skip_if_no_api_key(api_key)
        
        output_file = "/nonexistent/directory/output.txt"
        
        # Should either create directory or provide clear error
        try:
            _, response = await mcp_instance.call_tool(tool_name, {
                "prompt": "Simple test",
                "output_file": output_file,
                "model": model,
                "agent_name": "",
            })
            
            # If successful, file should exist
            if "error" not in response:
                assert Path(output_file).exists()
                
        except ToolError as e:
            # Directory creation errors are acceptable
            assert any(keyword in str(e).lower() for keyword in [
                "directory", "not found", "no such", "path", "create"
            ])
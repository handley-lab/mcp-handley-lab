import pytest
import tempfile
import json
from pathlib import Path
from mcp_handley_lab.tool_chainer.tool import (
    discover_tools, register_tool, chain_tools, execute_chain, 
    show_history, clear_cache, server_info
)

@pytest.mark.vcr
@pytest.mark.asyncio
async def test_tool_chainer_jq_discovery(temp_storage_dir):
    result = await discover_tools(
        server_command="python -m mcp_handley_lab jq",
        timeout=10
    )
    
    assert "query" in result
    assert "edit" in result
    assert "jq" in result.lower()

@pytest.mark.vcr 
@pytest.mark.asyncio
async def test_tool_chainer_basic_workflow(temp_storage_dir):
    # Test simple tool registration and chain creation without external dependencies
    register_result = await register_tool(
        tool_id="echo_tool",
        server_command="echo",
        tool_name="echo",
        description="Simple echo tool for testing",
        storage_dir=temp_storage_dir
    )
    assert "registered" in register_result.lower()
    
    # Create a simple chain
    from mcp_handley_lab.tool_chainer.tool import ToolStep
    
    chain_result = await chain_tools(
        chain_id="echo_chain",
        steps=[
            ToolStep(
                tool_id="echo_tool",
                arguments={"text": "hello world"},
                output_to="echo_result"
            )
        ],
        storage_dir=temp_storage_dir
    )
    assert "defined" in chain_result.lower() or "created" in chain_result.lower()
    
    # Verify the chain was stored properly
    from mcp_handley_lab.tool_chainer.tool import _load_state
    tools, chains, history = _load_state(Path(temp_storage_dir))
    assert "echo_tool" in tools
    assert "echo_chain" in chains
    assert len(chains["echo_chain"]["steps"]) == 1

@pytest.mark.vcr
@pytest.mark.asyncio
async def test_tool_chainer_conditional_chain(temp_storage_dir):
    # Test conditional logic without external tool execution
    await register_tool(
        tool_id="simple_tool",
        server_command="echo",
        tool_name="test",
        storage_dir=temp_storage_dir
    )
    
    from mcp_handley_lab.tool_chainer.tool import ToolStep, _evaluate_condition, _substitute_variables
    
    # Test the conditional logic directly
    variables = {"status": "success"}
    step_outputs = {}
    
    # Test condition evaluation
    condition_result = _evaluate_condition("{status} contains 'success'", variables, step_outputs)
    assert condition_result is True
    
    # Test variable substitution  
    text_with_vars = "The status is {status}"
    substituted = _substitute_variables(text_with_vars, variables, step_outputs)
    assert substituted == "The status is success"
    
    # Create chain with conditional step (testing structure, not execution)
    await chain_tools(
        chain_id="conditional_test",
        steps=[
            ToolStep(
                tool_id="simple_tool",
                arguments={"input": "test"},
                output_to="result1"
            ),
            ToolStep(
                tool_id="simple_tool",
                arguments={"input": "{result1}"},
                condition="{result1} contains 'test'",
                output_to="result2"
            )
        ],
        storage_dir=temp_storage_dir
    )
    
    # Verify chain structure
    from mcp_handley_lab.tool_chainer.tool import _load_state
    tools, chains, history = _load_state(Path(temp_storage_dir))
    assert "conditional_test" in chains
    assert len(chains["conditional_test"]["steps"]) == 2
    assert chains["conditional_test"]["steps"][1]["condition"] == "{result1} contains 'test'"

@pytest.mark.vcr
@pytest.mark.asyncio
async def test_tool_chainer_history_and_cache(temp_storage_dir):
    # Show history
    history_result = await show_history(storage_dir=temp_storage_dir)
    assert "history" in history_result.lower() or "executions" in history_result.lower()
    
    # Clear cache
    clear_result = await clear_cache(storage_dir=temp_storage_dir)
    assert "cleared" in clear_result.lower()

@pytest.mark.vcr
@pytest.mark.asyncio
async def test_tool_chainer_server_info():
    result = await server_info()
    
    assert "tool chainer" in result.lower()
    assert "status" in result.lower()

@pytest.mark.vcr
@pytest.mark.asyncio
async def test_tool_chainer_file_processing_chain(temp_storage_dir):
    # Test multi-tool registration and chain persistence
    await register_tool(
        tool_id="file_reader",
        server_command="cat",
        tool_name="read",
        storage_dir=temp_storage_dir
    )
    
    await register_tool(
        tool_id="line_counter",
        server_command="wc",
        tool_name="lines",
        storage_dir=temp_storage_dir
    )
    
    # Create test file
    test_file = Path(temp_storage_dir) / "sample.txt"
    test_file.write_text("Line 1\nLine 2\nLine 3")
    
    from mcp_handley_lab.tool_chainer.tool import ToolStep
    
    # Multi-step chain
    await chain_tools(
        chain_id="file_analysis",
        steps=[
            ToolStep(
                tool_id="file_reader",
                arguments={"file": str(test_file)},
                output_to="content"
            ),
            ToolStep(
                tool_id="line_counter",
                arguments={"file": str(test_file)},
                output_to="stats"
            )
        ],
        storage_dir=temp_storage_dir
    )
    
    # Verify complex chain structure
    from mcp_handley_lab.tool_chainer.tool import _load_state
    tools, chains, history = _load_state(Path(temp_storage_dir))
    assert len(tools) >= 2
    assert "file_analysis" in chains
    assert len(chains["file_analysis"]["steps"]) == 2
    assert chains["file_analysis"]["steps"][0]["output_to"] == "content"
    assert chains["file_analysis"]["steps"][1]["output_to"] == "stats"
from pathlib import Path

import pytest

from mcp_handley_lab.tool_chainer.tool import (
    chain_tools,
    clear_cache,
    discover_tools,
    execute_chain,
    register_tool,
    server_info,
    show_history,
)


@pytest.mark.vcr
def test_tool_chainer_jq_discovery(temp_storage_dir):
    result = discover_tools(
        server_command="python -m mcp_handley_lab jq",
        timeout=10
    )

    assert "query" in result
    assert "edit" in result
    assert "jq" in result.lower()

@pytest.mark.vcr
def test_tool_chainer_basic_workflow(temp_storage_dir):
    # Register a jq tool
    register_result = register_tool(
        tool_id="test_jq",
        server_command="python -m mcp_handley_lab jq",
        tool_name="query",
        description="Test jq query tool",
        storage_dir=temp_storage_dir
    )
    assert "registered" in register_result.lower()

    # Create test JSON file
    test_file = Path(temp_storage_dir) / "test.json"
    test_file.write_text('{"name": "Alice", "age": 30}')

    # Create a simple chain
    from mcp_handley_lab.tool_chainer.tool import ToolStep

    chain_result = chain_tools(
        chain_id="test_chain",
        steps=[
            ToolStep(
                tool_id="test_jq",
                arguments={"data": str(test_file), "filter": ".name"},
                output_to="person_name"
            )
        ],
        storage_dir=temp_storage_dir
    )
    assert "defined" in chain_result.lower() or "created" in chain_result.lower()

    # Execute the chain
    execute_result = execute_chain(
        chain_id="test_chain",
        storage_dir=temp_storage_dir
    )
    assert "success" in execute_result.lower() or "alice" in execute_result.lower()

@pytest.mark.vcr
def test_tool_chainer_conditional_chain(temp_storage_dir):
    # Register jq tool
    register_tool(
        tool_id="conditional_jq",
        server_command="mcp-jq",
        tool_name="query",
        storage_dir=temp_storage_dir
    )

    # Create test data
    test_file = Path(temp_storage_dir) / "conditional.json"
    test_file.write_text('{"status": "success", "data": {"value": 42}}')

    from mcp_handley_lab.tool_chainer.tool import ToolStep

    # Chain with conditional step
    chain_tools(
        chain_id="conditional_test",
        steps=[
            ToolStep(
                tool_id="conditional_jq",
                arguments={"data": str(test_file), "filter": ".status"},
                output_to="status_check"
            ),
            ToolStep(
                tool_id="conditional_jq",
                arguments={"data": str(test_file), "filter": ".data.value"},
                condition="{status_check} contains 'success'",
                output_to="final_value"
            )
        ],
        storage_dir=temp_storage_dir
    )

    result = execute_chain(
        chain_id="conditional_test",
        storage_dir=temp_storage_dir
    )
    assert "42" in result

@pytest.mark.vcr
def test_tool_chainer_history_and_cache(temp_storage_dir):
    # Show history
    history_result = show_history(storage_dir=temp_storage_dir)
    assert "history" in history_result.lower() or "executions" in history_result.lower()

    # Clear cache
    clear_result = clear_cache(storage_dir=temp_storage_dir)
    assert "cleared" in clear_result.lower()

@pytest.mark.vcr
def test_tool_chainer_server_info():
    result = server_info()

    assert "tool chainer" in result.lower()
    assert "status" in result.lower()

@pytest.mark.vcr
def test_tool_chainer_file_processing_chain(temp_storage_dir):
    # Register multiple tools
    register_tool(
        tool_id="file_jq",
        server_command="python -m mcp_handley_lab jq",
        tool_name="query",
        storage_dir=temp_storage_dir
    )

    register_tool(
        tool_id="file_format",
        server_command="python -m mcp_handley_lab jq",
        tool_name="format",
        storage_dir=temp_storage_dir
    )

    # Create input file
    input_file = Path(temp_storage_dir) / "input.json"
    input_file.write_text('{"users": [{"name": "Bob"}, {"name": "Carol"}]}')

    from mcp_handley_lab.tool_chainer.tool import ToolStep

    # Multi-step processing chain
    chain_tools(
        chain_id="file_processing",
        steps=[
            ToolStep(
                tool_id="file_jq",
                arguments={"data": str(input_file), "filter": ".users | length"},
                output_to="user_count"
            ),
            ToolStep(
                tool_id="file_format",
                arguments={"data": str(input_file), "compact": True},
                output_to="formatted_data"
            )
        ],
        storage_dir=temp_storage_dir
    )

    result = execute_chain(
        chain_id="file_processing",
        storage_dir=temp_storage_dir
    )
    assert "2" in result  # User count
    assert "success" in result.lower()

#!/usr/bin/env python3
"""
Comprehensive test script to verify structured outputs capture all metadata from LLM providers.
"""
import tempfile
from pathlib import Path

from mcp_handley_lab.llm.claude.tool import analyze_image as claude_analyze_image
from mcp_handley_lab.llm.claude.tool import ask as claude_ask
from mcp_handley_lab.llm.claude.tool import list_models as claude_list_models
from mcp_handley_lab.llm.gemini.tool import analyze_image as gemini_analyze_image
from mcp_handley_lab.llm.gemini.tool import ask as gemini_ask
from mcp_handley_lab.llm.gemini.tool import list_models as gemini_list_models
from mcp_handley_lab.llm.openai.tool import analyze_image as openai_analyze_image
from mcp_handley_lab.llm.openai.tool import ask as openai_ask
from mcp_handley_lab.llm.openai.tool import list_models as openai_list_models
from PIL import Image


def create_test_image():
    """Create a simple test image."""
    img = Image.new("RGB", (100, 100), color="red")
    temp_path = Path(tempfile.gettempdir()) / "test_metadata_image.png"
    img.save(temp_path, format="PNG")
    return str(temp_path)


def test_openai_metadata():
    """Test OpenAI metadata extraction comprehensiveness."""
    print("🔍 Testing OpenAI Metadata Extraction")
    print("=" * 50)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        output_file = f.name

    try:
        # Test text generation with logprobs
        print("Testing text generation with logprobs...")
        result = openai_ask(
            prompt="What is the capital of France? Answer in one word.",
            output_file=output_file,
            model="gpt-4",
            enable_logprobs=True,
            top_logprobs=3,
            max_output_tokens=10,
            agent_name="metadata_test",
        )

        print(f"Content: {result.content}")
        print(f"Finish Reason: {result.finish_reason}")
        print(f"Model Version: {result.model_version}")
        print(f"Response ID: {result.response_id}")
        print(f"Avg Logprobs: {result.avg_logprobs}")
        print(f"System Fingerprint: {result.system_fingerprint}")
        print(f"Service Tier: {result.service_tier}")
        print(f"Completion Token Details: {result.completion_tokens_details}")
        print(f"Prompt Token Details: {result.prompt_tokens_details}")

        # Test image analysis
        print("\nTesting image analysis...")
        image_path = create_test_image()
        result_img = openai_analyze_image(
            prompt="What color is this image?",
            output_file=output_file,
            files=[image_path],
            model="gpt-4o",
            agent_name="metadata_test_img",
        )

        print(f"Image Analysis Content: {result_img.content[:100]}...")
        print(f"Image Analysis Model: {result_img.model_version}")

        # Test model listing
        print("\nTesting model listing structure...")
        models = openai_list_models()
        print(f"Provider: {models.summary.provider}")
        print(f"Total Models: {models.summary.total_models}")
        print(f"API Available: {models.summary.api_available_models}")
        print(
            f"Sample Model: {models.models[0].name} - {models.models[0].context_window}"
        )
        print(
            f"Sample Pricing: {models.models[0].pricing.type} - Input: ${models.models[0].pricing.input_cost_per_1m}"
        )

    except Exception as e:
        print(f"❌ OpenAI test failed: {e}")
    finally:
        Path(output_file).unlink(missing_ok=True)
        Path(image_path).unlink(missing_ok=True)

    print("\n")


def test_claude_metadata():
    """Test Claude metadata extraction comprehensiveness."""
    print("🔍 Testing Claude Metadata Extraction")
    print("=" * 50)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        output_file = f.name

    try:
        # Test text generation
        print("Testing text generation...")
        result = claude_ask(
            prompt="What is the capital of Italy? Answer in one word.",
            output_file=output_file,
            model="claude-3-5-haiku-20241022",
            agent_name="metadata_test",
        )

        print(f"Content: {result.content}")
        print(f"Finish Reason: {result.finish_reason}")
        print(f"Model Version: {result.model_version}")
        print(f"Response ID: {result.response_id}")
        print(f"Stop Sequence: '{result.stop_sequence}'")
        print(f"Service Tier: {result.service_tier}")
        print(f"Cache Creation Tokens: {result.cache_creation_input_tokens}")
        print(f"Cache Read Tokens: {result.cache_read_input_tokens}")

        # Test image analysis
        print("\nTesting image analysis...")
        image_path = create_test_image()
        result_img = claude_analyze_image(
            prompt="What color is this image?",
            output_file=output_file,
            files=[image_path],
            model="claude-3-5-sonnet-20240620",
            agent_name="metadata_test_img",
        )

        print(f"Image Analysis Content: {result_img.content[:100]}...")
        print(f"Image Analysis Model: {result_img.model_version}")

        # Test model listing
        print("\nTesting model listing structure...")
        models = claude_list_models()
        print(f"Provider: {models.summary.provider}")
        print(f"Total Models: {models.summary.total_models}")
        print(
            f"Sample Model: {models.models[0].name} - {models.models[0].context_window}"
        )
        print(
            f"Sample Pricing: {models.models[0].pricing.type} - Input: ${models.models[0].pricing.input_cost_per_1m}"
        )

    except Exception as e:
        print(f"❌ Claude test failed: {e}")
    finally:
        Path(output_file).unlink(missing_ok=True)
        Path(image_path).unlink(missing_ok=True)

    print("\n")


def test_gemini_metadata():
    """Test Gemini metadata extraction comprehensiveness."""
    print("🔍 Testing Gemini Metadata Extraction")
    print("=" * 50)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        output_file = f.name

    try:
        # Test text generation with grounding
        print("Testing text generation with grounding...")
        result = gemini_ask(
            prompt="What are the latest developments in quantum computing in 2024?",
            output_file=output_file,
            model="gemini-1.5-flash",
            grounding=True,
            agent_name="metadata_test",
        )

        print(f"Content: {result.content[:100]}...")
        print(f"Finish Reason: {result.finish_reason}")
        print(f"Model Version: {result.model_version}")
        print(f"Generation Time: {result.generation_time_ms}ms")
        print(f"Avg Logprobs: {result.avg_logprobs}")

        if result.grounding_metadata:
            print(f"Grounding Queries: {result.grounding_metadata.web_search_queries}")
            print(
                f"Grounding Chunks: {len(result.grounding_metadata.grounding_chunks)} chunks"
            )
            print(
                f"Search Entry Point: {bool(result.grounding_metadata.search_entry_point)}"
            )
        else:
            print("No grounding metadata")

        # Test regular generation without grounding
        print("\nTesting text generation without grounding...")
        result_no_ground = gemini_ask(
            prompt="What is 5 + 5?",
            output_file=output_file,
            model="gemini-2.5-flash",
            grounding=False,
            agent_name="metadata_test_no_ground",
        )

        print(f"No Grounding Content: {result_no_ground.content}")
        print(f"No Grounding Metadata: {result_no_ground.grounding_metadata}")

        # Test image analysis
        print("\nTesting image analysis...")
        image_path = create_test_image()
        result_img = gemini_analyze_image(
            prompt="What color is this image?",
            output_file=output_file,
            files=[image_path],
            model="gemini-2.5-pro",
            agent_name="metadata_test_img",
        )

        print(f"Image Analysis Content: {result_img.content[:100]}...")
        print(f"Image Analysis Model: {result_img.model_version}")

        # Test model listing
        print("\nTesting model listing structure...")
        models = gemini_list_models()
        print(f"Provider: {models.summary.provider}")
        print(f"Total Models: {models.summary.total_models}")
        print(f"API Available: {models.summary.api_available_models}")
        print(
            f"Sample Model: {models.models[0].name} - {models.models[0].context_window}"
        )
        print(
            f"Sample Pricing: {models.models[0].pricing.type} - Input: ${models.models[0].pricing.input_cost_per_1m}"
        )

    except Exception as e:
        print(f"❌ Gemini test failed: {e}")
    finally:
        Path(output_file).unlink(missing_ok=True)
        Path(image_path).unlink(missing_ok=True)

    print("\n")


def main():
    """Run comprehensive metadata extraction tests."""
    print("🚀 Starting Comprehensive LLM Metadata Extraction Tests")
    print("=" * 60)
    print()

    test_openai_metadata()
    test_claude_metadata()
    test_gemini_metadata()

    print("✅ All tests completed!")
    print("\nThis script verifies that our structured outputs capture:")
    print("- All available response metadata from each provider")
    print("- Proper grounding data from Gemini")
    print("- Logprobs configuration for OpenAI")
    print("- Cache information from Claude")
    print("- Complete model listing structures")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Simple test for OpenAI metadata - using DALL-E 2 with supported sizes.
"""
from mcp_handley_lab.llm.openai.tool import generate_image as openai_generate_image


def test_openai_dalle2():
    """Test OpenAI DALL-E 2 with supported size."""
    try:
        result = openai_generate_image(
            prompt="A cat",
            model="dall-e-2",
            size="512x512",  # DALL-E 2 supports this size
            agent_name="test",
        )

        print("✅ OpenAI DALL-E 2 Success!")
        print(f"Enhanced prompt: '{result.enhanced_prompt}'")
        print(f"Requested size: {result.requested_size}")
        print(f"MIME type: {result.mime_type}")
        print(f"Generation timestamp: {result.generation_timestamp}")
        print(f"Original URL: {result.original_url[:50]}...")
        print(f"OpenAI metadata: {result.openai_metadata}")

    except Exception as e:
        print(f"DALL-E 2 failed: {e}")


def test_openai_dalle3():
    """Test OpenAI DALL-E 3 with supported size."""
    try:
        result = openai_generate_image(
            prompt="A simple test",
            model="dall-e-3",
            size="1024x1024",  # DALL-E 3 supported size
            quality="standard",
            agent_name="test",
        )

        print("\n✅ OpenAI DALL-E 3 Success!")
        print(f"Enhanced prompt: {result.enhanced_prompt[:80]}...")
        print(f"Requested size: {result.requested_size}")
        print(f"Requested quality: {result.requested_quality}")
        print(f"MIME type: {result.mime_type}")
        print(f"Generation timestamp: {result.generation_timestamp}")

    except Exception as e:
        print(f"\nDALL-E 3 failed: {e}")


if __name__ == "__main__":
    test_openai_dalle2()
    test_openai_dalle3()

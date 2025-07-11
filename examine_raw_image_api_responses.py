#!/usr/bin/env python3
"""
Script to examine raw API responses from image generation providers.
This will help us identify what metadata is available but not being captured.
"""
import os

import google.genai as genai
import openai
from google.genai.types import GenerateImagesConfig


def examine_openai_response():
    """Examine raw OpenAI DALL-E API response structure."""
    print("🔍 Examining OpenAI DALL-E Raw API Response")
    print("=" * 60)

    try:
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Generate image and capture raw response
        response = client.images.generate(
            model="dall-e-3",
            prompt="A simple test image",
            size="1024x1024",
            quality="standard",
            n=1,
        )

        print(f"Response type: {type(response)}")
        print(f"Response attributes: {dir(response)}")
        print(f"Response data type: {type(response.data)}")
        print(f"Response data length: {len(response.data)}")

        if response.data:
            image_obj = response.data[0]
            print(f"\nImage object type: {type(image_obj)}")
            print(f"Image object attributes: {dir(image_obj)}")

            # Print all available fields
            for attr in dir(image_obj):
                if not attr.startswith("_"):
                    try:
                        value = getattr(image_obj, attr)
                        if not callable(value):
                            print(f"  {attr}: {value}")
                    except Exception as e:
                        print(f"  {attr}: <error: {e}>")

        # Check if response has any additional metadata
        print("\nFull response dict (if available):")
        if hasattr(response, "model_dump"):
            print(response.model_dump())
        elif hasattr(response, "__dict__"):
            print(response.__dict__)

    except Exception as e:
        print(f"❌ OpenAI examination failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n")


def examine_gemini_response():
    """Examine raw Gemini Imagen API response structure."""
    print("🔍 Examining Gemini Imagen Raw API Response")
    print("=" * 60)

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        # Generate image and capture raw response
        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt="A simple test image",
            config=GenerateImagesConfig(number_of_images=1, aspect_ratio="1:1"),
        )

        print(f"Response type: {type(response)}")
        print(f"Response attributes: {dir(response)}")

        # Print all available fields
        for attr in dir(response):
            if not attr.startswith("_"):
                try:
                    value = getattr(response, attr)
                    if not callable(value):
                        if attr == "generated_images" and value:
                            print(f"  {attr}: {len(value)} images")
                            # Examine first generated image
                            img = value[0]
                            print(f"    Image type: {type(img)}")
                            print(f"    Image attributes: {dir(img)}")
                            for img_attr in dir(img):
                                if not img_attr.startswith("_"):
                                    try:
                                        img_value = getattr(img, img_attr)
                                        if not callable(img_value):
                                            if img_attr == "image" and img_value:
                                                print(
                                                    f"      {img_attr}: <GeneratedImage object>"
                                                )
                                                # Examine the image object
                                                for img_obj_attr in dir(img_value):
                                                    if not img_obj_attr.startswith("_"):
                                                        try:
                                                            img_obj_value = getattr(
                                                                img_value, img_obj_attr
                                                            )
                                                            if not callable(
                                                                img_obj_value
                                                            ):
                                                                if (
                                                                    img_obj_attr
                                                                    == "image_bytes"
                                                                ):
                                                                    print(
                                                                        f"        {img_obj_attr}: <{len(img_obj_value)} bytes>"
                                                                    )
                                                                else:
                                                                    print(
                                                                        f"        {img_obj_attr}: {img_obj_value}"
                                                                    )
                                                        except Exception as e:
                                                            print(
                                                                f"        {img_obj_attr}: <error: {e}>"
                                                            )
                                            else:
                                                print(f"      {img_attr}: {img_value}")
                                    except Exception as e:
                                        print(f"      {img_attr}: <error: {e}>")
                        else:
                            print(f"  {attr}: {value}")
                except Exception as e:
                    print(f"  {attr}: <error: {e}>")

        # Check if response has any additional metadata
        print("\nFull response dict (if available):")
        if hasattr(response, "model_dump"):
            print(response.model_dump())
        elif hasattr(response, "__dict__"):
            print(response.__dict__)

    except Exception as e:
        print(f"❌ Gemini examination failed: {e}")
        import traceback

        traceback.print_exc()

    print("\n")


def main():
    """Run comprehensive raw API response examination."""
    print("🚀 Starting Raw Image Generation API Response Analysis")
    print("=" * 70)
    print()

    examine_openai_response()
    examine_gemini_response()

    print("✅ Raw API response analysis completed!")
    print("\nKey findings to look for:")
    print("- Request IDs, generation timestamps")
    print("- Safety/content filter results")
    print("- Model versions used")
    print("- Generation parameters used")
    print("- Any additional metadata fields")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Debug script to test Gemini grounding feature directly
"""

import os
import google.genai as genai
from google.genai.types import GenerateContentConfig, Tool, GoogleSearch, GoogleSearchRetrieval

def test_gemini_grounding():
    # Configure the client
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        print("❌ GEMINI_API_KEY not found in environment")
        return
    
    client = genai.Client(api_key=api_key)
    
    print("🔍 Testing Gemini grounding feature...")
    
    try:
        # Test with grounding enabled using proper Tool configuration
        model = 'gemini-2.5-pro'
        tools = []
        if model.startswith("gemini-1.5"):
            tools.append(Tool(google_search_retrieval=GoogleSearchRetrieval()))
        else:
            tools.append(Tool(google_search=GoogleSearch()))
        
        config = GenerateContentConfig(
            temperature=1.0,
            max_output_tokens=1000,
            tools=tools
        )
        
        # Test grounded request with a more specific query
        response = client.models.generate_content(
            model=model,
            contents='What is the current weather and forecast for this evening in San Francisco, California?',
            config=config
        )
        
        print("✅ Response received:")
        print(f"Text: {response.text}")
        
        # Check usage metadata
        if hasattr(response, 'usage_metadata'):
            print(f"Usage: {response.usage_metadata}")
        else:
            print("No usage metadata found")
        
        # Check response structure
        print("\n🔍 Response structure:")
        response_dict = response.to_json_dict()
        print(f"Keys: {list(response_dict.keys())}")
        
        if "candidates" in response_dict and response_dict["candidates"]:
            candidate = response_dict["candidates"][0]
            print(f"Candidate keys: {list(candidate.keys())}")
            
            if "grounding_metadata" in candidate:
                metadata = candidate["grounding_metadata"]
                print(f"✅ Grounding metadata found!")
                print(f"Metadata keys: {list(metadata.keys())}")
                
                # Check for the failing key
                if "web_search_queries" in metadata:
                    print(f"Web search queries: {metadata['web_search_queries']}")
                else:
                    print("❌ 'web_search_queries' key missing from grounding metadata")
                    print(f"Available keys: {list(metadata.keys())}")
                
                # Check if retrieval_metadata exists and what it contains
                if "retrieval_metadata" in metadata:
                    print(f"Retrieval metadata: {metadata['retrieval_metadata']}")
                else:
                    print("❌ 'retrieval_metadata' key missing from grounding metadata")
            else:
                print("❌ No grounding metadata found in response")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Error type: {type(e)}")
        
        # Try to inspect the error more deeply
        if hasattr(e, 'args'):
            print(f"Error args: {e.args}")

if __name__ == "__main__":
    test_gemini_grounding()
#!/usr/bin/env python3
"""
Test script for GitHub Copilot integration in Location Finding Agent
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_github_copilot():
    """Test GitHub Copilot model connection"""
    try:
        # Initialize GitHub Copilot client
        github_token = os.getenv('GITHUB_TOKEN')
        if not github_token:
            print("❌ Error: GITHUB_TOKEN is not set in environment variables")
            print("Please set your GitHub Personal Access Token in the .env file")
            return False

        client = OpenAI(
            base_url="https://models.github.ai/inference",
            api_key=github_token,
        )

        # Test the connection with a simple query
        print("🔄 Testing GitHub Copilot connection...")
        
        response = client.chat.completions.create(
            model="openai/gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Respond with a simple confirmation that you're working."
                },
                {
                    "role": "user",
                    "content": "Hello, are you working?"
                }
            ],
            temperature=0.7,
            max_tokens=50
        )

        message = response.choices[0].message.content
        print(f"✅ GitHub Copilot is working! Response: {message}")
        return True

    except Exception as e:
        print(f"❌ Error connecting to GitHub Copilot: {e}")
        print("Please check your GITHUB_TOKEN and internet connection")
        return False

def test_location_parsing():
    """Test location parsing functionality"""
    try:
        github_token = os.getenv('GITHUB_TOKEN')
        client = OpenAI(
            base_url="https://models.github.ai/inference",
            api_key=github_token,
        )

        print("🔄 Testing location parsing...")
        
        test_message = "I'm looking for cafes with good pastries and wifi in downtown Seattle"
        
        response = client.chat.completions.create(
            model="openai/gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": """You are a location parsing assistant. Extract the following from user messages:
                    1. Location (city, neighborhood, address)
                    2. Preferences (pastries, food, study, wifi, outlets)
                    3. Any other specific requirements
                    
                    Return JSON format:
                    {
                        "location": "extracted location",
                        "filters": ["list", "of", "filters"],
                        "requirements": "additional requirements"
                    }"""
                },
                {
                    "role": "user",
                    "content": test_message
                }
            ],
            temperature=0.7
        )

        result = response.choices[0].message.content
        print(f"✅ Location parsing works! Result: {result}")
        return True

    except Exception as e:
        print(f"❌ Error testing location parsing: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting GitHub Copilot integration tests...\n")
    
    # Test basic connection
    basic_test = test_github_copilot()
    print()
    
    # Test location parsing if basic test passes
    if basic_test:
        parsing_test = test_location_parsing()
        print()
        
        if parsing_test:
            print("✅ All tests passed! Your Location Finding Agent is ready to use GitHub Copilot models.")
        else:
            print("⚠️  Basic connection works, but location parsing needs attention.")
    else:
        print("❌ Please fix the GitHub token setup before proceeding.")
    
    print("\n📋 Next steps:")
    print("1. Make sure you have a .env file with GITHUB_TOKEN set")
    print("2. Add your GOOGLE_MAPS_API_KEY to the .env file")
    print("3. Run the main application: python app.py")

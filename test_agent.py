"""
Test script for Location Finding Agent
Tests the agent's ability to parse intent and call Google Maps tools
"""

import asyncio
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_agent():
    """Test the location finding agent"""
    print("🧪 Testing Location Finding Agent...")
    
    try:
        # Import after loading env vars
        from app_agent import initialize_agent, LocationTools
        
        # Test 1: Initialize agent
        print("\n1️⃣ Initializing agent...")
        agent = await initialize_agent()
        print("✅ Agent initialized successfully")
        
        # Test 2: Test Google Maps tool directly
        print("\n2️⃣ Testing Google Maps tool...")
        result = LocationTools.search_places(
            location="Seattle, WA",
            place_type="cafe",
            filters=["coffee", "wifi"],
            max_results=3
        )
        
        tool_result = json.loads(result)
        if 'places' in tool_result and len(tool_result['places']) > 0:
            print(f"✅ Tool found {len(tool_result['places'])} places")
            print(f"   First place: {tool_result['places'][0]['name']}")
        else:
            print("❌ Tool didn't return places")
            print(f"   Result: {tool_result}")
        
        # Test 3: Test agent conversation
        print("\n3️⃣ Testing agent conversation...")
        thread = agent.get_new_thread()
        
        test_message = "Find me coffee shops with good wifi in Seattle"
        print(f"   User: {test_message}")
        
        agent_result = await agent.run(test_message, thread=thread)
        print(f"   Agent: {agent_result.text[:200]}...")
        
        if hasattr(agent_result, 'tool_results') and agent_result.tool_results:
            print("✅ Agent successfully called tools")
        else:
            print("⚠️ Agent didn't call any tools")
        
        # Test 4: Follow-up conversation
        print("\n4️⃣ Testing follow-up conversation...")
        followup_message = "What about the ratings for these places?"
        print(f"   User: {followup_message}")
        
        followup_result = await agent.run(followup_message, thread=thread)
        print(f"   Agent: {followup_result.text[:200]}...")
        
        print("\n🎉 All tests completed!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure to install: pip install agent-framework")
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    # Check environment variables
    if not os.getenv('GITHUB_TOKEN'):
        print("❌ GITHUB_TOKEN not found in environment")
        exit(1)
    
    if not os.getenv('GOOGLE_MAPS_API_KEY'):
        print("❌ GOOGLE_MAPS_API_KEY not found in environment")
        exit(1)
    
    # Run tests
    asyncio.run(test_agent())

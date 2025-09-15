"""OpenAI agent service for handling chat interactions."""

import json
import logging
from typing import List, Dict, Optional
from openai import AsyncOpenAI

from ..config import config
from ..models.data_models import ConversationMessage, ChatRequest, SearchResult
from ..services.cafe_search_service import CafeSearchService
from ..services.cafe_details_service import CafeDetailsService

logger = logging.getLogger(__name__)

class OpenAIAgentService:
    """Service for handling OpenAI agent interactions."""
    
    def __init__(self, cafe_search_service: CafeSearchService, cafe_details_service: CafeDetailsService):
        self.client = AsyncOpenAI(
            base_url=config.openai_base_url,
            api_key=config.github_token,
        )
        self.cafe_search_service = cafe_search_service
        self.cafe_details_service = cafe_details_service
        
        # Function definitions for OpenAI function calling
        self.functions = [
            self._get_find_cute_cafes_function(),
            self._get_cafe_details_function()
        ]
        
        logger.info("OpenAI Agent service initialized")
    
    async def run_cafe_agent(self, chat_request: ChatRequest) -> SearchResult:
        """Run the cafe finding agent using OpenAI function calling."""
        logger.info(f"Running cafe agent for message: '{chat_request.message}'")
        
        try:
            messages = self._build_messages(chat_request)
            
            # Make the initial request with function calling
            response = await self.client.chat.completions.create(
                model=config.model_name,
                messages=messages,
                tools=self.functions,
                tool_choice="auto",
                temperature=0.7
            )
            
            message = response.choices[0].message
            places_data = []
            
            # Check if the model wants to call a function
            if message.tool_calls:
                # Add the assistant's message to the conversation
                messages.append(message)
                
                # Process each tool call
                for tool_call in message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Calling function: {function_name} with args: {function_args}")
                    
                    if function_name == "find_cute_cafes":
                        function_result = await self._handle_find_cafes(function_args)
                    elif function_name == "get_cafe_details_and_reviews":
                        function_result = await self._handle_cafe_details(function_args)
                    else:
                        function_result = SearchResult(text="Unknown function called", places=[])
                    
                    places_data.extend(function_result.places)
                    
                    # Add the function result to the conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": function_result.text
                    })
                
                # Get the final response from the model
                final_response = await self.client.chat.completions.create(
                    model=config.model_name,
                    messages=messages,
                    temperature=0.7
                )
                
                return SearchResult(
                    text=final_response.choices[0].message.content,
                    places=places_data
                )
            else:
                # No function call needed, return the direct response
                return SearchResult(
                    text=message.content,
                    places=[]
                )
                
        except Exception as e:
            logger.error(f"Error in run_cafe_agent: {e}")
            return SearchResult(
                text=f"I apologize, but I'm having trouble processing your request right now. Please try again. Error: {str(e)}",
                places=[]
            )
    
    def _build_messages(self, chat_request: ChatRequest) -> List[Dict]:
        """Build the message list for OpenAI API."""
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt()
            }
        ]
        
        # Add conversation history
        if chat_request.conversation_history:
            logger.info(f"Adding {len(chat_request.conversation_history)} messages from conversation history")
            for msg in chat_request.conversation_history:
                if msg.get('type') == 'user':
                    messages.append({
                        "role": "user",
                        "content": msg.get('content', '')
                    })
                elif msg.get('type') == 'bot':
                    messages.append({
                        "role": "assistant", 
                        "content": msg.get('content', '')
                    })
        
        # Build enhanced message with filter context
        enhanced_message = chat_request.message
        if chat_request.filter_states:
            include_filters = [f for f, state in chat_request.filter_states.items() if state == 'include']
            exclude_filters = [f for f, state in chat_request.filter_states.items() if state == 'exclude']
            
            if include_filters or exclude_filters:
                enhanced_message += "\\n\\nAdditional preferences:"
                if include_filters:
                    enhanced_message += f" I want places with: {', '.join(include_filters)}."
                if exclude_filters:
                    enhanced_message += f" I want to avoid: {', '.join(exclude_filters)}."
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": enhanced_message
        })
        
        return messages
    
    async def _handle_find_cafes(self, function_args: Dict) -> SearchResult:
        """Handle the find_cute_cafes function call."""
        from ..models.data_models import SearchPreferences
        
        preferences = SearchPreferences(
            location=function_args.get("location", ""),
            preferences=function_args.get("preferences", "").split(),
            avoid=function_args.get("avoid", "").split(),
            underrated=function_args.get("underrated", False),
            specific_cafe_names=function_args.get("specific_cafe_names", "").split(',') if function_args.get("specific_cafe_names") else []
        )
        
        return self.cafe_search_service.search_cafes(preferences)
    
    async def _handle_cafe_details(self, function_args: Dict) -> SearchResult:
        """Handle the get_cafe_details_and_reviews function call."""
        cafe_name = function_args.get("cafe_name", "")
        location = function_args.get("location", config.default_location)
        
        return self.cafe_details_service.get_cafe_details(cafe_name, location)
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """You are a specialized cafe finding assistant focused on discovering cute, charming, aesthetic cafes. 
You have access to two main tools:

1. **find_cute_cafes**: Use this to search for cafes in a location based on preferences
2. **get_cafe_details_and_reviews**: Use this to get detailed information about a specific cafe including reviews, hours, contact info

**IMPORTANT: Only use these functions when users specifically request cafe-related information. Do NOT use them for:**
- General greetings ("hi", "hello", "how are you")
- General questions about your capabilities
- Casual conversation that doesn't involve cafes

**Use find_cute_cafes when users ask for:**
- Cafe recommendations in a specific location
- Coffee shop suggestions
- Restaurant or dining recommendations
- Places to eat or drink
- Study spots or work-friendly cafes
- Questions about specific cafe names or locations

**Use get_cafe_details_and_reviews when users ask for:**
- More details about a specific cafe mentioned in conversation
- Reviews for a particular cafe
- Hours, phone number, or address of a specific cafe
- Follow-up questions about cafes from previous recommendations
- "Tell me more about [Cafe Name]"
- "What are the reviews like for [Cafe Name]?"

**Special handling for specific cafe queries:**
- If the user asks about specific cafes by name (e.g., "tell me about Blue Bottle Coffee and Starbucks"), use find_cute_cafes with specific_cafe_names parameter
- If the user asks for MORE details about a cafe (reviews, hours, etc.), use get_cafe_details_and_reviews
- This will return detailed information including recent customer reviews

Key behaviors when finding cafes:
1. **Always prioritize cafes** - Focus on coffee shops and cafes first, only include restaurants if the user specifically asks for food
2. **Look for cute/aesthetic places** - Prioritize places that are likely to be Instagram-worthy, cozy, or have character
3. **Parse location carefully** - Extract any location mentions including neighborhoods, cities, districts, or landmarks
4. **Understand preferences** - Pay attention to mentions of:
   - pastries, bakery items, croissants, muffins
   - wifi, internet, work-friendly spaces
   - power outlets, laptop-friendly environments
   - comfortable seating, cozy atmosphere
   - specific food preferences

5. **Handle "underrated" requests** - If users want hidden gems or underrated places, set the underrated flag to true
6. **Handle specific cafe requests** - If user mentions specific cafe names, set specific_cafe_names parameter with comma-separated names
7. **Handle follow-up questions** - If user asks for more details about a specific cafe, use get_cafe_details_and_reviews

When a user asks for cafe recommendations:
1. Extract the location (if none provided, default to Seattle)
2. Check if they're asking about specific cafes by name (multiple names should be comma-separated)
3. Identify their preferences (pastries, wifi, outlets, etc.)
4. Note anything they want to avoid
5. Call the find_cute_cafes function with the parsed information
6. Present the results in a friendly, enthusiastic way

When a user asks for details about a specific cafe:
1. Extract the cafe name from their question
2. Extract or infer the location context from conversation history or their question
3. Call get_cafe_details_and_reviews to get comprehensive information
4. Present detailed information including reviews, hours, and contact details

In the response to the user, bold the name of the cafes if found. Don't give the address, but you can mention the neighborhood if they recommendations are in different places.

If the user asks a short question, give a short concise answer while remaining friendly.
For general conversation, respond helpfully without using any tools.
"""
    
    def _get_find_cute_cafes_function(self) -> Dict:
        """Get the find_cute_cafes function definition."""
        return {
            "type": "function",
            "function": {
                "name": "find_cute_cafes",
                "description": "Find cute cafes using Google Maps API based on location and preferences, or search for a specific cafe by name",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The location to search for cafes (city, neighborhood, or address)"
                        },
                        "preferences": {
                            "type": "string",
                            "description": "User preferences like 'pastries', 'wifi', 'outlets', 'food', 'coffee', 'seating'",
                            "default": ""
                        },
                        "avoid": {
                            "type": "string", 
                            "description": "Things to avoid",
                            "default": ""
                        },
                        "underrated": {
                            "type": "boolean",
                            "description": "Whether to focus on underrated/hidden gems with fewer reviews",
                            "default": False
                        },
                        "specific_cafe_names": {
                            "type": "string",
                            "description": "Comma-separated names of specific cafes to search for (returns only those cafes)",
                            "default": ""
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    
    def _get_cafe_details_function(self) -> Dict:
        """Get the cafe details function definition."""
        return {
            "type": "function",
            "function": {
                "name": "get_cafe_details_and_reviews",
                "description": "Get detailed information, reviews, hours, and other details about a specific cafe",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cafe_name": {
                            "type": "string",
                            "description": "Name of the cafe to get detailed information about"
                        },
                        "location": {
                            "type": "string",
                            "description": "Location to search in (city, neighborhood, or address)",
                            "default": "Seattle, WA"
                        }
                    },
                    "required": ["cafe_name"]
                }
            }
        }
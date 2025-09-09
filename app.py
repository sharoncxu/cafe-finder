from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from openai import OpenAI
import googlemaps
from dotenv import load_dotenv
import json
import logging

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='frontend/build', static_url_path='')
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Debug: Show which tokens are loaded
logger.info(f"GitHub token loaded: {os.getenv('GITHUB_TOKEN')[:10]}...")
logger.info(f"Google Maps key loaded: {os.getenv('GOOGLE_MAPS_API_KEY')[:10]}...")

# Initialize GitHub Copilot (GHCP) client
github_token = os.getenv('GITHUB_TOKEN')
if not github_token:
    logger.error("GITHUB_TOKEN is required for GitHub Copilot models")
    raise ValueError("GITHUB_TOKEN environment variable is required")

client = OpenAI(
    base_url="https://models.github.ai/inference",
    api_key=github_token,
)

# Initialize Google Maps API
gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))

# Chat history storage (in-memory for this example)
# In production, you'd want to use a database or session storage
chat_histories = {}

class LocationAgent:
    def __init__(self):
        self.filter_keywords = {
            'pastries': ['bakery', 'pastry', 'croissant', 'muffin', 'scone', 'danish'],
            'food': ['restaurant', 'cafe', 'bistro', 'eatery', 'dining'],
            'study': ['quiet', 'study', 'workspace', 'coworking', 'library'],
            'wifi': ['wifi', 'internet', 'wireless'],
            'outlets': ['power', 'charging', 'outlets', 'plugs']
        }
    
    def parse_user_message(self, message, filter_states=None, chat_history=None):
        """Extract location and preferences from user message using GitHub Copilot models"""
        logger.info(f"Parsing message: '{message}'")
        logger.info(f"Filter states: {filter_states}")
        logger.info(f"Chat history length: {len(chat_history) if chat_history else 0}")
        
        # Build filter context for the AI
        filter_context = ""
        if filter_states:
            include_filters = [f for f, state in filter_states.items() if state == 'include']
            exclude_filters = [f for f, state in filter_states.items() if state == 'exclude']
            
            if include_filters:
                filter_context += f" User wants places that MUST have: {', '.join(include_filters)}."
            if exclude_filters:
                filter_context += f" User wants to AVOID places with: {', '.join(exclude_filters)}."
        
        # Build chat context
        chat_context = ""
        if chat_history and len(chat_history) > 0:
            recent_messages = chat_history[-4:]  # Use last 4 messages for context
            chat_context = "Previous conversation context:\n"
            for msg in recent_messages:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')[:200]  # Limit length
                chat_context += f"{role}: {content}\n"
            chat_context += "\nConsider this context when parsing the current message."
        
        try:
            # Build messages for the API call
            messages = [
                {
                    "role": "system",
                    "content": f"""You are a location parsing assistant powered by GitHub Copilot. Extract the following from user messages:
                    1. Location (city, neighborhood, address) - if not specified, check conversation history
                    2. Preferences (pastries, food, study, wifi, outlets)
                    3. Any other specific requirements
                    
                    {filter_context}
                    
                    {chat_context}
                    
                    Return ONLY valid JSON. No extra commentary. The JSON must include keys: location, include_filters, exclude_filters, requirements.
                    {{
                        "location": "extracted location",
                        "include_filters": ["list", "of", "must-have", "filters"],
                        "exclude_filters": ["list", "of", "filters", "to", "avoid"],
                        "requirements": "additional requirements"
                    }}"""
                }
            ]
            
            # Add recent chat history if available
            if chat_history:
                recent_chat = chat_history[-2:]  # Last 2 exchanges
                for msg in recent_chat:
                    messages.append({
                        "role": msg.get('role', 'user'),
                        "content": msg.get('content', '')[:500]  # Limit content length
                    })
            
            # Add current message
            messages.append({
                "role": "user",
                "content": message
            })
            
            response = client.chat.completions.create(
                model="openai/gpt-4.1-mini",  # GitHub Copilot model
                messages=messages,
                temperature=0.7,
                top_p=0.9
            )
            
            raw_response = response.choices[0].message.content
            logger.info(f"Raw GitHub Copilot response: '{raw_response}'")
            
            # Try to parse the JSON
            result = json.loads(raw_response)
            logger.info(f"Successfully parsed JSON: {result}")
            
            # Merge with filter states from frontend
            if filter_states:
                frontend_include = [f for f, state in filter_states.items() if state == 'include']
                frontend_exclude = [f for f, state in filter_states.items() if state == 'exclude']
                
                # Combine AI-detected filters with frontend filter states
                result['include_filters'] = list(set(result.get('include_filters', []) + frontend_include))
                result['exclude_filters'] = list(set(result.get('exclude_filters', []) + frontend_exclude))
            
            # Validate the structure
            location = result.get('location', '').strip()
            include_filters = result.get('include_filters', [])
            exclude_filters = result.get('exclude_filters', [])
            requirements = result.get('requirements', '')
            
            logger.info(f"Extracted - Location: '{location}', Include: {include_filters}, Exclude: {exclude_filters}, Requirements: '{requirements}'")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Failed to parse response: '{raw_response if 'raw_response' in locals() else 'No response'}'")
            return {"location": "", "include_filters": [], "exclude_filters": [], "requirements": ""}
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return {"location": "", "include_filters": [], "exclude_filters": [], "requirements": ""}
    
    def generate_natural_response(self, message, parsed_data, places, chat_history=None):
        """Generate a natural language response from GitHub Copilot based on user message and found places"""
        logger.info(f"Generating natural language response for: '{message}'")
        
        try:
            # Prepare context about found places
            places_context = ""
            if places:
                places_context = f"Found {len(places)} places: " + ", ".join([
                    f"{place.get('name', 'Unknown')} (Rating: {place.get('rating', 'N/A')})"
                    for place in places[:5]
                ])
            else:
                places_context = "No suitable places found."
            
            # Format filter information
            include_filters = parsed_data.get('include_filters', [])
            exclude_filters = parsed_data.get('exclude_filters', [])
            
            filter_info = ""
            if include_filters:
                filter_info += f"Must have: {', '.join(include_filters)}. "
            if exclude_filters:
                filter_info += f"Avoiding: {', '.join(exclude_filters)}. "
            
            response = client.chat.completions.create(
                model="openai/gpt-4.1-mini",
                messages=[
                    {
                        "role": "system", 
                        "content": f"""You are a friendly cafe and restaurant finding assistant powered by GitHub Copilot. 
                        The user asked: "{message}". If they ask for a cafe, don't recommend restaurants or bars even if the bar is named "something cafe".
                        
                        You parsed their request as:
                        - Location: {parsed_data.get('location', 'Not specified')}
                        - {filter_info}
                        - Requirements: {parsed_data.get('requirements', 'None')}
                        
                        Search results: {places_context}
                        
                        Provide a helpful, conversational response that acknowledges their request and explains what you found. 
                        Be friendly and enthusiastic about helping them find great places!"""
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                temperature=0.8,
                top_p=0.9
            )
            
            natural_response = response.choices[0].message.content
            logger.info(f"Generated natural response: '{natural_response}'")
            return natural_response
            
        except Exception as e:
            logger.error(f"Error generating natural response: {e}")
            return "I found some great options for you! Let me share the details below."
    
    def search_places(self, location, include_filters, exclude_filters=None, radius=1000):
        """Search for places using Google Maps API"""
        try:
            # Geocode the location
            geocode_result = gmaps.geocode(location)
            if not geocode_result:
                return []
            
            lat_lng = geocode_result[0]['geometry']['location']
            
            # Build search query based on include filters
            query_terms = []
            for filter_name in include_filters:
                if filter_name in self.filter_keywords:
                    query_terms.extend(self.filter_keywords[filter_name])
            
            # Search for cafes and restaurants
            places_result = gmaps.places_nearby(
                location=lat_lng,
                radius=radius,
                type='restaurant',
                keyword=' '.join(query_terms) if query_terms else 'cafe'
            )
            
            return places_result.get('results', [])
        except Exception as e:
            logger.error(f"Error searching places: {e}")
            return []
    
    def rank_places(self, places, include_filters, exclude_filters=None):
        """Rank places based on rating and filter relevance with include/exclude logic"""
        if exclude_filters is None:
            exclude_filters = []
            
        scored_places = []
        
        for place in places:
            score = place.get('rating', 0) * 20  # Base score from rating
            
            # Get place description for matching
            name_desc = (place.get('name', '') + ' ' + 
                        ' '.join(place.get('types', []))).lower()
            
            # Check for exclude filters first - if found, heavily penalize or skip
            excluded = False
            for filter_name in exclude_filters:
                if filter_name in self.filter_keywords:
                    for keyword in self.filter_keywords[filter_name]:
                        if keyword in name_desc:
                            score -= 50  # Heavy penalty for excluded features
                            excluded = True
                            break
            
            # Bonus points for include filters
            include_matches = 0
            for filter_name in include_filters:
                if filter_name in self.filter_keywords:
                    for keyword in self.filter_keywords[filter_name]:
                        if keyword in name_desc:
                            score += 15  # Higher bonus for explicitly requested features
                            include_matches += 1
                            break
            
            # Additional bonus if place matches multiple include filters
            if include_matches > 1:
                score += include_matches * 5
            
            # Only include places that aren't heavily penalized by exclusions
            if not excluded or score > 0:
                scored_places.append({
                    'place': place,
                    'score': max(score, 0),  # Ensure score doesn't go negative
                    'include_matches': include_matches,
                    'excluded': excluded
                })
        
        # Sort by score, then by include matches, then by rating
        scored_places.sort(key=lambda x: (x['score'], x['include_matches'], x['place'].get('rating', 0)), reverse=True)
        
        # Filter out heavily excluded places if we have good alternatives
        if len(scored_places) > 5:
            non_excluded = [item for item in scored_places if not item['excluded']]
            if len(non_excluded) >= 5:
                scored_places = non_excluded
        
        return [item['place'] for item in scored_places[:5]]
    
    def format_recommendations(self, places):
        """Format place recommendations for chat response, ordered from best to worst"""
        if not places:
            return "I couldn't find any places matching your criteria. Try expanding your search area or adjusting your filters."
        
        recommendations = []
        for i, place in enumerate(places, 1):
            name = place.get('name', 'Unknown')
            rating = place.get('rating', 'No rating')
            price_level = place.get('price_level', 'Price not available')
            address = place.get('vicinity', 'Address not available')
            
            rec = f"{i}. **{name}**\n"
            rec += f"   📍 {address}\n"
            rec += f"   ⭐ {rating}/5"
            if price_level != 'Price not available':
                rec += f" | {'$' * price_level}"
            rec += "\n"
            
            recommendations.append(rec)
        
        return "\n".join(recommendations)

agent = LocationAgent()

@app.route('/api/health')
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '')
        filter_states = data.get('filterStates', {})
        session_id = data.get('sessionId', 'default')  # Get session ID for chat history
        
        logger.info(f"=== NEW CHAT REQUEST ===")
        logger.info(f"Received message: '{message}'")
        logger.info(f"Filter states: {filter_states}")
        logger.info(f"Session ID: {session_id}")
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        # Get or create chat history for this session
        if session_id not in chat_histories:
            chat_histories[session_id] = []
        
        chat_history = chat_histories[session_id]
        
        # Parse user message for structured data with chat history
        parsed = agent.parse_user_message(message, filter_states, chat_history)
        location = parsed.get('location', '').strip()
        include_filters = parsed.get('include_filters', [])
        exclude_filters = parsed.get('exclude_filters', [])
        
        logger.info(f"Final parsed result - Location: '{location}', Include: {include_filters}, Exclude: {exclude_filters}")
        
        if not location:
            logger.warning("No location found in message")
            # Add to chat history even for error responses
            chat_histories[session_id].append({
                "role": "user", 
                "content": message
            })
            chat_histories[session_id].append({
                "role": "assistant", 
                "content": "I need to know your location to help you find great places. Could you please specify a city, neighborhood, or address?"
            })
            return jsonify({
                "response": "I need to know your location to help you find great places. Could you please specify a city, neighborhood, or address?",
                "sessionId": session_id
            })
                
        # Search for places
        logger.info(f"Searching for places in '{location}' with include filters: {include_filters}, exclude filters: {exclude_filters}")
        places = agent.search_places(location, include_filters, exclude_filters)
        logger.info(f"Found {len(places)} places from Google Maps")
        
        # Rank and get top 5
        top_places = agent.rank_places(places, include_filters, exclude_filters)
        logger.info(f"Ranked to top {len(top_places)} places")
        
        # Generate natural language response from GitHub Copilot with chat history
        natural_response = agent.generate_natural_response(message, parsed, top_places, chat_history)
        
        # Format structured recommendations
        structured_recommendations = agent.format_recommendations(top_places)
        
        # Add to chat history
        chat_histories[session_id].append({
            "role": "user", 
            "content": message
        })
        chat_histories[session_id].append({
            "role": "assistant", 
            "content": natural_response,
            "places": top_places,
            "location": location,
            "filters": {"include": include_filters, "exclude": exclude_filters}
        })
        
        # Keep chat history manageable (last 20 messages)
        if len(chat_histories[session_id]) > 20:
            chat_histories[session_id] = chat_histories[session_id][-20:]
        
        logger.info(f"=== CHAT REQUEST COMPLETE ===")
        
        return jsonify({
            "response": natural_response,  # Natural language response from GitHub Copilot
            "structured_response": structured_recommendations,  # Formatted place details
            "places": top_places,
            "location": location,
            "filters": include_filters,  # For backward compatibility
            "include_filters": include_filters,
            "exclude_filters": exclude_filters,
            "parsed_data": parsed,  # Include the full parsed JSON
            "sessionId": session_id,  # Return session ID
            "chatHistory": chat_histories[session_id][-10:]  # Return last 10 messages
        })
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({"error": "Something went wrong. Please try again."}), 500

@app.route('/api/places', methods=['GET'])
def get_places():
    try:
        location = request.args.get('location', '')
        filters = request.args.getlist('filters')
        
        if not location:
            return jsonify({"error": "Location is required"}), 400
        
        places = agent.search_places(location, filters)
        top_places = agent.rank_places(places, filters)
        
        return jsonify({
            "places": top_places,
            "count": len(top_places)
        })
        
    except Exception as e:
        logger.error(f"Places error: {e}")
        return jsonify({"error": "Something went wrong. Please try again."}), 500

@app.route('/')
def serve_frontend():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
from openai import OpenAI
import googlemaps
from dotenv import load_dotenv
import json
import logging
import re
from typing import List, Dict, Optional, Tuple

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

class LocationAgent:
    def __init__(self):
        self.filter_keywords = {
            'pastries': ['bakery', 'pastry', 'croissant', 'muffin', 'scone', 'danish', 'donut', 'bagel', 'macaron', 'cake'],
            'food': ['restaurant', 'cafe', 'bistro', 'eatery', 'dining', 'kitchen', 'grill', 'tavern'],
            'coffee': ['coffee', 'espresso', 'cappuccino', 'latte', 'americano', 'brew', 'roastery'],
            'wifi': ['wifi', 'internet', 'wireless', 'free wifi', 'good wifi'],
            'outlets': ['power outlets', 'electrical outlets', 'laptop plugs', 'wall outlets', 'power sockets', 'laptop friendly', 'work friendly'],
            'seating': ['seating', 'seats', 'tables', 'comfortable seating', 'plenty of seats', 'lots of seating', 'spacious', 'ample seating', 'cozy seating']
        }
        
        # Known major cities to help with geocoding
        self.major_cities = [
            'Seattle', 'San Francisco', 'New York', 'Los Angeles', 'Chicago', 
            'Boston', 'Portland', 'Denver', 'Austin', 'Miami', 'Atlanta'
        ]
        
        # Cache for geocoding results to avoid repeated API calls
        self.geocoding_cache = {}
        
    def get_place_photos(self, place: Dict, max_photos: int = 1) -> List[str]:
        """Get photo URLs for a place"""
        try:
            place_id = place.get('place_id')
            if not place_id:
                return []
            
            # Get place details including photos
            details = gmaps.place(
                place_id=place_id, 
                fields=['photo'],
                language='en'  # Ensure consistent language
            )
            
            photos = details.get('result', {}).get('photos', [])
            
            if not photos:
                return []
            
            photo_urls = []
            for photo in photos[:max_photos]:
                photo_reference = photo.get('photo_reference')
                if photo_reference:
                    # Generate photo URL with better parameters
                    photo_url = (
                        f"https://maps.googleapis.com/maps/api/place/photo"
                        f"?maxwidth=400"
                        f"&maxheight=300"
                        f"&photo_reference={photo_reference}"
                        f"&key={os.getenv('GOOGLE_MAPS_API_KEY')}"
                    )
                    photo_urls.append(photo_url)
            
            return photo_urls
            
        except Exception as e:
            logger.warning(f"Error getting photos for place {place.get('name', 'Unknown')}: {e}")
            return []
    
    def get_google_maps_link(self, place: Dict) -> str:
        """Generate Google Maps deep link for a place"""
        try:
            place_id = place.get('place_id')
            if place_id:
                # Use place_id for most accurate link
                return f"https://maps.google.com/maps?q=place_id:{place_id}"
            
            # Fallback: use name and location
            name = place.get('name', '').replace(' ', '+')
            lat = place.get('geometry', {}).get('location', {}).get('lat')
            lng = place.get('geometry', {}).get('location', {}).get('lng')
            
            if lat and lng:
                return f"https://maps.google.com/maps?q={name}@{lat},{lng}"
            
            # Last resort: search by name
            if name:
                return f"https://maps.google.com/maps?q={name}"
            
            return "https://maps.google.com"
            
        except Exception as e:
            logger.warning(f"Error generating Google Maps link for {place.get('name', 'Unknown')}: {e}")
            return "https://maps.google.com"
    
    def enhance_location_query(self, location: str) -> List[str]:
        """
        Generate multiple location query variants to improve geocoding success
        """
        location = location.strip()
        queries = [location]
        
        # If it's likely a neighborhood/area, try adding major cities
        if len(location.split()) <= 3 and not any(city.lower() in location.lower() for city in self.major_cities):
            # Add common city suffixes for US locations
            for city in ['Seattle', 'San Francisco', 'New York', 'Los Angeles', 'Chicago']:
                queries.append(f"{location}, {city}")
                queries.append(f"{location} neighborhood, {city}")
                queries.append(f"{location} area, {city}")
        
        # Try adding "WA" for Pacific Northwest neighborhoods
        if any(keyword in location.lower() for keyword in ['queen anne', 'south lake union', 'capitol hill', 'fremont', 'ballard']):
            queries.extend([
                f"{location}, Seattle, WA",
                f"{location} Seattle",
                f"{location} neighborhood Seattle"
            ])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_queries = []
        for query in queries:
            if query.lower() not in seen:
                seen.add(query.lower())
                unique_queries.append(query)
        
        logger.info(f"Enhanced location queries: {unique_queries}")
        return unique_queries
    
    def smart_geocode(self, location: str) -> Optional[Dict]:
        """
        Try multiple location query variants to find the best geocoding result
        """
        if location in self.geocoding_cache:
            logger.info(f"Using cached geocoding result for: {location}")
            return self.geocoding_cache[location]
        
        location_queries = self.enhance_location_query(location)
        
        for query in location_queries:
            try:
                logger.info(f"Trying geocoding query: '{query}'")
                geocode_result = gmaps.geocode(query)
                
                if geocode_result:
                    result = geocode_result[0]
                    logger.info(f"Successful geocoding for '{query}': {result['formatted_address']}")
                    
                    # Cache the successful result
                    self.geocoding_cache[location] = result
                    return result
                    
            except Exception as e:
                logger.warning(f"Geocoding failed for '{query}': {e}")
                continue
        
        logger.warning(f"All geocoding attempts failed for: {location}")
        return None
    
    def parse_user_message(self, message: str, filter_states: Optional[Dict] = None, conversation_history: Optional[List] = None) -> Dict:
        """Extract location and preferences from user message using GitHub Copilot models"""
        logger.info(f"Parsing message: '{message}'")
        logger.info(f"Filter states: {filter_states}")
        
        # Build filter context for the AI
        filter_context = ""
        if filter_states:
            include_filters = [f for f, state in filter_states.items() if state == 'include']
            exclude_filters = [f for f, state in filter_states.items() if state == 'exclude']
            
            if include_filters:
                filter_context += f" User wants places that MUST have: {', '.join(include_filters)}."
            if exclude_filters:
                filter_context += f" User wants to AVOID places with: {', '.join(exclude_filters)}."
        
        # Build conversation history context
        history_context = ""
        if conversation_history and len(conversation_history) > 0:
            recent_history = conversation_history[-4:]  # Last 4 messages for context
            history_summary = []
            for msg in recent_history:
                if msg.get('type') == 'user':
                    history_summary.append(f"User asked: {msg.get('content', '')}")
                elif msg.get('type') == 'bot':
                    # Extract location if mentioned in previous response
                    content = msg.get('content', '')
                    if 'Seattle' in content or 'seattle' in content:
                        history_summary.append("Previously searched in Seattle")
                    else:
                        history_summary.append(f"Bot responded about places")
            
            if history_summary:
                history_context = f"\n\nConversation context: {'; '.join(history_summary)}"

        try:
            # Build messages array including conversation history
            messages = [
                {
                    "role": "system",
                    "content": f"""You are an expert cafe locater identifier specializing in identifying aesthetic cafes. Extract information from user messages about finding places to eat/drink/work. Focus on cafes where the reviews say "cute". If the user mentions underrated, only show cafes with less than 1000 reviews.

IMPORTANT: Be very liberal with location extraction. Extract ANY location mentions including:
- Neighborhoods (Queen Anne, South Lake Union, Capitol Hill, SoHo, Mission District)
- Districts and areas (Downtown, Uptown, Midtown, Financial District)
- Cities (Seattle, San Francisco, New York)
- Addresses or cross streets
- Landmarks or popular areas

For preferences, look for mentions of:
- pastries (bakery, croissants, muffins, donuts, pastries)
- food (restaurant, dining, meals, lunch, dinner)
- coffee (coffee, espresso, latte, cappuccino, brew)
- wifi (wifi, internet, wireless)
- outlets (power outlets, electrical outlets, laptop plugs, wall outlets for laptops)
- seating (seating, seats, tables, comfortable seating, spacious)

If the user mentions any of these following conditions, behave accordingly:
- underrated (only show locations with less than 1000 reviews)

{filter_context}{history_context}

Return ONLY valid JSON with these exact keys:
{{
    "location": "extracted location (be liberal - include neighborhoods, districts, areas)",
    "include_filters": ["filters", "user", "specifically", "wants"],
    "exclude_filters": ["filters", "user", "wants", "to", "avoid"],
    "review_limit": 1000 (if user mentions underrated, hidden gems, or wants lesser-known places),
    "requirements": "any additional specific requirements",
    "context": "brief context about what user is looking for"
}}"""
                }
            ]
            
            # Add recent conversation history (last 3 exchanges)
            if conversation_history:
                recent_messages = conversation_history[-6:]  # Last 6 messages (3 exchanges)
                for msg in recent_messages:
                    if msg.get('type') == 'user':
                        messages.append({"role": "user", "content": msg.get('content', '')})
                    elif msg.get('type') == 'bot':
                        messages.append({"role": "assistant", "content": msg.get('content', '')})
            
            # Add current message
            messages.append({"role": "user", "content": message})

            response = client.chat.completions.create(
                model="openai/gpt-4.1-mini",
                messages=messages,
                temperature=0.3,  # Lower temperature for more consistent parsing
                top_p=0.9
            )
            
            raw_response = response.choices[0].message.content.strip()
            logger.info(f"Raw GitHub Copilot response: '{raw_response}'")
            
            # Clean up the response to ensure it's valid JSON
            if raw_response.startswith('```json'):
                raw_response = raw_response.replace('```json', '').replace('```', '').strip()
            elif raw_response.startswith('```'):
                raw_response = raw_response.replace('```', '').strip()
            
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
            
            # Clean and validate extracted data
            location = result.get('location', '').strip()
            include_filters = [f.lower() for f in result.get('include_filters', []) if f]
            exclude_filters = [f.lower() for f in result.get('exclude_filters', []) if f]
            
            result.update({
                'location': location,
                'include_filters': include_filters,
                'exclude_filters': exclude_filters
            })
            
            logger.info(f"Cleaned result - Location: '{location}', Include: {include_filters}, Exclude: {exclude_filters}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Failed to parse response: '{raw_response if 'raw_response' in locals() else 'No response'}'")
            return {"location": "", "include_filters": [], "exclude_filters": [], "requirements": "", "context": ""}
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return {"location": "", "include_filters": [], "exclude_filters": [], "requirements": "", "context": ""}
    
    def search_places_comprehensive(self, location: str, include_filters: List[str], exclude_filters: Optional[List[str]] = None, radius: int = 1500) -> List[Dict]:
        """
        Comprehensive place search using multiple strategies, optimized for cafes by default
        """
        geocode_result = self.smart_geocode(location)
        if not geocode_result:
            return []
        
        lat_lng = geocode_result['geometry']['location']
        all_places = []
        seen_place_ids = set()
        
        # Strategy 1: Keyword-based search
        query_terms = []
        for filter_name in include_filters:
            if filter_name in self.filter_keywords:
                query_terms.extend(self.filter_keywords[filter_name])
        
        search_queries = []
        if query_terms:
            # Create focused searches
            search_queries.extend([
                ' '.join(query_terms[:3]),  # Top 3 keywords
                ' '.join(query_terms[:2]) if len(query_terms) > 1 else query_terms[0]
            ])
        
        # Strategy 2: Smart type-based searches - only search for what user wants
        place_types = ['cafe']  # Always search cafes
        
        # Only add specific types if user explicitly mentions them
        user_wants_restaurants = 'food' in include_filters
        user_wants_bakeries = 'pastries' in include_filters
        
        if user_wants_restaurants:
            place_types.extend(['restaurant', 'meal_takeaway'])
            logger.info("User wants food - including restaurants in search")
        
        if user_wants_bakeries:
            place_types.append('bakery')
            logger.info("User wants pastries - including bakeries in search")
        
        # Add general food type only if user specifically wants food
        if user_wants_restaurants or user_wants_bakeries:
            place_types.append('food')
        
        logger.info(f"Searching place types: {place_types}")
        
        for search_type in place_types:
            try:
                logger.info(f"Searching by type: {search_type}")
                places_result = gmaps.places_nearby(
                    location=lat_lng,
                    radius=radius,
                    type=search_type
                )
                
                for place in places_result.get('results', []):
                    place_id = place.get('place_id')
                    if place_id and place_id not in seen_place_ids:
                        all_places.append(place)
                        seen_place_ids.add(place_id)
                        
            except Exception as e:
                logger.warning(f"Error searching by type {search_type}: {e}")
        
        # Strategy 3: Optimized keyword searches - focus on coffee/cafe by default
        if not search_queries:
            # Default searches - focus on coffee places, not restaurants
            search_queries = ['coffee shop', 'cafe', 'espresso']
            
            # Only add food-related searches if user wants food
            if user_wants_restaurants:
                search_queries.extend(['restaurant', 'dining'])
            if user_wants_bakeries:
                search_queries.extend(['bakery', 'pastries'])
        
        logger.info(f"Using keyword searches: {search_queries}")
        
        for query in search_queries:
            try:
                logger.info(f"Searching with keyword: '{query}'")
                places_result = gmaps.places_nearby(
                    location=lat_lng,
                    radius=radius,
                    keyword=query
                )
                
                for place in places_result.get('results', []):
                    place_id = place.get('place_id')
                    if place_id and place_id not in seen_place_ids:
                        all_places.append(place)
                        seen_place_ids.add(place_id)
                        
            except Exception as e:
                logger.warning(f"Error searching with keyword '{query}': {e}")
        
        logger.info(f"Found {len(all_places)} unique places total")
        return all_places
    
    def analyze_reviews_for_filters(self, place_id: str, filter_names: List[str]) -> Dict[str, bool]:
        """
        Analyze place reviews to check if they mention specific filter criteria
        """
        filter_matches = {filter_name: False for filter_name in filter_names}
        
        try:
            # Get place details including reviews
            place_details = gmaps.place(
                place_id=place_id,
                fields=['reviews']
            )
            
            reviews = place_details.get('result', {}).get('reviews', [])
            if not reviews:
                return filter_matches
            
            # Combine all review text
            all_review_text = ' '.join([
                review.get('text', '').lower() 
                for review in reviews[:5]  # Only check first 5 reviews for performance
            ])
            
            # Check each filter for keyword matches in reviews
            for filter_name in filter_names:
                if filter_name in self.filter_keywords:
                    for keyword in self.filter_keywords[filter_name]:
                        if keyword.lower() in all_review_text:
                            filter_matches[filter_name] = True
                            break
                            
        except Exception as e:
            logger.warning(f"Error analyzing reviews for place {place_id}: {e}")
            
        return filter_matches
    
    def advanced_place_ranking(self, places: List[Dict], include_filters: List[str], exclude_filters: Optional[List[str]] = None, review_limit: Optional[int] = None) -> List[Dict]:
        """
        Advanced ranking algorithm with multiple scoring factors, photo integration, and review limit filtering
        """
        if exclude_filters is None:
            exclude_filters = []
        
        # Filter places by review limit first if specified
        if review_limit:
            original_count = len(places)
            places = [place for place in places if place.get('user_ratings_total', 0) < review_limit]
            filtered_count = original_count - len(places)
            if filtered_count > 0:
                logger.info(f"Filtered out {filtered_count} places with {review_limit}+ reviews for 'underrated' search")
            
        scored_places = []
        
        for place in places:
            # Base score from rating (0-100)
            rating = place.get('rating', 2.5)
            rating_count = place.get('user_ratings_total', 0)
            
            # Rating score with confidence adjustment
            rating_score = rating * 15
            if rating_count > 100:
                rating_score += 10  # Bonus for well-reviewed places
            elif rating_count < 10:
                rating_score -= 5   # Penalty for places with few reviews
            
            # Price level consideration (lower price = slight bonus for accessibility)
            price_level = place.get('price_level', 2)
            price_score = max(0, 5 - price_level)
            
            # Text analysis for filter matching
            searchable_text = ' '.join([
                place.get('name', '').lower(),
                ' '.join(place.get('types', [])).lower(),
                place.get('vicinity', '').lower()
            ])
            
            # Include filter scoring
            include_score = 0
            include_matches = 0
            for filter_name in include_filters:
                if filter_name in self.filter_keywords:
                    for keyword in self.filter_keywords[filter_name]:
                        if keyword in searchable_text:
                            include_score += 20
                            include_matches += 1
                            break  # Only count each filter once per place
            
            # Exclude filter scoring
            exclude_penalty = 0
            exclude_matches = 0
            for filter_name in exclude_filters:
                if filter_name in self.filter_keywords:
                    for keyword in self.filter_keywords[filter_name]:
                        if keyword in searchable_text:
                            exclude_penalty += 30
                            exclude_matches += 1
                            break
            
            # Calculate final score
            final_score = rating_score + price_score + include_score - exclude_penalty
            
            # Bonus for places that match multiple include filters
            if include_matches > 1:
                final_score += include_matches * 5
            
            # Store detailed scoring info for debugging
            place_score_info = {
                'place': place,
                'final_score': max(final_score, 0),  # Don't allow negative scores
                'rating_score': rating_score,
                'include_score': include_score,
                'exclude_penalty': exclude_penalty,
                'include_matches': include_matches,
                'exclude_matches': exclude_matches,
                'rating': rating,
                'rating_count': rating_count
            }
            
            scored_places.append(place_score_info)
        
        # Sort by final score, then by rating, then by review count
        scored_places.sort(key=lambda x: (x['final_score'], x['rating'], x['rating_count']), reverse=True)
        
        # Log top scoring details for debugging
        logger.info("Top 3 scoring breakdown:")
        for i, item in enumerate(scored_places[:3]):
            logger.info(f"{i+1}. {item['place'].get('name', 'Unknown')} - Score: {item['final_score']:.1f} "
                       f"(Rating: {item['rating_score']:.1f}, Include: {item['include_score']}, "
                       f"Exclude: -{item['exclude_penalty']}, Matches: {item['include_matches']})")
        
        # Get top places and add photos efficiently
        top_places = [item['place'] for item in scored_places[:8]]
        
        # Add photos to top places (only for the top ones to avoid API quota issues)
        for i, place in enumerate(top_places[:6]):  # Only get photos for top 6
            try:
                photos = self.get_place_photos(place, max_photos=1)
                place['photo_urls'] = photos
                place['google_maps_link'] = self.get_google_maps_link(place)
                
                # Analyze reviews for filter matches
                # Check ALL available filters, not just the ones actively selected
                all_available_filters = list(self.filter_keywords.keys())
                place['filter_matches'] = self.analyze_reviews_for_filters(place.get('place_id'), all_available_filters)
                
                if photos:
                    logger.info(f"Added {len(photos)} photo(s) for {place.get('name', 'Unknown')}")
            except Exception as e:
                logger.warning(f"Failed to get photos for {place.get('name', 'Unknown')}: {e}")
                place['photo_urls'] = []
                place['google_maps_link'] = self.get_google_maps_link(place)
                # Still analyze reviews even if photo fetch fails
                all_available_filters = list(self.filter_keywords.keys())
                try:
                    place['filter_matches'] = self.analyze_reviews_for_filters(place.get('place_id'), all_available_filters)
                except:
                    place['filter_matches'] = {}
        
        # For places 7-8, don't fetch photos to save API calls but still add maps links
        for place in top_places[6:]:
            place['photo_urls'] = []
            place['google_maps_link'] = self.get_google_maps_link(place)
        
        return top_places
    
    def generate_natural_response(self, message: str, parsed_data: Dict, places: List[Dict], conversation_history: Optional[List] = None) -> str:
        """Generate a natural language response from GitHub Copilot based on user message and found places"""
        logger.info(f"Generating natural language response for: '{message}'")
        
        try:
            # Prepare context about found places
            places_context = ""
            if places:
                top_places = places[:6]  # Focus on top 6 for response
                places_context = f"Found {len(places)} places, top options: " + "; ".join([
                    f"{place.get('name', 'Unknown')} (★{place.get('rating', 'N/A')}, {place.get('vicinity', 'Location TBD')})"
                    for place in top_places
                ])
            else:
                places_context = "No suitable places found matching the criteria."
            
            # Format filter information
            include_filters = parsed_data.get('include_filters', [])
            exclude_filters = parsed_data.get('exclude_filters', [])
            location = parsed_data.get('location', '')
            context = parsed_data.get('context', '')
            defaulted_to_seattle = parsed_data.get('defaulted_to_seattle', False)
            
            # Add context about defaulting to Seattle
            location_context = ""
            if defaulted_to_seattle:
                location_context = "Since no location was specified, I'm showing you great options in Seattle. "
            
            # Build messages array including conversation history
            messages = [
                {
                    "role": "system", 
                    "content": f"""You are an enthusiastic local guide assistant. The user asked: "{message}"

Location: {location}
{location_context}Looking for: {', '.join(include_filters) if include_filters else 'general recommendations'}
Avoiding: {', '.join(exclude_filters) if exclude_filters else 'nothing specific'}
Context: {context}

Results: {places_context}

Respond in a friendly, conversational way. If defaulted to Seattle, start by mentioning "Since you didn't specify a location, I'm showing you great cafes in Seattle!" Acknowledge their preferences. 
If places were found, briefly highlight what makes them good choices and **bold the cafe names** using markdown formatting. You can mention the neighborhood if they are different for each result, but don't explicitly say the address.
If no places found, suggest ways to broaden the search.
Keep it concise but enthusiastic - 2-3 sentences max."""
                }
            ]
            
            # Add recent conversation history (last 2 exchanges for context)
            if conversation_history:
                recent_messages = conversation_history[-4:]  # Last 4 messages (2 exchanges)
                for msg in recent_messages:
                    if msg.get('type') == 'user':
                        messages.append({"role": "user", "content": msg.get('content', '')})
                    elif msg.get('type') == 'bot':
                        messages.append({"role": "assistant", "content": msg.get('content', '')})
            
            # Add current message
            messages.append({"role": "user", "content": message})

            response = client.chat.completions.create(
                model="openai/gpt-4.1-mini",
                messages=messages,
                temperature=0.7,
                top_p=0.9
            )
            
            natural_response = response.choices[0].message.content
            logger.info(f"Generated natural response: '{natural_response}'")
            return natural_response
            
        except Exception as e:
            logger.error(f"Error generating natural response: {e}")
            return f"Great! I found some excellent options in {parsed_data.get('location', 'your area')}. Check out the recommendations below!"
    
    def format_recommendations(self, places: List[Dict]) -> str:
        """Format place recommendations for chat response, ordered from best to worst"""
        if not places:
            return "I couldn't find any places matching your criteria. Try expanding your search area or adjusting your filters."
        
        recommendations = []
        for i, place in enumerate(places[:6], 1):  # Limit to top 6 for cleaner display
            name = place.get('name', 'Unknown')
            rating = place.get('rating', 'No rating')
            rating_count = place.get('user_ratings_total', 0)
            price_level = place.get('price_level')
            address = place.get('vicinity', 'Address not available')
            
            rec = f"{i}. **{name}**\n"
            rec += f"   📍 {address}\n"
            
            # Enhanced rating display
            if rating != 'No rating':
                rec += f"   ⭐ {rating}/5"
                if rating_count > 0:
                    rec += f" ({rating_count} reviews)"
            else:
                rec += "   ⭐ Not yet rated"
            
            if price_level is not None and price_level > 0:
                rec += f" | {'$' * price_level}"
            rec += "\n"
            
            recommendations.append(rec)
        
        return "\n".join(recommendations)

agent = LocationAgent()

@app.route('/api/health')
def health_check():
    return jsonify({"status": "healthy", "geocoding_cache_size": len(agent.geocoding_cache)})

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        message = data.get('message', '')
        filter_states = data.get('filterStates', {})
        conversation_history = data.get('conversationHistory', [])
        
        logger.info(f"=== NEW CHAT REQUEST ===")
        logger.info(f"Received message: '{message}'")
        logger.info(f"Filter states: {filter_states}")
        logger.info(f"Conversation history: {len(conversation_history)} messages")
        
        if not message:
            return jsonify({"error": "Message is required"}), 400
        
        # Parse user message for structured data
        parsed = agent.parse_user_message(message, filter_states, conversation_history)
        location = parsed.get('location', '').strip()
        include_filters = parsed.get('include_filters', [])
        exclude_filters = parsed.get('exclude_filters', [])
        review_limit = parsed.get('review_limit')  # NEW: Get review limit
        
        logger.info(f"Final parsed result - Location: '{location}', Include: {include_filters}, Exclude: {exclude_filters}, Review limit: {review_limit}")
        
        # Default to Seattle if no location is specified
        defaulted_to_seattle = False
        if not location:
            location = "Seattle, WA"
            defaulted_to_seattle = True
            logger.info(f"No location specified, defaulting to: {location}")
        
        # Add this info to parsed data for response generation
        parsed['location'] = location
        parsed['defaulted_to_seattle'] = defaulted_to_seattle
        
        # Search for places with comprehensive strategy
        logger.info(f"Searching for places in '{location}' with include filters: {include_filters}, exclude filters: {exclude_filters}")
        places = agent.search_places_comprehensive(location, include_filters, exclude_filters)
        logger.info(f"Found {len(places)} places from comprehensive search")
        
        # Advanced ranking to get best matches with review limit filtering
        top_places = agent.advanced_place_ranking(places, include_filters, exclude_filters, review_limit)
        logger.info(f"Ranked to top {len(top_places)} places")
        
        # Generate natural language response from GitHub Copilot
        natural_response = agent.generate_natural_response(message, parsed, top_places, conversation_history)
        
        # Format structured recommendations
        structured_recommendations = agent.format_recommendations(top_places)
        
        # Add review limit info to response if applied
        response_data = {
            "response": natural_response,
            "structured_response": structured_recommendations,
            "places": top_places[:6],
            "location": location,
            "filters": include_filters,
            "include_filters": include_filters,
            "exclude_filters": exclude_filters,
            "parsed_data": parsed,
            "total_found": len(places),
            "review_limit_applied": review_limit  # NEW: Include this info
        }
        
        # Add a note about filtering if review limit was applied
        if review_limit and len(top_places) < len(places):
            filtered_count = len(places) - len(top_places)
            response_data["filter_note"] = f"Filtered out {filtered_count} places with more than {review_limit} reviews to find hidden gems."
        
        logger.info(f"=== CHAT REQUEST COMPLETE ===")
        
        return jsonify(response_data)
        
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
        
        places = agent.search_places_comprehensive(location, filters)
        top_places = agent.advanced_place_ranking(places, filters, None, None)  # No exclude filters or review limit for simple endpoint
        
        return jsonify({
            "places": top_places[:6],
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
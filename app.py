from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import asyncio
import googlemaps
from dotenv import load_dotenv
import json
import logging
from typing import List, Dict, Optional, Annotated

from openai import AsyncOpenAI

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='frontend/build', static_url_path='')
CORS(app)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def require_env_var(name: str) -> str:
    """Get an environment variable and fail with clear message if missing or empty."""
    logger.info(f"[FUNCTION CALL] require_env_var called with name: {name}")
    value = os.getenv(name)
    if value is None:
        raise ValueError(f"{name} environment variable is MISSING (not set in .env or system).")
    if value.strip() == "":
        raise ValueError(f"{name} environment variable is EMPTY (check formatting in .env).")
    return value

# Load required environment variables
github_token = require_env_var("GITHUB_TOKEN")
google_maps_key = require_env_var("GOOGLE_MAPS_API_KEY")

logger.info(f"GitHub token loaded: {github_token[:10]}...")
logger.info(f"Google Maps key loaded: {google_maps_key[:10]}...")

# Initialize clients
gmaps = googlemaps.Client(key=google_maps_key)
openai_client = AsyncOpenAI(
    base_url="https://models.github.ai/inference",
    api_key=github_token,
)

# Google Maps helper functions
def get_place_photos(place: Dict, max_photos: int = 1) -> List[str]:
    """Get photo URLs for a place"""
    logger.info(f"[FUNCTION CALL] get_place_photos called for place: {place.get('name', 'Unknown')}, max_photos: {max_photos}")
    try:
        place_id = place.get('place_id')
        if not place_id:
            return []
        
        details = gmaps.place(
            place_id=place_id, 
            fields=['photo'],
            language='en'
        )
        
        photos = details.get('result', {}).get('photos', [])
        if not photos:
            return []
        
        photo_urls = []
        for photo in photos[:max_photos]:
            photo_reference = photo.get('photo_reference')
            if photo_reference:
                photo_url = (
                    f"https://maps.googleapis.com/maps/api/place/photo"
                    f"?maxwidth=400&maxheight=300"
                    f"&photo_reference={photo_reference}"
                    f"&key={google_maps_key}"
                )
                photo_urls.append(photo_url)
        
        return photo_urls
        
    except Exception as e:
        logger.warning(f"Error getting photos for place {place.get('name', 'Unknown')}: {e}")
        return []

def get_place_reviews(place: Dict, max_reviews: int = 5) -> List[str]:
    """Get review text for a place to analyze for filtering"""
    logger.info(f"[FUNCTION CALL] get_place_reviews called for place: {place.get('name', 'Unknown')}, max_reviews: {max_reviews}")
    try:
        place_id = place.get('place_id')
        if not place_id:
            return []
        
        details = gmaps.place(
            place_id=place_id,
            fields=['review'],
            language='en'
        )
        
        reviews = details.get('result', {}).get('reviews', [])
        if not reviews:
            return []
        
        review_texts = []
        for review in reviews[:max_reviews]:
            text = review.get('text', '')
            if text:
                review_texts.append(text.lower())
        
        return review_texts
        
    except Exception as e:
        logger.warning(f"Error getting reviews for place {place.get('name', 'Unknown')}: {e}")
        return []

def get_cafe(
    cafe_name: Annotated[str, "Name of the cafe to get detailed information about"] = "",
    place_id: Annotated[str, "Google Maps Place ID of the specific cafe"] = "",
    location: Annotated[str, "Location to search in (city, neighborhood, or address)"] = "Seattle, WA"
) -> Dict:
    """Get detailed information and reviews for a specific cafe by name or place_id"""
    logger.info(f"[FUNCTION CALL] get_cafe called for cafe: '{cafe_name}', place_id: '{place_id}' in location: '{location}'")
    try:
        # Geocode the location first
        geocode_result = smart_geocode(location)
        if not geocode_result:
            return {
                "text": f"Sorry, I couldn't find the location '{location}'. Please try a more specific address or well-known area.",
                "places": []
            }
        
        lat_lng = geocode_result['geometry']['location']
        logger.info(f"Found coordinates for {location}: {lat_lng}")
        
        # Search for the specific cafe
        try:
            # Search using places_nearby
            nearby_search = gmaps.places_nearby(
                location=lat_lng,
                radius=5000,
                keyword=cafe_name
            )
            
            # Also try text search for better results
            text_search = gmaps.places(
                query=f"{cafe_name} {location}",
                location=lat_lng,
                radius=5000
            )
            
            # Combine and find best match
            all_results = []
            seen_place_ids = set()
            
            for result_set in [nearby_search.get('results', []), text_search.get('results', [])]:
                for place in result_set:
                    place_id = place.get('place_id')
                    if place_id and place_id not in seen_place_ids:
                        place_name_lower = place.get('name', '').lower()
                        search_name_lower = cafe_name.lower()
                        
                        # Check if this matches the cafe we're looking for
                        if (search_name_lower in place_name_lower or 
                            any(word in place_name_lower for word in search_name_lower.split()) or
                            place_name_lower in search_name_lower):
                            all_results.append(place)
                            seen_place_ids.add(place_id)
            
            if not all_results:
                return {
                    "text": f"I couldn't find '{cafe_name}' in {location}. Could you check the spelling or try a different location?",
                    "places": []
                }
            
            # Pick the best match
            best_match = max(all_results, key=lambda x: (
                len(set(cafe_name.lower().split()) & set(x.get('name', '').lower().split())),
                x.get('rating', 0)
            ))
            
            place_id = best_match.get('place_id')
            
            # Get detailed information including reviews
            details = gmaps.place(
                place_id=place_id,
                fields=[
                    'name', 'rating', 'user_ratings_total', 'formatted_address', 
                    'formatted_phone_number', 'website', 'opening_hours', 
                    'price_level', 'reviews', 'type', 'photo'
                ],
                language='en'
            )
            
            place_details = details.get('result', {})
            
            # Format the response
            name = place_details.get('name', 'Unknown')
            rating = place_details.get('rating', 'No rating')
            rating_count = place_details.get('user_ratings_total', 0)
            address = place_details.get('formatted_address', 'Address not available')
            phone = place_details.get('formatted_phone_number', '')
            website = place_details.get('website', '')
            price_level = place_details.get('price_level')
            place_types = place_details.get('type', [])  # Note: singular 'type' from API
            
            response = f"Here's detailed information about **{name}**:\n\n"
            response += f"📍 **Address**: {address}\n"
            
            if rating != 'No rating':
                response += f"⭐ **Rating**: {rating}/5"
                if rating_count > 0:
                    response += f" ({rating_count} reviews)"
                response += "\n"
            
            if price_level is not None and price_level > 0:
                response += f"💰 **Price Level**: {'$' * price_level}\n"
            
            if phone:
                response += f"📞 **Phone**: {phone}\n"
            
            if website:
                response += f"🌐 **Website**: {website}\n"
            
            # Add opening hours if available
            opening_hours = place_details.get('opening_hours', {})
            if opening_hours.get('weekday_text'):
                response += f"\n🕒 **Hours**:\n"
                for day_hours in opening_hours['weekday_text'][:3]:  # Show first 3 days
                    response += f"   {day_hours}\n"
                if len(opening_hours['weekday_text']) > 3:
                    response += "   (and more...)\n"
            
            # Add recent reviews
            reviews = place_details.get('reviews', [])
            if reviews:
                response += f"\n📝 **Recent Reviews**:\n\n"
                for i, review in enumerate(reviews[:3], 1):  # Show top 3 reviews
                    author = review.get('author_name', 'Anonymous')
                    review_rating = review.get('rating', 'N/A')
                    review_text = review.get('text', '')
                    time_desc = review.get('relative_time_description', '')
                    
                    response += f"**Review {i}** by {author}"
                    if review_rating != 'N/A':
                        response += f" (⭐ {review_rating}/5)"
                    if time_desc:
                        response += f" - {time_desc}"
                    response += f":\n\"{review_text[:200]}{'...' if len(review_text) > 200 else ''}\"\n\n"
            
            # Add place type information
            if place_types:
                relevant_types = [t.replace('_', ' ').title() for t in place_types if t not in ['establishment', 'point_of_interest']]
                if relevant_types:
                    response += f"🏷️ **Categories**: {', '.join(relevant_types[:3])}\n"
            
            # Add photos and maps link to the place object
            best_match['photo_urls'] = get_place_photos(best_match, max_photos=1)
            best_match['google_maps_link'] = get_google_maps_link(best_match)
            
            logger.info(f"Successfully retrieved detailed information for {name}")
            return {
                "text": response,
                "places": [best_match]
            }
            
        except Exception as e:
            logger.error(f"Error getting details for cafe '{cafe_name}': {e}")
            return {
                "text": f"I had trouble getting detailed information about '{cafe_name}'. Please try again or ask about a different cafe.",
                "places": []
            }
            
    except Exception as e:
        logger.error(f"Error in get_cafe: {e}")
        return {
            "text": f"Sorry, I encountered an error while getting information about '{cafe_name}'. Please try again.",
            "places": []
        }

def get_google_maps_link(place: Dict) -> str:
    """Generate Google Maps deep link for a place"""
    logger.info(f"[FUNCTION CALL] get_google_maps_link called for place: {place.get('name', 'Unknown')}")
    try:
        place_id = place.get('place_id')
        if place_id:
            return f"https://maps.google.com/maps?q=place_id:{place_id}"
        
        # Fallback: use name and location
        name = place.get('name', '').replace(' ', '+')
        lat = place.get('geometry', {}).get('location', {}).get('lat')
        lng = place.get('geometry', {}).get('location', {}).get('lng')
        
        if lat and lng:
            return f"https://maps.google.com/maps?q={name}@{lat},{lng}"
        
        if name:
            return f"https://maps.google.com/maps?q={name}"
        
        return "https://maps.google.com"
        
    except Exception as e:
        logger.warning(f"Error generating Google Maps link for {place.get('name', 'Unknown')}: {e}")
        return "https://maps.google.com"

def smart_geocode(location: str) -> Optional[Dict]:
    """Smart geocoding with fallbacks for common locations"""
    logger.info(f"[FUNCTION CALL] smart_geocode called with location: '{location}'")
    try:
        logger.info(f"Geocoding location: '{location}'")
        
        # Try original location first
        geocode_result = gmaps.geocode(location)
        if geocode_result:
            result = geocode_result[0]
            logger.info(f"Successful geocoding: {result['formatted_address']}")
            return result
        
        # Fallback queries for neighborhoods
        location_queries = [
            f"{location}, Seattle, WA",
            f"{location}, San Francisco, CA", 
            f"{location}, New York, NY",
            f"{location} neighborhood"
        ]
        
        for query in location_queries:
            try:
                logger.info(f"Trying geocoding query: '{query}'")
                geocode_result = gmaps.geocode(query)
                if geocode_result:
                    result = geocode_result[0]
                    logger.info(f"Successful geocoding for '{query}': {result['formatted_address']}")
                    return result
            except Exception as e:
                logger.warning(f"Geocoding failed for '{query}': {e}")
                continue
        
        logger.warning(f"All geocoding attempts failed for: {location}")
        return None
        
    except Exception as e:
        logger.error(f"Error in smart_geocode: {e}")
        return None

def search_cafes(
    location: Annotated[str, "The location to search for cafes (city, neighborhood, or address)"],
    preferences: Annotated[str, "User preferences like 'pastries', 'wifi', 'outlets', 'food', 'coffee', 'seating'"] = "",
    avoid: Annotated[str, "Things to avoid"] = "",
    underrated: Annotated[bool, "Whether to focus on underrated/hidden gems with fewer reviews"] = False,
    radius: Annotated[int, "Search radius in meters (default: auto-determined based on location specificity)"] = None
) -> Dict:
    """Search for cafes using Google Maps API based on location and preferences. Reviews customer reviews to find matches."""
    logger.info(f"[FUNCTION CALL] search_cafes called with location: '{location}', preferences: '{preferences}', avoid: '{avoid}', underrated: {underrated}, radius: {radius}")
    try:
        logger.info(f"Searching cafes for location: '{location}', preferences: '{preferences}', avoid: '{avoid}', underrated: {underrated}, radius: {radius}")
        
        # Default to Seattle if no location provided
        if not location.strip():
            location = "Seattle, WA"
            logger.info("No location provided, defaulting to Seattle")
        
        # Geocode the location
        geocode_result = smart_geocode(location)
        if not geocode_result:
            return {
                "text": f"Sorry, I couldn't find the location '{location}'. Please try a more specific address or well-known area.",
                "places": []
            }
        
        lat_lng = geocode_result['geometry']['location']
        logger.info(f"Found coordinates: {lat_lng}")
        
        # Determine search radius
        if radius is not None:
            search_radius = radius
            logger.info(f"Using user-specified search radius: {search_radius}m")
        else:
            search_radius = 1500  # Default 1.5km radius
            logger.info(f"Using default search radius: {search_radius}m")
        
        # Search for places (Focus on cafes with conditional expansion)
        all_places = []
        seen_place_ids = set()
        
        # PRIMARY: Search for cafes by default
        primary_search_types = ['cafe']
        primary_keywords = ['coffee shop', 'cafe', 'espresso', 'coffee bar', 'coffeehouse']
        
        # CONDITIONAL: Add other types only if explicitly requested
        additional_search_types = []
        additional_keywords = []
        
        # Check if user specifically wants bakeries or pastries
        pastry_request_keywords = ['pastries', 'pastry', 'bakery', 'baked goods', 'croissant', 'muffin', 'scone', 'danish']
        user_wants_pastries = any(keyword in preferences.lower() for keyword in pastry_request_keywords)
        
        if user_wants_pastries:
            additional_search_types.append('bakery')
            additional_keywords.extend(['bakery', 'pastries'])
            logger.info("User requested pastries/bakery items - including bakeries in search")
        
        # Check if user wants food/restaurants
        if ('food' in preferences.lower() or 'restaurant' in preferences.lower() or 
            'meal' in preferences.lower() or 'lunch' in preferences.lower() or
            'breakfast' in preferences.lower() or 'brunch' in preferences.lower()):
            additional_search_types.extend(['restaurant'])
            additional_keywords.extend(['bistro', 'brunch spot'])
            logger.info("User requested food/meals - including restaurants in search")
        
        # Combine search types (cafes first, then conditionals)
        all_search_types = primary_search_types + additional_search_types
        all_keywords = primary_keywords + additional_keywords
        
        # Log the final radius that will be passed to Google Maps API
        logger.info(f"Starting Google Maps search with radius: {search_radius}m")
        
        # Search by types
        for search_type in all_search_types:
            try:
                places_result = gmaps.places_nearby(
                    location=lat_lng,
                    radius=search_radius,
                    type=search_type
                )
                
                for place in places_result.get('results', []):
                    place_id = place.get('place_id')
                    if place_id and place_id not in seen_place_ids:
                        all_places.append(place)
                        seen_place_ids.add(place_id)
                        
            except Exception as e:
                logger.warning(f"Error searching by type {search_type}: {e}")
        
        # Search by keywords
        for keyword in all_keywords:
            try:
                places_result = gmaps.places_nearby(
                    location=lat_lng,
                    radius=search_radius,
                    keyword=keyword
                )
                
                for place in places_result.get('results', []):
                    place_id = place.get('place_id')
                    if place_id and place_id not in seen_place_ids:
                        all_places.append(place)
                        seen_place_ids.add(place_id)
                        
            except Exception as e:
                logger.warning(f"Error searching with keyword '{keyword}': {e}")
        
        logger.info(f"Found {len(all_places)} total places")
        
        if not all_places:
            return {
                "text": f"I couldn't find any cafes in {location}. Try expanding your search area or checking the location name.",
                "places": []
            }
        
        # ENHANCED FILTERING: Prioritize cafes and filter out unwanted business types
        filtered_places = []
        
        # Define unwanted business types (unless explicitly requested)
        unwanted_types = {
            'ice_cream_shop', 'frozen_yogurt_shop', 'dessert_shop', 
            'candy_store', 'donut_shop', 'cake_shop', 'gelato_shop',
            'ice_cream_parlor', 'gelato_parlor', 'sorbet_shop'
        }
        
        # Add bakery and related types to unwanted unless user specifically wants pastries/bakery items
        if not user_wants_pastries:
            unwanted_types.update({'bakery', 'cake_shop', 'cupcake_shop', 'pastry_shop'})
            logger.info("User did not request pastries - filtering out bakeries and cake shops")
        
        # Add restaurants to lower priority unless user wants food
        deprioritize_types = set()
        if not ('food' in preferences.lower() or 'restaurant' in preferences.lower()):
            deprioritize_types.update({'restaurant', 'meal_takeaway', 'meal_delivery'})
        
        preference_keywords = {
            'pastries': ['bakery', 'pastry', 'croissant', 'muffin', 'scone', 'danish', 'donut', 'brownie', 'cookie', 'cake', 'tart', 'eclair', 'macaron'],
            'coffee': ['coffee', 'espresso', 'cappuccino', 'latte', 'americano', 'mocha', 'flat white', 'cortado', 'pour over', 'cold brew'],
            'wifi': ['wifi', 'internet', 'wireless', 'laptop friendly', 'work', 'study', 'remote work', 'bring laptop', 'good wifi'],
            'outlets': ['power', 'outlet', 'laptop', 'work', 'charging', 'plug', 'study space', 'workspace', 'laptop friendly'],
            'food': ['restaurant', 'food', 'dining', 'meal', 'lunch', 'breakfast', 'sandwich', 'salad', 'soup', 'brunch'],
            'seating': ['seating', 'spacious', 'cozy', 'comfortable', 'plenty of seats', 'roomy', 'good seating', 'tables', 'chairs'],
            'cute': ['cute', 'aesthetic', 'aesthetically', 'instagram', 'instagrammable', 'pretty', 'beautiful', 'charming', 'lovely', 'adorable'],
            'aesthetic': ['aesthetic', 'aesthetically', 'instagram', 'instagrammable', 'stylish', 'trendy', 'hip', 'atmospheric', 'ambiance', 'ambience']
        }
        
        for place in all_places:
            place_types = set(place.get('types', []))
            place_name = place.get('name', '').lower()
            
            # Skip unwanted business types
            if place_types & unwanted_types:
                logger.info(f"Filtering out {place.get('name', 'Unknown')} - unwanted type: {place_types & unwanted_types}")
                continue
            
            # Skip places with gelato/ice cream focused names (catches misclassified places)
            gelato_ice_cream_names = ['gelato', 'ice cream', 'frozen yogurt', 'sorbet', 'popsicle', 'gelati']
            if any(keyword in place_name for keyword in gelato_ice_cream_names):
                # Exception: Allow if user specifically wants desserts/ice cream
                if not any(dessert_word in preferences.lower() for dessert_word in ['ice cream', 'gelato', 'dessert', 'frozen']):
                    logger.info(f"Filtering out {place.get('name', 'Unknown')} - gelato/ice cream focused name")
                    continue
            
            # Apply underrated filter
            if underrated:
                review_count = place.get('user_ratings_total', 0)
                if review_count >= 1000:
                    continue
            
            # Score places with cafe prioritization
            rating = place.get('rating', 2.5)
            rating_count = place.get('user_ratings_total', 0)
            score = rating * 20
            
            # MAJOR BOOST for cafe-type establishments
            if 'cafe' in place_types or any(cafe_word in place.get('name', '').lower() 
                                           for cafe_word in ['cafe', 'coffee', 'espresso']):
                score += 25
                logger.info(f"Cafe boost applied to {place.get('name', 'Unknown')}")
            
            # MINOR PENALTY for restaurant types (unless user wants food)
            if place_types & deprioritize_types:
                score -= 10
                logger.info(f"Restaurant penalty applied to {place.get('name', 'Unknown')}")
            
            # Confidence adjustment
            if rating_count > 100:
                score += 10
            elif rating_count < 10:
                score -= 5
            
            # Get place reviews for enhanced filtering
            place_reviews = get_place_reviews(place, max_reviews=5)
            review_text = ' '.join(place_reviews) if place_reviews else ''
            
            # Build searchable text including name, types, and reviews
            searchable_text = ' '.join([
                place.get('name', '').lower(),
                ' '.join(place.get('types', [])).lower(),
                review_text
            ])
            
            # Preference matching with enhanced scoring using reviews
            for pref in preferences.lower().split():
                if pref in preference_keywords:
                    keywords_found = 0
                    review_matches = 0
                    
                    for keyword in preference_keywords[pref]:
                        if keyword in searchable_text:
                            keywords_found += 1
                            # Give extra points if found in reviews (more reliable)
                            if keyword in review_text:
                                review_matches += 1
                    
                    if keywords_found > 0:
                        base_score = 15 * keywords_found
                        # Bonus for review mentions (more trustworthy)
                        review_bonus = 10 * review_matches
                        score += base_score + review_bonus
                        
                        if review_matches > 0:
                            logger.info(f"Review match boost (+{base_score + review_bonus}) for '{pref}' applied to {place.get('name', 'Unknown')}")
            
            # Avoid keywords with review analysis
            for avoid_item in avoid.lower().split():
                if avoid_item in preference_keywords:
                    for keyword in preference_keywords[avoid_item]:
                        if keyword in searchable_text:
                            penalty = -20
                            # Stronger penalty if mentioned in reviews
                            if keyword in review_text:
                                penalty = -30
                            score += penalty
            
            place['calculated_score'] = max(score, 0)
            place['review_analyzed'] = len(place_reviews) > 0
            filtered_places.append(place)
        
        # Sort by score and get top 6 places
        filtered_places.sort(key=lambda x: (x['calculated_score'], x.get('rating', 0), x.get('user_ratings_total', 0)), reverse=True)
        top_places = filtered_places[:6]
        
        # Count how many places had review analysis
        review_analyzed_count = sum(1 for place in top_places if place.get('review_analyzed', False))
        logger.info(f"Review analysis applied to {review_analyzed_count}/{len(top_places)} places")
        
        # Add photos and maps links to top places
        for place in top_places:
            place['photo_urls'] = get_place_photos(place, max_photos=1)
            place['google_maps_link'] = get_google_maps_link(place)
        
        # Format response
        if not top_places:
            return {
                "text": f"I found some cafes in {location}, but none matched your specific preferences based on customer reviews. Try broadening your search area or adjusting your preferences.",
                "places": []
            }
        
        response = f"Here are the top cafes I found in {location} that match your preferences:\n\n"
        
        for i, place in enumerate(top_places, 1):
            name = place.get('name', 'Unknown')
            rating = place.get('rating', 'No rating')
            rating_count = place.get('user_ratings_total', 0)
            address = place.get('vicinity', 'Address not available')
            price_level = place.get('price_level')
            
            response += f"{i}. **{name}**\n"
            response += f"   📍 {address}\n"
            
            if rating != 'No rating':
                response += f"   ⭐ {rating}/5"
                if rating_count > 0:
                    response += f" ({rating_count} reviews)"
            else:
                response += "   ⭐ Not yet rated"
            
            if price_level is not None and price_level > 0:
                response += f" | {'$' * price_level}"
            
            response += "\n\n"
        
        if underrated:
            response += "✨ Showing hidden gems with fewer than 1000 reviews!\n"
        
        if radius is not None:
            response += f"\n📍 Search customized to {radius}m radius as requested.\n"
        
        if review_analyzed_count > 0:
            response += f"\n🔍 Found matches using customer review analysis for {review_analyzed_count} places!"
        
        logger.info(f"Successfully found {len(top_places)} cafes for {location}")
        return {
            "text": response,
            "places": top_places
        }
        
    except Exception as e:
        logger.error(f"Error in search_cafes: {e}")
        return {
            "text": f"Sorry, I encountered an error while searching for cafes. Please try again.",
            "places": []
        }

# Function definition for OpenAI function calling
search_cafes_function = {
    "type": "function",
    "function": {
        "name": "search_cafes",
        "description": "Search for cafes based on location and user preferences. Reviews customer reviews to find recommendations that match the search criteria.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The location to search for cafes (city, neighborhood, or address)"
                },
                "preferences": {
                    "type": "string",
                    "description": "User preferences like 'pastries', 'wifi', 'outlets', 'food', 'coffee', 'seating', 'cute', 'aesthetic'",
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
                "radius": {
                    "type": "integer",
                    "description": "Search radius in meters (e.g., 500 for focused search, 1500 for broader search). If not specified, will be auto-determined based on location specificity.",
                    "minimum": 100,
                    "maximum": 50000
                }
            },
            "required": ["location"]
        }
    }
}

get_cafe_function = {
    "type": "function",
    "function": {
        "name": "get_cafe",
        "description": "Get detailed information for a specific, identified cafe including reviews, hours, contact info, and other details",
        "parameters": {
            "type": "object",
            "properties": {
                "cafe_name": {
                    "type": "string",
                    "description": "The exact name of the cafe to get information about"
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

async def run_cafe_agent(user_message: str, conversation_history: List = None) -> Dict:
    """Run the cafe finding agent using OpenAI function calling"""
    logger.info(f"[FUNCTION CALL] run_cafe_agent called with message: '{user_message}', history length: {len(conversation_history) if conversation_history else 0}")
    try:
        logger.info(f"Running cafe agent for message: '{user_message}'")
        
        places_data = None  # Store places data from function call
        
        messages = [
            {
                "role": "system",
                "content": """You are a specialized cafe assistant specializing in answering questions about cafes or helping the user discover new ones. 
You have access to two main tools:

1. **search_cafes**: Use this to search for cafes in a location based on user preferences
2. **get_cafe**: Use this to get detailed information about a specific cafe including reviews, hours, contact info

**Use search_cafes when users ask for:**
- Cafe recommendations in a specific location
- Coffee shop suggestions
- Restaurant or dining recommendations (if they mention food preferences)
- Places to eat or drink
- Study spots or work-friendly cafes
- Cafes with specific features (wifi, outlets, pastries, etc.)
- Underrated or hidden gem locations

**Use get_cafe when users ask for:**
- More details about a specific cafe mentioned in conversation
- Reviews for a particular cafe
- Hours, phone number, or address of a specific cafe
- Follow-up questions about cafes from previous recommendations
- "Tell me more about [Cafe Name]"
- "What are the reviews like for [Cafe Name]?"

Key behaviors when finding cafes:
1. **Always prioritize cafes** - Focus on coffee shops, cafes, or tea houses first, only include restaurants/bakeries if the user specifically requests them
2. **Use review analysis** - The search function analyzes customer reviews to match user preferences accurately
3. **Parse location carefully** - Extract any location mentions including neighborhoods, cities, districts, or landmarks
4. **Set Search radius" - If the user says "near [location]", and specifies an exact address (e.g. 819 Virginia St), building (e.g. Wholefoods at Westlake), or landmark (e.g. Space Needle), set the search radius to 400, otherwise use 1500
5. **Understand preferences** - Pay attention to mentions of:
   - pastries, bakery items, croissants, muffins
   - wifi, internet, work-friendly spaces
   - power outlets, laptop-friendly environments  
   - comfortable seating, cozy atmosphere
   - specific food preferences

6. **Handle "underrated" requests** - If users want hidden gems or underrated places, set the underrated flag to true
7. **Handle follow-up questions** - If user asks for more details about a specific cafe, use get_cafe


When a user asks for cafe recommendations:
1. Extract the location (if none provided, default to Seattle)
2. Identify their preferences (pastries, wifi, outlets, etc.)
3. Note anything they want to avoid
4. Call the search_cafes function with the parsed information
5. Present the results in a friendly, enthusiastic way

When a user asks for details about a specific cafe:
1. Extract the cafe name from their question
2. Extract or infer the location context from conversation history or their question
3. Call get_cafe to get comprehensive information
4. Present detailed information including reviews, hours, and contact details

In the response to the user, bold the name of the cafes if found. Don't give the address, but you can mention the neighborhood if the recommendations are in different places.

If the user asks a short question, give a short concise answer while remaining friendly.
For general conversation, respond helpfully without using any tools.

"""
            }
        ]
        
        # Add conversation history to maintain context
        if conversation_history:
            logger.info(f"Adding {len(conversation_history)} messages from conversation history")
            for msg in conversation_history:
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
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Make the initial request with function calling
        response = await openai_client.chat.completions.create(
            model="openai/gpt-4.1-mini",
            messages=messages,
            tools=[search_cafes_function, get_cafe_function],
            tool_choice="auto",
            temperature=0.7
        )
        
        message = response.choices[0].message
        
        # Check if the model wants to call a function
        if message.tool_calls:
            # Add the assistant's message to the conversation
            messages.append(message)
            
            # Process each tool call
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                logger.info(f"Calling function: {function_name} with args: {function_args}")
                
                if function_name == "search_cafes":
                    # Call our function
                    function_result = search_cafes(
                        location=function_args.get("location", ""),
                        preferences=function_args.get("preferences", ""),
                        avoid=function_args.get("avoid", ""),
                        underrated=function_args.get("underrated", False),
                        radius=function_args.get("radius")
                    )
                    
                    # Store places data for frontend
                    places_data = function_result.get("places", [])
                    
                    # Add the function result to the conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": function_result.get("text", "")
                    })
                
                elif function_name == "get_cafe":
                    # Call the detailed reviews function
                    function_result = get_cafe(
                        place_id=function_args.get("place_id", ""),
                        location=function_args.get("location", "Seattle, WA"),
                        cafe_name=function_args.get("cafe_name", "")
                    )
                    
                    # Store places data for frontend
                    places_data = function_result.get("places", [])
                    
                    # Add the function result to the conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": function_result.get("text", "")
                    })
            
            # Get the final response from the model
            final_response = await openai_client.chat.completions.create(
                model="openai/gpt-4.1-mini",
                messages=messages,
                temperature=0.7
            )
            
            return {
                "text": final_response.choices[0].message.content,
                "places": places_data or []
            }
        else:
            # No function call needed, return the direct response
            return {
                "text": message.content,
                "places": []
            }
            
    except Exception as e:
        logger.error(f"Error in run_cafe_agent: {e}")
        return {
            "text": f"I apologize, but I'm having trouble processing your request right now. Please try again. Error: {str(e)}",
            "places": []
        }

def format_agent_response_for_frontend(agent_result: Dict, user_message: str) -> Dict:
    """Format agent response for frontend compatibility"""
    logger.info(f"[FUNCTION CALL] format_agent_response_for_frontend called with response length: {len(agent_result.get('text', ''))}, message: '{user_message}'")
    return {
        "response": agent_result.get("text", ""),
        "structured_response": agent_result.get("text", ""),
        "places": agent_result.get("places", []),
        "location": "Location handled by agent",
        "filters": [],
        "include_filters": [],
        "exclude_filters": [],
        "parsed_data": {"agent_handled": True},
        "total_found": len(agent_result.get("places", [])),
        "review_limit_applied": None
    }

# Flask routes
@app.route('/api/health')
def health_check():
    logger.info("[FUNCTION CALL] health_check endpoint called")
    return jsonify({"status": "healthy", "agent_framework": "Microsoft Agent Framework", "model": "gpt-4.1-mini"})

@app.route('/api/chat', methods=['POST'])
def chat():
    logger.info("[FUNCTION CALL] chat endpoint called")
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
        
        # Build enhanced message with filter context
        enhanced_message = message
        if filter_states:
            include_filters = [f for f, state in filter_states.items() if state == 'include']
            exclude_filters = [f for f, state in filter_states.items() if state == 'exclude']
            
            if include_filters or exclude_filters:
                enhanced_message += "\n\nAdditional preferences:"
                if include_filters:
                    enhanced_message += f" I want places with: {', '.join(include_filters)}."
                if exclude_filters:
                    enhanced_message += f" I want to avoid: {', '.join(exclude_filters)}."
        
        # Run the agent asynchronously
        async def run_agent():
            try:
                return await run_cafe_agent(enhanced_message, conversation_history)
            except Exception as e:
                logger.error(f"Agent error: {e}")
                return {
                    "text": f"I apologize, but I'm having trouble processing your request right now. Please try again. Error: {str(e)}",
                    "places": []
                }
        
        # Use asyncio to run the agent
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            agent_result = loop.run_until_complete(run_agent())
        finally:
            loop.close()
        
        logger.info(f"Agent response: {agent_result.get('text', '')}")
        
        # Format response for frontend compatibility
        response_data = format_agent_response_for_frontend(agent_result, message)
        
        logger.info(f"=== CHAT REQUEST COMPLETE ===")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({"error": "Something went wrong. Please try again."}), 500

@app.route('/api/places', methods=['GET'])
def get_places():
    logger.info("[FUNCTION CALL] get_places endpoint called")
    try:
        location = request.args.get('location', '')
        filters = request.args.getlist('filters')
        
        if not location:
            return jsonify({"error": "Location is required"}), 400
        
        # Create a simple message for the agent
        filter_text = f" with {', '.join(filters)}" if filters else ""
        message = f"Find cute cafes in {location}{filter_text}"
        
        # Run the agent
        async def run_agent():
            try:
                return await run_cafe_agent(message, [])  # No conversation history for places endpoint
            except Exception as e:
                logger.error(f"Agent error: {e}")
                return {
                    "text": f"Error finding places: {str(e)}",
                    "places": []
                }
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            agent_result = loop.run_until_complete(run_agent())
        finally:
            loop.close()
        
        return jsonify({
            "places": agent_result.get("places", []),
            "response": agent_result.get("text", ""),
            "count": len(agent_result.get("places", []))
        })
        
    except Exception as e:
        logger.error(f"Places error: {e}")
        return jsonify({"error": "Something went wrong. Please try again."}), 500

@app.route('/')
def serve_frontend():
    logger.info("[FUNCTION CALL] serve_frontend endpoint called")
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def static_files(path):
    logger.info(f"[FUNCTION CALL] static_files endpoint called with path: {path}")
    return send_from_directory(app.static_folder, path)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
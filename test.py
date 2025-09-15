import os
import googlemaps
from dotenv import load_dotenv
import logging
from typing import List, Dict, Optional, Annotated

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def require_env_var(name: str) -> str:
    """Get an environment variable and fail with clear message if missing or empty."""
    value = os.getenv(name)
    if value is None:
        raise ValueError(f"{name} environment variable is MISSING (not set in .env or system).")
    if value.strip() == "":
        raise ValueError(f"{name} environment variable is EMPTY (check formatting in .env).")
    return value

# Load required environment variables
google_maps_key = require_env_var("GOOGLE_MAPS_API_KEY")

logger.info(f"Google Maps key loaded: {google_maps_key[:10]}...")

# Initialize Google Maps client
gmaps = googlemaps.Client(key=google_maps_key)

# Google Maps helper functions
def get_place_photos(place: Dict, max_photos: int = 1) -> List[str]:
    """Get photo URLs for a place"""
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

def get_google_maps_link(place: Dict) -> str:
    """Generate Google Maps deep link for a place"""
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

def find_cute_cafes(
    location: str,
    preferences: str = "",
    avoid: str = "",
    underrated: bool = False
) -> str:
    """Find cute cafes using Google Maps API based on location and preferences."""
    try:
        logger.info(f"Finding cafes for location: '{location}', preferences: '{preferences}', avoid: '{avoid}', underrated: {underrated}")
        
        # Default to Seattle if no location provided
        if not location.strip():
            location = "Seattle, WA"
            logger.info("No location provided, defaulting to Seattle")
        
        # Geocode the location
        geocode_result = smart_geocode(location)
        if not geocode_result:
            return f"Sorry, I couldn't find the location '{location}'. Please try a more specific address or well-known area."
        
        lat_lng = geocode_result['geometry']['location']
        logger.info(f"Found coordinates: {lat_lng}")
        
        # Search for places
        all_places = []
        seen_place_ids = set()
        
        # Define search parameters
        search_types = ['cafe']
        search_keywords = ['coffee shop', 'cafe', 'espresso']
        
        # Add specific types based on preferences
        if 'pastries' in preferences.lower() or 'bakery' in preferences.lower():
            search_types.append('bakery')
            search_keywords.extend(['bakery', 'pastries', 'croissant'])
        
        if 'food' in preferences.lower() or 'restaurant' in preferences.lower():
            search_types.extend(['restaurant', 'meal_takeaway'])
            search_keywords.extend(['restaurant', 'bistro'])
        
        # Search by types and keywords
        for search_type in search_types:
            try:
                places_result = gmaps.places_nearby(
                    location=lat_lng,
                    radius=1500,
                    type=search_type
                )
                
                for place in places_result.get('results', []):
                    place_id = place.get('place_id')
                    if place_id and place_id not in seen_place_ids:
                        all_places.append(place)
                        seen_place_ids.add(place_id)
                        
            except Exception as e:
                logger.warning(f"Error searching by type {search_type}: {e}")
        
        for keyword in search_keywords:
            try:
                places_result = gmaps.places_nearby(
                    location=lat_lng,
                    radius=1500,
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
            return f"I couldn't find any cafes in {location}. Try expanding your search area or checking the location name."
        
        # Filter and rank places
        filtered_places = []
        preference_keywords = {
            'pastries': ['bakery', 'pastry', 'croissant', 'muffin', 'scone'],
            'coffee': ['coffee', 'espresso', 'cappuccino', 'latte'],
            'wifi': ['wifi', 'internet', 'wireless'],
            'outlets': ['power', 'outlet', 'laptop', 'work'],
            'food': ['restaurant', 'food', 'dining', 'meal'],
            'seating': ['seating', 'spacious', 'cozy']
        }
        
        for place in all_places:
            # Apply underrated filter
            if underrated:
                review_count = place.get('user_ratings_total', 0)
                if review_count >= 1000:
                    continue
            
            # Score places
            rating = place.get('rating', 2.5)
            rating_count = place.get('user_ratings_total', 0)
            score = rating * 20
            
            # Confidence adjustment
            if rating_count > 100:
                score += 10
            elif rating_count < 10:
                score -= 5
            
            # Check preferences in name and types
            searchable_text = ' '.join([
                place.get('name', '').lower(),
                ' '.join(place.get('types', [])).lower()
            ])
            
            # Preference matching
            for pref in preferences.lower().split():
                if pref in preference_keywords:
                    for keyword in preference_keywords[pref]:
                        if keyword in searchable_text:
                            score += 15
                            break
            
            # Avoid keywords
            for avoid_item in avoid.lower().split():
                if avoid_item in preference_keywords:
                    for keyword in preference_keywords[avoid_item]:
                        if keyword in searchable_text:
                            score -= 20
                            break
            
            place['calculated_score'] = max(score, 0)
            filtered_places.append(place)
        
        # Sort by score and get top 6 places
        filtered_places.sort(key=lambda x: (x['calculated_score'], x.get('rating', 0), x.get('user_ratings_total', 0)), reverse=True)
        top_places = filtered_places[:6]
        
        # Add photos and maps links to top places
        for place in top_places:
            place['photo_urls'] = get_place_photos(place, max_photos=1)
            place['google_maps_link'] = get_google_maps_link(place)
        
        # Format response
        if not top_places:
            return f"I found some places in {location}, but none matched your specific preferences. Try broadening your search criteria."
        
        response = f"Here are the top cute cafes I found in {location}:\n\n"
        
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
            response += "✨ Showing hidden gems with fewer than 1000 reviews!"
        
        logger.info(f"Successfully found {len(top_places)} cafes for {location}")
        return response
        
    except Exception as e:
        logger.error(f"Error in find_cute_cafes: {e}")
        return f"Sorry, I encountered an error while searching for cafes. Please try again."

# Example usage
if __name__ == "__main__":
    # Test the function directly
    location = input("Enter a location: ")
    preferences = input("Enter preferences (pastries, wifi, outlets, food, coffee, seating): ")
    avoid = input("Enter things to avoid: ")
    underrated_input = input("Show only underrated places? (y/n): ").lower()
    underrated = underrated_input == 'y' or underrated_input == 'yes'
    
    print("\n" + "="*50)
    print("SEARCHING FOR CAFES...")
    print("="*50)
    
    result = find_cute_cafes(location, preferences, avoid, underrated)
    print(result)
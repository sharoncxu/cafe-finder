"""Google Maps service for location and place operations."""

import googlemaps
import logging
from typing import List, Dict, Optional, Set
from ..config import config
from ..models.data_models import Place, Location, PlacePhoto, SearchPreferences

logger = logging.getLogger(__name__)

class GoogleMapsService:
    """Service class for Google Maps API operations."""
    
    def __init__(self):
        self.client = googlemaps.Client(key=config.google_maps_api_key)
        logger.info("Google Maps service initialized")
    
    def smart_geocode(self, location: str) -> Optional[Dict]:
        """Smart geocoding with fallbacks for common locations."""
        logger.info(f"Geocoding location: '{location}'")
        
        try:
            # Try original location first
            geocode_result = self.client.geocode(location)
            if geocode_result:
                result = geocode_result[0]
                logger.info(f"Successful geocoding: {result['formatted_address']}")
                return result
            
            # Fallback queries for neighborhoods
            fallback_queries = [
                f"{location}, Seattle, WA",
                f"{location}, San Francisco, CA", 
                f"{location}, New York, NY",
                f"{location} neighborhood"
            ]
            
            for query in fallback_queries:
                try:
                    logger.info(f"Trying geocoding query: '{query}'")
                    geocode_result = self.client.geocode(query)
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
    
    def get_place_photos(self, place: Place, max_photos: int = None) -> List[str]:
        """Get photo URLs for a place."""
        max_photos = max_photos or config.max_photos
        logger.info(f"Getting photos for place: {place.name}, max_photos: {max_photos}")
        
        try:
            if not place.place_id:
                return []
            
            details = self.client.place(
                place_id=place.place_id, 
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
                        f"&key={config.google_maps_api_key}"
                    )
                    photo_urls.append(photo_url)
            
            return photo_urls
            
        except Exception as e:
            logger.warning(f"Error getting photos for place {place.name}: {e}")
            return []
    
    def get_place_reviews(self, place: Place, max_reviews: int = None) -> List[str]:
        """Get review text for a place to analyze for filtering."""
        max_reviews = max_reviews or config.max_reviews
        logger.info(f"Getting reviews for place: {place.name}, max_reviews: {max_reviews}")
        
        try:
            if not place.place_id:
                return []
            
            details = self.client.place(
                place_id=place.place_id,
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
            logger.warning(f"Error getting reviews for place {place.name}: {e}")
            return []
    
    def search_places_nearby(self, location_coords: Dict, search_type: str = None, 
                           keyword: str = None, radius: int = None) -> List[Place]:
        """Search for places using places_nearby API."""
        radius = radius or config.search_radius
        
        try:
            search_params = {
                'location': location_coords,
                'radius': radius
            }
            
            if search_type:
                search_params['type'] = search_type
            if keyword:
                search_params['keyword'] = keyword
            
            places_result = self.client.places_nearby(**search_params)
            
            places = []
            for place_data in places_result.get('results', []):
                place = self._convert_api_place_to_model(place_data)
                if place:
                    places.append(place)
            
            return places
            
        except Exception as e:
            logger.warning(f"Error searching places nearby with type='{search_type}', keyword='{keyword}': {e}")
            return []
    
    def search_places_by_text(self, query: str, location_coords: Dict, radius: int = None) -> List[Place]:
        """Search for places using text search API."""
        radius = radius or config.search_radius
        
        try:
            places_result = self.client.places(
                query=query,
                location=location_coords,
                radius=radius
            )
            
            places = []
            for place_data in places_result.get('results', []):
                place = self._convert_api_place_to_model(place_data)
                if place:
                    places.append(place)
            
            return places
            
        except Exception as e:
            logger.warning(f"Error searching places by text '{query}': {e}")
            return []
    
    def get_place_details(self, place_id: str, fields: List[str] = None) -> Optional[Dict]:
        """Get detailed place information."""
        if not fields:
            fields = [
                'name', 'rating', 'user_ratings_total', 'formatted_address', 
                'formatted_phone_number', 'website', 'opening_hours', 
                'price_level', 'reviews', 'type', 'photo'
            ]
        
        try:
            details = self.client.place(
                place_id=place_id,
                fields=fields,
                language='en'
            )
            return details.get('result', {})
        except Exception as e:
            logger.error(f"Error getting place details for {place_id}: {e}")
            return None
    
    def generate_google_maps_link(self, place: Place) -> str:
        """Generate Google Maps deep link for a place."""
        try:
            if place.place_id:
                return f"https://maps.google.com/maps?q=place_id:{place.place_id}"
            
            # Fallback: use name and location
            location = place.get_location()
            if location:
                name = place.name.replace(' ', '+')
                return f"https://maps.google.com/maps?q={name}@{location.lat},{location.lng}"
            
            if place.name:
                return f"https://maps.google.com/maps?q={place.name.replace(' ', '+')}"
            
            return "https://maps.google.com"
            
        except Exception as e:
            logger.warning(f"Error generating Google Maps link for {place.name}: {e}")
            return "https://maps.google.com"
    
    def _convert_api_place_to_model(self, place_data: Dict) -> Optional[Place]:
        """Convert Google Maps API place data to Place model."""
        try:
            return Place(
                place_id=place_data.get('place_id', ''),
                name=place_data.get('name', 'Unknown'),
                rating=place_data.get('rating'),
                user_ratings_total=place_data.get('user_ratings_total'),
                vicinity=place_data.get('vicinity'),
                formatted_address=place_data.get('formatted_address'),
                price_level=place_data.get('price_level'),
                types=place_data.get('types', []),
                geometry=place_data.get('geometry')
            )
        except Exception as e:
            logger.warning(f"Error converting place data to model: {e}")
            return None
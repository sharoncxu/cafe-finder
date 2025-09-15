"""Service for getting detailed cafe information."""

import logging
from typing import Dict, Optional
from ..models.data_models import SearchResult, Place
from ..services.google_maps_service import GoogleMapsService
from ..config import config

logger = logging.getLogger(__name__)

class CafeDetailsService:
    """Service for getting detailed cafe information and reviews."""
    
    def __init__(self, google_maps_service: GoogleMapsService):
        self.google_maps = google_maps_service
    
    def get_cafe_details(self, cafe_name: str, location: str = None) -> SearchResult:
        """Get detailed information and reviews for a specific cafe."""
        location = location or config.default_location
        logger.info(f"Getting details for cafe: '{cafe_name}' in location: '{location}'")
        
        try:
            # Geocode the location first
            geocode_result = self.google_maps.smart_geocode(location)
            if not geocode_result:
                return SearchResult(
                    text=f"Sorry, I couldn't find the location '{location}'. Please try a more specific address or well-known area.",
                    places=[]
                )
            
            lat_lng = geocode_result['geometry']['location']
            logger.info(f"Found coordinates for {location}: {lat_lng}")
            
            # Find the cafe
            cafe_place = self._find_specific_cafe(cafe_name, location, lat_lng)
            if not cafe_place:
                return SearchResult(
                    text=f"I couldn't find '{cafe_name}' in {location}. Could you check the spelling or try a different location?",
                    places=[]
                )
            
            # Get detailed information
            detailed_info = self._get_detailed_cafe_info(cafe_place)
            
            # Enhance place data
            cafe_place.photo_urls = self.google_maps.get_place_photos(cafe_place)
            cafe_place.google_maps_link = self.google_maps.generate_google_maps_link(cafe_place)
            
            logger.info(f"Successfully retrieved detailed information for {cafe_place.name}")
            return SearchResult(
                text=detailed_info,
                places=[cafe_place]
            )
            
        except Exception as e:
            logger.error(f"Error in get_cafe_details: {e}")
            return SearchResult(
                text=f"Sorry, I encountered an error while getting information about '{cafe_name}'. Please try again.",
                places=[]
            )
    
    def _find_specific_cafe(self, cafe_name: str, location: str, lat_lng: Dict) -> Optional[Place]:
        """Find a specific cafe by name."""
        try:
            # Search using both nearby and text search
            nearby_places = self.google_maps.search_places_nearby(lat_lng, keyword=cafe_name)
            text_places = self.google_maps.search_places_by_text(f"{cafe_name} {location}", lat_lng)
            
            # Combine and find best match
            all_results = []
            seen_place_ids = set()
            
            for places_list in [nearby_places, text_places]:
                for place in places_list:
                    if place.place_id and place.place_id not in seen_place_ids:
                        place_name_lower = place.name.lower()
                        search_name_lower = cafe_name.lower()
                        
                        # Check if this matches the cafe we're looking for
                        if (search_name_lower in place_name_lower or 
                            any(word in place_name_lower for word in search_name_lower.split()) or
                            place_name_lower in search_name_lower):
                            all_results.append(place)
                            seen_place_ids.add(place.place_id)
            
            if not all_results:
                return None
            
            # Pick the best match
            best_match = max(all_results, key=lambda x: (
                len(set(cafe_name.lower().split()) & set(x.name.lower().split())),
                x.rating or 0
            ))
            
            return best_match
            
        except Exception as e:
            logger.error(f"Error finding specific cafe '{cafe_name}': {e}")
            return None
    
    def _get_detailed_cafe_info(self, place: Place) -> str:
        """Get detailed information for a cafe including reviews and hours."""
        try:
            # Get detailed place information
            place_details = self.google_maps.get_place_details(place.place_id)
            if not place_details:
                return f"Could not get detailed information for {place.name}."
            
            # Extract information
            name = place_details.get('name', place.name)
            rating = place_details.get('rating', 'No rating')
            rating_count = place_details.get('user_ratings_total', 0)
            address = place_details.get('formatted_address', 'Address not available')
            phone = place_details.get('formatted_phone_number', '')
            website = place_details.get('website', '')
            price_level = place_details.get('price_level')
            place_types = place_details.get('type', [])
            
            # Build response
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
                relevant_types = [t.replace('_', ' ').title() for t in place_types 
                                if t not in ['establishment', 'point_of_interest']]
                if relevant_types:
                    response += f"🏷️ **Categories**: {', '.join(relevant_types[:3])}\n"
            
            return response
            
        except Exception as e:
            logger.error(f"Error getting detailed info for {place.name}: {e}")
            return f"I had trouble getting detailed information about '{place.name}'. Please try again or ask about a different cafe."
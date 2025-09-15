"""Cafe search service with filtering and scoring logic."""

import logging
from typing import List, Dict, Set, Optional
from ..models.data_models import Place, SearchPreferences, SearchResult
from ..services.google_maps_service import GoogleMapsService
from ..config import config

logger = logging.getLogger(__name__)

class CafeSearchService:
    """Service for searching and filtering cafes."""
    
    def __init__(self, google_maps_service: GoogleMapsService):
        self.google_maps = google_maps_service
        
        # Preference keywords mapping
        self.preference_keywords = {
            'pastries': ['bakery', 'pastry', 'croissant', 'muffin', 'scone', 'danish', 'donut', 'brownie', 'cookie', 'cake', 'tart', 'eclair', 'macaron'],
            'coffee': ['coffee', 'espresso', 'cappuccino', 'latte', 'americano', 'mocha', 'flat white', 'cortado', 'pour over', 'cold brew'],
            'wifi': ['wifi', 'internet', 'wireless', 'laptop friendly', 'work', 'study', 'remote work', 'bring laptop', 'good wifi'],
            'outlets': ['power', 'outlet', 'laptop', 'work', 'charging', 'plug', 'study space', 'workspace', 'laptop friendly'],
            'food': ['restaurant', 'food', 'dining', 'meal', 'lunch', 'breakfast', 'sandwich', 'salad', 'soup', 'brunch'],
            'seating': ['seating', 'spacious', 'cozy', 'comfortable', 'plenty of seats', 'roomy', 'good seating', 'tables', 'chairs']
        }
        
        # Cute/aesthetic keywords for filtering
        self.cute_aesthetic_keywords = [
            'cute', 'aesthetic', 'aesthetically', 'instagram', 'instagrammable', 
            'pretty', 'beautiful', 'charming', 'lovely', 'adorable', 'cozy', 
            'atmospheric', 'ambiance', 'ambience', 'stylish', 'trendy', 'hip'
        ]
        
        # Unwanted business types
        self.unwanted_types = {
            'ice_cream_shop', 'frozen_yogurt_shop', 'dessert_shop', 
            'candy_store', 'donut_shop', 'cake_shop', 'gelato_shop',
            'ice_cream_parlor', 'gelato_parlor', 'sorbet_shop'
        }
        
        # Gelato/ice cream focused names for additional filtering
        self.gelato_ice_cream_names = ['gelato', 'ice cream', 'frozen yogurt', 'sorbet', 'popsicle', 'gelati']
    
    def search_cafes(self, preferences: SearchPreferences) -> SearchResult:
        """Main search method for finding cafes."""
        logger.info(f"Searching for cafes with preferences: {preferences}")
        
        # Default to Seattle if no location provided
        location = preferences.location.strip() or config.default_location
        
        # Geocode the location
        geocode_result = self.google_maps.smart_geocode(location)
        if not geocode_result:
            return SearchResult(
                text=f"Sorry, I couldn't find the location '{location}'. Please try a more specific address or well-known area.",
                places=[]
            )
        
        lat_lng = geocode_result['geometry']['location']
        logger.info(f"Found coordinates for {location}: {lat_lng}")
        
        # Handle specific cafe names search
        if preferences.specific_cafe_names:
            return self._search_specific_cafes(preferences, lat_lng, location)
        
        # Search for places
        all_places = self._search_all_places(preferences, lat_lng)
        
        if not all_places:
            return SearchResult(
                text=f"I couldn't find any cafes in {location}. Try expanding your search area or checking the location name.",
                places=[]
            )
        
        # Filter and score places
        filtered_places = self._filter_and_score_places(all_places, preferences)
        
        # Sort by score and get top places
        filtered_places.sort(
            key=lambda x: (x.calculated_score, x.rating or 0, x.user_ratings_total or 0), 
            reverse=True
        )
        top_places = filtered_places[:config.max_places]
        
        # Add photos and maps links
        for place in top_places:
            place.photo_urls = self.google_maps.get_place_photos(place)
            place.google_maps_link = self.google_maps.generate_google_maps_link(place)
        
        # Generate response
        return self._generate_search_response(top_places, location, len(all_places), preferences)
    
    def _search_specific_cafes(self, preferences: SearchPreferences, lat_lng: Dict, location: str) -> SearchResult:
        """Search for specific cafes by name."""
        logger.info(f"Searching for specific cafes: {preferences.specific_cafe_names} in {location}")
        
        found_cafes = []
        
        for cafe_name in preferences.specific_cafe_names:
            try:
                logger.info(f"Searching for: '{cafe_name}'")
                
                # Search using both nearby and text search
                nearby_places = self.google_maps.search_places_nearby(lat_lng, keyword=cafe_name)
                text_places = self.google_maps.search_places_by_text(f"{cafe_name} {location}", lat_lng)
                
                # Combine and find best match
                all_results = []
                seen_place_ids = set()
                
                for places_list in [nearby_places, text_places]:
                    for place in places_list:
                        if place.place_id and place.place_id not in seen_place_ids:
                            # Check if this matches the cafe we're looking for
                            place_name_lower = place.name.lower()
                            search_name_lower = cafe_name.lower()
                            
                            if (search_name_lower in place_name_lower or 
                                any(word in place_name_lower for word in search_name_lower.split()) or
                                place_name_lower in search_name_lower):
                                all_results.append(place)
                                seen_place_ids.add(place.place_id)
                
                if all_results:
                    # Pick the best match
                    best_match = max(all_results, key=lambda x: (
                        len(set(cafe_name.lower().split()) & set(x.name.lower().split())),
                        x.rating or 0
                    ))
                    
                    # Enhance the place data
                    best_match.photo_urls = self.google_maps.get_place_photos(best_match)
                    best_match.google_maps_link = self.google_maps.generate_google_maps_link(best_match)
                    best_match.calculated_score = 100  # High score for specific search
                    best_match.review_analyzed = True
                    
                    found_cafes.append(best_match)
                    logger.info(f"Found cafe: {best_match.name} for search '{cafe_name}'")
                else:
                    logger.warning(f"Could not find cafe matching '{cafe_name}'")
                    
            except Exception as e:
                logger.error(f"Error searching for cafe '{cafe_name}': {e}")
        
        if found_cafes:
            response_text = self._format_specific_cafes_response(found_cafes, location)
            return SearchResult(text=response_text, places=found_cafes)
        else:
            missing_cafes = preferences.specific_cafe_names
            if len(missing_cafes) == 1:
                error_msg = f"I couldn't find '{missing_cafes[0]}' in {location}. Try checking the spelling or searching for cafes in that area instead."
            else:
                error_msg = f"I couldn't find the cafes you mentioned ({', '.join(missing_cafes)}) in {location}. Try checking the spelling or searching for cafes in that area instead."
            
            return SearchResult(text=error_msg, places=[])
    
    def _search_all_places(self, preferences: SearchPreferences, lat_lng: Dict) -> List[Place]:
        """Search for all relevant places based on preferences."""
        all_places = []
        seen_place_ids = set()
        
        # Primary search: cafes
        primary_types = ['cafe']
        primary_keywords = ['coffee shop', 'cafe', 'espresso', 'coffee bar', 'coffeehouse']
        
        # Additional searches based on preferences
        additional_types = []
        additional_keywords = []
        
        # Check for pastry requests
        pastry_keywords = ['pastries', 'pastry', 'bakery', 'baked goods', 'croissant', 'muffin', 'scone', 'danish']
        if any(keyword in ' '.join(preferences.preferences).lower() for keyword in pastry_keywords):
            additional_types.append('bakery')
            additional_keywords.extend(['bakery', 'pastries'])
            logger.info("User requested pastries/bakery items - including bakeries in search")
        
        # Check for food requests
        food_keywords = ['food', 'restaurant', 'meal', 'lunch', 'breakfast', 'brunch']
        if any(keyword in ' '.join(preferences.preferences).lower() for keyword in food_keywords):
            additional_types.append('restaurant')
            additional_keywords.extend(['bistro', 'brunch spot'])
            logger.info("User requested food/meals - including restaurants in search")
        
        # Combine all search parameters
        all_search_types = primary_types + additional_types
        all_keywords = primary_keywords + additional_keywords
        
        # Search by types
        for search_type in all_search_types:
            places = self.google_maps.search_places_nearby(lat_lng, search_type=search_type)
            for place in places:
                if place.place_id and place.place_id not in seen_place_ids:
                    all_places.append(place)
                    seen_place_ids.add(place.place_id)
        
        # Search by keywords
        for keyword in all_keywords:
            places = self.google_maps.search_places_nearby(lat_lng, keyword=keyword)
            for place in places:
                if place.place_id and place.place_id not in seen_place_ids:
                    all_places.append(place)
                    seen_place_ids.add(place.place_id)
        
        logger.info(f"Found {len(all_places)} total places")
        return all_places
    
    def _filter_and_score_places(self, places: List[Place], preferences: SearchPreferences) -> List[Place]:
        """Filter and score places based on preferences."""
        filtered_places = []
        
        # Determine what types to filter out
        unwanted_types = self.unwanted_types.copy()
        
        # Add bakery types if not specifically requested
        pastry_keywords = ['pastries', 'pastry', 'bakery', 'baked goods', 'croissant', 'muffin', 'scone', 'danish']
        user_wants_pastries = any(keyword in ' '.join(preferences.preferences).lower() for keyword in pastry_keywords)
        
        if not user_wants_pastries:
            unwanted_types.update({'bakery', 'cake_shop', 'cupcake_shop', 'pastry_shop'})
            logger.info("User did not request pastries - filtering out bakeries and cake shops")
        
        # Determine deprioritized types
        deprioritize_types = set()
        food_preferences = ['food', 'restaurant']
        if not any(pref in ' '.join(preferences.preferences).lower() for pref in food_preferences):
            deprioritize_types.update({'restaurant', 'meal_takeaway', 'meal_delivery'})
        
        for place in places:
            place_types = set(place.types)
            place_name = place.name.lower()
            
            # Skip unwanted business types
            if place_types & unwanted_types:
                logger.info(f"Filtering out {place.name} - unwanted type: {place_types & unwanted_types}")
                continue
            
            # Skip gelato/ice cream focused names
            if any(keyword in place_name for keyword in self.gelato_ice_cream_names):
                if not any(dessert_word in ' '.join(preferences.preferences).lower() 
                          for dessert_word in ['ice cream', 'gelato', 'dessert', 'frozen']):
                    logger.info(f"Filtering out {place.name} - gelato/ice cream focused name")
                    continue
            
            # Apply underrated filter
            if preferences.underrated and (place.user_ratings_total or 0) >= 1000:
                continue
            
            # Score the place
            score = self._calculate_place_score(place, preferences, place_types, deprioritize_types)
            place.calculated_score = max(score, 0)
            
            filtered_places.append(place)
        
        return filtered_places
    
    def _calculate_place_score(self, place: Place, preferences: SearchPreferences, 
                              place_types: Set[str], deprioritize_types: Set[str]) -> float:
        """Calculate a score for a place based on various factors."""
        rating = place.rating or 2.5
        rating_count = place.user_ratings_total or 0
        score = rating * 20
        
        # Major boost for cafe-type establishments
        if 'cafe' in place_types or any(cafe_word in place.name.lower() 
                                       for cafe_word in ['cafe', 'coffee', 'espresso']):
            score += 25
            logger.info(f"Cafe boost applied to {place.name}")
        
        # Minor penalty for restaurant types (unless user wants food)
        if place_types & deprioritize_types:
            score -= 10
            logger.info(f"Restaurant penalty applied to {place.name}")
        
        # Confidence adjustment based on review count
        if rating_count > 100:
            score += 10
        elif rating_count < 10:
            score -= 5
        
        # Get reviews and apply cute/aesthetic filtering
        place_reviews = self.google_maps.get_place_reviews(place)
        review_text = ' '.join(place_reviews) if place_reviews else ''
        place.review_analyzed = len(place_reviews) > 0
        
        # Apply cute/aesthetic filtering
        has_cute_aesthetic = any(keyword in review_text for keyword in self.cute_aesthetic_keywords)
        
        # Strict filtering: skip places without cute/aesthetic mentions in reviews
        if review_text and not has_cute_aesthetic:
            logger.info(f"Filtering out {place.name} - no cute/aesthetic mentions in reviews")
            return -1  # Mark for exclusion
        
        # If no reviews available, allow it through (potential hidden gem)
        if not review_text:
            logger.info(f"Including {place.name} - no reviews available (potential hidden gem)")
        
        # Build searchable text
        searchable_text = ' '.join([
            place.name.lower(),
            ' '.join(place.types).lower(),
            review_text
        ])
        
        # Major bonus for cute/aesthetic mentions
        cute_aesthetic_score = 0
        for keyword in self.cute_aesthetic_keywords:
            if keyword in review_text:
                if keyword in ['cute', 'aesthetic', 'aesthetically', 'instagrammable']:
                    cute_aesthetic_score += 30  # High bonus for primary keywords
                else:
                    cute_aesthetic_score += 15  # Medium bonus for related keywords
        
        score += cute_aesthetic_score
        if cute_aesthetic_score > 0:
            logger.info(f"Cute/Aesthetic boost (+{cute_aesthetic_score}) applied to {place.name}")
        
        # Preference matching
        for pref in preferences.preferences:
            if pref.lower() in self.preference_keywords:
                keywords_found = 0
                review_matches = 0
                
                for keyword in self.preference_keywords[pref.lower()]:
                    if keyword in searchable_text:
                        keywords_found += 1
                        if keyword in review_text:
                            review_matches += 1
                
                if keywords_found > 0:
                    base_score = 15 * keywords_found
                    review_bonus = 10 * review_matches
                    score += base_score + review_bonus
        
        # Apply avoid penalties
        for avoid_item in preferences.avoid:
            if avoid_item.lower() in self.preference_keywords:
                for keyword in self.preference_keywords[avoid_item.lower()]:
                    if keyword in searchable_text:
                        penalty = -20
                        if keyword in review_text:
                            penalty = -30
                        score += penalty
        
        return score
    
    def _generate_search_response(self, places: List[Place], location: str, 
                                 total_analyzed: int, preferences: SearchPreferences) -> SearchResult:
        """Generate the final search response."""
        if not places:
            return SearchResult(
                text=f"I found some cafes in {location}, but none had reviews mentioning 'cute' or 'aesthetic' appeal. Try broadening your search area or looking in more trendy neighborhoods where customers often mention Instagram-worthy spots!",
                places=[]
            )
        
        response = f"Here are the top cute cafes I found in {location}:\n\n"
        
        for i, place in enumerate(places, 1):
            rating_text = f"{place.rating}/5" if place.rating else "No rating"
            rating_count_text = f" ({place.user_ratings_total} reviews)" if place.user_ratings_total else ""
            price_text = f" | {'$' * place.price_level}" if place.price_level else ""
            
            response += f"{i}. **{place.name}**\n"
            response += f"   📍 {place.vicinity or 'Address not available'}\n"
            response += f"   ⭐ {rating_text}{rating_count_text}{price_text}\n\n"
        
        if preferences.underrated:
            response += "✨ Showing hidden gems with fewer than 1000 reviews!\n"
        
        response += "💖 **Cute & Aesthetic Filter Applied**: Only showing cafes where customers mention aesthetic appeal in reviews!\n"
        
        review_analyzed_count = sum(1 for place in places if place.review_analyzed)
        if review_analyzed_count > 0:
            response += f"🔍 Enhanced filtering applied using customer review analysis for {review_analyzed_count} places!"
        
        logger.info(f"Successfully found {len(places)} cafes for {location}")
        
        return SearchResult(
            text=response,
            places=places,
            location_found=location,
            total_analyzed=total_analyzed,
            review_analyzed_count=review_analyzed_count
        )
    
    def _format_specific_cafes_response(self, places: List[Place], location: str) -> str:
        """Format response for specific cafes search."""
        response = f"Here's the information for the {'cafe' if len(places) == 1 else 'cafes'} you asked about in {location}:\n\n"
        
        for i, place in enumerate(places, 1):
            rating_text = f"{place.rating}/5" if place.rating else "Not yet rated"
            rating_count_text = f" ({place.user_ratings_total} reviews)" if place.user_ratings_total else ""
            price_text = f" | {'$' * place.price_level}" if place.price_level else ""
            
            response += f"{i}. **{place.name}**\n"
            response += f"   📍 {place.vicinity or 'Address not available'}\n"
            response += f"   ⭐ {rating_text}{rating_count_text}{price_text}\n\n"
        
        return response
import os
from openai import OpenAI
import googlemaps
from dotenv import load_dotenv
import json
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            'pastries': ['bakery', 'pastry', 'croissant', 'muffin', 'scone', 'danish'],
            'food': ['restaurant', 'cafe', 'bistro', 'eatery', 'dining'],
            'study': ['quiet', 'study', 'workspace', 'coworking', 'library'],
            'wifi': ['wifi', 'internet', 'wireless'],
            'outlets': ['power', 'charging', 'outlets', 'plugs']
        }

    def parse_user_message(self, message):
        """Extract location and preferences from user message using GitHub Copilot models"""
        logger.info(f"Parsing message: '{message}'")
        try:
            response = client.chat.completions.create(
                model="openai/gpt-4.1-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are a location parsing assistant powered by GitHub Copilot. 
                        Extract the following from user messages:
                        1. Location (city, neighborhood, address)
                        2. Preferences (pastries, food, study, wifi, outlets)
                        3. Any other specific requirements
                        
                        Return ONLY valid JSON. No extra commentary. The JSON must include keys: location, filters, requirements.
                        {
                            "location": "extracted location",
                            "filters": ["list", "of", "filters"],
                            "requirements": "additional requirements"
                        }"""
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                temperature=0.7,
                top_p=0.9
            )
            raw_response = response.choices[0].message.content
            logger.info(f"Raw GitHub Copilot response: '{raw_response}'")

            # Parse JSON
            result = json.loads(raw_response)
            logger.info(f"Successfully parsed JSON: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Failed to parse response: '{raw_response if 'raw_response' in locals() else 'No response'}'")
            return {"location": "", "filters": [], "requirements": ""}
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            return {"location": "", "filters": [], "requirements": ""}

    def search_places(self, location, filters, radius=1000):
        """Search for places using Google Maps API"""
        try:
            geocode_result = gmaps.geocode(location)
            if not geocode_result:
                return []

            lat_lng = geocode_result[0]['geometry']['location']
            query_terms = []
            for filter_name in filters:
                if filter_name in self.filter_keywords:
                    query_terms.extend(self.filter_keywords[filter_name])

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

    def rank_places(self, places, filters):
        """Rank places based on rating and filter relevance"""
        scored_places = []

        for place in places:
            score = place.get('rating', 0) * 20
            name_desc = (place.get('name', '') + ' ' + ' '.join(place.get('types', []))).lower()
            for filter_name in filters:
                if filter_name in self.filter_keywords:
                    for keyword in self.filter_keywords[filter_name]:
                        if keyword in name_desc:
                            score += 10

            scored_places.append({'place': place, 'score': score})

        scored_places.sort(key=lambda x: x['score'], reverse=True)
        return [item['place'] for item in scored_places[:3]]

    def format_recommendations(self, places):
        """Format place recommendations for chat response"""
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

# Example usage for testing
if __name__ == "__main__":
    agent = LocationAgent()
    test_message = "I'm looking for a cozy cafe with good pastries in Seattle."
    parsed = agent.parse_user_message(test_message)
    print("Parsed:", parsed)

    if parsed.get("location"):
        places = agent.search_places(parsed["location"], parsed.get("filters", []))
        top_places = agent.rank_places(places, parsed.get("filters", []))
        print("Top Places:", top_places)
        print(agent.format_recommendations(top_places))

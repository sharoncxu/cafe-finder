"""Data models for the Location Finding Agent."""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum

class FilterState(Enum):
    """Enum for filter states."""
    NEUTRAL = "neutral"
    INCLUDE = "include"
    EXCLUDE = "exclude"

@dataclass
class PlacePhoto:
    """Represents a place photo."""
    url: str
    reference: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

@dataclass
class PlaceReview:
    """Represents a place review."""
    author_name: str
    rating: int
    text: str
    time_description: Optional[str] = None
    relative_time_description: Optional[str] = None

@dataclass
class Location:
    """Represents a geographic location."""
    lat: float
    lng: float
    formatted_address: Optional[str] = None

@dataclass
class Place:
    """Represents a place from Google Maps."""
    place_id: str
    name: str
    rating: Optional[float] = None
    user_ratings_total: Optional[int] = None
    vicinity: Optional[str] = None
    formatted_address: Optional[str] = None
    price_level: Optional[int] = None
    types: List[str] = field(default_factory=list)
    geometry: Optional[Dict[str, Any]] = None
    
    # Enhanced fields
    photo_urls: List[str] = field(default_factory=list)
    google_maps_link: Optional[str] = None
    calculated_score: float = 0.0
    review_analyzed: bool = False
    filter_matches: Dict[str, bool] = field(default_factory=dict)
    
    def get_location(self) -> Optional[Location]:
        """Get the location coordinates of the place."""
        if not self.geometry or 'location' not in self.geometry:
            return None
        loc_data = self.geometry['location']
        return Location(
            lat=loc_data.get('lat', 0),
            lng=loc_data.get('lng', 0),
            formatted_address=self.formatted_address
        )

@dataclass
class SearchPreferences:
    """Represents user search preferences."""
    location: str
    preferences: List[str] = field(default_factory=list)
    avoid: List[str] = field(default_factory=list)
    underrated: bool = False
    specific_cafe_names: List[str] = field(default_factory=list)
    filter_states: Dict[str, FilterState] = field(default_factory=dict)

@dataclass
class SearchResult:
    """Represents a search result."""
    text: str
    places: List[Place] = field(default_factory=list)
    location_found: Optional[str] = None
    total_analyzed: int = 0
    review_analyzed_count: int = 0

@dataclass
class ConversationMessage:
    """Represents a conversation message."""
    role: str  # 'user', 'assistant', 'tool'
    content: str
    tool_call_id: Optional[str] = None
    places: List[Place] = field(default_factory=list)

@dataclass
class ChatRequest:
    """Represents an incoming chat request."""
    message: str
    filter_states: Dict[str, str] = field(default_factory=dict)
    conversation_history: List[Dict] = field(default_factory=list)
    
    def get_preferences(self) -> SearchPreferences:
        """Convert chat request to search preferences."""
        include_filters = [f for f, state in self.filter_states.items() if state == 'include']
        exclude_filters = [f for f, state in self.filter_states.items() if state == 'exclude']
        
        return SearchPreferences(
            location="",  # Will be extracted from message
            preferences=include_filters,
            avoid=exclude_filters,
            filter_states={f: FilterState(state) for f, state in self.filter_states.items()}
        )
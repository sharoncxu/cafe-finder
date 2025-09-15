"""Custom exceptions for the Location Finding Agent."""

class LocationFinderError(Exception):
    """Base exception for Location Finder application."""
    pass

class ConfigurationError(LocationFinderError):
    """Raised when there's a configuration error."""
    pass

class GoogleMapsError(LocationFinderError):
    """Raised when there's an error with Google Maps API."""
    pass

class OpenAIError(LocationFinderError):
    """Raised when there's an error with OpenAI API."""
    pass

class GeocodeError(GoogleMapsError):
    """Raised when geocoding fails."""
    pass

class PlaceSearchError(GoogleMapsError):
    """Raised when place search fails."""
    pass

class PlaceDetailsError(GoogleMapsError):
    """Raised when getting place details fails."""
    pass
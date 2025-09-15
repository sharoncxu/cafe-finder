"""Configuration management for the Location Finding Agent."""

import os
from typing import Optional
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    """Application configuration class."""
    
    def __init__(self):
        self.github_token = self._require_env_var("GITHUB_TOKEN")
        self.google_maps_api_key = self._require_env_var("GOOGLE_MAPS_API_KEY")
        self.flask_env = os.getenv("FLASK_ENV", "development")
        self.flask_debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
        self.port = int(os.getenv("PORT", 5000))
        self.host = os.getenv("HOST", "0.0.0.0")
        
        # API Configuration
        self.openai_base_url = "https://models.github.ai/inference"
        self.model_name = "openai/gpt-4.1-mini"
        
        # Search Configuration
        self.default_location = "Seattle, WA"
        self.search_radius = 1500  # meters
        self.max_photos = 1
        self.max_reviews = 5
        self.max_places = 6
        
        # Logging Configuration
        self.log_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper())
        
    def _require_env_var(self, name: str) -> str:
        """Get an environment variable and fail with clear message if missing or empty."""
        logger.info(f"Loading environment variable: {name}")
        value = os.getenv(name)
        if value is None:
            raise ValueError(f"{name} environment variable is MISSING (not set in .env or system).")
        if value.strip() == "":
            raise ValueError(f"{name} environment variable is EMPTY (check formatting in .env).")
        logger.info(f"{name} loaded successfully: {value[:10]}...")
        return value

# Global configuration instance
config = Config()
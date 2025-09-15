"""Application factory for the Location Finding Agent."""

import logging
from flask import Flask
from flask_cors import CORS

from .config import config
from .utils.logging import setup_logging
from .services.google_maps_service import GoogleMapsService
from .services.cafe_search_service import CafeSearchService
from .services.cafe_details_service import CafeDetailsService
from .services.openai_agent_service import OpenAIAgentService
from .routes import create_routes

logger = logging.getLogger(__name__)

def create_app() -> Flask:
    """Create and configure the Flask application."""
    
    # Setup logging first
    setup_logging()
    logger.info("Creating Location Finding Agent application")
    
    # Create Flask app
    app = Flask(__name__, static_folder='../frontend/build', static_url_path='')
    CORS(app)
    
    # Configure app
    app.config['DEBUG'] = config.flask_debug
    app.config['ENV'] = config.flask_env
    
    # Initialize services
    google_maps_service = GoogleMapsService()
    cafe_search_service = CafeSearchService(google_maps_service)
    cafe_details_service = CafeDetailsService(google_maps_service)
    openai_agent_service = OpenAIAgentService(cafe_search_service, cafe_details_service)
    
    # Create routes
    create_routes(app, openai_agent_service)
    
    logger.info("Application created successfully")
    return app
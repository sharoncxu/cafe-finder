"""Flask routes for the Location Finding Agent."""

import logging
import asyncio
from flask import Flask, request, jsonify, send_from_directory

from .models.data_models import ChatRequest, SearchResult
from .services.openai_agent_service import OpenAIAgentService
from .utils.logging import RequestLogger

logger = logging.getLogger(__name__)

def create_routes(app: Flask, openai_agent_service: OpenAIAgentService) -> None:
    """Create and register all Flask routes."""
    
    @app.route('/api/health')
    def health_check():
        """Health check endpoint."""
        with RequestLogger(logger, "health_check"):
            return jsonify({
                "status": "healthy", 
                "agent_framework": "OpenAI Function Calling", 
                "model": "gpt-4.1-mini"
            })
    
    @app.route('/api/chat', methods=['POST'])
    def chat():
        """Main chat endpoint."""
        with RequestLogger(logger, "chat_request") as req_logger:
            try:
                data = request.json
                if not data:
                    return jsonify({"error": "No data provided"}), 400
                
                message = data.get('message', '')
                if not message:
                    return jsonify({"error": "Message is required"}), 400
                
                # Create chat request object
                chat_request = ChatRequest(
                    message=message,
                    filter_states=data.get('filterStates', {}),
                    conversation_history=data.get('conversationHistory', [])
                )
                
                logger.info(f"Processing chat request: '{message}'")
                logger.info(f"Filter states: {chat_request.filter_states}")
                logger.info(f"Conversation history: {len(chat_request.conversation_history)} messages")
                
                # Run the agent
                result = _run_agent_sync(openai_agent_service, chat_request)
                
                # Format response for frontend compatibility
                response_data = _format_response_for_frontend(result, message)
                
                logger.info("Chat request completed successfully")
                return jsonify(response_data)
                
            except Exception as e:
                logger.error(f"Chat error: {e}")
                return jsonify({"error": "Something went wrong. Please try again."}), 500
    
    @app.route('/api/places', methods=['GET'])
    def get_places():
        """Places endpoint for direct place queries."""
        with RequestLogger(logger, "places_request"):
            try:
                location = request.args.get('location', '')
                filters = request.args.getlist('filters')
                
                if not location:
                    return jsonify({"error": "Location is required"}), 400
                
                # Create a simple chat request
                filter_text = f" with {', '.join(filters)}" if filters else ""
                message = f"Find cute cafes in {location}{filter_text}"
                
                chat_request = ChatRequest(message=message)
                
                # Run the agent
                result = _run_agent_sync(openai_agent_service, chat_request)
                
                return jsonify({
                    "places": [place.__dict__ for place in result.places] if result.places else [],
                    "response": result.text,
                    "count": len(result.places) if result.places else 0
                })
                
            except Exception as e:
                logger.error(f"Places error: {e}")
                return jsonify({"error": "Something went wrong. Please try again."}), 500
    
    @app.route('/')
    def serve_frontend():
        """Serve the frontend application."""
        return send_from_directory(app.static_folder, 'index.html')
    
    @app.route('/<path:path>')
    def static_files(path):
        """Serve static files."""
        return send_from_directory(app.static_folder, path)
    
    logger.info("Routes created successfully")

def _run_agent_sync(agent_service: OpenAIAgentService, chat_request: ChatRequest) -> SearchResult:
    """Run the agent synchronously using asyncio."""
    async def run_agent():
        try:
            return await agent_service.run_cafe_agent(chat_request)
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return SearchResult(
                text=f"I apologize, but I'm having trouble processing your request right now. Please try again. Error: {str(e)}",
                places=[]
            )
    
    # Use asyncio to run the agent
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_agent())
    finally:
        loop.close()

def _format_response_for_frontend(result: SearchResult, user_message: str) -> dict:
    """Format agent response for frontend compatibility."""
    return {
        "response": result.text,
        "structured_response": result.text,
        "places": [place.__dict__ for place in result.places] if result.places else [],
        "location": result.location_found or "Location handled by agent",
        "filters": [],
        "include_filters": [],
        "exclude_filters": [],
        "parsed_data": {"agent_handled": True},
        "total_found": len(result.places) if result.places else 0,
        "review_limit_applied": None
    }
# Location Finding Agent

An intelligent location finding agent built with Microsoft Agent Framework that uses LLM-powered intent parsing to determine when and how to call Google Maps API tools.

## Architecture

### Agent-Based Design
- **Microsoft Agent Framework**: Orchestrates the AI agent with tool calling capabilities
- **GitHub Models (GPT-4.1-mini)**: Powers intent parsing and natural conversation
- **Google Maps API Tool**: Fetches location data based on agent decisions
- **Thread-based Conversations**: Maintains context across multiple exchanges

### How It Works

1. **Intent Parsing**: The agent uses GPT-4.1-mini to understand user requests for locations
2. **Tool Decision**: The LLM determines when to call the Google Maps search tool
3. **Data Fetching**: The tool searches Google Maps API with intelligent filtering
4. **Response Generation**: The agent crafts natural language responses with place recommendations

## Key Features

### 🤖 Intelligent Agent
- Automatically determines when to search for places vs. general conversation
- Maintains conversation context across multiple exchanges
- Handles complex queries with multiple preferences

### 🛠️ Smart Tools
- **search_places**: Google Maps integration with advanced filtering
- Supports location, place type, preference filters (coffee, wifi, outlets, etc.)
- Returns enriched data with photos and Google Maps links

### 🧠 Advanced Capabilities
- Natural language understanding for location requests
- Context-aware follow-up questions
- Intelligent ranking based on ratings and filter matches
- Session management with conversation threads

## Installation

### 1. Install Dependencies
```bash
pip install -r requirements_agent.txt
```

### 2. Set Environment Variables
```bash
# GitHub Personal Access Token for GitHub Models
GITHUB_TOKEN=your_github_token_here

# Google Maps API Key
GOOGLE_MAPS_API_KEY=your_google_maps_key_here
```

### 3. Run the Agent
```bash
python app_agent.py
```

## Usage Examples

### Basic Location Search
```
User: "Find coffee shops in Seattle"
Agent: [Calls search_places tool] -> Returns top-rated coffee shops with details
```

### Complex Filtering
```
User: "I need a cafe with good wifi and outlets for working in downtown Portland"
Agent: [Calls search_places with filters=["wifi", "outlets"]] -> Returns work-friendly cafes
```

### Follow-up Conversations
```
User: "Find cafes in Boston"
Agent: [Returns cafe recommendations]

User: "What about the ratings for these?"
Agent: [Uses conversation context to discuss previously found cafes]
```

## API Endpoints

### Chat Endpoint
```
POST /api/chat
{
  "message": "Find cafes with pastries in Seattle",
  "sessionId": "user_123"
}
```

Response includes:
- Natural language response from agent
- Structured place data (if tools were called)
- Session management for context

### Legacy Support
The app maintains backward compatibility with the original API structure.

## Testing

Run the test suite to verify agent functionality:

```bash
python test_agent.py
```

Tests cover:
- Agent initialization
- Google Maps tool functionality  
- Conversation flow
- Context maintenance

## Comparison: Original vs Agent Architecture

### Original App
- **Manual parsing**: Hand-coded intent extraction
- **Direct API calls**: Immediate Google Maps requests
- **Limited context**: Basic conversation history
- **Fixed responses**: Template-based formatting

### Agent Architecture  
- **LLM-powered parsing**: Intelligent intent understanding
- **Tool-driven decisions**: Agent decides when to call APIs
- **Rich context**: Full conversation threads with Microsoft Agent Framework
- **Natural responses**: AI-generated, contextual replies

## Benefits of Agent Architecture

1. **Smarter Intent Understanding**: The LLM can handle complex, ambiguous queries
2. **Dynamic Tool Usage**: Agent decides when tools are needed vs. general conversation
3. **Better Context Management**: Conversation threads maintain rich context
4. **Extensible Design**: Easy to add new tools and capabilities
5. **Natural Interactions**: More human-like conversation flow

## Development Notes

### Adding New Tools
```python
@staticmethod
def new_tool(
    param: Annotated[str, "Parameter description"]
) -> str:
    """Tool function with proper annotations"""
    # Tool implementation
    return json.dumps(result)

# Add to agent tools list
agent = ChatClientAgent(
    # ... other config ...
    tools=[LocationTools.search_places, LocationTools.new_tool]
)
```

### Model Selection
The agent uses `openai/gpt-4.1-mini` from GitHub Models for:
- Cost efficiency
- Good intent parsing capabilities  
- Function calling support
- Fast response times

### Thread Management
- Automatic session cleanup (keeps last 50 sessions)
- Thread persistence across requests
- Context maintained throughout conversation

## License

MIT License - See LICENSE file for details

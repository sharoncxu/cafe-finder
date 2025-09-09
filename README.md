# Location Finding Agent

A chat-based application that provides personalized recommendations for cafes and restaurants based on user preferences and location.

## Features

- **Interactive Chat Interface**: Natural language conversations to find perfect venues
- **Smart Filtering**: Filter by pastries, food, study-friendly, wifi, and power outlets
- **Google Maps Integration**: Real-time data from Google Places API
- **AI-Powered Recommendations**: GitHub Copilot models (GPT-4.1-mini) for intelligent suggestions
- **Top 3 Results**: Curated list based on ratings and proximity

## Tech Stack

- **Backend**: Python Flask with GitHub Copilot integration
- **Frontend**: React with modern chat UI
- **Data Source**: Google Maps Places API
- **AI Model**: GitHub Copilot (GPT-4.1-mini) for natural language processing

## Setup

### Prerequisites
- Python 3.8+
- Node.js 16+
- GitHub Personal Access Token (for Copilot models)
- Google Maps API key

### Installation

1. Clone the repository
2. Install backend dependencies: `pip install -r requirements.txt`
3. Install frontend dependencies: `cd frontend && npm install`
4. Create `.env` file from `.env.example`
5. Set up your GitHub Personal Access Token:
   - Go to GitHub Settings → Developer settings → Personal access tokens
   - Generate a token with appropriate permissions
   - Add it to your `.env` file as `GITHUB_TOKEN`
6. Add your Google Maps API key to the `.env` file
7. Run the application: `python app.py`

## Usage

1. Start a conversation by typing your location and preferences
2. Use filters to specify your needs (pastries, study space, etc.)
3. Get personalized recommendations with ratings and details
4. Click on results to view on Google Maps

## API Endpoints

- `POST /api/chat` - Process chat messages and return recommendations
- `GET /api/places` - Search places with filters
- `GET /api/health` - Health check endpoint

## Environment Variables

- `GITHUB_TOKEN` - Your GitHub Personal Access Token for Copilot models
- `GOOGLE_MAPS_API_KEY` - Your Google Maps Places API key
- `FLASK_ENV` - Development/production environment

import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    {
      type: 'bot',
      content: 'Hi! I\'m here to help you find cute cafes. Tell me what kind of place you\'re looking for, and I\'ll help you find the perfect spot!'
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [filterStates, setFilterStates] = useState({
    pastries: 'neutral',
    food: 'neutral',
    coffee: 'neutral',
    wifi: 'neutral',
    outlets: 'neutral',
    seating: 'neutral'
  });
  const [justChanged, setJustChanged] = useState(new Set());
  const messagesEndRef = useRef(null);

  const filters = [
    { id: 'pastries', label: '🥐 Pastries', description: 'Great baked goods' },
    { id: 'food', label: '🍽️ Food', description: 'Full meal options' },
    { id: 'coffee', label: '☕ Coffee', description: 'Quality coffee drinks' },
    { id: 'wifi', label: '📶 WiFi', description: 'Strong internet' },
    { id: 'outlets', label: '🔌 Outlets', description: 'Charging outlets' },
    { id: 'seating', label: '🪑 Seating', description: 'Comfortable seating' }
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const toggleFilter = (filterId) => {
    // Mark this filter as just changed to disable hover effect
    setJustChanged(prev => new Set(prev).add(filterId));

    setFilterStates(prev => {
      const currentState = prev[filterId];
      let nextState;
      
      if (currentState === 'neutral') {
        nextState = 'include';
      } else if (currentState === 'include') {
        nextState = 'exclude';
      } else { // exclude
        nextState = 'neutral';
      }
      
      return { ...prev, [filterId]: nextState };
    });
  };

  const handleMouseEnter = (filterId) => {
    // Re-enable hover effect when mouse enters
    setJustChanged(prev => {
      const newSet = new Set(prev);
      newSet.delete(filterId);
      return newSet;
    });
  };

  const sendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage = inputMessage;
    
    // Build filter message based on states
    const includeFilters = Object.entries(filterStates)
      .filter(([_, state]) => state === 'include')
      .map(([filter, _]) => filter);
    
    const excludeFilters = Object.entries(filterStates)
      .filter(([_, state]) => state === 'exclude')
      .map(([filter, _]) => filter);
    
    let filtersMessage = '';
    if (includeFilters.length > 0) {
      filtersMessage += ` Must have: ${includeFilters.join(', ')}`;
    }
    if (excludeFilters.length > 0) {
      filtersMessage += ` Avoid: ${excludeFilters.join(', ')}`;
    }
    
    const fullMessage = userMessage + filtersMessage;

    // Add user message to chat
    setMessages(prev => [...prev, { type: 'user', content: userMessage }]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await axios.post('/api/chat', {
        message: fullMessage,
        filterStates: filterStates,
        conversationHistory: messages  // Send conversation history to backend
      });

      // Add bot response to chat
      setMessages(prev => [...prev, { 
        type: 'bot', 
        content: response.data.response,
        places: response.data.places,
        location: response.data.location,
        filters: response.data.filters
      }]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, { 
        type: 'bot', 
        content: 'Sorry, I encountered an error. Please try again.' 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const parseMarkdown = (text) => {
    // Simple markdown parser for bold text
    return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  };

  const renderMessageContent = (content) => {
    return content.split('\n').map((line, i) => (
      <div 
        key={i} 
        dangerouslySetInnerHTML={{ __html: parseMarkdown(line) }}
      />
    ));
  };

  return (
    <div className="App">
      <header className="app-header">
        <h1>✨Cute Cafe Finder✨</h1>
        <p>Find the most popular and aesthetic cafes near you</p>
      </header>

      <div className="chat-container">
        <div className="messages">
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.type}`}>
              <div className="message-content">
                {renderMessageContent(message.content)}
                {message.places && message.places.length > 0 && (
                  <div className="places-preview">
                    {message.places.slice(0, 6).map((place, placeIndex) => (
                      <div 
                        key={placeIndex} 
                        className="place-card clickable"
                        onClick={() => {
                          if (place.google_maps_link) {
                            window.open(place.google_maps_link, '_blank');
                          }
                        }}
                        title="Click to open in Google Maps"
                      >
                        <div className="place-image-container">
                          {place.photo_urls && place.photo_urls.length > 0 ? (
                            <img 
                              src={place.photo_urls[0]} 
                              alt={place.name} 
                              className="place-photo"
                              onError={(e) => {
                                // Better fallback - show placeholder instead of hiding
                                e.target.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAwIiBoZWlnaHQ9IjMwMCIgdmlld0JveD0iMCAwIDQwMCAzMDAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSI0MDAiIGhlaWdodD0iMzAwIiBmaWxsPSIjZjNmNGY2Ii8+CjxwYXRoIGQ9Ik0yMDAgMTUwQzIwMCAxNzIuMDkxIDE4Mi4wOTEgMTkwIDE2MCAxOTBDMTM3LjkwOSAxOTAgMTIwIDE3Mi4wOTEgMTIwIDE1MEMxMjAgMTI3LjkwOSAxMzcuOTA5IDExMCAxNjAgMTEwQzE4Mi4wOTEgMTEwIDIwMCAxMjcuOTA5IDIwMCAxNTBaIiBmaWxsPSIjZDFkNWRiIi8+CjxwYXRoIGQ9Ik0yNDAgMTkwSDE2MEwyMDAgMTUwTDI0MCAxOTBaIiBmaWxsPSIjZDFkNWRiIi8+PC9zdmc+Cg==';
                                e.target.classList.add('placeholder-image');
                              }}
                            />
                          ) : (
                            <div className="place-photo-placeholder">
                              <div className="placeholder-icon">📍</div>
                              <div className="placeholder-text">No image</div>
                            </div>
                          )}
                        </div>
                        <div className="place-info">
                          <div className="place-name">{place.name}</div>
                          <div className="place-rating">
                            ⭐ {place.rating || 'N/A'} 
                            {place.user_ratings_total && ` (${place.user_ratings_total} reviews)`}
                          </div>
                          <div className="place-address">{place.vicinity}</div>
                          {place.filter_matches && Object.keys(place.filter_matches).some(key => place.filter_matches[key]) && (
                            <div className="filter-matches">
                              {Object.entries(place.filter_matches)
                                .filter(([_, matches]) => matches)
                                .map(([filterName, _]) => (
                                  <span key={filterName} className="filter-match">
                                    ✓ {filterName}
                                  </span>
                                ))}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="message bot">
              <div className="message-content">
                <div className="typing">Searching for great places...</div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="fixed-input-section">
        <div className="input-section">
          <div className="input-container">
            <div className="textarea-wrapper">
              <textarea
                value={inputMessage}
                onChange={(e) => setInputMessage(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Tell me where you want to go... (e.g., 'cafes in downtown Seattle' or 'study spots near UCLA')"
                rows="2"
                disabled={isLoading}
              />
              <button 
                onClick={sendMessage} 
                disabled={isLoading || !inputMessage.trim()}
                className="send-btn-icon"
                title="Send message"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M2 21L23 12L2 3V10L17 12L2 14V21Z" fill="currentColor"/>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <div className="filter-section">
          <div className="filters">
            {filters.map(filter => (
              <button
                key={filter.id}
                className={`filter-btn ${filterStates[filter.id]} ${justChanged.has(filter.id) ? 'hover-disabled' : ''}`}
                onClick={() => toggleFilter(filter.id)}
                onMouseEnter={() => handleMouseEnter(filter.id)}
                title={`${filter.description} - Click to cycle: Neutral → Include → Exclude`}
              >
                {filterStates[filter.id] === 'include' && '✅ '}
                {filterStates[filter.id] === 'exclude' && '❌ '}
                {filter.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;

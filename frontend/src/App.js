import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    {
      type: 'bot',
      content: 'Hi! I\'m your location finding agent. Tell me what kind of place you\'re looking for and where, and I\'ll help you find the perfect cafe or restaurant!'
    }
  ]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [filterStates, setFilterStates] = useState({
    pastries: 'neutral',
    food: 'neutral', 
    study: 'neutral',
    wifi: 'neutral',
    outlets: 'neutral'
  });
  const [sessionId] = useState(() => {
    // Generate a unique session ID for this browser session
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  });
  const messagesEndRef = useRef(null);

  const filters = [
    { id: 'pastries', label: '🥐 Pastries', description: 'Great baked goods' },
    { id: 'food', label: '🍽️ Food', description: 'Full meal options' },
    { id: 'study', label: '📚 Study', description: 'Quiet workspace' },
    { id: 'wifi', label: '📶 WiFi', description: 'Strong internet' },
    { id: 'outlets', label: '🔌 Outlets', description: 'Power charging' }
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const toggleFilter = (filterId) => {
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

  const sendMessage = async () => {
    if (!inputMessage.trim()) return;

    const userMessage = inputMessage;
    
    // Add user message to chat
    setMessages(prev => [...prev, { type: 'user', content: userMessage }]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await axios.post('/api/chat', {
        message: userMessage,
        filters: filterStates,  // Send filter states to backend
        sessionId: sessionId    // Send session ID for chat history
      });

      // Add bot response to chat
      const botMessage = { 
        type: 'bot', 
        content: response.data.response,
        places: response.data.places,
        location: response.data.location,
        filters: response.data.filters
      };

      // If chat history is returned, use it to set the complete conversation
      if (response.data.chatHistory && response.data.chatHistory.length > 0) {
        // Convert backend chat history format to frontend format
        const convertedHistory = response.data.chatHistory.map(msg => ({
          type: msg.role === 'user' ? 'user' : 'bot',
          content: msg.content,
          places: msg.places || undefined,
          location: msg.location || undefined,
          filters: msg.filters || undefined
        }));
        setMessages(convertedHistory);
      } else {
        setMessages(prev => [...prev, botMessage]);
      }
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

  return (
    <div className="App">
      <header className="app-header">
        <h1>Cute Cafe Finder</h1>
        <p>Find the perfect cafes and restaurants near you</p>
      </header>

      <div className="filter-section">
        <h3>What are you looking for?</h3>
        <div className="filters">
          {filters.map(filter => (
            <button
              key={filter.id}
              className={`filter-btn ${filterStates[filter.id]}`}
              onClick={() => toggleFilter(filter.id)}
              title={`${filter.description} - Click to cycle: Neutral → Include → Exclude`}
            >
              {filterStates[filter.id] === 'include' && '✅ '}
              {filterStates[filter.id] === 'exclude' && '❌ '}
              {filter.label}
            </button>
          ))}
        </div>
        <div className="filter-legend">
          <small>
            <span className="legend-item">⚪ Neutral</span>
            <span className="legend-item">✅ Must Have</span>
            <span className="legend-item">❌ Avoid</span>
          </small>
        </div>
      </div>

      <div className="chat-container">
        <div className="messages">
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.type}`}>
              <div className="message-content">
                {message.content.split('\n').map((line, i) => (
                  <div key={i}>{line}</div>
                ))}
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

        <div className="input-section">
          <div className="input-container">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Tell me where you want to go and what you're looking for... (e.g., 'cafes in downtown Seattle' or 'study spots near UCLA')"
              rows="2"
              disabled={isLoading}
            />
            <button 
              onClick={sendMessage} 
              disabled={isLoading || !inputMessage.trim()}
              className="send-btn"
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;

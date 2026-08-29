// ChatMode.jsx: A fully functional chat interface connected to your FastAPI backend
import React, { useState } from 'react';
import apiClient from '../api/client';

export default function ChatMode() {
  const [messages, setMessages] = useState([
    { sender: 'system', text: 'Connected to Agentic Chat Backend.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = input;
    setMessages((prev) => [...prev, { sender: 'user', text: userMessage }]);
    setInput('');
    setLoading(true);

    try {
      // Updated payload key from 'message' to 'prompt' to match FastAPI backend expectation
      const response = await apiClient.post('/chat', {
        prompt: userMessage
      });

      const botReply = response.data.response || response.data.message || JSON.stringify(response.data);
      setMessages((prev) => [...prev, { sender: 'bot', text: botReply }]);
    } catch (error) {
      console.error("Chat API error:", error);
      setMessages((prev) => [...prev, { sender: 'error', text: 'Failed to fetch response from backend agent.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '700px', margin: '0 auto', background: '#fff', padding: '20px', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
      <h2>💬 Agentic Chat Interface</h2>
      
      <div style={{ height: '350px', overflowY: 'scroll', border: '1px solid #e1e4e8', padding: '15px', marginBottom: '15px', background: '#f8f9fa', borderRadius: '6px' }}>
        {messages.map((msg, index) => (
          <div key={index} style={{ margin: '10px 0', textAlign: msg.sender === 'user' ? 'right' : 'left' }}>
            <span style={{
              display: 'inline-block',
              padding: '10px 14px',
              borderRadius: '8px',
              background: msg.sender === 'user' ? '#007bff' : msg.sender === 'error' ? '#dc3545' : '#e2e3e5',
              color: msg.sender === 'user' || msg.sender === 'error' ? '#fff' : '#212529',
              maxWidth: '80%',
              wordBreak: 'break-word',
              textAlign: 'left'
            }}>
              {msg.text}
            </span>
          </div>
        ))}
        {loading && <div style={{ fontStyle: 'italic', color: '#6c757d', textAlign: 'left' }}>Agent is thinking...</div>}
      </div>

      <form onSubmit={sendMessage} style={{ display: 'flex', gap: '10px' }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message to the agent..."
          style={{ flex: 1, padding: '10px', borderRadius: '4px', border: '1px solid #ced4da' }}
        />
        <button type="submit" disabled={loading} style={{ padding: '10px 20px', background: '#007bff', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
          {loading ? 'Sending...' : 'Send'}
        </button>
      </form>
    </div>
  );
}
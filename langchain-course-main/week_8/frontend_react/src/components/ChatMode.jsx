// ChatMode.jsx: A fully functional chat interface connected to your FastAPI backend with client-side guardrails
import React, { useState } from 'react';
import apiClient from '../api/client';

// 1. Define client-side guardrail patterns for instant UX protection (0 bytes local storage required)
const BLOCKED_PATTERNS = [
  /ignore previous instructions/i,
  /reveal system prompt/i,
  /you are now a/i,
  /disregard all rules/i,
  /bypass safety/i
];

function clientSideGuardrail(input) {
  if (!input || typeof input !== "string") return { isSafe: false };

  if (input.length > 1000) {
    return { isSafe: false, reason: "Query is too long." };
  }

  for (const pattern of BLOCKED_PATTERNS) {
    if (pattern.test(input)) {
      return { 
        isSafe: false, 
        reason: "🛡️ Intercepted by client guardrail: Potentially unsafe prompt pattern detected." 
      };
    }
  }

  return { isSafe: true };
}

export default function ChatMode() {
  const [messages, setMessages] = useState([
    { sender: 'system', text: 'Connected to Agentic Chat Backend with Guardrails.' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMessage = input;
    setInput('');

    // 2. Run client-side guardrail check before making any API request
    const check = clientSideGuardrail(userMessage);
    if (!check.isSafe) {
      setMessages((prev) => [
        ...prev, 
        { sender: 'user', text: userMessage },
        { sender: 'error', text: check.reason }
      ]);
      return;
    }

    // 3. Proceed with normal workflow if safe
    setMessages((prev) => [...prev, { sender: 'user', text: userMessage }]);
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
      <h2>💬 Agentic Chat Interface (Secured)</h2>
      
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
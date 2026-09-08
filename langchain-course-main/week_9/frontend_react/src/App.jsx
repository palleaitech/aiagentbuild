// App.jsx: A simple sidebar or tab navigation layout to switch between the Chat view and the Planner-Executor view seamlessly in your browser
// App.jsx: A simple sidebar or tab navigation layout to switch between the Chat view and the Planner-Executor view seamlessly in your browser
import React, { useState } from 'react';
import ChatMode from './components/ChatMode';
import PlannerMode from './components/PlannerMode';

export default function App() {
  const [activeTab, setActiveTab] = useState('chat');

  return (
    <div style={{ fontFamily: 'Arial, sans-serif', minHeight: '100vh', background: '#f4f7f6' }}>
      {/* Header & Navigation Bar */}
      <header style={{ background: '#2c3e50', color: '#fff', padding: '15px 30px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem' }}>Agentic Workflow Studio</h1>
        <nav style={{ display: 'flex', gap: '10px' }}>
          <button 
            onClick={() => setActiveTab('chat')}
            style={{
              padding: '8px 16px',
              background: activeTab === 'chat' ? '#3498db' : 'transparent',
              color: '#fff',
              border: '1px solid #3498db',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Chat View
          </button>
          <button 
            onClick={() => setActiveTab('planner')}
            style={{
              padding: '8px 16px',
              background: activeTab === 'planner' ? '#3498db' : 'transparent',
              color: '#fff',
              border: '1px solid #3498db',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Planner-Executor View
          </button>
        </nav>
      </header>

      {/* Main Content Area */}
      <main style={{ padding: '30px', maxWidth: '1100px', margin: '0 auto' }}>
        {activeTab === 'chat' ? <ChatMode /> : <PlannerMode />}
      </main>
    </div>
  );
}
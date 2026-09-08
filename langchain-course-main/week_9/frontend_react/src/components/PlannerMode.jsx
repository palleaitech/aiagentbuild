// PlannerMode.jsx: Renders detailed execution history findings just like Streamlit
import React, { useState } from 'react';
import apiClient from '../api/client';

export default function PlannerMode() {
  const [goal, setGoal] = useState("Plan a 3-day itinerary for Chennai focusing on tech hubs and local food.");
  const [threadId, setThreadId] = useState(null);
  const [status, setStatus] = useState("idle");
  const [planSteps, setPlanSteps] = useState([]);
  const [resultData, setResultData] = useState(null);
  const [loading, setLoading] = useState(false);

  const startPlanner = async () => {
    setLoading(true);
    try {
      const response = await apiClient.post('/run-planner-agent', {
        goal: goal,
        city: "Chennai",
        execution_engine: "background"
      });
      
      setThreadId(response.data.thread_id);
      setStatus("paused_for_approval");

      const backendPlan = response.data.plan || response.data.initial_plan || response.data.result?.plan;
      if (backendPlan && Array.isArray(backendPlan) && backendPlan.length > 0) {
        setPlanSteps(backendPlan);
      } else {
        setPlanSteps([
          "Step 1: Research major IT parks in Taramani and OMR.",
          "Step 2: Identify famous authentic Chettinad and Biryani spots.",
          "Step 3: Structure a balanced 3-day timeline."
        ]);
      }
    } catch (error) {
      console.error("Failed to start planner", error);
    } finally {
      setLoading(false);
    }
  };

  const resumeExecution = async () => {
    setLoading(true);
    try {
      const response = await apiClient.post('/resume-planner-agent', {
        thread_id: threadId,
        updated_plan: planSteps
      });
      setResultData(response.data);
      setStatus("completed");
    } catch (error) {
      console.error("Failed to resume execution", error);
    } finally {
      setLoading(false);
    }
  };

  const resetPlanner = () => {
    setStatus("idle");
    setThreadId(null);
    setPlanSteps([]);
    setResultData(null);
  };

  // Pull execution history for deep research findings, falling back to plan
  const executionHistory = resultData?.result?.execution_history || resultData?.execution_history || [];
  const fallbackPlan = resultData?.result?.plan || resultData?.plan || [];

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial', maxWidth: '850px', margin: '0 auto', background: '#fff', borderRadius: '8px', boxShadow: '0 2px 4px rgba(0,0,0,0.1)' }}>
      <h2>🔍 Multi-Step Planner & Execution Studio</h2>
      
      {status === "idle" && (
        <div>
          <label style={{ fontWeight: 'bold' }}>Enter complex goal:</label><br />
          <input 
            type="text" 
            value={goal} 
            onChange={(e) => setGoal(e.target.value)} 
            style={{ width: '100%', padding: '10px', margin: '10px 0', borderRadius: '4px', border: '1px solid #ced4da' }} 
          /><br />
          <button onClick={startPlanner} disabled={loading} style={{ padding: '10px 20px', background: '#007bff', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
            {loading ? "Initializing..." : "🚀 Start Planner Agent"}
          </button>
        </div>
      )}

      {status === "paused_for_approval" && (
        <div style={{ background: '#f9f9f9', padding: '20px', borderRadius: '8px', border: '1px solid #ddd' }}>
          <h3>🛑 Review & Edit Plan Steps</h3>
          <p>Active Thread ID: <code>{threadId}</code></p>
          
          {planSteps.map((step, index) => (
            <div key={index} style={{ margin: '10px 0' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 'bold', color: '#444' }}>Step {index + 1}</label><br />
              <input 
                type="text" 
                value={step} 
                onChange={(e) => {
                  const newSteps = [...planSteps];
                  newSteps[index] = e.target.value;
                  setPlanSteps(newSteps);
                }} 
                style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid #ced4da', background: '#fff' }}
              />
            </div>
          ))}

          <div style={{ display: 'flex', gap: '10px', marginTop: '15px' }}>
            <button onClick={resumeExecution} disabled={loading} style={{ background: '#28a745', color: 'white', padding: '10px 20px', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
              {loading ? "Executing..." : "✅ Approve & Run Execution"}
            </button>
            <button onClick={resetPlanner} style={{ background: '#6c757d', color: 'white', padding: '10px 20px', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
              Cancel
            </button>
          </div>
        </div>
      )}

      {status === "completed" && resultData && (
        <div style={{ marginTop: '20px', background: '#f8f9fa', padding: '20px', borderRadius: '8px', border: '1px solid #e1e4e8' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
            <h3 style={{ margin: 0, color: '#28a745' }}>🔍 Execution & Research Findings</h3>
            <button onClick={resetPlanner} style={{ background: '#007bff', color: '#fff', padding: '8px 16px', border: 'none', borderRadius: '4px', cursor: 'pointer' }}>
              🔄 Plan Another Goal
            </button>
          </div>

          <div style={{ background: '#fff', padding: '15px', borderRadius: '6px', border: '1px solid #dee2e6' }}>
            <p><strong>Goal:</strong> {resultData.result?.input || goal}</p>
            <p><strong>City:</strong> {resultData.result?.city || "Chennai"}</p>
            
            <h4 style={{ borderBottom: '1px solid #eee', paddingBottom: '5px', marginTop: '15px' }}>Detailed Step Findings:</h4>
            
            {executionHistory.length > 0 ? (
              <div style={{ marginTop: '10px', lineHeight: '1.6' }}>
                {executionHistory.map((item, idx) => (
                  <div key={idx} style={{ marginBottom: '15px', paddingBottom: '10px', borderBottom: '1px dashed #eee', whiteSpace: 'pre-wrap' }}>
                    {item}
                  </div>
                ))}
              </div>
            ) : fallbackPlan.length > 0 ? (
              <ul style={{ paddingLeft: '20px', lineHeight: '1.6', marginTop: '10px' }}>
                {fallbackPlan.map((stepText, idx) => (
                  <li key={idx} style={{ marginBottom: '8px', whiteSpace: 'pre-wrap' }}>{stepText}</li>
                ))}
              </ul>
            ) : (
              <p style={{ color: '#dc3545', fontStyle: 'italic' }}>No execution history recorded.</p>
            )}
          </div>

          <details style={{ marginTop: '15px', color: '#6c757d', cursor: 'pointer' }}>
            <summary>View Raw JSON Response</summary>
            <pre style={{ background: '#fff', padding: '10px', borderRadius: '4px', overflowX: 'auto', fontSize: '0.85rem', marginTop: '5px' }}>
              {JSON.stringify(resultData, null, 2)}
            </pre>
          </details>
        </div>
      )}
    </div>
  );
}
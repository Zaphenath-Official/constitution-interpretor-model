import React, { useState, useRef, useEffect } from 'react';
import './App.css';

export default function App() {
  // Session storage safely keeps history during page reloads, but drops it when the tab closes
  const [messages, setMessages] = useState(() => {
    const saved = sessionStorage.getItem('lawbot_session_messages');
    return saved ? JSON.parse(saved) : [];
  });
  
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  // Mobile navigation toggle: 'input' view or 'results' view
  const [mobileView, setMobileView] = useState('input');
  
  const messagesEndRef = useRef(null);
const API_URL = process.env.REACT_APP_API_URL || "https://kenyan-legal-interpreter-api.onrender.com/api/chat";

  useEffect(() => {
    sessionStorage.setItem('lawbot_session_messages', JSON.stringify(messages));
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage = { role: 'user', text: input.trim() };
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setInput('');
    setIsLoading(true);

    // On mobile, immediately shift focus to the display column to watch the streaming result
    setMobileView('results');

    try {
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userMessage.text })
      });

      if (!response.ok) throw new Error('Server Error');

      const data = await response.json();
      setMessages([...updatedMessages, { role: 'assistant', text: data.interpretation }]);
    } catch (error) {
      setMessages([...updatedMessages, { 
        role: 'assistant', 
        text: "Samahani, I failed to pull context from the legal records. Please check your network and try again." 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const fillInput = (text) => {
    setInput(text);
    // If a template is tapped on mobile view, slide back to input card so they can review/submit it
    setMobileView('input');
  };

  const clearSession = () => {
    sessionStorage.removeItem('lawbot_session_messages');
    setMessages([]);
    setMobileView('input');
  };

  return (
    <div className="page-wrapper">
      <div className="main-window-container">
        
        {/* LEFT COLUMN: FIXED BRAND & INTERACTION FORM */}
        <section className={`left-interaction-column ${mobileView === 'input' ? 'active-mobile' : 'hidden-mobile'}`}>
          <div className="brand-header">
            <span className="brand-gavel">§</span>
            <span className="brand-title">Law<span className="highlight-purple-text">Bot</span></span>
            {messages.length > 0 && (
              <button className="mobile-view-toggle-btn" onClick={() => setMobileView('results')}>
                View Chat →
              </button>
            )}
          </div>

          <div className="static-control-card">
            <div className="card-header-accent">
              <h2>Knowledge Is Power</h2>
              <p>Understand the Kenyan legal system easily.</p>
            </div>

            <div className="avatar-3d-wrapper">
              <div className="avatar-sphere">
                <span className="scale-balance">⚖️</span>
                <div className="pulse-ring"></div>
              </div>
            </div>

            <form onSubmit={handleSend} className="chat-input-form">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend(e);
                  }
                }}
                placeholder="Ask LawBot..."
                rows={2}
              />
              <button type="submit" className="action-send-btn" disabled={!input.trim() || isLoading}>
                {isLoading ? "Thinking..." : "Send Query"}
              </button>
            </form>

            {messages.length > 0 && (
              <button className="clear-btn-inline" onClick={clearSession}>
                Reset Conversation
              </button>
            )}

            <p className="system-caution-footer">
              LawBot can make mistakes. Verify formal legal actions.
            </p>
          </div>

          <div className="ephemeral-notice-banner">
            <span className="warn-dot"></span>
            <p>Session ends when the tab or browser is closed.</p>
          </div>
        </section>

        {/* RIGHT COLUMN: INDEPENDENT SCROLLING CONTENT VIEW */}
        <section className={`right-stream-column ${mobileView === 'results' ? 'active-mobile' : 'hidden-mobile'}`}>
          
          {/* Mobile Specific Header Actions */}
          <div className="mobile-navigation-bar">
            <button className="back-to-form-btn" onClick={() => setMobileView('input')}>
              ← Edit Query / Form
            </button>
            <button className="reset-session-mobile" onClick={clearSession}>
              Reset
            </button>
          </div>

          <div className="workspace-scroll-container">
            {messages.length === 0 ? (
              <div className="dashboard-intro-view">
                
                <div className="hero-highlight-card">
                  <h1>
                    Law<span className="inner-card-purple">Bot</span> Explains Kenyan Legal Matters And Its Context In Simple Ways You Can Understand And Relate To <span className="inner-card-white">Daily Narratives</span>.
                  </h1>
                </div>

                <div className="jargon-text-showcase">
                  <span className="sample-label-tag">Statutory Context Sample</span>
                  <p className="raw-statute-text">
                    "Any person may, upon application in the prescribed form and payment of the prescribed fee, inspect any register..."
                  </p>
                  <p className="plain-explanation-text">
                    <strong>In plain language:</strong> You have the absolute right to verify who owns any plot of land in Kenya. You don't need special permission; you just file an official search form at the land registry and pay the small processing fee to avoid getting conned.
                  </p>
                </div>

                <div className="shortcuts-wrapper">
                  <h3>Select A Template Prompt</h3>
                  <div className="shortcut-cards-row">
                    <div className="shortcut-card" onClick={() => fillInput("What are the key steps to register a limited liability partnership (LLP) in Kenya?")}>
                      <h4>Corporate Law</h4>
                      <p>Requirements for establishing an LLP corporate framework.</p>
                    </div>
                    <div className="shortcut-card" onClick={() => fillInput("Explain the grounds for termination of a lease agreement under the Land Act.")}>
                      <h4>Property Rights</h4>
                      <p>Understanding notice durations and structural tenancy breaches.</p>
                    </div>
                    <div className="shortcut-card" onClick={() => fillInput("What does the Kenya Gazette say about public land allocations this month?")}>
                      <h4>Gazette Audits</h4>
                      <p>Scrutinize ongoing government notices and constitutional filings.</p>
                    </div>
                  </div>
                </div>

              </div>
            ) : (
              <div className="chat-history-stream">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`stream-row ${msg.role}`}>
                    <div className="stream-identity-tag">
                      {msg.role === 'user' ? 'You' : 'LawBot'}
                    </div>
                    <div className="stream-text-content">
                      {msg.text}
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="stream-row assistant loading">
                    <div className="stream-identity-tag pulsing">LawBot</div>
                    <div className="stream-text-content loading-placeholder">
                      Searching 5,232 Gazette layers and writing explanation...
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          <footer className="workspace-footer-copyright">
            &copy; {new Date().getFullYear()} LawBot Kenya. RAG Engine Active.
          </footer>
        </section>

      </div>
    </div>
  );
}
import React, { useState } from 'react';
import { sendAIQuery } from '../api';
import './AISidebar.css';

/* ===== ANALYTICAL DISTRIBUTION ===== */
function PlantDistribution({ plantStats }) {
    const plants = Object.entries(plantStats);
    
    return (
        <div className="ai-status-card">
            <div className="status-header">
                <span className="status-label">Operational Distribution</span>
            </div>
            <div className="distribution-list" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {plants.map(([name, data]) => (
                    <div key={name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-secondary)' }}>{name}</span>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <span style={{ fontSize: '1.2rem', fontWeight: 800, color: 'var(--text-main)' }}>{data.people_count}</span>
                            <div style={{ 
                                width: '40px', height: '4px', background: 'var(--border-light)', borderRadius: '2px', overflow: 'hidden' 
                            }}>
                                <div style={{ 
                                    width: `${Math.min(100, (data.people_count / 50) * 100)}%`, 
                                    height: '100%', 
                                    background: 'var(--grad-primary)' 
                                }}></div>
                            </div>
                        </div>
                    </div>
                ))}
                {plants.length === 0 && <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Awaiting telemetry stream...</span>}
            </div>
        </div>
    );
}

/* ===== EVENT LOG ===== */
function EventLog({ events }) {
    return (
        <div className="event-section">
            <span className="section-title">Anomalies & Events</span>
            <div className="event-list">
                {events?.slice(0, 8).map((event, i) => (
                    <div key={i} className="event-row">
                        <div className="severity-bar" style={{ background: event.severity === 'info' ? 'var(--primary)' : `var(--${event.severity})` }}></div>
                        <div className="event-info">
                            <div className="event-main">{event.description}</div>
                            <div className="event-timestamp">
                                {new Date(event.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </div>
                        </div>
                    </div>
                ))}
                {(!events || events.length === 0) && (
                    <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)', fontSize: '0.9rem' }}>
                        No anomalies detected.
                    </div>
                )}
            </div>
        </div>
    );
}

/* ===== ANALYTICAL QUERY ===== */
function AIQuery() {
    const [messages, setMessages] = useState([]);
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSend = async () => {
        if (!query.trim()) return;
        const userQ = query.trim();
        setMessages(prev => [...prev, { role: 'user', text: userQ }]);
        setQuery('');
        setLoading(true);

        try {
            const res = await sendAIQuery(userQ);
            setMessages(prev => [...prev, { role: 'ai', text: res.response || 'Analysis complete.' }]);
        } catch (e) {
            setMessages(prev => [...prev, { role: 'ai', text: 'Telemetry link error.' }]);
        }
        setLoading(false);
    };

    return (
        <div className="ai-terminal">
            <div className="terminal-screen">
                {messages.length === 0 && (
                    <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', fontStyle: 'italic' }}>
                        Input analytical query for cross-plant processing...
                    </div>
                )}
                {messages.slice(-2).map((m, i) => (
                    <div key={i} className="line-text" style={{ 
                        color: m.role === 'ai' ? 'var(--text-main)' : 'var(--primary)',
                    }}>
                        <span style={{ fontWeight: 800, marginRight: '8px', fontSize: '0.7rem' }}>{m.role === 'ai' ? 'ANALYSIS' : 'QUERY'}</span>
                        {m.text}
                    </div>
                ))}
                {loading && <div className="line-text" style={{ opacity: 0.5, fontSize: '0.8rem' }}>Processing neural nodes...</div>}
            </div>
            <input
                className="terminal-input"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleSend()}
                placeholder="Query AI model..."
            />
        </div>
    );
}

function AISidebar({ insights, events, plantStats }) {
    return (
        <aside className="ai-sidebar">
            <div className="sidebar-inner">
                <div className="sidebar-top">
                    <div className="node-title">Analytical Hub</div>
                </div>

                <div className="sidebar-scrollable">
                    <PlantDistribution plantStats={plantStats} />
                    <EventLog events={events} />
                </div>

                <AIQuery />
            </div>
        </aside>
    );
}

export default AISidebar;

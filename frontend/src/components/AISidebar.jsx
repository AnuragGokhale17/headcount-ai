import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Filler, Legend } from 'chart.js';
import { sendAIQuery, sendAIVoice } from '../api';
import './AISidebar.css';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Legend);

/* ===== STATUS HERO ===== */
function StatusHero({ insights }) {
    const status = insights?.system_status || 'NORMAL';
    const trend = insights?.trend || 'stable';
    const cls = status === 'CRITICAL' ? 'status-critical' : status === 'ELEVATED' ? 'status-elevated' : 'status-normal';
    const label = status === 'CRITICAL' ? '⚠️ CRITICAL — ATTENTION REQUIRED' :
        status === 'ELEVATED' ? '🟡 ELEVATED — MONITORING' : '✅ NORMAL OPERATIONS';
    const trendEmoji = { rising: '📈', falling: '📉', stable: '➡️' };

    return (
        <div className={`ai-status-hero ${cls}`}>
            <div className="ai-status-label">System Status</div>
            <div className="ai-status-text">{label}</div>
            <div className="ai-trend-text">Trend: {trendEmoji[trend] || ''} {trend} · Learning patterns...</div>
        </div>
    );
}


/* ===== ENRICHED INSIGHT GRID ===== */
function InsightGrid({ insights, stats, cameras }) {
    const dwellSec = insights?.avg_dwell_seconds || 0;
    const dwellText = dwellSec >= 60 ? Math.floor(dwellSec / 60) + 'm' : dwellSec + 's';

    const totalCams = cameras?.length ? cameras.length + 1 : 1; // +1 for primary
    const offlineCount = cameras?.filter(c => !c.is_connected).length || 0;

    return (
        <div className="insight-grid">
            <div className="insight-card">
                <div className="insight-icon">🔮</div>
                <div className="insight-value" style={{ color: 'var(--primary)' }}>{insights?.prediction_next_hour ?? 0}</div>
                <div className="insight-label">Expected Crowd</div>
            </div>
            <div className="insight-card">
                <div className="insight-icon">⏱️</div>
                <div className="insight-value" style={{ color: 'var(--warning)' }}>{dwellText}</div>
                <div className="insight-label">Average Stay Time</div>
            </div>
            <div className="insight-card">
                <div className="insight-icon">📹</div>
                <div className="insight-value" style={{ color: offlineCount > 0 ? 'var(--danger)' : 'var(--success)' }}>
                    {totalCams - offlineCount}/{totalCams}
                </div>
                <div className="insight-label">Live Cameras</div>
            </div>
            <div className="insight-card">
                <div className="insight-icon">👁️</div>
                <div className="insight-value" style={{ color: insights?.loitering_count > 0 ? 'var(--danger)' : 'var(--text-main)' }}>
                    {insights?.loitering_count ?? 0}
                </div>
                <div className="insight-label">Waiting Too Long</div>
            </div>
        </div>
    );
}


/* ===== AREA ALERTS (45 Min Drops) ===== */
function AreaAlerts({ alerts }) {
    if (!alerts || alerts.length === 0) return null;
    return (
        <div className="ai-section">
            <div className="section-title">
                <span>Unusual Activity</span>
                <span className="section-count">{alerts.length}</span>
            </div>
            <div className="alerts-list">
                {alerts.map((a, i) => (
                    <div key={i} className="area-alert-item">
                        <span className="alert-dot"></span>
                        <div className="alert-content">
                            <strong>{a.area}</strong>: {a.message}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

/* ===== OCCUPANCY CHART ===== */
function OccupancyChart({ insights }) {
    const occData = insights?.occupancy_trend || [];
    const prediction = insights?.prediction_next_hour ?? 0;

    const data = useMemo(() => {
        const labels = Array(20).fill('');
        const actual = Array(20).fill(null);
        occData.forEach((v, i) => { actual[20 - occData.length + i] = v; });

        const predicted = Array(20).fill(null);
        if (occData.length > 0) {
            predicted[19] = prediction;
            predicted[18] = occData[occData.length - 1];
        }

        return {
            labels,
            datasets: [
                {
                    label: 'Occupancy',
                    data: actual,
                    borderColor: '#22d3ee',
                    backgroundColor: 'rgba(34, 211, 238, 0.08)',
                    borderWidth: 2,
                    tension: 0.4,
                    fill: true,
                    pointRadius: 0,
                },
                {
                    label: 'Predicted',
                    data: predicted,
                    borderColor: '#6366f1',
                    borderWidth: 1.5,
                    borderDash: [5, 5],
                    tension: 0.4,
                    fill: false,
                    pointRadius: 0,
                }
            ]
        };
    }, [occData, prediction]);

    const options = useMemo(() => ({
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
                position: 'top',
                labels: { color: '#64748b', font: { size: 9, family: 'Inter' }, boxWidth: 12, padding: 8 }
            }
        },
        scales: {
            x: { display: false },
            y: {
                display: true,
                beginAtZero: true,
                grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false },
                ticks: { color: '#64748b', font: { size: 9 } },
                suggestedMax: 12,
            }
        },
        animation: { duration: 0 }
    }), []);

    return (
        <div className="chart-card">
            <div className="chart-container">
                <Line data={data} options={options} />
            </div>
        </div>
    );
}

/* ===== EVENT LOG ===== */
function EventLog({ events }) {
    return (
        <div className="ai-section" style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <div className="section-title">
                <span>Recent Events</span>
                <span className="section-count">{events?.length || 0}</span>
            </div>
            <div className="event-log">
                {events?.slice(0, 50).map((event, i) => (
                    <div key={i} className="event-item">
                        <div className={`event-severity sev-${event.severity}`}></div>
                        <div className="event-body">
                            <div className="event-title">{event.event_type}</div>
                            <div className="event-desc">{event.description}</div>
                        </div>
                        <div className="event-time">
                            {new Date(event.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                    </div>
                ))}
                {(!events || events.length === 0) && (
                    <div className="empty-state">No significant events logged yet.</div>
                )}
            </div>
        </div>
    );
}

/* ===== AI VOICE CHAT ===== */
function AIChat({ insights, stats }) {
    const [messages, setMessages] = useState([
        { role: 'ai', text: 'AI Assistant online. Ask me about system status, alerts, or details.' }
    ]);
    const [query, setQuery] = useState('');
    const [loading, setLoading] = useState(false);
    const [recording, setRecording] = useState(false);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);
    const audioPlayerRef = useRef(new Audio());

    const handleSend = async () => {
        if (!query.trim()) return;
        const userQ = query.trim();
        setMessages(prev => [...prev, { role: 'user', text: userQ }]);
        setQuery('');
        setLoading(true);

        try {
            const res = await sendAIQuery(userQ);
            setMessages(prev => [...prev, { role: 'ai', text: res.response || 'No response.' }]);
        } catch (e) {
            setMessages(prev => [...prev, { role: 'ai', text: 'Error connecting to Nerve Center core.' }]);
        }
        setLoading(false);
    };

    const toggleRecording = () => {
        if (recording) {
            // Stopping handled by recognition.onend/onerror usually, 
            // but we can manually stop if needed
            return;
        }

        const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!Recognition) {
            alert('Your browser does not support Speech Recognition. Please use Chrome/Edge.');
            return;
        }

        const recognition = new Recognition();
        recognition.lang = 'en-US';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            setRecording(true);
        };

        recognition.onresult = async (event) => {
            const transcript = event.results[0][0].transcript;
            console.log("🎙️ Detected speech:", transcript);
            setMessages(prev => [...prev, { role: 'user', text: transcript }]);
            setLoading(true);

            try {
                // Now we send TEXT to the API, which it already supports!
                const res = await fetch('/api/ai_voice', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: transcript })
                });

                if (res.ok) {
                    const responseText = res.headers.get('X-Response-Text') || 'Processing complete.';
                    setMessages(prev => [...prev, { role: 'ai', text: responseText }]);

                    const resBlob = await res.blob();
                    const url = URL.createObjectURL(resBlob);
                    audioPlayerRef.current.src = url;
                    audioPlayerRef.current.play();
                } else {
                    setMessages(prev => [...prev, { role: 'ai', text: 'Nerve Center voice module failed.' }]);
                }
            } catch (e) {
                console.error("Voice API error:", e);
                setMessages(prev => [...prev, { role: 'ai', text: 'Connection to Nerve Center timed out.' }]);
            }
            setLoading(false);
        };

        recognition.onerror = (event) => {
            console.error("Speech recognition error:", event.error);
            setRecording(false);
        };

        recognition.onend = () => {
            setRecording(false);
        };

        recognition.start();
    };

    return (
        <div className="ai-chat">
            <div className="chat-messages">
                {messages.map((m, i) => (
                    <div key={i} className={`chat-msg chat-${m.role}`}>{m.text}</div>
                ))}
                {loading && <div className="chat-msg chat-ai">Nerve Center is analyzing...</div>}
            </div>
            <div className="chat-input-row">
                <button
                    className={`chat-mic ${recording ? 'recording' : ''}`}
                    onClick={toggleRecording}
                    title="Press to talk"
                >
                    {recording ? '⏹' : '🎤'}
                </button>
                <input
                    className="chat-input"
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSend()}
                    placeholder="Ask AI Assistant..."
                />
                <button className="chat-send" onClick={handleSend} disabled={loading || !query.trim()}>
                    ➤
                </button>
            </div>
        </div>
    );
}


function AISidebar({ stats, insights, events, cameras, alerts }) {
    return (
        <aside className="ai-sidebar">
            <div className="sidebar-header">
                <div className="sidebar-title">🧠 AI Assistant</div>
                <div className="pulse-indicator"></div>
            </div>

            <div className="sidebar-content">
                <StatusHero insights={insights} />
                <InsightGrid insights={insights} stats={stats} cameras={cameras} />
                <AreaAlerts alerts={alerts} />

                <div className="ai-section">
                    <div className="section-title">
                        <span>Crowd Forecast</span>
                    </div>
                    <OccupancyChart insights={insights} />
                </div>

                <EventLog events={events} />
            </div>

            <AIChat insights={insights} stats={stats} />
        </aside>
    );
}

export default AISidebar;

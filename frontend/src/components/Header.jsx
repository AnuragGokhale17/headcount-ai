import React, { useState, useEffect } from 'react';
import './Header.css';

function Header({ status, onManageCameras, onResetStats, onToggleAI, showAI, isDemoMode, onToggleDemo }) {
    const [clock, setClock] = useState('');

    useEffect(() => {
        const update = () => setClock(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        update();
        const id = setInterval(update, 1000);
        return () => clearInterval(id);
    }, []);

    const formattedDate = new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

    return (
        <header className="header">
            <div className="brand">
                <img src="/static/solarsred.png" alt="Solar Logo" className="brand-logo" />
                <h1 className="brand-text">Headcount <span className="brand-suffix">AI</span></h1>
            </div>

            <div className="header-right">
                <div className="header-telemetry">
                    <div className="telemetry-item">
                        <span className="telemetry-label">Network Status</span>
                        <span className="telemetry-value" style={{ 
                            color: status === 'OFFLINE' ? 'var(--secondary)' : 'var(--accent)' 
                        }}>
                            {status === 'OFFLINE' ? 'Disconnected' : (isDemoMode ? 'Simulation' : 'Connected')}
                        </span>
                    </div>
                </div>

                <div className="header-nav">
                    <button 
                        className={`header-btn ${isDemoMode ? 'active' : ''}`} 
                        onClick={onToggleDemo}
                        style={{ borderColor: isDemoMode ? 'var(--accent)' : '' }}
                    >
                        {isDemoMode ? 'Disable Demo' : 'Demo Mode'}
                    </button>
                    <button className="header-btn" onClick={onManageCameras}>Manage Nodes</button>
                    <button className="header-btn" onClick={onToggleAI}>{showAI ? 'Hide Analytics' : 'AI Analytics'}</button>
                    <button className="header-btn primary" onClick={onResetStats}>Reset Counts</button>
                </div>

                <div className="clock-group">
                    <span className="header-clock">{clock}</span>
                    <span className="header-date">{formattedDate}</span>
                </div>
            </div>
        </header>
    );
}

export default Header;

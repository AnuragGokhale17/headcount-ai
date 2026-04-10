import React, { useState, useEffect } from 'react';
import './Header.css';

function Header({ status, gpu, onManageCameras, onResetStats, onToggleAI, showAI, theme, onToggleTheme }) {
    const [clock, setClock] = useState('');

    useEffect(() => {
        const update = () => setClock(new Date().toLocaleTimeString());
        update();
        const id = setInterval(update, 1000);
        return () => clearInterval(id);
    }, []);

    const threatClass = status === 'CRITICAL' ? 'threat-critical' :
        status === 'ELEVATED' ? 'threat-elevated' : 'threat-normal';

    return (
        <header className="header">
            <div className="brand">
                <img
                    src={theme === 'light' ? '/static/solarsred.png' : '/static/solars.png'}
                    alt="Solar Group"
                    className="brand-logo"
                />
                <div className="brand-divider" />
                <span>AI Command Center</span>
            </div>
            <div className="header-right">
                <button className="header-btn" onClick={onManageCameras} title="Add / Manage Cameras">
                    <span>＋</span> Add Camera
                </button>

                <button className="header-btn danger-btn" onClick={onResetStats} title="Clear all entry/exit counts">
                    Reset Data
                </button>

                <button className="header-btn" onClick={onToggleAI} title="AI Panel">
                    🧠 {showAI ? 'Hide AI' : 'AI Panel'}
                </button>

                <div className={`threat-badge ${threatClass}`}>
                    <span>●</span>
                    <span>{status}</span>
                </div>

                {gpu && (
                    <div className="gpu-badge">
                        <div className="gpu-metrics">
                            <span className="gpu-label">RTX 5090</span>
                            <span className="gpu-val">{gpu.utilization}%</span>
                        </div>
                        <div className="gpu-bar">
                            <div className="gpu-progress" style={{ width: `${gpu.utilization}%` }} />
                        </div>
                        <div className="gpu-meta">
                            {Math.round(gpu.memory_used / 1024)} / {Math.round(gpu.memory_total / 1024)} GB
                        </div>
                    </div>
                )}
                <button className="theme-toggle" onClick={onToggleTheme} title="Toggle Theme">
                    {theme === 'dark' ? '☀️' : '🌙'}
                </button>
                <span className="header-clock mono">{clock}</span>
            </div>
        </header>
    );
}

export default Header;

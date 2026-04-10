import React from 'react';
import './StatsBar.css';

function StatsBar({ stats, insights }) {
    const dwellSec = insights?.avg_dwell_seconds || 0;
    const dwellText = dwellSec >= 60 ? Math.floor(dwellSec / 60) + 'm' : dwellSec + 's';

    return (
        <div className="stats-bar">
            <div className={`stat-card ${stats.occupancy >= 10 ? 'alert-pulse' : ''}`}>
                <div className="stat-label">Occupancy</div>
                <div className="stat-value val-occupancy">{stats.occupancy}</div>
                <div className="stat-sub">Current headcount</div>
            </div>
            <div className="stat-card">
                <div className="stat-label">Total In</div>
                <div className="stat-value val-in">{stats.in}</div>
                <div className="stat-sub">Entries logged</div>
            </div>
            <div className="stat-card">
                <div className="stat-label">Total Out</div>
                <div className="stat-value val-out">{stats.out}</div>
                <div className="stat-sub">Exits logged</div>
            </div>
            <div className="stat-card">
                <div className="stat-label">Avg Dwell</div>
                <div className="stat-value val-dwell">{dwellText}</div>
                <div className="stat-sub">Stay duration</div>
            </div>
            <div className="stat-card">
                <div className="stat-label">Prediction</div>
                <div className="stat-value val-prediction">{insights?.prediction_next_hour ?? 0}</div>
                <div className="stat-sub">Next hour est.</div>
            </div>
        </div>
    );
}

export default StatsBar;

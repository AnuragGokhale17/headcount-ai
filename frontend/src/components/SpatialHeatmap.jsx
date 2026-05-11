import React, { useState, useEffect, useRef } from 'react';
import { fetchHeatmap, cameraSnapshotUrl } from '../api';
import './SpatialHeatmap.css';

function SpatialHeatmap({ camera, onClose }) {
    const [grid, setGrid] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const timerRef = useRef(null);

    const refreshData = async () => {
        try {
            const data = await fetchHeatmap(camera.id);
            if (data && data.grid) {
                setGrid(data.grid);
            }
            setLoading(false);
            setError(null);
        } catch (err) {
            console.error('Heatmap fetch error:', err);
            setError('Failed to load activity data');
            setLoading(false);
        }
    };

    useEffect(() => {
        refreshData();
        timerRef.current = setInterval(refreshData, 3000); // Refresh every 3 seconds
        return () => clearInterval(timerRef.current);
    }, [camera.id]);

    const getCellColor = (value) => {
        if (value <= 0) return 'transparent';
        
        // Heatmap gradient: Blue (low) -> Green -> Yellow -> Red (high)
        const opacity = Math.min(0.1 + (value / 50), 0.85);
        
        if (value < 10) return `rgba(59, 130, 246, ${opacity})`;   // Blue
        if (value < 30) return `rgba(16, 185, 129, ${opacity})`;  // Green
        if (value < 60) return `rgba(245, 158, 11, ${opacity})`;  // Amber
        return `rgba(239, 68, 68, ${opacity})`;                   // Red
    };

    return (
        <div className="heatmap-overlay">
            <div className="heatmap-container">
                <div className="heatmap-header">
                    <div className="heatmap-title">
                        <h2>Spatial Activity Map</h2>
                        <p>{camera.name} — {camera.area}</p>
                    </div>
                    <button className="heatmap-close" onClick={onClose}>&times;</button>
                </div>

                <div className="heatmap-body">
                    {loading && !grid ? (
                        <div className="heatmap-status">Initializing intelligence engine...</div>
                    ) : error ? (
                        <div className="heatmap-status error">{error}</div>
                    ) : (
                        <div className="heatmap-canvas-wrapper">
                            <img 
                                src={cameraSnapshotUrl(camera.id) + "?t=" + Date.now()} 
                                alt="Reference" 
                                className="heatmap-bg"
                            />
                            <div className="heatmap-grid">
                                {grid && grid.map((row, y) => (
                                    row.map((val, x) => (
                                        <div 
                                            key={`${x}-${y}`} 
                                            className="heatmap-cell"
                                            style={{ 
                                                backgroundColor: getCellColor(val),
                                                boxShadow: val > 20 ? `0 0 15px ${getCellColor(val)}` : 'none'
                                            }}
                                            title={`Activity: ${Math.round(val)}`}
                                        />
                                    ))
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                <div className="heatmap-footer">
                    <div className="heatmap-legend">
                        <span>Low Activity</span>
                        <div className="legend-gradient"></div>
                        <span>High Traffic</span>
                    </div>
                    <div className="heatmap-hint">
                        Updated in real-time. Showing cumulative traffic patterns with 5-minute decay.
                    </div>
                </div>
            </div>
        </div>
    );
}

export default SpatialHeatmap;

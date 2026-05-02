import React, { useState, useEffect, useCallback } from 'react';
import { fetchCameras, addCamera, deleteCamera, updateCamera, fetchAreas, fetchAreaAlerts, cameraFeedUrl, setAreaLimit, fetchAreaStatus } from '../api';
import CameraFeed from './CameraFeed';
import SpatialHeatmap from './SpatialHeatmap';
import './CameraManager.css';

function CameraManager({ onClose }) {
    const [cameras, setCameras] = useState([]);
    const [areas, setAreas] = useState({});
    const [alerts, setAlerts] = useState([]);
    const [tab, setTab] = useState('cameras'); // 'cameras' | 'areas' | 'alerts'
    const [showAddForm, setShowAddForm] = useState(false);
    const [newName, setNewName] = useState('');
    const [newUrl, setNewUrl] = useState('');
    const [newArea, setNewArea] = useState('');
    const [newPlant, setNewPlant] = useState('');
    const [loading, setLoading] = useState(false);
    const [selectedFeed, setSelectedFeed] = useState(null);
    const [editingId, setEditingId] = useState(null);
    const [editName, setEditName] = useState('');
    const [editUrl, setEditUrl] = useState('');
    const [editArea, setEditArea] = useState('');
    const [editPlant, setEditPlant] = useState('');
    const [areaLimits, setAreaLimits] = useState({});
    const [savingLimit, setSavingLimit] = useState(null); // area name being saved
    const [activeHeatmap, setActiveHeatmap] = useState(null);
    const [error, setError] = useState(null);

    const loadData = useCallback(async () => {
        try {
            const [cams, areaData, alertData, statusData] = await Promise.all([
                fetchCameras(), fetchAreas(), fetchAreaAlerts(), fetchAreaStatus()
            ]);
            setCameras(cams);
            setAreas(areaData);
            setAlerts(alertData);
            
            // Map limits from statusData
            const limits = {};
            Object.entries(statusData).forEach(([area, info]) => {
                limits[area] = info.people_limit;
            });
            setAreaLimits(limits);
        } catch (e) {
            console.error('Camera data load error:', e);
        }
    }, []);

    useEffect(() => {
        loadData();
        const id = setInterval(loadData, 5000);
        return () => clearInterval(id);
    }, [loadData]);

    const handleAdd = async (e) => {
        e.preventDefault();
        if (!newName.trim() || !newUrl.trim()) return;
        setLoading(true);
        try {
            const result = await addCamera(newName.trim(), newUrl.trim(), newArea.trim() || 'default', newPlant.trim() || 'Plant 1');
            if (result.warning) {
                alert(result.warning);
            }
            setNewName('');
            setNewUrl('');
            setNewArea('');
            setNewPlant('');
            setShowAddForm(false);
            setError(null);
            await loadData();
        } catch (e) {
            console.error('Add camera error:', e);
            setError(e.message || 'Failed to add camera');
        }
        setLoading(false);
    };

    const handleDelete = async (id) => {
        if (!confirm('Remove this camera?')) return;
        try {
            await deleteCamera(id);
            await loadData();
        } catch (e) {
            console.error('Delete camera error:', e);
        }
    };

    const handleEdit = (cam) => {
        setEditingId(cam.id);
        setEditName(cam.name);
        setEditUrl(cam.url);
        setEditArea(cam.area);
        setEditPlant(cam.plant);
    };

    const handleSaveEdit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await updateCamera(editingId, {
                name: editName.trim(),
                url: editUrl.trim(),
                area: editArea.trim(),
                plant: editPlant.trim()
            });
            setEditingId(null);
            await loadData();
        } catch (e) {
            console.error('Update camera error:', e);
        }
        setLoading(false);
    };

    const handleSaveLimit = async (area) => {
        const limit = areaLimits[area];
        setSavingLimit(area);
        try {
            await setAreaLimit(area, limit);
            await loadData();
        } catch (e) {
            console.error('Save limit error:', e);
        }
        setSavingLimit(null);
    };

    const handleLimitChange = (area, val) => {
        setAreaLimits(prev => ({ ...prev, [area]: parseInt(val) || 0 }));
    };

    return (
        <div className="cm-overlay" onClick={onClose}>
            <div className="cm-modal" onClick={e => e.stopPropagation()}>
                {/* HEADER */}
                <div className="cm-header">
                    <h2>📹 Camera Management</h2>
                    <button className="cm-close-btn" onClick={onClose}>✕</button>
                </div>

                {/* TABS */}
                <div className="cm-tabs">
                    <button className={`cm-tab ${tab === 'cameras' ? 'active' : ''}`} onClick={() => setTab('cameras')}>
                        Cameras ({cameras.length})
                    </button>
                    <button className={`cm-tab ${tab === 'areas' ? 'active' : ''}`} onClick={() => setTab('areas')}>
                        Areas ({Object.keys(areas).length})
                    </button>
                    <button className={`cm-tab ${tab === 'alerts' ? 'active' : ''}`} onClick={() => setTab('alerts')}>
                        Alerts ({alerts.length})
                    </button>
                </div>

                {/* CONTENT */}
                <div className="cm-content">
                    {tab === 'cameras' && (
                        <>
                            <button className="cm-add-btn" onClick={() => setShowAddForm(!showAddForm)}>
                                {showAddForm ? '✕ Cancel' : '+ Add Camera'}
                            </button>

                            {showAddForm && (
                                <form className="cm-form" onSubmit={handleAdd}>
                                    <div className="cm-form-row">
                                        <label>Camera Name</label>
                                        <input
                                            type="text" placeholder="e.g. Entrance Cam"
                                            value={newName} onChange={e => setNewName(e.target.value)}
                                            required autoFocus
                                        />
                                    </div>
                                    <div className="cm-form-row">
                                        <label>RTSP URL</label>
                                        <input
                                            type="text" placeholder="rtsp://admin:password@10.0.0.1:554/..."
                                            value={newUrl} onChange={e => setNewUrl(e.target.value)}
                                            required
                                        />
                                    </div>
                                    <div className="cm-form-row">
                                        <label>Plant Name</label>
                                        <input
                                            type="text" placeholder="e.g. Solar Plant"
                                            value={newPlant} onChange={e => setNewPlant(e.target.value)}
                                        />
                                    </div>
                                    <div className="cm-form-row">
                                        <label>Area Name</label>
                                        <input
                                            type="text" placeholder="e.g. Main Gate"
                                            value={newArea} onChange={e => setNewArea(e.target.value)}
                                        />
                                    </div>
                                    {error && <div className="cm-error-msg">❌ {error}</div>}
                                    <button type="submit" className="cm-submit-btn" disabled={loading}>
                                        {loading ? 'Adding...' : '🚀 Add & Start'}
                                    </button>
                                </form>
                            )}

                            {/* CAMERA LIST */}
                            <div className="cm-list">
                                {cameras.length === 0 && (
                                    <div className="cm-empty">No cameras added yet. Click "+ Add Camera" to get started.</div>
                                )}
                                {cameras.map(cam => (
                                    <div key={cam.id} className={`cm-card ${cam.is_connected ? '' : 'disconnected'} ${editingId === cam.id ? 'editing' : ''}`}>
                                        {editingId === cam.id ? (
                                            <form className="cm-edit-form" onSubmit={handleSaveEdit}>
                                                <div className="cm-form-row">
                                                    <label>Camera Name</label>
                                                    <input value={editName} onChange={e => setEditName(e.target.value)} required />
                                                </div>
                                                <div className="cm-form-row">
                                                    <label>URL</label>
                                                    <input value={editUrl} onChange={e => setEditUrl(e.target.value)} required />
                                                </div>
                                                <div className="cm-form-row">
                                                    <label>Plant</label>
                                                    <input value={editPlant} onChange={e => setEditPlant(e.target.value)} />
                                                </div>
                                                <div className="cm-form-row">
                                                    <label>Area</label>
                                                    <input value={editArea} onChange={e => setEditArea(e.target.value)} />
                                                </div>
                                                <div className="cm-edit-actions">
                                                    <button type="submit" className="cm-save-btn" disabled={loading}>💾 Save</button>
                                                    <button type="button" className="cm-cancel-btn" onClick={() => setEditingId(null)}>✕ Cancel</button>
                                                </div>
                                            </form>
                                        ) : (
                                            <>
                                                <div className="cm-card-header">
                                                    <div className="cm-card-title">
                                                        <span className={`cm-dot ${cam.is_connected ? 'green' : 'red'}`} />
                                                        <strong>{cam.name}</strong>
                                                    </div>
                                                    <div className="cm-card-actions">
                                                        <button className="cm-edit-btn" onClick={() => handleEdit(cam)} title="Edit">✏️</button>
                                                        <button className="cm-view-btn" onClick={() => setSelectedFeed(selectedFeed === cam.id ? null : cam.id)} title="View Feed">
                                                            {selectedFeed === cam.id ? '🔽' : '👁️'}
                                                        </button>
                                                        <button className="cm-view-btn cm-fire-btn" onClick={() => setActiveHeatmap(cam)} title="Strategic Heatmap">
                                                            🔥
                                                        </button>
                                                        <button className="cm-del-btn" onClick={() => handleDelete(cam.id)} title="Remove">🗑️</button>
                                                    </div>
                                                </div>
                                                <div className="cm-card-meta">
                                                    <span className="cm-area-tag">{cam.plant} | {cam.area}</span>
                                                    <div className="cm-card-stats">
                                                        <div className="cm-card-stat">
                                                            <span className="cm-card-stat-label">Detecting</span>
                                                            <span className="cm-card-stat-value">{cam.people_count || 0}</span>
                                                        </div>
                                                        <div className="cm-card-stat">
                                                            <span className="cm-card-stat-label">Throughput</span>
                                                            <span className="cm-card-stat-value">{(cam.in || 0) + (cam.out || 0)}</span>
                                                        </div>
                                                        <div className="cm-card-stat">
                                                            <span className="cm-card-stat-label">Performance</span>
                                                            <span className="cm-card-stat-value">{cam.fps || 0} FPS</span>
                                                        </div>
                                                    </div>
                                                </div>
                                                {cam.last_error && (
                                                    <div className="cm-card-error">⚠️ {cam.last_error}</div>
                                                )}
                                                {selectedFeed === cam.id && (
                                                    <div className="cm-feed-container">
                                                        <CameraFeed cameraId={cam.id} alt={cam.name} className="cm-feed" />
                                                    </div>
                                                )}
                                            </>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </>
                    )}

                    {tab === 'areas' && (
                        <div className="cm-areas">
                            {Object.keys(areas).length === 0 && (
                                <div className="cm-empty">No areas detected. Add cameras with area names to see aggregated stats.</div>
                            )}
                            {Object.entries(areas).map(([area, data]) => (
                                <div key={area} className="cm-area-card">
                                    <div className="cm-area-name">{area}</div>
                                    <div className="cm-area-stats">
                                        <div className="cm-area-stat">
                                            <span className="cm-stat-value">{data.people_count}</span>
                                            <span className="cm-stat-label">People</span>
                                        </div>
                                        <div className="cm-area-stat">
                                            <span className="cm-stat-value">{data.cameras}</span>
                                            <span className="cm-stat-label">Cameras</span>
                                        </div>
                                    </div>
                                    
                                    <div className="cm-area-limit-section">
                                        <label>Capacity Limit</label>
                                        <div className="cm-limit-row">
                                            <input 
                                                type="number" 
                                                min="0"
                                                value={areaLimits[area] ?? 0} 
                                                onChange={e => handleLimitChange(area, e.target.value)}
                                            />
                                            <button 
                                                className="cm-limit-save" 
                                                onClick={() => handleSaveLimit(area)}
                                                disabled={savingLimit === area}
                                            >
                                                {savingLimit === area ? '...' : 'Set'}
                                            </button>
                                        </div>
                                        <p className="cm-limit-hint">Alerts trigger when {areaLimits[area] || 'X'} people are detected.</p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {tab === 'alerts' && (
                        <div className="cm-alerts">
                            {alerts.length === 0 && (
                                <div className="cm-empty">No alerts yet. You'll see alerts here when people count drops for 45+ minutes.</div>
                            )}
                            {alerts.map((alert, i) => (
                                <div key={i} className="cm-alert-card">
                                    <div className="cm-alert-header">
                                        <span className="cm-alert-type">⚠️ {alert.type}</span>
                                        <span className="cm-alert-time">{new Date(alert.timestamp).toLocaleTimeString()}</span>
                                    </div>
                                    <div className="cm-alert-msg">{alert.message}</div>
                                    <div className="cm-alert-detail">
                                        Peak: {alert.peak_count} → Current: {alert.current_count} | Duration: {alert.duration_minutes}min
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {activeHeatmap && (
                <SpatialHeatmap 
                    camera={activeHeatmap} 
                    onClose={() => setActiveHeatmap(null)} 
                />
            )}
        </div>
    );
}

export default CameraManager;

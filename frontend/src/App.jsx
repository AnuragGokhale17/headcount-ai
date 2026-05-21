import React, { useState, useEffect } from 'react'
import Header from './components/Header'
import AISidebar from './components/AISidebar'
import CameraManager from './components/CameraManager'
import CameraFeed from './components/CameraFeed'
import ZoneDrawer from './components/ZoneDrawer'
import SpatialHeatmap from './components/SpatialHeatmap'
import SpatialCalibrator from './components/SpatialCalibrator'
import { fetchStats, fetchAIInsights, fetchAIEvents, fetchCameras, fetchBuildingTotal, fetchPlants, deleteCamera, restartCamera, resetStats } from './api'
import './App.css'

function App() {
    const [stats, setStats] = useState({ in: 0, out: 0, occupancy: 0, fps: 0 });
    const [plantStats, setPlantStats] = useState({});
    const [insights, setInsights] = useState(null);
    const [events, setEvents] = useState([]);
    const [cameras, setCameras] = useState([]);
    const [showCameraManager, setShowCameraManager] = useState(false);
    const [showAI, setShowAI] = useState(false);
    const [configZoneCameraId, setConfigZoneCameraId] = useState(null);
    const [configCalibrationCameraId, setConfigCalibrationCameraId] = useState(null);
    const [heatmapCamera, setHeatmapCamera] = useState(null);

    const [isDemoMode, setIsDemoMode] = useState(false);

    useEffect(() => {
        const poll = async () => {
            if (isDemoMode) {
                // System metadata only
                setInsights({
                    system_status: 'DEMO MODE',
                    uptime: '1h 22m',
                    gpu_util: '45%'
                });
                return;
            }
            try {
                const [s, ai, plants] = await Promise.all([fetchStats(), fetchAIInsights(), fetchPlants()]);
                setStats(s);
                setInsights(ai);
                setPlantStats(plants || {});
            } catch (e) { 
                setInsights(prev => ({ ...prev, system_status: 'OFFLINE' }));
            }
        };
        poll();
        const id = setInterval(poll, 2000);
        return () => clearInterval(id);
    }, [isDemoMode]);

    useEffect(() => {
        const poll = async () => {
            if (isDemoMode) {
                setCameras([
                    { id: 'cam1', name: 'Main Lobby', plant: 'Plant A', area: 'Entrance', people_count: 3, total_detected: 142 },
                    { id: 'cam2', name: 'Back Loading Dock', plant: 'Plant A', area: 'Logistics', people_count: 1, total_detected: 89 },
                    { id: 'cam3', name: 'Production Line 4', plant: 'Plant B', area: 'Assembly', people_count: 8, total_detected: 1024 }
                ]);
                return;
            }
            try {
                const [cams, evs] = await Promise.all([
                    fetchCameras(), fetchAIEvents()
                ]);
                setCameras(cams);
                setEvents(evs);
            } catch (e) { }
        };
        poll();
        const id = setInterval(poll, 5000);
        return () => clearInterval(id);
    }, [isDemoMode]);

    const handleDeleteCamera = async (camId) => {
        if (isDemoMode) return alert('Cannot delete cameras in Demo Mode');
        if (!confirm('Remove this camera?')) return;
        try {
            await deleteCamera(camId);
            setCameras(prev => prev.filter(c => c.id !== camId));
        } catch (e) { }
    };

    const handleRestartCamera = async (camId) => {
        if (isDemoMode) return alert('Cannot restart in Demo Mode');
        try {
            const res = await restartCamera(camId);
            if (res.error) alert(res.error);
            else alert('Camera restart signal sent');
        } catch (e) { 
            alert('Failed to connect to backend for restart');
        }
    };

    const handleResetStats = async () => {
        if (isDemoMode) return setStats({ in: 0, out: 0, occupancy: 0, fps: 0 });
        if (!confirm('Reset all analytics counts?')) return;
        try {
            await resetStats();
            setStats(prev => ({ ...prev, in: 0, out: 0, occupancy: 0 }));
        } catch (e) { }
    };

    const handleDemoCount = (type) => {
        setStats(prev => ({
            ...prev,
            in: type === 'in' ? prev.in + 1 : prev.in,
            out: type === 'out' ? prev.out + 1 : prev.out,
            occupancy: type === 'in' ? prev.occupancy + 1 : (type === 'out' ? Math.max(0, prev.occupancy - 1) : prev.occupancy)
        }));
    };

    return (
        <>
            <div className="bg-blob blob-1"></div>
            <div className="bg-blob blob-2"></div>

            <Header
                status={isDemoMode ? 'DEMO' : (insights?.system_status || 'NORMAL')}
                onManageCameras={() => setShowCameraManager(true)}
                onResetStats={handleResetStats}
                onToggleAI={() => setShowAI(!showAI)}
                showAI={showAI}
                isDemoMode={isDemoMode}
                onToggleDemo={() => {
                    setIsDemoMode(!isDemoMode);
                    if (!isDemoMode) setStats({ in: 0, out: 0, occupancy: 0, fps: 29.5 });
                }}
            />

            <div className="dashboard-container">
                <div className="main-content">
                    <div className="kpi-section">
                        {/* Dynamic Plant-based Occupancy */}
                        {Object.entries(plantStats).map(([plantName, data], idx) => (
                            <div key={plantName} className={`bento-card kpi-card ${idx === 0 ? 'primary' : ''}`}>
                                <span className="kpi-label">{plantName} Occupancy</span>
                                <div className="kpi-value text-gradient">
                                    {data.people_count} <span className="kpi-unit">people</span>
                                </div>
                            </div>
                        ))}
                        
                        {/* Fallback if no plants data yet or Demo mode */}
                        {(Object.keys(plantStats).length === 0 || isDemoMode) && (
                            <div className="bento-card kpi-card primary">
                                <span className="kpi-label">Active Occupancy</span>
                                <div className="kpi-value text-gradient">
                                    {stats.occupancy} <span className="kpi-unit">{isDemoMode ? 'simulated' : 'detecting...'}</span>
                                </div>
                            </div>
                        )}

                        <div className="bento-card kpi-card">
                            <span className="kpi-label">Total Entries</span>
                            <div className="kpi-value" style={{ color: 'var(--accent)' }}>
                                {stats.in}
                            </div>
                        </div>
                        <div className="bento-card kpi-card">
                            <span className="kpi-label">Total Exits</span>
                            <div className="kpi-value" style={{ color: 'var(--secondary)' }}>
                                {stats.out}
                            </div>
                        </div>
                    </div>

                    <div className="camera-section">
                        {cameras.map((cam, index) => (
                            <div key={cam.id} className="camera-tile bento-card">
                                <div className="tile-feed-container">
                                    <CameraFeed 
                                        cameraId={cam.id} 
                                        className="tile-feed" 
                                        alt={cam.name} 
                                        index={index}
                                        total={cameras.length}
                                        isDemoMode={isDemoMode}
                                        onDemoCount={handleDemoCount}
                                    />
                                    <div className="tile-overlay-top">
                                        <div className="live-indicator">
                                            <span className={`live-dot ${isDemoMode ? 'demo' : ''}`} />
                                            {isDemoMode ? 'DEMO FEED' : 'LIVE'}
                                        </div>
                                        <div className="tile-info-badge">
                                            {isDemoMode ? (
                                                <>
                                                    <span className="badge-primary">{stats.occupancy > 0 ? Math.floor(stats.occupancy / cameras.length) + (index === 0 ? stats.occupancy % cameras.length : 0) : 0} IN ZONE</span>
                                                </>
                                            ) : (
                                                <>
                                                    <span className="badge-primary">{cam.people_count || 0} IN ZONE</span>
                                                    {cam.total_detected > 0 && (
                                                        <span className="badge-secondary">{cam.total_detected} TOTAL</span>
                                                    )}
                                                </>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                <div className="tile-footer">
                                    <div>
                                        <span className="tile-name">{cam.name}</span>
                                        <span className="tile-meta">{cam.plant} • {cam.area}</span>
                                    </div>
                                    <div className="tile-actions">
                                        <button className="action-btn" title="Restart AI Engine" onClick={() => handleRestartCamera(cam.id)}>
                                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.5 2v6h-6M2.5 22v-6h6M2 12c0-4.4 3.6-8 8-8 3.3 0 6.2 2 7.4 5M22 12c0 4.4-3.6 8-8 8-3.3 0-6.2-2-7.4-5"/></svg>
                                        </button>
                                        <button className="action-btn" title="Zones" onClick={() => setConfigZoneCameraId(cam.id)}>
                                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>
                                        </button>
                                        <button className="action-btn" title="Spatial Calibration" onClick={() => setConfigCalibrationCameraId(cam.id)}>
                                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>
                                        </button>
                                        <button className="action-btn" title="Spatial Heatmap" onClick={() => setHeatmapCamera(cam)}>
                                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2v10m0 0l-3-3m3 3l3-3"/><path d="M2 12h20"/><path d="M20 12v8a2 2 0 01-2 2H6a2 2 0 01-2-2v-8"/></svg>
                                        </button>
                                        <button className="action-btn danger" title="Delete" onClick={() => handleDeleteCamera(cam.id)}>
                                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 6h18m-2 0v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6m3 0V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2m-6 9 2 2 4-4"/></svg>
                                        </button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>

                {showAI && (
                    <AISidebar stats={stats} insights={insights} events={events} cameras={cameras} plantStats={plantStats} />
                )}
            </div>

            {showCameraManager && <CameraManager onClose={() => setShowCameraManager(false)} />}
            {configZoneCameraId !== null && (
                <ZoneDrawer
                    cameraId={configZoneCameraId}
                    onClose={() => setConfigZoneCameraId(null)}
                    onSaved={() => setConfigZoneCameraId(null)}
                />
            )}
            {configCalibrationCameraId !== null && (
                <SpatialCalibrator
                    cameraId={configCalibrationCameraId}
                    onClose={() => setConfigCalibrationCameraId(null)}
                    onSaved={() => setConfigCalibrationCameraId(null)}
                />
            )}
            {heatmapCamera && (
                <SpatialHeatmap 
                    camera={heatmapCamera} 
                    onClose={() => setHeatmapCamera(null)} 
                    />
            )}
        </>
    );
}

export default App;

import React, { useState, useEffect, useCallback } from 'react'
import Header from './components/Header'
import AISidebar from './components/AISidebar'
import CameraManager from './components/CameraManager'
import CameraFeed from './components/CameraFeed'
import ZoneDrawer from './components/ZoneDrawer'
import { fetchStats, resetStats, fetchAIInsights, fetchAIEvents, fetchCameras, fetchAreaAlerts, fetchBuildingTotal, fetchAreas, fetchPlants, deleteCamera, cameraFeedUrl, VIDEO_FEED_URL } from './api'
import './App.css'

function App() {
    const [stats, setStats] = useState({ in: 0, out: 0, occupancy: 0, fps: 0 });
    const [plantStats, setPlantStats] = useState({});
    const [buildingTotal, setBuildingTotal] = useState(0);
    const [insights, setInsights] = useState(null);
    const [events, setEvents] = useState([]);
    const [cameras, setCameras] = useState([]);
    const [areaStats, setAreaStats] = useState({});
    const [alerts, setAlerts] = useState([]);
    const [showCameraManager, setShowCameraManager] = useState(false);
    const [showAI, setShowAI] = useState(false);
    const [configZoneCameraId, setConfigZoneCameraId] = useState(null); // null = closed, 0 = primary, else = camera ID
    const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark');

    // Apply theme
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
    }, [theme]);

    // Poll stats + insights + plants
    useEffect(() => {
        const poll = async () => {
            try {
                const [s, ai, plants] = await Promise.all([fetchStats(), fetchAIInsights(), fetchPlants()]);
                setStats(s);
                setInsights(ai);
                setPlantStats(plants || {});
            } catch (e) { console.error('Stats poll error:', e); }
        };
        poll();
        const id = setInterval(poll, 300);
        return () => clearInterval(id);
    }, []);

    // Poll events
    useEffect(() => {
        const poll = async () => {
            try { setEvents(await fetchAIEvents()); } catch (e) { }
        };
        poll();
        const id = setInterval(poll, 3000);
        return () => clearInterval(id);
    }, []);

    // Poll cameras + alerts + building total
    useEffect(() => {
        const poll = async () => {
            try {
                const [cams, alertData, btData] = await Promise.all([
                    fetchCameras(), fetchAreaAlerts(), fetchBuildingTotal()
                ]);
                setCameras(cams);
                setAlerts(alertData);
                setBuildingTotal(btData?.total || 0);
            } catch (e) { }
        };
        poll();
        const id = setInterval(poll, 5000);
        return () => clearInterval(id);
    }, []);

    const handleDeleteCamera = async (camId) => {
        if (!confirm('Remove this camera?')) return;
        try {
            await deleteCamera(camId);
            setCameras(prev => prev.filter(c => c.id !== camId));
        } catch (e) { }
    };

    const handleResetStats = async () => {
        if (!confirm('Are you sure you want to clear the entry/exit counts?')) return;
        console.log('🧹 Resetting all counts...');
        try {
            await resetStats();
            setStats(prev => ({ ...prev, in: 0, out: 0, occupancy: 0 }));
        } catch (e) { console.error('Error resetting stats:', e); }
    };

    // Grid layout logic
    const visibleCameras = cameras.length;
    const gridClass = `camera-grid cams-${Math.min(visibleCameras, 6)}`;

    return (
        <>
            <Header
                status={insights?.system_status || 'NORMAL'}
                gpu={insights?.gpu}
                onManageCameras={() => setShowCameraManager(true)}
                onResetStats={handleResetStats}

                onToggleAI={() => setShowAI(!showAI)}
                showAI={showAI}
                theme={theme}
                onToggleTheme={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
            />

            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                <div className="main-content">
                    {/* Primary camera always shows */}
                    <div className={gridClass}>


                        {/* Dynamic cameras from database */}
                        {cameras.map(cam => (
                            <div key={cam.id} className="camera-tile">
                                <CameraFeed cameraId={cam.id} className="tile-feed" alt={cam.name} />
                                <div className="tile-overlay">
                                    <div className="tile-left">
                                        <span className="tile-tag rec">● REC</span>
                                        <span className="tile-tag">{cam.name}</span>
                                        {cam.plant && <span className="tile-tag plant">{cam.plant}</span>}
                                        {cam.area && <span className="tile-tag area">{cam.area}</span>}
                                    </div>
                                    <span className="tile-badge">{cam.people_count || 0} people</span>
                                </div>
                                <div className="tile-footer">
                                    <div className="tile-info">
                                        <div className="tile-status">
                                            <span className={`tile-dot ${cam.is_connected ? 'green' : 'red'}`} />
                                            <span style={{ color: cam.is_connected ? 'var(--success)' : 'var(--danger)', fontSize: '0.65rem' }}>
                                                {cam.is_connected ? 'Connected' : 'Offline'}
                                            </span>
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', gap: '6px' }}>
                                        <button className="tile-del" onClick={() => setConfigZoneCameraId(cam.id)} title="Configure Zones">⚙️</button>
                                        <button className="tile-del" onClick={() => handleDeleteCamera(cam.id)} title="Remove">🗑️</button>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Compact Stats Strip */}
                    <div className="stats-strip">
                        {Object.entries(plantStats).map(([plant, data]) => (
                            <div key={plant} className="strip-stat">
                                <div className="strip-val" style={{ color: 'var(--accent)' }}>{data.people_count}</div>
                                <div className="strip-meta">
                                    <span className="strip-label">{plant}</span>
                                    <span className="strip-sub">People Right Now</span>
                                </div>
                            </div>
                        ))}

                        <div className="strip-stat">
                            <div className="strip-val" style={{ color: 'var(--success)' }}>{stats.in}</div>
                            <div className="strip-meta">
                                <span className="strip-label">Total In</span>
                                <span className="strip-sub">Entries</span>
                            </div>
                        </div>
                        <div className="strip-stat">
                            <div className="strip-val" style={{ color: 'var(--danger)' }}>{stats.out}</div>
                            <div className="strip-meta">
                                <span className="strip-label">Total Out</span>
                                <span className="strip-sub">Exits</span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* AI Sidebar / Nerve Center — toggleable */}
                {showAI && (
                    <AISidebar stats={stats} insights={insights} events={events} cameras={cameras} alerts={alerts} />
                )}
            </div>

            {showCameraManager && (
                <CameraManager onClose={() => setShowCameraManager(false)} />
            )}
            {configZoneCameraId !== null && (
                <ZoneDrawer
                    cameraId={configZoneCameraId === 0 ? null : configZoneCameraId}
                    onClose={() => setConfigZoneCameraId(null)}
                    onSaved={() => setConfigZoneCameraId(null)}
                />
            )}
        </>
    );
}

export default App;

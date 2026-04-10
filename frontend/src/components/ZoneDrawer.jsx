import React, { useState, useRef, useEffect, useCallback } from 'react';
import { fetchCameraZones, saveCameraZones, cameraSnapshotUrl, SNAPSHOT_URL } from '../api';
import './ZoneDrawer.css';

function ZoneDrawer({ cameraId, onClose, onSaved }) {
    const canvasRef = useRef(null);
    const imgRef = useRef(null);
    const [imgLoaded, setImgLoaded] = useState(false);
    const [activeZone, setActiveZone] = useState('A'); // 'A' or 'B'
    const [zoneA, setZoneA] = useState([]);
    const [zoneB, setZoneB] = useState([]);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState('');
    const [imgSize, setImgSize] = useState({ w: 0, h: 0 });

    // Load existing zones
    useEffect(() => {
        if (cameraId) {
            fetchCameraZones(cameraId).then(data => {
                if (data.zone_a) setZoneA(data.zone_a);
                if (data.zone_b) setZoneB(data.zone_b);
            }).catch(() => { });
        }
    }, [cameraId]);

    // Handle image load
    const handleImgLoad = useCallback(() => {
        const img = imgRef.current;
        if (img) {
            setImgSize({ w: img.naturalWidth, h: img.naturalHeight });
            setImgLoaded(true);
        }
    }, []);

    // Draw on canvas
    useEffect(() => {
        if (!imgLoaded || !canvasRef.current || !imgRef.current) return;

        const canvas = canvasRef.current;
        const img = imgRef.current;
        const ctx = canvas.getContext('2d');

        // Match canvas to displayed size
        const rect = img.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const scaleX = rect.width / imgSize.w;
        const scaleY = rect.height / imgSize.h;

        // Draw Zone A (red)
        drawPolygon(ctx, zoneA, scaleX, scaleY, 'rgba(255, 82, 82, 0.3)', '#FF5252', activeZone === 'A');
        // Draw Zone B (green)
        drawPolygon(ctx, zoneB, scaleX, scaleY, 'rgba(0, 230, 118, 0.3)', '#00E676', activeZone === 'B');

    }, [zoneA, zoneB, activeZone, imgLoaded, imgSize]);

    function drawPolygon(ctx, points, scaleX, scaleY, fill, stroke, isActive) {
        if (points.length === 0) return;

        const scaled = points.map(p => [p[0] * scaleX, p[1] * scaleY]);

        // Fill
        ctx.beginPath();
        ctx.moveTo(scaled[0][0], scaled[0][1]);
        for (let i = 1; i < scaled.length; i++) {
            ctx.lineTo(scaled[i][0], scaled[i][1]);
        }
        ctx.closePath();
        ctx.fillStyle = fill;
        ctx.fill();

        // Stroke
        ctx.strokeStyle = stroke;
        ctx.lineWidth = isActive ? 2.5 : 1.5;
        ctx.stroke();

        // Vertices
        scaled.forEach((p, i) => {
            ctx.beginPath();
            ctx.arc(p[0], p[1], isActive ? 5 : 3, 0, Math.PI * 2);
            ctx.fillStyle = stroke;
            ctx.fill();

            if (isActive) {
                ctx.fillStyle = '#fff';
                ctx.font = '10px Inter';
                ctx.fillText(i + 1, p[0] + 8, p[1] - 4);
            }
        });
    }

    // Handle click on canvas
    const handleCanvasClick = (e) => {
        const canvas = canvasRef.current;
        const img = imgRef.current;
        if (!canvas || !img) return;

        const rect = img.getBoundingClientRect();
        const scaleX = imgSize.w / rect.width;
        const scaleY = imgSize.h / rect.height;

        const x = Math.round((e.clientX - rect.left) * scaleX);
        const y = Math.round((e.clientY - rect.top) * scaleY);

        if (activeZone === 'A') {
            setZoneA(prev => [...prev, [x, y]]);
        } else {
            setZoneB(prev => [...prev, [x, y]]);
        }
    };

    // Undo last point
    const undo = () => {
        if (activeZone === 'A') {
            setZoneA(prev => prev.slice(0, -1));
        } else {
            setZoneB(prev => prev.slice(0, -1));
        }
    };

    // Clear active zone
    const clearActive = () => {
        if (activeZone === 'A') setZoneA([]);
        else setZoneB([]);
    };

    // Save
    const handleSave = async () => {
        if (zoneA.length < 3 || zoneB.length < 3) {
            setMessage('⚠️ Each zone needs at least 3 points.');
            return;
        }
        setSaving(true);
        setMessage('');
        try {
            if (cameraId) {
                const res = await saveCameraZones(cameraId, zoneA, zoneB);
                if (res.success) {
                    setMessage('✅ Zones saved! Camera will reload.');
                    setTimeout(() => onSaved(), 1500);
                } else {
                    setMessage('❌ ' + (res.error || 'Save failed'));
                }
            } else {
                setMessage('❌ No camera selected');
            }
        } catch (e) {
            setMessage('❌ Network error');
        }
        setSaving(false);
    };

    // Refresh snapshot
    const getShotUrl = () => cameraId ? cameraSnapshotUrl(cameraId) : SNAPSHOT_URL;
    const [snapshotUrl, setSnapshotUrl] = useState(getShotUrl() + '?t=' + Date.now());
    const refreshSnapshot = () => {
        setImgLoaded(false);
        setSnapshotUrl(getShotUrl() + '&t=' + Date.now());
    };

    return (
        <div className="zone-drawer-overlay" onClick={onClose}>
            <div className="zone-drawer-modal" onClick={e => e.stopPropagation()}>
                {/* Header */}
                <div className="zd-header">
                    <h2>⚙️ Zone Configuration</h2>
                    <button className="zd-close" onClick={onClose}>✕</button>
                </div>

                {/* Toolbar */}
                <div className="zd-toolbar">
                    <div className="zd-zone-tabs">
                        <button
                            className={`zd-tab ${activeZone === 'A' ? 'zd-tab-a-active' : ''}`}
                            onClick={() => setActiveZone('A')}
                        >
                            Zone A (Entry) · {zoneA.length} pts
                        </button>
                        <button
                            className={`zd-tab ${activeZone === 'B' ? 'zd-tab-b-active' : ''}`}
                            onClick={() => setActiveZone('B')}
                        >
                            Zone B (Inside) · {zoneB.length} pts
                        </button>
                    </div>
                    <div className="zd-actions">
                        <button className="zd-btn zd-btn-sm" onClick={undo}>↩ Undo</button>
                        <button className="zd-btn zd-btn-sm" onClick={clearActive}>🗑 Clear</button>
                        <button className="zd-btn zd-btn-sm" onClick={refreshSnapshot}>🔄 Refresh</button>
                    </div>
                </div>

                {/* Canvas */}
                <div className="zd-canvas-wrap">
                    <img
                        ref={imgRef}
                        src={snapshotUrl}
                        alt="Camera snapshot"
                        className="zd-snapshot"
                        onLoad={handleImgLoad}
                        crossOrigin="anonymous"
                    />
                    <canvas
                        ref={canvasRef}
                        className="zd-canvas"
                        onClick={handleCanvasClick}
                    />
                    {!imgLoaded && (
                        <div className="zd-loading">📷 Loading camera snapshot...</div>
                    )}
                </div>

                {/* Instructions */}
                <div className="zd-instructions">
                    Click on the image to add polygon vertices. Switch between Zone A (entry area, red) and Zone B (inside area, green).
                    Each zone needs at least 3 points.
                </div>

                {/* Footer */}
                <div className="zd-footer">
                    {message && <span className="zd-message">{message}</span>}
                    <div className="zd-footer-actions">
                        <button className="zd-btn" onClick={onClose}>Cancel</button>
                        <button className="zd-btn zd-btn-primary" onClick={handleSave} disabled={saving}>
                            {saving ? 'Saving...' : '💾 Save Zones'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default ZoneDrawer;

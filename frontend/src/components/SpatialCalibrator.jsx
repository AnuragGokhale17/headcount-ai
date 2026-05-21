import React, { useState, useRef, useEffect } from 'react';
import { cameraSnapshotUrl, calibrateCamera, importAmcCalibration } from '../api';
import './SpatialCalibrator.css';

const SpatialCalibrator = ({ cameraId, onClose, onSaved }) => {
    const [srcPoints, setSrcPoints] = useState([]);
    const [dstPoints, setDstPoints] = useState([
        [0, 0], [1000, 0], [1000, 1000], [0, 1000]
    ]);
    const [loading, setLoading] = useState(false);
    const [frameLoaded, setFrameLoaded] = useState(false);
    const [frameError, setFrameError] = useState(false);
    const imgRef = useRef(null);

    const [amcFile, setAmcFile] = useState(null);
    const [amcLoading, setAmcLoading] = useState(false);
    const fileInputRef = useRef(null);

    const handleFileChange = (e) => {
        if (e.target.files && e.target.files[0]) {
            setAmcFile(e.target.files[0]);
        }
    };

    const handleAmcUpload = async () => {
        if (!amcFile) return;
        setAmcLoading(true);
        try {
            const res = await importAmcCalibration(cameraId, amcFile);
            if (res.success) {
                alert('Successfully imported AutoMagicCalib matrix!');
                onSaved();
            } else {
                alert('Import failed: ' + (res.error || 'Unknown error'));
            }
        } catch (e) {
            alert('Upload error: ' + e.message);
        } finally {
            setAmcLoading(false);
        }
    };


    const handleImageClick = (e) => {
        if (srcPoints.length >= 4) return;

        const rect = imgRef.current.getBoundingClientRect();
        // Map relative click position to 1920x1080 coordinate space
        const x = ((e.clientX - rect.left) / rect.width) * 1920;
        const y = ((e.clientY - rect.top) / rect.height) * 1080;

        setSrcPoints([...srcPoints, [Math.round(x), Math.round(y)]]);
    };

    const handleCalibrate = async () => {
        if (srcPoints.length !== 4) return;

        setLoading(true);
        try {
            const res = await calibrateCamera(cameraId, srcPoints, dstPoints);
            if (res.success) {
                onSaved();
            } else {
                alert('Calibration failed: ' + (res.error || 'Unknown error'));
            }
        } catch (e) {
            alert('Connection error: ' + e.message);
        } finally {
            setLoading(false);
        }
    };

    // Frame polling for live preview during calibration
    const [frameSrc, setFrameSrc] = useState('');
    useEffect(() => {
        const updateFrame = () => {
            setFrameSrc(`${cameraSnapshotUrl(cameraId)}?t=${Date.now()}`);
        };
        updateFrame();
        const interval = setInterval(updateFrame, 5000); // Update snapshot every 5s
        return () => clearInterval(interval);
    }, [cameraId]);

    return (
        <div className="spatial-modal-overlay">
            <div className="spatial-modal-content">
                <div className="spatial-modal-header">
                    <h2>
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
                        Spatial Homography Calibration
                    </h2>
                    <button className="spatial-modal-close" onClick={onClose}>&times;</button>
                </div>

                <div className="spatial-modal-body">
                    <div className="spatial-cal-workspace">
                        <img 
                            ref={imgRef}
                            src={frameSrc}
                            alt="Camera Feed"
                            className={`spatial-cal-img ${!frameLoaded ? 'loading' : ''}`}
                            onClick={handleImageClick}
                            onLoad={() => setFrameLoaded(true)}
                            onError={() => setFrameError(true)}
                        />
                        
                        {!frameLoaded && (
                            <div className="loading-pulse">
                                <span>Establishing secure video link...</span>
                            </div>
                        )}

                        <div className="spatial-cal-overlay">
                            {srcPoints.map((p, i) => (
                                <div 
                                    key={i} 
                                    className="spatial-marker"
                                    style={{ left: `${(p[0] / 1920) * 100}%`, top: `${(p[1] / 1080) * 100}%` }}
                                >
                                    {i + 1}
                                </div>
                            ))}
                            
                            {/* Draw connecting lines */}
                            {srcPoints.length > 1 && (
                                <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
                                    {srcPoints.map((p, i) => {
                                        if (i === 0) return null;
                                        const prev = srcPoints[i-1];
                                        return (
                                            <line 
                                                key={i}
                                                x1={`${(prev[0] / 1920) * 100}%`} y1={`${(prev[1] / 1080) * 100}%`}
                                                x2={`${(p[0] / 1920) * 100}%`} y2={`${(p[1] / 1080) * 100}%`}
                                                stroke="var(--primary)" strokeWidth="3" strokeDasharray="6,4"
                                            />
                                        );
                                    })}
                                    {srcPoints.length === 4 && (
                                        <line 
                                            x1={`${(srcPoints[3][0] / 1920) * 100}%`} y1={`${(srcPoints[3][1] / 1080) * 100}%`}
                                            x2={`${(srcPoints[0][0] / 1920) * 100}%`} y2={`${(srcPoints[0][1] / 1080) * 100}%`}
                                            stroke="var(--primary)" strokeWidth="3" strokeDasharray="6,4"
                                        />
                                    )}
                                </svg>
                            )}
                        </div>
                    </div>

                    <div className="spatial-sidebar">
                        <div className="instruction-card">
                            <h4>
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
                                Setup Instructions
                            </h4>
                            <ul className="instruction-list">
                                <li className={`instruction-item ${srcPoints.length === 0 ? 'active' : ''}`}>
                                    <div className="step-number">1</div>
                                    <span>Top-Left Corner</span>
                                </li>
                                <li className={`instruction-item ${srcPoints.length === 1 ? 'active' : ''}`}>
                                    <div className="step-number">2</div>
                                    <span>Top-Right Corner</span>
                                </li>
                                <li className={`instruction-item ${srcPoints.length === 2 ? 'active' : ''}`}>
                                    <div className="step-number">3</div>
                                    <span>Bottom-Right Corner</span>
                                </li>
                                <li className={`instruction-item ${srcPoints.length === 3 ? 'active' : ''}`}>
                                    <div className="step-number">4</div>
                                    <span>Bottom-Left Corner</span>
                                </li>
                            </ul>
                        </div>

                        <div className="amc-card">
                            <h4>
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
                                AutoMagicCalib Import
                            </h4>
                            <p className="amc-description">
                                Upload a camera calibration YAML file generated by the NVIDIA AMC tool.
                            </p>
                            <div className="amc-upload-zone" onClick={() => fileInputRef.current.click()}>
                                <input 
                                    type="file" 
                                    ref={fileInputRef} 
                                    onChange={handleFileChange} 
                                    accept=".yml,.yaml" 
                                    style={{ display: 'none' }}
                                />
                                {amcFile ? (
                                    <span className="amc-file-name">{amcFile.name}</span>
                                ) : (
                                    <span className="amc-upload-placeholder">Choose AMC YAML File</span>
                                )}
                            </div>
                            {amcFile && (
                                <button 
                                    className="btn-primary amc-upload-btn" 
                                    onClick={handleAmcUpload}
                                    disabled={amcLoading}
                                >
                                    {amcLoading ? 'Processing...' : 'Apply AMC Matrix'}
                                </button>
                            )}
                        </div>

                        <div className="points-list">
                            {srcPoints.map((p, i) => (
                                <div key={i} className="point-row filled">
                                    <span>Point #{i+1}</span>
                                    <span className="point-coord">{p[0]}, {p[1]}</span>
                                </div>
                            ))}
                            {Array.from({ length: 4 - srcPoints.length }).map((_, i) => (
                                <div key={i} className="point-row">
                                    <span style={{ color: 'var(--text-muted)' }}>Pending...</span>
                                </div>
                            ))}
                        </div>

                        <div className="spatial-actions">
                            <button className="btn-secondary" onClick={() => setSrcPoints([])}>
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
                                Reset Points
                            </button>
                            <button 
                                className="btn-primary" 
                                disabled={srcPoints.length !== 4 || loading}
                                onClick={handleCalibrate}
                            >
                                {loading ? 'Computing Matrix...' : (
                                    <>
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                                        Apply Calibration
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default SpatialCalibrator;

import React from 'react';
import './CameraFeed.css';

function CameraFeed({ cameraId, className, alt, index = 0, total = 1, isDemoMode = false, onDemoCount }) {
    const host = window.location.hostname || "127.0.0.1";
    const webrtcUrl = `http://${host}:8889/stream/?autoplay=true&muted=true`;
    
    // Prefer local demo video if user places it in public/test.mp4, otherwise fallback to public sample
    const demoVideoUrl = "/test.mp4";
    const fallbackVideoUrl = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4";

    const [isLoading, setIsLoading] = React.useState(true);

    React.useEffect(() => {
        setIsLoading(true);
        const timer = setTimeout(() => setIsLoading(false), 1500);
        return () => clearTimeout(timer);
    }, [cameraId, total, isDemoMode]);

    let cols = 1, rows = 1;
    if (total <= 1) { cols = 1; rows = 1; }
    else if (total <= 4) { cols = 2; rows = 2; }
    else if (total <= 9) { cols = 3; rows = 3; }
    else { cols = 4; rows = 4; }

    const colIndex = index % cols;
    const rowIndex = Math.floor(index / cols);

    const effectiveCols = total > 1 ? cols : 1;
    const effectiveRows = total > 1 ? rows : 1;

    const [mockBoxes, setMockBoxes] = React.useState([]);

    React.useEffect(() => {
        if (!isDemoMode) return;
        
        const interval = setInterval(() => {
            setMockBoxes(prev => {
                if (prev.length === 0 || Math.random() > 0.98) {
                    return Array.from({ length: 2 + Math.floor(Math.random() * 2) }, (_, i) => ({
                        id: 100 + i + (index * 10),
                        x: 10 + Math.random() * 80,
                        y: Math.random() > 0.5 ? 0 : 100, // Start from top or bottom
                        w: 8 + Math.random() * 5,
                        h: 15 + Math.random() * 10,
                        vy: Math.random() > 0.5 ? 0.5 : -0.5,
                        hasCrossed: false
                    }));
                }
                
                return prev.map(box => {
                    const nextY = box.y + box.vy;
                    // Tripwire at Y=50%
                    if (!box.hasCrossed) {
                        if ((box.y < 50 && nextY >= 50)) {
                            if (onDemoCount) onDemoCount('in');
                            return { ...box, y: nextY, hasCrossed: true };
                        } else if (box.y > 50 && nextY <= 50) {
                            if (onDemoCount) onDemoCount('out');
                            return { ...box, y: nextY, hasCrossed: true };
                        }
                    }
                    return { ...box, y: nextY };
                }).filter(box => box.y > -10 && box.y < 110);
            });
        }, 50);
        
        return () => clearInterval(interval);
    }, [isDemoMode, index, onDemoCount]);

    return (
        <div className={`camera-feed-container ${className || ''}`}>
            {/* Loading Overlay */}
            {isLoading && (
                <div className="camera-feed-overlay">
                    <div className="camera-feed-connecting">
                        <div className="connecting-spinner"></div>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)' }}>
                            {isDemoMode ? 'SIMULATING FEED' : 'INITIALIZING FEED'}
                        </span>
                    </div>
                </div>
            )}

            <div style={{
                position: 'absolute',
                top: 0, left: 0,
                width: '100%', height: '100%',
                overflow: 'hidden'
            }}>
                {isDemoMode ? (
                    <>
                        <video
                            autoPlay
                            muted
                            loop
                            playsInline
                            style={{
                                width: '100%',
                                height: '100%',
                                objectFit: 'cover',
                                opacity: isLoading ? 0 : 1,
                                transition: 'opacity 0.6s'
                            }}
                        >
                            <source src={demoVideoUrl} type="video/mp4" />
                            <source src={fallbackVideoUrl} type="video/mp4" />
                        </video>
                        
                        {/* Tripwire Visual */}
                        {!isLoading && (
                            <div style={{
                                position: 'absolute',
                                top: '50%',
                                left: '10%',
                                right: '10%',
                                height: '1px',
                                background: 'rgba(255, 255, 255, 0.3)',
                                boxShadow: '0 0 8px rgba(255, 255, 255, 0.2)',
                                zIndex: 5
                            }} />
                        )}

                        {/* Mock Tracking Bounding Boxes */}
                        {!isLoading && mockBoxes.map(box => (
                            <div key={box.id} style={{
                                position: 'absolute',
                                left: `${box.x}%`,
                                top: `${box.y}%`,
                                width: `${box.w}%`,
                                height: `${box.h}%`,
                                border: '1px solid #fff',
                                boxShadow: '0 0 4px rgba(255,255,255,0.5)',
                                pointerEvents: 'none',
                                zIndex: 6,
                                transition: 'top 0.05s linear'
                            }}>
                                <div style={{
                                    position: 'absolute',
                                    top: '-18px',
                                    left: '-1px',
                                    background: box.hasCrossed ? 'var(--accent)' : 'var(--grad-primary)',
                                    color: '#fff',
                                    fontSize: '10px',
                                    padding: '2px 6px',
                                    borderRadius: '2px 2px 0 0',
                                    whiteSpace: 'nowrap',
                                    fontWeight: 'bold',
                                    transition: 'background 0.3s'
                                }}>
                                    P{box.id}
                                </div>
                                {/* Futuristic corners */}
                                <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', height: '4px', borderTop: '2px solid #fff', borderLeft: '2px solid #fff' }} />
                                <div style={{ position: 'absolute', top: 0, right: 0, width: '4px', height: '4px', borderTop: '2px solid #fff', borderRight: '2px solid #fff' }} />
                                <div style={{ position: 'absolute', bottom: 0, left: 0, width: '4px', height: '4px', borderBottom: '2px solid #fff', borderLeft: '2px solid #fff' }} />
                                <div style={{ position: 'absolute', bottom: 0, right: 0, width: '4px', height: '4px', borderBottom: '2px solid #fff', borderRight: '2px solid #fff' }} />
                            </div>
                        ))}
                    </>
                ) : (
                    <iframe
                        key={`${cameraId}-${total}-${index}`}
                        title={`AI Feed - ${alt || cameraId}`}
                        src={webrtcUrl}
                        frameBorder="0"
                        scrolling="no"
                        allow="autoplay; fullscreen"
                        style={{ 
                            position: 'absolute',
                            width: `${effectiveCols * 100}%`, 
                            height: `${effectiveRows * 100}%`,
                            left: `-${colIndex * 100}%`,
                            top: `-${rowIndex * 100}%`,
                            border: 'none',
                            opacity: isLoading ? 0 : 1,
                            transition: 'opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1)',
                            pointerEvents: 'none'
                        }}
                    />
                )}
            </div>
            
            <div style={{ position: 'absolute', inset: 0, zIndex: 5 }} />
        </div>
    );
}

export default CameraFeed;

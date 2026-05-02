import React from 'react';
import './CameraFeed.css';

function CameraFeed({ cameraId, className, alt, index = 0, total = 1 }) {
    const host = window.location.hostname || "127.0.0.1";
    const webrtcUrl = `http://${host}:8889/stream/?autoplay=true&muted=true`;

    const [isLoading, setIsLoading] = React.useState(true);

    React.useEffect(() => {
        setIsLoading(true);
        const timer = setTimeout(() => setIsLoading(false), 1500);
        return () => clearTimeout(timer);
    }, [cameraId, total]);

    let cols = 1, rows = 1;
    if (total <= 1) { cols = 1; rows = 1; }
    else if (total <= 4) { cols = 2; rows = 2; }
    else if (total <= 9) { cols = 3; rows = 3; }
    else { cols = 4; rows = 4; }

    const colIndex = index % cols;
    const rowIndex = Math.floor(index / cols);

    const effectiveCols = total > 1 ? cols : 1;
    const effectiveRows = total > 1 ? rows : 1;

    return (
        <div className={`camera-feed-container ${className || ''}`}>
            {/* Loading Overlay */}
            {isLoading && (
                <div className="camera-feed-overlay">
                    <div className="camera-feed-connecting">
                        <div className="connecting-spinner"></div>
                        <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)' }}>INITIALIZING FEED</span>
                    </div>
                </div>
            )}

            <div style={{
                position: 'absolute',
                top: 0, left: 0,
                width: '100%', height: '100%',
                overflow: 'hidden'
            }}>
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
            </div>
            
            <div style={{ position: 'absolute', inset: 0, zIndex: 5 }} />
        </div>
    );
}

export default CameraFeed;

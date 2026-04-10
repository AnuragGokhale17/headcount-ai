import React, { useRef, useEffect, useState, useCallback } from 'react';
import './CameraFeed.css';

/**
 * CameraFeed — Canvas-based video feed that polls JPEG snapshots at ~24 FPS.
 * 
 * This replaces the MJPEG <img> approach which has known FPS issues in browsers.
 * Uses requestAnimationFrame + Image preloading for smooth playback.
 */
function CameraFeed({ cameraId, className, alt }) {
    const canvasRef = useRef(null);
    const [connected, setConnected] = useState(false);
    const [displayFps, setDisplayFps] = useState(0);

    const frameUrl = `/api/cameras/${cameraId}/frame`;

    const drawLoop = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        let running = true;
        let frameCount = 0;
        let lastFpsUpdate = performance.now();
        const TARGET_INTERVAL = 1000 / 24; // ~41.67ms for 24 FPS
        let lastFrameTime = 0;

        const loadAndDraw = (timestamp) => {
            if (!running) return;

            // Throttle to target FPS
            const elapsed = timestamp - lastFrameTime;
            if (elapsed < TARGET_INTERVAL) {
                requestAnimationFrame(loadAndDraw);
                return;
            }
            lastFrameTime = timestamp - (elapsed % TARGET_INTERVAL);

            const img = new Image();
            img.crossOrigin = 'anonymous';

            img.onload = () => {
                if (!running) return;
                // Resize canvas to match image aspect ratio
                if (canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight) {
                    canvas.width = img.naturalWidth;
                    canvas.height = img.naturalHeight;
                }
                ctx.drawImage(img, 0, 0);
                setConnected(true);

                frameCount++;
                const now = performance.now();
                if (now - lastFpsUpdate >= 1000) {
                    setDisplayFps(frameCount);
                    frameCount = 0;
                    lastFpsUpdate = now;
                }

                requestAnimationFrame(loadAndDraw);
            };

            img.onerror = () => {
                if (!running) return;
                setConnected(false);
                // Retry after a short delay on error
                setTimeout(() => {
                    if (running) requestAnimationFrame(loadAndDraw);
                }, 500);
            };

            // Append timestamp to bust cache
            img.src = `${frameUrl}?t=${Date.now()}`;
        };

        requestAnimationFrame(loadAndDraw);

        return () => {
            running = false;
        };
    }, [frameUrl]);

    useEffect(() => {
        const cleanup = drawLoop();
        return cleanup;
    }, [drawLoop]);

    return (
        <div className={`camera-feed-container ${className || ''}`}>
            <canvas
                ref={canvasRef}
                className="camera-feed-canvas"
                title={alt || 'Camera Feed'}
            />
            {!connected && (
                <div className="camera-feed-overlay">
                    <div className="camera-feed-connecting">
                        <div className="connecting-spinner" />
                        <span>Connecting to camera...</span>
                    </div>
                </div>
            )}
        </div>
    );
}

export default CameraFeed;

import React from 'react';
import { VIDEO_FEED_URL } from '../api';
import './VideoPanel.css';

function VideoPanel({ fps }) {
    return (
        <section className="video-section">
            <div className="video-container">
                <div className="video-overlay">
                    <span className="overlay-tag" style={{ color: 'var(--danger)' }}>● REC</span>
                    <span className="overlay-tag">CAM-01</span>
                    <span className="overlay-tag mono">{fps} FPS</span>
                </div>
                <img src={VIDEO_FEED_URL} className="video-feed" alt="Connecting to Camera..." />
            </div>
        </section>
    );
}

export default VideoPanel;

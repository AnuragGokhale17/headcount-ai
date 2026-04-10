/**
 * Centralized API calls for the Headcount AI system.
 */

const API_BASE = '';  // Uses Vite proxy in dev, same origin in prod

export async function fetchStats() {
    const res = await fetch(`${API_BASE}/api/stats`);
    return res.json();
}

export async function resetStats() {
    const res = await fetch(`${API_BASE}/api/stats/reset`, { method: 'POST' });
    return res.json();
}

export async function fetchAIInsights() {
    const res = await fetch(`${API_BASE}/api/ai_insights`);
    return res.json();
}

export async function fetchAIEvents() {
    const res = await fetch(`${API_BASE}/api/ai_events`);
    return res.json();
}

export async function fetchZones() {
    const res = await fetch(`${API_BASE}/api/zones`);
    return res.json();
}

export async function saveZones(zoneA, zoneB) {
    const res = await fetch(`${API_BASE}/api/zones`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ zone_a: zoneA, zone_b: zoneB })
    });
    return res.json();
}

export async function sendAIQuery(query) {
    const res = await fetch(`${API_BASE}/api/ai_query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
    });
    return res.json();
}

export async function sendAIVoice(textQuery) {
    const res = await fetch(`${API_BASE}/api/ai_voice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: textQuery })
    });

    if (!res.ok) {
        const err = await res.json();
        throw new Error(err.error || 'Voice synthesis failed');
    }

    return res;
}

export const SNAPSHOT_URL = `${API_BASE}/api/snapshot`;
export const VIDEO_FEED_URL = `${API_BASE}/video_feed`;

// --- Camera Management ---

export async function fetchCameras() {
    const res = await fetch(`${API_BASE}/api/cameras`);
    return res.json();
}

export async function addCamera(name, url, area, plant) {
    const res = await fetch(`${API_BASE}/api/cameras`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, url, area, plant })
    });
    return res.json();
}

export async function deleteCamera(cameraId) {
    const res = await fetch(`${API_BASE}/api/cameras/${cameraId}`, {
        method: 'DELETE'
    });
    return res.json();
}

export async function updateCamera(cameraId, data) {
    const res = await fetch(`${API_BASE}/api/cameras/${cameraId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    return res.json();
}

export async function fetchAreas() {
    const res = await fetch(`${API_BASE}/api/areas`);
    return res.json();
}

export async function fetchAreaAlerts() {
    const res = await fetch(`${API_BASE}/api/area_alerts`);
    return res.json();
}

export async function fetchPlants() {
    const res = await fetch(`${API_BASE}/api/plants`);
    return res.json();
}

export async function fetchAreaStatus() {
    const res = await fetch(`${API_BASE}/api/area_status`);
    return res.json();
}

export function cameraFeedUrl(cameraId) {
    return `${API_BASE}/api/cameras/${cameraId}/feed`;
}

export function cameraFrameUrl(cameraId) {
    return `${API_BASE}/api/cameras/${cameraId}/frame`;
}

export async function fetchCameraZones(cameraId) {
    const res = await fetch(`${API_BASE}/api/cameras/${cameraId}/zones`);
    return res.json();
}

export async function saveCameraZones(cameraId, zoneA, zoneB) {
    const res = await fetch(`${API_BASE}/api/cameras/${cameraId}/zones`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ zone_a: zoneA, zone_b: zoneB })
    });
    return res.json();
}

export function cameraSnapshotUrl(cameraId) {
    return `${API_BASE}/api/cameras/${cameraId}/snapshot`;
}

// --- Building Total ---

export async function fetchBuildingTotal() {
    const res = await fetch(`${API_BASE}/api/building_total`);
    return res.json();
}

// --- Area Limits ---

export async function fetchAreaLimits() {
    const res = await fetch(`${API_BASE}/api/areas/limits`);
    return res.json();
}

export async function setAreaLimit(area, limit) {
    const res = await fetch(`${API_BASE}/api/areas/${encodeURIComponent(area)}/limit`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit })
    });
    return res.json();
}

// --- Email Alert Config ---

export async function fetchAlertConfig() {
    const res = await fetch(`${API_BASE}/api/alert_config`);
    return res.json();
}

export async function updateAlertConfig(config) {
    const res = await fetch(`${API_BASE}/api/alert_config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
    });
    return res.json();
}

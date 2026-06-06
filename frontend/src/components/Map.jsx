import React, { useEffect, useState, useRef } from 'react';

export default function MapView() {
  const [objects, setObjects] = useState([]);
  const [status, setStatus] = useState('connecting');
  const canvasRef = useRef(null);

  useEffect(() => {
    // Attempt to connect to the new SSE endpoint the backend agent is building
    const eventSource = new EventSource('/api/stream/spatial');

    eventSource.onopen = () => setStatus('connected');
    
    eventSource.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (Array.isArray(data)) setObjects(data);
      } catch (err) {
        console.error('Error parsing map data', err);
      }
    };

    eventSource.onerror = () => {
      setStatus('error');
    };

    return () => eventSource.close();
  }, []);

  // Simple rendering of 2D points on a canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw grid
    ctx.strokeStyle = '#e5e7eb';
    for (let i = 0; i < canvas.width; i += 50) {
      ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, canvas.height); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(canvas.width, i); ctx.stroke();
    }

    // Origin
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const scale = 20; // 20 pixels per global coordinate meter

    objects.forEach(obj => {
      const cx = centerX + (obj.x * scale);
      const cy = centerY - (obj.y * scale); // Invert Y for canvas

      ctx.beginPath();
      ctx.arc(cx, cy, 6, 0, 2 * Math.PI);
      ctx.fillStyle = '#3b82f6';
      ctx.fill();
      ctx.strokeStyle = '#1d4ed8';
      ctx.stroke();

      ctx.fillStyle = '#1f2937';
      ctx.font = '10px Arial';
      ctx.fillText(obj.id || '?', cx + 8, cy + 4);
    });
  }, [objects]);

  return (
    <div className="bg-white rounded-lg shadow p-6 flex flex-col h-full">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-semibold">Live Top-Down Map</h3>
        <span className={`text-sm px-2 py-1 rounded ${status === 'connected' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
          {status === 'connected' ? 'Live Stream Active' : 'Connecting to Stream...'}
        </span>
      </div>
      <div className="flex-1 border rounded-lg bg-gray-50 overflow-hidden relative">
        {/* We use a large arbitrary size for the canvas demo. A real implementation would pan/zoom. */}
        <canvas 
          ref={canvasRef} 
          width={800} 
          height={600} 
          className="w-full h-full object-contain"
        />
        {objects.length === 0 && status === 'connected' && (
          <div className="absolute inset-0 flex items-center justify-center text-gray-400 pointer-events-none">
            No objects detected in global space.
          </div>
        )}
      </div>
    </div>
  );
}
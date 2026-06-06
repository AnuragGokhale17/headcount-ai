import React, { useEffect, useState } from 'react';
import { fetchCameras } from '../api';

export default function LiveFeeds() {
  const [cameras, setCameras] = useState([]);

  useEffect(() => {
    fetchCameras().then(setCameras).catch(console.error);
  }, []);

  const host = window.location.hostname || "127.0.0.1";
  const webrtcUrl = `http://${host}:8889/stream/`;

  const total = cameras.length;
  let effectiveCols = 1, effectiveRows = 1;
  if (total === 1) { effectiveCols = 1; effectiveRows = 1; }
  else if (total <= 4) { effectiveCols = 2; effectiveRows = 2; }
  else if (total <= 9) { effectiveCols = 3; effectiveRows = 3; }
  else { effectiveCols = 4; effectiveRows = 4; }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {cameras.map((cam, index) => {
          const rowIndex = Math.floor(index / effectiveCols);
          const colIndex = index % effectiveCols;

          return (
            <div key={cam.id} className="bg-white rounded-lg shadow overflow-hidden flex flex-col">
              <div className="px-4 py-3 bg-gray-50 border-b flex justify-between items-center z-10 relative shadow-sm">
                <h3 className="font-semibold text-gray-800">{cam.name}</h3>
                <span className="text-xs text-gray-500 bg-gray-200 px-2 py-1 rounded">Area: {cam.area}</span>
              </div>
              <div className="relative bg-black aspect-video overflow-hidden">
                <iframe
                  title={`Feed ${cam.name}`}
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
                    border: 'none'
                  }}
                />
              </div>
            </div>
          );
        })}
        {cameras.length === 0 && (
          <div className="col-span-full text-center py-12 text-gray-500">
            No cameras configured.
          </div>
        )}
      </div>
    </div>
  );
}
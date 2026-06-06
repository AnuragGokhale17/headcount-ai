import React, { useState } from 'react';
import { saveCameraHomography } from '../api';

export default function AmcImporter({ camera }) {
  const [fileData, setFileData] = useState(null);
  const [status, setStatus] = useState('');

  const handleFileUpload = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const json = JSON.parse(event.target.result);
        if (json.sensors && Array.isArray(json.sensors)) {
          setFileData(json.sensors);
          setStatus('');
        } else {
          setStatus('Invalid JSON format: missing sensors array.');
        }
      } catch (err) {
        setStatus('Failed to parse JSON file.');
      }
    };
    reader.readAsText(file);
  };

  const handleSelectSensor = async (sensor) => {
    if (!sensor.homography) {
      setStatus('Selected sensor has no homography matrix.');
      return;
    }

    setStatus('Saving...');
    try {
      const res = await saveCameraHomography(camera.id, sensor.homography);
      if (res.success || !res.error) {
        setStatus('Calibration saved successfully!');
      } else {
        setStatus(`Error: ${res.error}`);
      }
    } catch (err) {
      setStatus(`Failed to save: ${err.message}`);
    }
  };

  return (
    <div className="mt-4 p-4 bg-gray-50 rounded border border-gray-200">
      <h4 className="font-semibold text-gray-700 mb-2">Import AMC Calibration (JSON)</h4>
      <input 
        type="file" 
        accept=".json" 
        onChange={handleFileUpload} 
        className="block w-full text-sm text-gray-500
          file:mr-4 file:py-2 file:px-4
          file:rounded file:border-0
          file:text-sm file:font-semibold
          file:bg-blue-50 file:text-blue-700
          hover:file:bg-blue-100"
      />
      
      {status && (
        <p className={`mt-2 text-sm ${status.includes('success') ? 'text-green-600' : 'text-red-600'}`}>
          {status}
        </p>
      )}

      {fileData && (
        <div className="mt-4">
          <p className="text-sm text-gray-600 mb-2">Select the matching AMC sensor for <strong>{camera.name}</strong>:</p>
          <div className="flex flex-wrap gap-2">
            {fileData.map(sensor => (
              <button 
                key={sensor.id}
                onClick={() => handleSelectSensor(sensor)}
                className="px-3 py-1 bg-white border border-gray-300 shadow-sm text-gray-700 hover:bg-gray-100 rounded text-sm transition-colors"
              >
                {sensor.id}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
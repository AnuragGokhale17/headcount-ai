import React, { useEffect, useState } from 'react';
import { fetchCameras, updateAmcConfig } from '../api';
import AmcImporter from './AmcImporter';

export default function Settings() {
  const [cameras, setCameras] = useState([]);
  const [selectedCam, setSelectedCam] = useState('amc_config');
  const [amcFiles, setAmcFiles] = useState(null);
  const [amcStatus, setAmcStatus] = useState('');

  useEffect(() => {
    fetchCameras().then(setCameras).catch(console.error);
  }, []);

  const handleSaveAmcConfig = async () => {
    if (!amcFiles || amcFiles.length === 0) {
      setAmcStatus('Please select at least 1 video file.');
      return;
    }
    try {
      setAmcStatus('Saving...');
      await updateAmcConfig(amcFiles.length);
      setAmcStatus(`Successfully updated AMC config for ${amcFiles.length} cameras.`);
    } catch (err) {
      setAmcStatus(`Error: ${err.message}`);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow flex overflow-hidden" style={{ minHeight: '600px' }}>
      {/* Settings Sidebar */}
      <div className="w-1/3 border-r border-gray-200 p-4 bg-gray-50">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Settings</h3>
        <ul className="space-y-2 mb-6">
          <li>
            <button 
              onClick={() => setSelectedCam('amc_config')}
              className={`w-full text-left px-4 py-3 rounded-md transition-colors ${selectedCam === 'amc_config' ? 'bg-blue-100 text-blue-700 border border-blue-200' : 'bg-white border border-gray-200 text-gray-700 hover:bg-gray-100'}`}
            >
              <div className="font-semibold">AMC Configuration</div>
              <div className="text-xs opacity-80 mt-1">Global AMC Setup</div>
            </button>
          </li>
        </ul>

        <h3 className="text-lg font-semibold text-gray-800 mb-4">Cameras</h3>
        <ul className="space-y-2">
          {cameras.map(cam => (
            <li key={cam.id}>
              <button 
                onClick={() => setSelectedCam(cam)}
                className={`w-full text-left px-4 py-3 rounded-md transition-colors ${selectedCam?.id === cam.id ? 'bg-blue-100 text-blue-700 border border-blue-200' : 'bg-white border border-gray-200 text-gray-700 hover:bg-gray-100'}`}
              >
                <div className="font-semibold">{cam.name}</div>
                <div className="text-xs opacity-80 mt-1 break-all">{cam.url}</div>
              </button>
            </li>
          ))}
          {cameras.length === 0 && <p className="text-gray-500 text-sm">No cameras found.</p>}
        </ul>
      </div>

      {/* Settings Content */}
      <div className="flex-1 p-6">
        {selectedCam === 'amc_config' ? (
          <div>
             <h2 className="text-2xl font-bold text-gray-800 mb-6">AMC Configuration</h2>
             <section className="bg-gray-50 p-6 rounded border border-gray-200">
                <h3 className="text-lg font-semibold mb-2 text-gray-800">Dynamic Video Selection</h3>
                <p className="text-gray-600 mb-4">
                  Select the local video files to be processed by the AMC Microservice. This dynamically updates the <code>mv_amc_config.yaml</code> backend file.
                </p>
                <input 
                  type="file" 
                  multiple 
                  accept="video/*" 
                  onChange={(e) => setAmcFiles(e.target.files)} 
                  className="mb-4 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
                <button 
                  onClick={handleSaveAmcConfig}
                  className="px-4 py-2 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 transition-colors"
                >
                  Save AMC Configuration
                </button>
                {amcStatus && (
                  <p className={`mt-3 text-sm ${amcStatus.includes('Error') ? 'text-red-600' : 'text-green-600'}`}>
                    {amcStatus}
                  </p>
                )}
             </section>
          </div>
        ) : selectedCam ? (
          <div>
            <div className="flex justify-between items-start mb-6">
              <div>
                <h2 className="text-2xl font-bold text-gray-800">{selectedCam.name}</h2>
                <p className="text-gray-500 break-all">{selectedCam.url}</p>
              </div>
              <span className="bg-gray-200 text-gray-700 px-3 py-1 rounded text-sm">Area: {selectedCam.area}</span>
            </div>

            <div className="space-y-8">
              {/* AMC Calibration Section */}
              <section>
                <h3 className="text-xl font-semibold border-b pb-2 mb-4">Spatial Calibration</h3>
                <p className="text-gray-600 mb-4">
                  Import a <code>calibration.json</code> file generated by AMC to teach the AI how to map video pixels to the 2D map.
                </p>
                <AmcImporter camera={selectedCam} />
              </section>
            </div>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center text-gray-400">
            Select an item from the sidebar to view settings.
          </div>
        )}
      </div>
    </div>
  );
}
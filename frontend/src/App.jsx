import React, { useState } from 'react';
import Dashboard from './components/Dashboard';
import MapView from './components/Map';
import LiveFeeds from './components/LiveFeeds';
import Settings from './components/Settings';

export default function App() {
  const [currentView, setCurrentView] = useState('dashboard');

  const renderView = () => {
    switch (currentView) {
      case 'dashboard': return <Dashboard />;
      case 'map': return <MapView />;
      case 'cameras': return <LiveFeeds />;
      case 'settings': return <Settings />;
      default: return <Dashboard />;
    }
  };

  const navItemClass = (view) => 
    `w-full text-left px-4 py-2 my-1 rounded-md transition-colors ${currentView === view ? 'bg-blue-600 text-white' : 'text-gray-300 hover:bg-gray-800'}`;

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      {/* Sidebar */}
      <div className="w-64 bg-gray-900 text-white shadow-xl flex flex-col">
        <div className="p-6 text-2xl font-bold border-b border-gray-700 tracking-wide text-blue-400">
          Headcount AI
        </div>
        <nav className="flex-1 px-4 py-6">
          <button className={navItemClass('dashboard')} onClick={() => setCurrentView('dashboard')}>Dashboard</button>
          <button className={navItemClass('map')} onClick={() => setCurrentView('map')}>Live Map</button>
          <button className={navItemClass('cameras')} onClick={() => setCurrentView('cameras')}>Live Feeds</button>
          <button className={navItemClass('settings')} onClick={() => setCurrentView('settings')}>Settings & AMC</button>
        </nav>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white shadow-sm px-6 py-4 flex justify-between items-center">
          <h2 className="text-xl font-semibold text-gray-800 capitalize">{currentView.replace('-', ' ')}</h2>
        </header>
        <main className="flex-1 overflow-x-hidden overflow-y-auto bg-gray-50 p-6">
          {renderView()}
        </main>
      </div>
    </div>
  );
}
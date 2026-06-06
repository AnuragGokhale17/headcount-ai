import React, { useEffect, useState } from 'react';
import { fetchBuildingTotal, fetchAreaAlerts } from '../api';

export default function Dashboard() {
  const [total, setTotal] = useState(0);
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    const loadData = async () => {
      try {
        const totalData = await fetchBuildingTotal();
        setTotal(totalData.total || 0);

        const alertsData = await fetchAreaAlerts();
        setAlerts(alertsData || []);
      } catch (err) {
        console.error('Error fetching dashboard data', err);
      }
    };
    
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-500">
          <h3 className="text-gray-500 text-sm uppercase tracking-wider">Total Building Headcount</h3>
          <p className="text-4xl font-bold text-gray-800 mt-2">{total}</p>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-800">Active Area Alerts</h3>
        </div>
        <div className="p-6">
          {alerts.length === 0 ? (
            <p className="text-gray-500">No active alerts.</p>
          ) : (
            <ul className="space-y-3">
              {alerts.map((alert, idx) => (
                <li key={idx} className="bg-red-50 text-red-700 px-4 py-3 rounded border border-red-200 flex justify-between items-center">
                  <span>
                    <strong>{alert.area}</strong> has exceeded capacity!
                  </span>
                  <span className="font-bold">{alert.count} / {alert.limit}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
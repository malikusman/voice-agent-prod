import { useState, useEffect } from 'react';
import axios from 'axios';

function AdminDashboard() {
  const [calls, setCalls] = useState([]);
  const [transcripts, setTranscripts] = useState([]);
  const [selectedCallId, setSelectedCallId] = useState(null);
  const [error, setError] = useState(null);

  const apiKey = import.meta.env.VITE_ADMIN_API_KEY || 'your-secret-api-key';
  const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:5000';

  // Fetch calls on mount
  useEffect(() => {
    axios
      .get(`${baseUrl}/api/calls`, {
        headers: { 'X-API-Key': apiKey },
      })
      .then((response) => {
        setCalls(response.data);
      })
      .catch((err) => {
        setError('Failed to fetch calls');
        console.error(err);
      });
  }, []);

  // Fetch transcripts when a call is selected
  const handleCallSelect = (callId) => {
    setSelectedCallId(callId);
    axios
      .get(`${baseUrl}/api/calls/${callId}/transcripts`, {
        headers: { 'X-API-Key': apiKey },
      })
      .then((response) => {
        setTranscripts(response.data);
        setError(null);
      })
      .catch((err) => {
        setError('Failed to fetch transcripts');
        console.error(err);
      });
  };

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <h1 className="text-3xl font-bold mb-6">Admin Dashboard</h1>
      {error && <div className="text-red-500 mb-4">{error}</div>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Calls Table */}
        <div>
          <h2 className="text-2xl font-semibold mb-4">Call History</h2>
          <table className="w-full bg-white shadow rounded-lg">
            <thead>
              <tr className="bg-gray-200">
                <th className="p-3 text-left">Call SID</th>
                <th className="p-3 text-left">Caller Phone</th>
                <th className="p-3 text-left">Status</th>
                <th className="p-3 text-left">Start Time</th>
                <th className="p-3 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {calls.map((call) => (
                <tr key={call.id} className="border-b">
                  <td className="p-3">{call.call_sid}</td>
                  <td className="p-3">{call.caller_phone}</td>
                  <td className="p-3">{call.status}</td>
                  <td className="p-3">{call.start_time}</td>
                  <td className="p-3">
                    <button
                      onClick={() => handleCallSelect(call.id)}
                      className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                    >
                      View Transcripts
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {/* Transcripts View */}
        <div>
          <h2 className="text-2xl font-semibold mb-4">
            Transcripts {selectedCallId ? `for Call ID ${selectedCallId}` : ''}
          </h2>
          {transcripts.length > 0 ? (
            <div className="bg-white shadow rounded-lg p-4">
              {transcripts.map((transcript) => (
                <div
                  key={transcript.id}
                  className={`mb-4 p-3 rounded ${
                    transcript.role === 'user' ? 'bg-blue-100' : 'bg-green-100'
                  }`}
                >
                  <p className="font-semibold">{transcript.role.toUpperCase()}</p>
                  <p>{transcript.text}</p>
                  <p className="text-sm text-gray-500">{transcript.timestamp}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-600">
              {selectedCallId ? 'No transcripts available' : 'Select a call to view transcripts'}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminDashboard;
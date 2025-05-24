function LandingPage() {
    return (
      <div className="min-h-screen bg-gray-100 flex flex-col items-center justify-center">
        <h1 className="text-4xl font-bold mb-4">Welcome to Voice Agent</h1>
        <p className="text-lg text-gray-600 mb-6">
          Your intelligent voice assistant for managing bookings and customer support.
        </p>
        <a
          href="/admin"
          className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          Go to Admin Dashboard
        </a>
      </div>
    );
  }
  
  export default LandingPage;
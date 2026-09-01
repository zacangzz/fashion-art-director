import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import ObservabilityPage from './pages/ObservabilityPage.jsx';
import { AuthProvider } from './contexts/AuthContext.jsx';
import './index.css';

function Root() {
  const [currentPath, setCurrentPath] = useState(() => {
    return window.location.pathname + window.location.hash;
  });

  useEffect(() => {
    const handleLocationChange = () => {
      setCurrentPath(window.location.pathname + window.location.hash);
    };

    window.addEventListener('popstate', handleLocationChange);
    window.addEventListener('hashchange', handleLocationChange);

    return () => {
      window.removeEventListener('popstate', handleLocationChange);
      window.removeEventListener('hashchange', handleLocationChange);
    };
  }, []);

  const isTelemetry =
    currentPath.startsWith('/telemetry') ||
    currentPath.startsWith('/observability') ||
    currentPath.includes('#/telemetry') ||
    currentPath.includes('#/observability');

  if (isTelemetry) {
    return <ObservabilityPage />;
  }

  return <App />;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AuthProvider>
      <Root />
    </AuthProvider>
  </React.StrictMode>
);

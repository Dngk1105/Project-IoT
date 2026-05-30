import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { MainLayout } from './components/layout/MainLayout';

// Import các trang
import { CalendarPage } from './pages/CalendarPage';
import { TelemetryPage } from './pages/TelemetryPage';
import { AiStatusPage } from './pages/AiStatusPage';
import { MqttPage } from './pages/MqttPage';
import { LogsPage } from './pages/LogsPage';

const App: React.FC = () => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<CalendarPage />} />
          <Route path="telemetry" element={<TelemetryPage />} />
          <Route path="ai-status" element={<AiStatusPage />} />
          <Route path="mqtt" element={<MqttPage />} />
          <Route path="logs" element={<LogsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
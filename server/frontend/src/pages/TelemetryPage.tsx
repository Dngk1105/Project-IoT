import React from 'react';
import { theme } from '../core/theme';

export const TelemetryPage: React.FC = () => {
  return (
    <div style={{ color: theme.colors.textPrimary }}>
      <h2>ESP32 Telemetry</h2>
      <p style={{ color: theme.colors.textSecondary }}>Khu vực hiển thị đồ thị Recharts (Đang xây dựng)...</p>
    </div>
  );
};
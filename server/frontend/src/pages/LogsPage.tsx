import React from 'react';
import { theme } from '../core/theme';

export const LogsPage: React.FC = () => {
  return (
    <div style={{ color: theme.colors.textPrimary }}>
      <h2>System Logs</h2>
      <div style={{ 
        backgroundColor: theme.colors.bgSidebar, 
        padding: '15px', 
        border: `1px solid ${theme.colors.border}`,
        fontFamily: 'monospace' // Log nên dùng font monospace cho dễ đọc
      }}>
        [2026-05-30] Hệ thống khởi động thành công...
      </div>
    </div>
  );
};
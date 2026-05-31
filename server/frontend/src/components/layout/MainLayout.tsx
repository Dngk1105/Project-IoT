import React, { useState } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { theme } from '../../core/theme';

export const MainLayout: React.FC = () => {
  const location = useLocation();
  const [hoveredPath, setHoveredPath] = useState<string | null>(null);

  const navItems = [
    { path: '/', label: 'Lịch Trạm' },
    { path: '/telemetry', label: 'ESP32 Telemetry' },
    { path: '/ai-status', label: 'AI Status' },
    { path: '/mqtt', label: 'MQTT Config' },
    { path: '/logs', label: 'System Logs' },
  ];

  return (
    <div style={{
      display: 'flex',
      minHeight: '100vh',
      fontFamily: theme.typography.fontFamily,
      backgroundColor: theme.colors.bgMain,
      color: theme.colors.textPrimary,
      margin: 0,
      padding: 0
    }}>
      {/* CSS Toàn cục để bắt ép chế độ forced-colors trên toàn trình duyệt */}
      <style>
        {`
          body { background-color: Canvas !important; color: CanvasText !important; }
          * { border-radius: 0px !important; box-shadow: none !important; }
        `}
      </style>

      {/* Thanh Menu bên trái (Sidebar) */}
      <aside style={{
        width: '240px',
        borderRight: `0px solid ${theme.colors.border}`,
        display: 'flex',
        flexDirection: 'column',
      }}>
        <div style={{
          padding: theme.spacing(2.5),
          fontSize: '18px',
          fontWeight: 'bold',
          borderBottom: `2px solid ${theme.colors.border}`,
          textTransform: 'uppercase',
          letterSpacing: '1px'
        }}>
          Control Dashboard
        </div>
        
        <nav style={{ padding: `${theme.spacing(2)} 0`, display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {navItems.map((item) => {
            const isActive = location.pathname === item.path;
            const isHovered = hoveredPath === item.path;

            let backgroundColor = 'transparent';
            let color = theme.colors.textPrimary;
            let borderStyle = '2px solid transparent';

            // Cơ chế Đảo Màu (Invert) tối cao của High Contrast
            if (isActive) {
              backgroundColor = theme.colors.selectedBg; // Ăn màu Nâu hoang mạc
              color = theme.colors.selectedText;       // Chữ biến thành trắng ngà
              borderStyle = `2px solid ${theme.colors.border}`;
            } else if (isHovered) {
              borderStyle = `2px dashed ${theme.colors.border}`; // Hiện khung nét đứt khi rê chuột
            }

            return (
              <Link
                key={item.path}
                to={item.path}
                onMouseEnter={() => setHoveredPath(item.path)}
                onMouseLeave={() => setHoveredPath(null)}
                style={{
                  padding: '10px 18px',
                  textDecoration: 'none',
                  color: color,
                  backgroundColor: backgroundColor,
                  fontWeight: isActive ? 'bold' : 'normal',
                  border: borderStyle,
                  margin: '0 8px',
                }}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>

      {/* Vùng không gian làm việc chính */}
      <main style={{
        flex: 1,
        padding: theme.spacing(4),
        overflowY: 'auto'
      }}>
        <Outlet />
      </main>
    </div>
  );
};
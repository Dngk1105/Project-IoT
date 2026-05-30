import { Link, useLocation } from 'react-router-dom';

const menuItems = [
  { text: 'Trạm Lịch (Calendar)', path: '/' },
  { text: 'Status & Telemetry', path: '/telemetry' },
  { text: 'AI Status', path: '/ai-status' },
  { text: 'Quản lý MQTT', path: '/mqtt' },
  { text: 'Log Hệ Thống', path: '/logs' },
];

export default function Sidebar() {
  const location = useLocation();

  return (
    <aside style={{
      position: 'fixed',
      top: '60px',
      left: 0,
      bottom: 0,
      width: '240px',
      backgroundColor: '#ffffff',
      borderRight: '1px solid #e5e7eb', // Viền phải phân tách với nội dung
      padding: '24px 16px',
      fontFamily: 'sans-serif'
    }}>
      <nav style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {menuItems.map((item) => {
          const isActive = location.pathname === item.path;

          return (
            <Link
              key={item.path}
              to={item.path}
              style={{
                display: 'block',
                padding: '10px 16px',
                borderRadius: '6px',
                textDecoration: 'none',
                fontSize: '14px',
                // TỰ ĐỘNG ĐỔI MÀU NỀN VÀ MÀU CHỮ KHI ACTIVE
                backgroundColor: isActive ? '#f3f4f6' : 'transparent', // Nền xám nhạt nếu chọn
                color: isActive ? '#111827' : '#4b5563', // Chữ đậm hoặc xám nhạt
                fontWeight: isActive ? 600 : 500,
                transition: 'all 0.2s'
              }}
            >
              {item.text}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
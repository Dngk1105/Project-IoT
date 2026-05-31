import React, { useState } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';

// Giả định huynh đang dùng theme High Contrast Desert
// import { theme } from '../../../core/theme'; 
// (Tạm khai báo lại biến theme ở đây để huynh dễ hình dung, trong thực tế huynh cứ import bình thường)
const theme = {
  typography: { fontFamily: "'Segoe UI', sans-serif" },
  colors: { border: 'ButtonBorder', textPrimary: 'CanvasText' }
};

// 1. Định nghĩa khuôn dữ liệu sự kiện có thêm trường Phân Loại (Category)
type EventCategory = 'normal' | 'warning' | 'error';

interface CalendarEvent {
  id: string;
  title: string;
  start: string;
  end?: string;
  category: EventCategory;
}

export const CalendarWidget: React.FC = () => {
  // 2. Dữ liệu mốc (Có nhiều sự kiện trùng ngày để test tính năng thu gọn)
  const [events, setEvents] = useState<CalendarEvent[]>([
    { id: '1', title: 'Khởi động ESP32', start: '2026-05-31T08:00:00', category: 'normal' },
    { id: '2', title: 'Cảnh báo nhiệt độ cao ở trạm 01 (Nội dung cực kỳ dài)', start: '2026-05-31T09:00:00', category: 'warning' },
    { id: '3', title: 'Mất kết nối MQTT', start: '2026-05-31T10:00:00', category: 'error' },
    { id: '4', title: 'Đồng bộ FastAPI', start: '2026-06-02T14:00:00', category: 'normal' }
  ]);

  // Bộ nhớ quản lý Hộp thoại (Modal)
  const [modal, setModal] = useState({
    isOpen: false,
    isEdit: false,
    id: '',
    title: '',
    start: '',
    category: 'normal' as EventCategory
  });

  // 3. Hàm ánh xạ màu sắc dựa theo phân loại
  const getEventColors = (category: EventCategory) => {
    switch (category) {
      case 'error': return { bg: '#8A3B32', text: '#FFFAEF' }; // Đỏ sậm chữ ngà
      case 'warning': return { bg: '#903909', text: '#FFFAEF' }; // Nâu Desert
      case 'normal': 
      default: return { bg: 'Highlight', text: 'HighlightText' }; // Màu hệ thống mặc định
    }
  };

  // Ánh xạ events state sang định dạng của FullCalendar
  const calendarEvents = events.map(ev => {
    const colors = getEventColors(ev.category);
    return {
      id: ev.id,
      title: ev.title,
      start: ev.start,
      end: ev.end,
      backgroundColor: colors.bg,
      textColor: colors.text,
      borderColor: theme.colors.border,
      extendedProps: { category: ev.category }
    };
  });

  // --- XỬ LÝ SỰ KIỆN TƯƠNG TÁC ---
  const handleDateClick = (arg: any) => {
    setModal({
      isOpen: true, isEdit: false,
      id: String(Date.now()), title: '', start: arg.dateStr, category: 'normal'
    });
  };

  const handleEventClick = (clickInfo: any) => {
    setModal({
      isOpen: true, isEdit: true,
      id: clickInfo.event.id,
      title: clickInfo.event.title,
      start: clickInfo.event.startStr,
      category: clickInfo.event.extendedProps.category
    });
  };

  const handleSave = () => {
    if (!modal.title.trim()) return;
    if (modal.isEdit) {
      setEvents(events.map(ev => ev.id === modal.id ? { ...ev, title: modal.title, category: modal.category } : ev));
    } else {
      setEvents([...events, { id: modal.id, title: modal.title, start: modal.start, category: modal.category }]);
    }
    setModal({ ...modal, isOpen: false });
  };

  const handleDelete = () => {
    setEvents(events.filter(ev => ev.id !== modal.id));
    setModal({ ...modal, isOpen: false });
  };

  return (
    <div style={{
      padding: '16px',
      color: theme.colors.textPrimary,
      fontFamily: theme.typography.fontFamily,
      position: 'relative'
    }}>
      <style>
        {`
          .fc { font-family: ${theme.typography.fontFamily}; color: ${theme.colors.textPrimary}; }
          
          /* Lưới lịch không viền (chỉ kẻ ngang ở tiêu đề) */
          .fc-theme-standard td, .fc-theme-standard th, .fc-theme-standard .fc-scrollgrid { border: none !important; }
          .fc-col-header-cell { padding: 8px 0; border-bottom: 1px solid ${theme.colors.textPrimary} !important; }
          .fc-daygrid-day-number { color: ${theme.colors.textPrimary} !important; padding: 4px 8px !important; text-decoration: none; }
          
          /* ÉP KHUNG NGÀY VUÔNG VẮN */
          .fc-daygrid-day-frame {
            aspect-ratio: 1 / 1;
            min-height: 120px; /* Chiều cao tối thiểu chống sập khung */
          }

          /* NÚT BẤM ĐIỀU HƯỚNG */
          .fc-button-primary { 
            background-color: ButtonFace !important; 
            border: 2px solid ${theme.colors.border} !important; 
            color: ButtonText !important; 
            font-weight: bold !important;
            border-radius: 0px !important;
            text-transform: uppercase;
            padding: 4px 12px !important;
          }
          .fc-button-primary:hover { border-style: dashed !important; }
          .fc-button-primary:not(:disabled).fc-button-active { 
            background-color: Highlight !important; color: HighlightText !important; border-style: solid !important; 
          }

          /* KHUNG SỰ KIỆN Bám sát text và Cắt chữ (dành cho chế độ Month) */
          .fc-daygrid-event {
            border-radius: 0px !important;
            padding: 4px 6px !important;
            font-size: 12px !important;
            font-weight: bold;
            margin-bottom: 2px !important;
            border: 1px solid ${theme.colors.border} !important;
            
            /* Kỹ thuật ép khung vừa text và hiện dấu 3 chấm */
            width: max-content !important;
            max-width: 95% !important; /* Không cho tràn ra ngoài ô */
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            display: block;
          }
          
          /* Ẩn dấu chấm giờ mặc định để ưu tiên chữ */
          .fc-event-time { display: none; }
          
          /* Tinh chỉnh nút +X more khi quá nhiều sự kiện */
          .fc-daygrid-more-link {
            font-weight: bold; color: Highlight !important; font-size: 12px; padding-left: 4px;
          }
        `}
      </style>

      <FullCalendar
        plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
        initialView="dayGridMonth"
        events={calendarEvents}
        dateClick={handleDateClick}
        eventClick={handleEventClick}
        dayMaxEvents={3} /* Giới hạn tối đa 3 sự kiện 1 ngày, phần dư bị gộp lại */
        headerToolbar={{
          left: 'prev,next today',
          center: 'title',
          right: 'dayGridMonth,timeGridWeek'
        }}
        slotMinTime="06:00:00" // Trục giờ bắt đầu từ 6h sáng
        slotMaxTime="22:00:00"
        height="750px"
      />

      {/* GIAO DIỆN CHỈNH SỬA SỰ KIỆN (MODAL) */}
      {modal.isOpen && (
        <div style={{
          position: 'fixed', inset: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 9999
        }}>
          {/* Lớp nền xám trong suốt che lịch */}
          <div style={{ position: 'absolute', inset: 0, backgroundColor: 'CanvasText', opacity: 0.2 }} onClick={() => setModal({ ...modal, isOpen: false })} />
          
          <div style={{
            position: 'relative', backgroundColor: 'Canvas', border: '4px solid CanvasText',
            padding: '24px', width: '400px', display: 'flex', flexDirection: 'column', gap: '16px',
            boxShadow: '8px 8px 0px CanvasText' /* Tạo hiệu ứng khối thô cứng chuẩn retro */
          }}>
            <h3 style={{ margin: 0, textTransform: 'uppercase', borderBottom: '2px solid CanvasText', paddingBottom: '8px' }}>
              {modal.isEdit ? 'Thông tin sự kiện' : 'Tạo mới sự kiện'}
            </h3>
            
            <input 
              type="text" value={modal.title} onChange={(e) => setModal({ ...modal, title: e.target.value })}
              placeholder="Nhập nội dung (VD: Bảo trì Cảm biến)" autoFocus
              style={{ padding: '8px', border: '2px solid CanvasText', backgroundColor: 'Canvas', color: 'CanvasText', outline: 'none' }}
            />

            <select 
              value={modal.category} onChange={(e) => setModal({ ...modal, category: e.target.value as EventCategory })}
              style={{ padding: '8px', border: '2px solid CanvasText', backgroundColor: 'Canvas', color: 'CanvasText', outline: 'none', cursor: 'pointer' }}
            >
              <option value="normal">Thông thường (Mặc định)</option>
              <option value="warning">Cảnh báo (Màu Nâu)</option>
              <option value="error">Nghiêm trọng (Màu Đỏ)</option>
            </select>

            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end', marginTop: '12px' }}>
              {modal.isEdit && (
                <button onClick={handleDelete} style={{ padding: '8px 16px', cursor: 'pointer', border: '2px solid CanvasText', backgroundColor: 'Canvas', color: 'CanvasText', fontWeight: 'bold' }}>
                  XÓA
                </button>
              )}
              <button onClick={() => setModal({ ...modal, isOpen: false })} style={{ padding: '8px 16px', cursor: 'pointer', border: '2px dashed CanvasText', backgroundColor: 'Canvas', color: 'CanvasText', fontWeight: 'bold' }}>
                HỦY
              </button>
              <button onClick={handleSave} style={{ padding: '8px 16px', cursor: 'pointer', border: '2px solid CanvasText', backgroundColor: 'Highlight', color: 'HighlightText', fontWeight: 'bold' }}>
                LƯU
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
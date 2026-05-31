import type { CalendarEvent, CreateEventDTO } from '../types';

//const API_BASE_URL = 'http://localhost:8000/api/v1/calendar'; // Thay bằng URL FastAPI thực tế sau

export const calendarService = {
  // 1. Lấy danh sách lịch (bỏ qua các record bị soft-delete)
  fetchEvents: async (): Promise<CalendarEvent[]> => {
    try {
      // MỞ ĐƯỜNG: Khi Backend sẵn sàng, mở comment đoạn dưới
      // const response = await fetch(`${API_BASE_URL}/events`);
      // return await response.json();

      // Dữ liệu giả lập (Mock) tạm thời:
      return [
        { id: '1', title: 'Bảo trì mạng ESP32', start: '2026-05-31' },
        { id: '2', title: 'Đồng bộ API FastAPI', start: '2026-06-02' }
      ];
    } catch (error) {
      console.error('Lỗi khi tải lịch:', error);
      return [];
    }
  },

  // 2. Thêm lịch mới
  createEvent: async (data: CreateEventDTO): Promise<CalendarEvent | null> => {
    try {
      // MỞ ĐƯỜNG:
      // const response = await fetch(`${API_BASE_URL}/events`, {
      //   method: 'POST',
      //   headers: { 'Content-Type': 'application/json' },
      //   body: JSON.stringify(data)
      // });
      // return await response.json();
      
      console.log('Đang gửi API tạo lịch:', data);
      return { id: String(Date.now()), ...data }; // Trả về mock data có ID
    } catch (error) {
      console.error('Lỗi khi tạo lịch:', error);
      return null;
    }
  },

  // 3. Xóa mềm (Soft Delete)
  softDeleteEvent: async (id: string): Promise<boolean> => {
    try {
      // MỞ ĐƯỜNG:
      // const response = await fetch(`${API_BASE_URL}/events/${id}/soft-delete`, { method: 'PATCH' });
      // return response.ok;
      
      console.log(`Đã gửi lệnh xóa mềm lịch ID: ${id}`);
      return true;
    } catch (error) {
      console.error('Lỗi khi xóa lịch:', error);
      return false;
    }
  }
};
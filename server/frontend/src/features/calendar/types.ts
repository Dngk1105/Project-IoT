export interface CalendarEvent {
  id: string;
  title: string;
  start: string; // ISO 8601 string, vd: "2026-05-31T10:00:00"
  end?: string;
  isDeleted?: boolean; // Cờ phục vụ cơ chế Soft-delete của Backend
}

// Dữ liệu dùng để gửi lên Backend khi tạo mới (chưa có ID)
export type CreateEventDTO = Omit<CalendarEvent, 'id' | 'isDeleted'>;
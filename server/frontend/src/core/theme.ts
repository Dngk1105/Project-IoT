export const theme = {
  typography: {
    fontFamily: "'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif",
  },
  colors: {
    // Ép hệ thống dùng các từ khóa màu hệ thống (CSS System Colors)
    bgMain: 'Canvas',            // Tự động ăn theo màu nền hệ thống (Desert: #FFFAEF)
    bgSidebar: 'Canvas',         
    cardBg: 'Canvas',

    textPrimary: 'CanvasText',   // Chữ chính (Desert: #3D3D3D hoặc #202020)
    textSecondary: 'CanvasText', 
    inactiveText: 'GrayText',    // Chữ khi bị vô hiệu hóa

    // Trạng thái khi click chọn hoặc bôi đen
    selectedBg: 'Highlight',     // Nền vùng chọn (Desert: Nâu sẫm #903909)
    selectedText: 'HighlightText',// Chữ trong vùng chọn (Desert: Trắng ngà #FFFAEF)
    
    // Đường viền và siêu liên kết
    border: 'ButtonBorder',      // Viền sắc cạnh nét đậm
    hyperlink: 'LinkText',       // Link (Desert: Xanh dương #0063B3)
    
    // Nút bấm
    buttonBg: 'ButtonFace',
    buttonText: 'ButtonText',
  },
  spacing: (multiplier: number) => `${8 * multiplier}px`,
};
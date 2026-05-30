import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

// Reset margin/padding mặc định của trình duyệt bằng thẻ style toàn cục ngắn gọn
const GlobalStyle = () => (
  <style>
    {`
      body, html { margin: 0; padding: 0; height: 100%; }
      * { box-sizing: border-box; }
    `}
  </style>
);

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <GlobalStyle />
    <App />
  </React.StrictMode>
);
// Cấu hình MQTT Broker (WebSocket)
const brokerUrl = 'ws://localhost:9001';
const clientId = 'web_dashboard_' + Math.random().toString(16).substr(2, 8);

// Cấu hình Topic giám sát ESP32 (Chỉnh theo code ESP của dev 1)
const espStatusTopic = 'hust_iot/assistant/esp32_main/sys/status';

// Khởi tạo kết nối MQTT qua WebSocket
const client = mqtt.connect(brokerUrl, {
    clientId: clientId,
    clean: true,
    connectTimeout: 4000,
    reconnectPeriod: 2000,
});

// UI Elements
const uiStatusEl = document.getElementById('ui-status');
const espStatusEl = document.getElementById('esp-status');
const consoleLogEl = document.getElementById('console-log');
const clearBtn = document.getElementById('clear-btn');
const publishForm = document.getElementById('publish-form');

function updateStatus(element, statusClass, text) {
    element.className = 'status ' + statusClass;
    element.innerText = text;
}

// Thêm dòng log vào console
function appendLog(topic, payload) {
    const time = new Date().toLocaleTimeString();
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    
    // Đảm bảo payload in ra là string an toàn
    let safePayload = payload;
    if (typeof payload === 'object') { safePayload = JSON.stringify(payload); } 
    else { safePayload = payload.toString(); }

    logEntry.innerHTML = `
        <span class="log-time">[${time}]</span>
        <span class="log-topic">${topic}:</span>
        <span class="log-payload">${safePayload}</span>
    `;
    consoleLogEl.appendChild(logEntry);
    consoleLogEl.scrollTop = consoleLogEl.scrollHeight; // Cuộn xuống dưới
}

// --- XỬ LÝ SỰ KIỆN MQTT ---
client.on('connect', () => {
    updateStatus(uiStatusEl, 'success', 'Thành công');
    
    // Subscribe Topic "#" để hứng mọi thứ bay qua broker
    client.subscribe('#', (err) => {
        if (!err) appendLog('SYSTEM', 'Đã subscribe topic: # (Bắt đầu lắng nghe)');
        else appendLog('ERROR', 'Lỗi subscribe: ' + err.message);
    });
});

client.on('reconnect', () => updateStatus(uiStatusEl, 'connecting', 'Đang kết nối lại...'));
client.on('error', (err) => {
    updateStatus(uiStatusEl, 'error', 'Lỗi kết nối');
    appendLog('ERROR', err.message);
});
client.on('close', () => {
    updateStatus(uiStatusEl, 'error', 'Mất kết nối');
    updateStatus(espStatusEl, 'offline', 'Không rõ (Broker sập)');
});

// Hứng tin nhắn
client.on('message', (topic, message) => {
    const payloadStr = message.toString();
    appendLog(topic, payloadStr);

    // Phát hiện trạng thái online/offline của ESP32 qua LWT hoặc bản tin status
    if (topic === espStatusTopic) {
        try {
            const data = JSON.parse(payloadStr);
            if (data.status === 'online') updateStatus(espStatusEl, 'success', 'Online');
            if (data.status === 'offline') updateStatus(espStatusEl, 'error', 'Offline');
        } catch (e) {
            // Fallback nếu payload không phải JSON
            if (payloadStr.includes('online')) updateStatus(espStatusEl, 'success', 'Online');
            if (payloadStr.includes('offline')) updateStatus(espStatusEl, 'error', 'Offline');
        }
    }
});

// Xử lý nút xóa Log
clearBtn.addEventListener('click', () => { consoleLogEl.innerHTML = ''; });

// Xử lý Form Publish
publishForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const topic = document.getElementById('pub-topic').value;
    const payload = document.getElementById('pub-payload').value;

    if (client.connected) {
        client.publish(topic, payload, (err) => {
            if (err) alert('Lỗi publish: ' + err.message);
            else appendLog(`PUBLISHED [${topic}]`, payload);
        });
    } else {
        alert('Không thể publish. Chưa kết nối tới Broker!');
    }
});
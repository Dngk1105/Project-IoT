let client = null;
const logWindow = document.getElementById('log-window');

// Hàm in log ra màn hình Terminal giả lập
function appendLog(direction, topic, payload) {
    const time = new Date().toLocaleTimeString();
    const div = document.createElement('div');
    div.className = direction === 'IN' ? 'log-in' : 'log-out';
    
    div.innerHTML = `
        <span class="log-time">[${time}] ${direction}</span> 
        <span class="log-topic">${topic}</span><br>
        <span class="log-payload">${payload}</span>
    `;
    
    logWindow.appendChild(div);
    logWindow.scrollTop = logWindow.scrollHeight; // Tự động cuộn xuống dòng mới nhất
}

// Xử lý nút Kết nối
document.getElementById('btnConnect').addEventListener('click', () => {
    const url = document.getElementById('brokerUrl').value;
    
    if (client && client.connected) {
        client.end();
    }

    appendLog('IN', 'SYSTEM', `Đang kết nối tới ${url}...`);
    
    // Khởi tạo Client với protocol MQTT v5
    client = mqtt.connect(url, {
        clientId: 'web_tester_' + Math.random().toString(16).substring(2, 8),
        protocolVersion: 5 
    });

    client.on('connect', () => {
        document.getElementById('btnConnect').innerText = 'Đã kết nối (Màu xanh)';
        document.getElementById('btnConnect').style.background = '#388E3C';
        appendLog('IN', 'SYSTEM', 'Kết nối thành công! Bắt đầu rình rập...');
        
        // Subscribe wildcard '#' để bắt MỌI gói tin trên hệ thống
        client.subscribe('#', (err) => {
            if (!err) appendLog('IN', 'SYSTEM', 'Đã subscribe wildcard: #');
        });
    });

    // Sự kiện hứng gói tin (Rất quan trọng)
    client.on('message', (topic, message) => {
        appendLog('IN', topic, message.toString());
    });

    client.on('error', (err) => {
        appendLog('IN', 'ERROR', err.message);
    });
});

// Xử lý nút Publish lệnh giả lập
document.getElementById('btnPublish').addEventListener('click', () => {
    if (!client || !client.connected) {
        alert("Vui lòng kết nối Broker trước!");
        return;
    }
    const topic = document.getElementById('pubTopic').value;
    const payload = document.getElementById('pubPayload').value;
    
    // Gửi đi với QoS 1 (như chuẩn đã quy định)
    client.publish(topic, payload, { qos: 1 }, (err) => {
        if (!err) {
            appendLog('OUT', topic, payload);
        } else {
            appendLog('OUT', 'ERROR', 'Gửi thất bại: ' + err);
        }
    });
});

// Xóa màn hình
document.getElementById('btnClear').addEventListener('click', () => {
    logWindow.innerHTML = '';
});
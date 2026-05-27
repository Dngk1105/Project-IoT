let client = null;
const logWindow = document.getElementById('log-window');

// ==========================================
// HỆ THỐNG ÂM THANH (WEB AUDIO API)
// ==========================================
let audioCtx = null;
let nextPlayTime = 0;

// Khởi tạo Card âm thanh ảo (Yêu cầu click từ người dùng)
document.getElementById('btnInitAudio').addEventListener('click', () => {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
    }
    if (audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
    document.getElementById('btnInitAudio').innerText = '✅ Loa đã mở! Sẵn sàng rống!';
    document.getElementById('btnInitAudio').style.background = '#4CAF50';
});

function playRawPCM(messageBuffer) {
    if (!audioCtx || audioCtx.state !== 'running') return; 

    // [FIX LỖI MEMORY ALIGNMENT] 
    // Tạo một bản sao độc lập để reset byteOffset về 0
    const safeBuffer = new Uint8Array(messageBuffer).buffer;
    
    // 1. Ép mảng byte thành mảng số nguyên 16-bit an toàn
    const int16Array = new Int16Array(safeBuffer);
    
    // 2. Chuyển sang mảng số thực Float32 (Chuẩn Web Audio)
    const float32Array = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0; 
    }

    // ... (Giữ nguyên các đoạn code khởi tạo AudioBuffer bên dưới)
    const audioBuffer = audioCtx.createBuffer(1, float32Array.length, 16000);
    audioBuffer.getChannelData(0).set(float32Array);

    const source = audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioCtx.destination);

    const currentTime = audioCtx.currentTime;
    if (nextPlayTime < currentTime) {
        nextPlayTime = currentTime + 0.05; 
    }

    source.start(nextPlayTime);
    nextPlayTime += audioBuffer.duration;
}


document.getElementById('btnSendBeep').addEventListener('click', () => {
    if (!client || !client.connected) {
        alert("Vui lòng kết nối Broker trước!");
        return;
    }

    // Cấu hình âm thanh chuẩn với ESP32: 16kHz, 16-bit Mono
    const sampleRate = 16000;
    const duration = 0.5; // Dài nửa giây
    const numSamples = sampleRate * duration; 
    const frequency = 440; // Tần số 440Hz (Nốt La chuẩn)
    const volume = 10000; // Biên độ (Max 32767, để 10000 cho khỏi cháy loa)

    // Tạo mảng 16-bit
    const pcmBuffer = new Int16Array(numSamples);
    
    // Đổ sóng Sin vào mảng
    for (let i = 0; i < numSamples; i++) {
        const t = i / sampleRate;
        pcmBuffer[i] = Math.sin(2 * Math.PI * frequency * t) * volume;
    }

    // Ép kiểu về mảng Byte (Uint8) để gửi qua mạng
    const payload = new Uint8Array(pcmBuffer.buffer);
    
    // Điền ID thiết bị của huynh vào đây
    const targetDeviceId = "e072a1d6f1bc"; 
    const topic = `iot_schedule/${targetDeviceId}/audio/stream_down`;

    // Bắn gói tin QoS 0 cho nhẹ mạng
    client.publish(topic, payload, { qos: 0 }, (err) => {
        if (!err) {
            appendLog('OUT', topic, `[🎵 Đã bắn tiếng Bíp: ${payload.length} bytes]`);
        } else {
            appendLog('OUT', 'ERROR', 'Gửi thất bại: ' + err);
        }
    });
});

// ==========================================
// HỆ THỐNG GIAO DIỆN & MQTT
// ==========================================

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
        if (topic.includes('audio')){
            appendLog('IN', topic, `[Nhận dữ liệu âm thanh: ${message.byteLength} bytes]`);
            playRawPCM(message);
        }
        else {
            appendLog('IN', topic, message.toString());
        }
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
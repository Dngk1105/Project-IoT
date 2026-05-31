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
    const bytes = new Uint8Array(messageBuffer);
    const safeBuffer = bytes.slice().buffer;
    
    // 1. Ép mảng byte thành mảng số nguyên 16-bit an toàn
    const int16Array = new Int16Array(safeBuffer);
    
    // 2. Chuyển sang mảng số thực Float32 (Chuẩn Web Audio)
    const float32Array = new Float32Array(int16Array.length);
    for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0; 
    }

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


document.getElementById('btnSendBeep').addEventListener('click', async () => {
    if (!client || !client.connected) {
        alert("Vui lòng kết nối Broker trước!");
        return;
    }

    // 🔴 CHÚ Ý: Huynh nhớ kiểm tra Serial Log của ESP32 để lấy đúng ID nhé!
    const targetDeviceId = "e072a1d6f1bc"; 
    const controlTopic = `iot_schedule/${targetDeviceId}/audio/control`;
    const streamTopic = `iot_schedule/${targetDeviceId}/audio/stream_down`;

    // 1. Tạo sóng Sin 440Hz dài 1 giây (16000 mẫu = 32000 bytes)
    const sampleRate = 16000;
    const duration = 1.0; 
    const numSamples = sampleRate * duration; 
    const frequency = 440; 
    const volume = 10000; 

    const pcmBuffer = new Int16Array(numSamples);
    for (let i = 0; i < numSamples; i++) {
        const t = i / sampleRate;
        pcmBuffer[i] = Math.sin(2 * Math.PI * frequency * t) * volume;
    }
    const fullPayload = new Uint8Array(pcmBuffer.buffer);

    // 2. GỬI LỆNH START (Mồi cho ESP32 mở amply)
    const sessionId = "beep_" + Math.floor(Math.random()*1000);
    const startPayload = JSON.stringify({
        msg_id: "msg_js_1",
        timestamp: Math.floor(Date.now() / 1000),
        v: "1.0",
        data: { 
            action: "start", 
            session_id: sessionId, 
            chunk_count: Math.ceil(fullPayload.length / 4096), 
            sample_rate: 16000 
        }
    });
    client.publish(controlTopic, startPayload, { qos: 1 });
    appendLog('OUT', controlTopic, `[START] Chuẩn bị gửi ${fullPayload.length} bytes`);

    // Đợi 150ms cho ESP32 cấp phát xong RAM I2S
    await new Promise(r => setTimeout(r, 150));

    // 3. BƠM DATA NHỊ PHÂN CÓ ĐIỀU TỐC (MÁY TẠO NHỊP)
    const chunkSize = 4096; // 4096 bytes = 128ms audio
    const totalChunks = Math.ceil(fullPayload.length / chunkSize);
    
    const startTime = Date.now(); // Lấy mốc thời gian gốc
    
    for (let i = 0; i < fullPayload.length; i += chunkSize) {
        const chunk = fullPayload.slice(i, i + chunkSize);
        
        client.publish(streamTopic, chunk, { qos: 0 });
        appendLog('OUT', streamTopic, `[Bơm chunk ${Math.floor(i/chunkSize) + 1}/${totalChunks}]`);
        
        // TÍNH TOÁN THỜI GIAN TUYỆT ĐỐI (Cách ly hoàn toàn sai số của setTimeout)
        const targetTime = startTime + ((i / chunkSize) + 1) * 90;
        const sleepDuration = targetTime - Date.now();
        
        // Chỉ ngủ bù phần thời gian còn thiếu
        if (sleepDuration > 0) {
            await new Promise(r => setTimeout(r, sleepDuration));
        }
    }

    // ========================================================
    // 4. GỬI LỆNH STOP (Báo ESP32 chốt file và xả sạch màng loa)
    // ĐÂY LÀ KHÚC HUYNH BỊ THIẾU Ở BẢN TRƯỚC ĐÓ!
    // ========================================================
    const stopPayload = JSON.stringify({
        msg_id: "msg_js_2",
        timestamp: Math.floor(Date.now() / 1000),
        v: "1.0",
        data: { action: "stop", session_id: sessionId }
    });
    client.publish(controlTopic, stopPayload, { qos: 1 });
    appendLog('OUT', controlTopic, `[STOP] Đã bắn xong tiếng Bíp! Báo ESP32 ngắt dòng!`);
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
    if (logWindow) logWindow.innerHTML = '';
});
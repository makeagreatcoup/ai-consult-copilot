/**
 * 咨询AI副驾 - 前端逻辑
 */
let ws = null;
let timerInterval = null;
let startTime = null;

// WebSocket 连接
function connectWebSocket() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onopen = () => console.log("WebSocket 已连接");
    ws.onclose = () => {
        console.log("WebSocket 断开，3秒后重连...");
        setTimeout(connectWebSocket, 3000);
    };
    ws.onerror = (err) => console.error("WebSocket 错误:", err);

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleMessage(data);
    };
}

// 处理服务端消息
function handleMessage(data) {
    switch (data.type) {
        case "transcript":
            addTranscript(data);
            break;
        case "suggestion":
            addSuggestion(data);
            break;
        case "status":
            updateStatus(data);
            break;
        case "mode_changed":
            break;
    }
}

// 添加对话记录
function addTranscript(data) {
    const list = document.getElementById("transcriptList");
    // 移除空提示
    const hint = list.querySelector(".empty-hint");
    if (hint) hint.remove();

    const isSelf = data.source === "mic";
    const item = document.createElement("div");
    item.className = "transcript-item";
    item.innerHTML = `
        <div class="time">${data.time}</div>
        <div class="speaker ${isSelf ? "self" : "user"}">${data.speaker}</div>
        <div class="text">${escapeHtml(data.text)}</div>
    `;
    list.appendChild(item);
    list.scrollTop = list.scrollHeight;
}

// 添加AI建议
function addSuggestion(data) {
    const list = document.getElementById("suggestionList");
    const hint = list.querySelector(".empty-hint");
    if (hint) hint.remove();

    const item = document.createElement("div");
    item.className = `suggestion-item ${data.suggestion_type === "refine" ? "refine" : ""}`;
    item.innerHTML = `
        <div class="time">${data.time}</div>
        <div class="label">${data.label}</div>
        <div class="text">${escapeHtml(data.text)}</div>
        <div class="trigger">基于: "${escapeHtml(data.trigger)}..."</div>
    `;
    list.appendChild(item);
    list.scrollTop = list.scrollHeight;
}

// 更新状态
function updateStatus(data) {
    const badge = document.getElementById("statusBadge");
    const btnStart = document.getElementById("btnStart");
    const btnStop = document.getElementById("btnStop");

    if (data.status === "active") {
        badge.textContent = "进行中";
        badge.className = "status-badge active";
        btnStart.disabled = true;
        btnStop.disabled = false;
        startTime = data.start_time;
        startTimer();
    } else if (data.status === "ended") {
        badge.textContent = "已结束";
        badge.className = "status-badge ended";
        btnStart.disabled = false;
        btnStop.disabled = true;
        stopTimer();
    }
}

// 计时器
function startTimer() {
    stopTimer();
    timerInterval = setInterval(() => {
        if (!startTime) return;
        const elapsed = Math.floor(Date.now() / 1000 - startTime);
        const h = String(Math.floor(elapsed / 3600)).padStart(2, "0");
        const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, "0");
        const s = String(elapsed % 60).padStart(2, "0");
        document.getElementById("timer").textContent = `${h}:${m}:${s}`;
    }, 1000);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

// 控制命令
function startSession() {
    const mode = document.getElementById("modeSelect").value;
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: "start", mode }));
    }
}

function stopSession() {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ command: "stop" }));
    }
}

// 工具函数
function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// 初始化
document.addEventListener("DOMContentLoaded", () => {
    connectWebSocket();

    document.getElementById("modeSelect").addEventListener("change", (e) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ command: "switch_mode", mode: e.target.value }));
        }
    });
});

if (!window.APP_CONFIG || !window.APP_CONFIG.API_URL) {
    console.error("Missing frontend config. Please check static/config.js");
    alert("System Error: Missing APP_CONFIG. Please check static/config.js");
}

const API_URL = window.APP_CONFIG ? window.APP_CONFIG.API_URL : null;
const WS_URL = window.APP_CONFIG ? window.APP_CONFIG.WS_URL : null;

console.log("🚀 Using API_URL:", API_URL);
console.log("🔌 Using WS_URL:", WS_URL);

let token = localStorage.getItem("token");

// --- Canvas Particle System ---
const canvas = document.getElementById('bgCanvas');
const ctx = canvas ? canvas.getContext('2d') : null;
let particles = [];

function initCanvas() {
    if (!canvas) return;
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}

class Particle {
    constructor() {
        this.x = Math.random() * canvas.width;
        this.y = Math.random() * canvas.height;
        this.size = Math.random() * 2 + 1;
        this.speedX = Math.random() * 1 - 0.5;
        this.speedY = Math.random() * 1 - 0.5;
        this.color = 'rgba(79, 70, 229, 0.1)';
    }
    update() {
        this.x += this.speedX;
        this.y += this.speedY;
        if (this.x > canvas.width) this.x = 0;
        else if (this.x < 0) this.x = canvas.width;
        if (this.y > canvas.height) this.y = 0;
        else if (this.y < 0) this.y = canvas.height;
    }
    draw() {
        ctx.fillStyle = this.color;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
        ctx.fill();
    }
}

function createParticles() {
    if (!canvas) return;
    particles = [];
    const count = (canvas.width * canvas.height) / 15000;
    for (let i = 0; i < count; i++) {
        particles.push(new Particle());
    }
}

function animateParticles() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    particles.forEach(p => {
        p.update();
        p.draw();
    });
    requestAnimationFrame(animateParticles);
}

window.addEventListener('resize', () => {
    initCanvas();
    createParticles();
});

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

function renderMarkdown(value) {
    const source = String(value ?? "");
    if (!window.marked || !window.DOMPurify) {
        return escapeHtml(source).replace(/\n/g, "<br>");
    }

    const html = window.marked.parse(source, {
        breaks: true,
        gfm: true
    });

    return window.DOMPurify.sanitize(html);
}

function appendChatMessage(chatBox, role, label, message) {
    const messageEl = document.createElement("div");
    messageEl.className = `${role}-message chat-message`;

    const labelEl = document.createElement("strong");
    labelEl.className = "message-label";
    labelEl.textContent = `${label}:`;

    const contentEl = document.createElement("div");
    contentEl.className = "message-content markdown-body";
    contentEl.innerHTML = renderMarkdown(message);

    messageEl.append(labelEl, contentEl);
    chatBox.appendChild(messageEl);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function toggleAssistantWidget(widgetName, forceOpen) {
    const widget = document.querySelector(`.assistant-widget[data-widget="${widgetName}"]`);
    if (!widget) return;

    const shouldOpen = typeof forceOpen === "boolean"
        ? forceOpen
        : !widget.classList.contains("open");

    widget.classList.toggle("open", shouldOpen);
}

// --- App Logic ---
window.onload = () => {
    const urlParams = new URLSearchParams(window.location.search);
    const paymentStatus = urlParams.get("payment");
    if (paymentStatus === "success") {
        alert("Payment Successful!");
        window.history.replaceState({}, document.title, "/");
    }
    if (token) showApp();
};

function showAlert(msg) {
    const alertBox = document.getElementById("alertBox");
    alertBox.innerText = msg;
    setTimeout(() => alertBox.innerText = "", 5000);
}

function setAvatarState(state) {
    const container = document.getElementById("avatarContainer");
    const label = document.getElementById("avatarLabel");
    if (!container || !label) return;
    container.className = `avatar-container state-${state}`;
    label.innerText = state.toUpperCase();
}

function updateStatusUI(isPro) {
    const statusEl = document.getElementById("userStatus");
    const upgradeBtn = document.querySelector(".btn-pro");
    if (isPro) {
        statusEl.innerText = "PRO ACCOUNT ✨";
        statusEl.className = "text-[10px] font-black text-indigo-600 uppercase tracking-widest";
        if (upgradeBtn) upgradeBtn.style.display = "none";
    } else {
        statusEl.innerText = "FREE ACCOUNT";
        statusEl.className = "text-[10px] font-black text-slate-400 uppercase tracking-widest";
        if (upgradeBtn) upgradeBtn.style.display = "block";
    }
}

async function register() {
    const u = document.getElementById("username").value;
    const p = document.getElementById("password").value;
    const res = await fetch(`${API_URL}/auth/register`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p })
    });
    const data = await res.json();
    if (res.status === 200) {
        showAlert("Registration successful! Logging you in...");
        // Automatically login after successful registration
        setTimeout(() => login(), 1000);
    } else {
        showAlert(data.detail || data.message);
    }
}

async function login() {
    const u = document.getElementById("username").value;
    const p = document.getElementById("password").value;
    const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: u, password: p })
    });
    const data = await res.json();
    if (data.token) {
        token = data.token;
        localStorage.setItem("token", token);
        updateStatusUI(data.is_pro);
        showApp();
    } else {
        showAlert(data.detail || "Login failed");
    }
}

function logout() {
    localStorage.removeItem("token");
    token = null;
    document.getElementById("authSection").classList.remove("hidden");
    document.getElementById("appSection").classList.add("hidden");
    document.getElementById("trainingSection").classList.add("hidden");
    document.getElementById("chatBox").innerHTML = "";
    updateStatusUI(false);
}

async function showApp() {
    document.getElementById("authSection").classList.add("hidden");
    document.getElementById("appSection").classList.remove("hidden");
    document.getElementById("trainingSection").classList.remove("hidden");

    const res = await fetch(`${API_URL}/auth/me`, {
        headers: { "X-Token": token }
    });
    if (res.status === 200) {
        const data = await res.json();
        document.getElementById("userIdDisplay").innerText = data.id;
        updateStatusUI(data.is_pro);
    } else if (res.status === 401) {
        logout();
        return;
    }
    loadHistory();
    loadTrainedTasks();
}

async function loadTrainedTasks() {
    const res = await fetch(`${API_URL}/automation/tasks`, {
        headers: { "X-Token": token }
    });
    if (res.status === 200) {
        const tasks = await res.json();
        const taskList = document.getElementById("taskList");
        taskList.innerHTML = "";
        tasks.forEach(task => {
            taskList.innerHTML += `
                <li class="flex flex-col gap-2 p-4 bg-white/50 rounded-xl border border-slate-100">
                    <div class="flex items-center justify-between">
                        <span class="text-sm font-bold text-slate-700">${task.name}</span>
                        <div class="flex gap-2">
                            <button onclick="executeTrainedTask('${task.id}')" class="px-4 py-2 bg-indigo-600 text-white rounded-lg text-xs font-black hover:bg-indigo-700 transition-all shadow-md">RUN</button>
                            <button onclick="editTask('${task.id}', '${task.name.replace(/'/g, "\\'")}', '${(task.note || '').replace(/'/g, "\\'")}')" class="px-4 py-2 bg-amber-500 text-white rounded-lg text-xs font-black hover:bg-amber-600 transition-all shadow-md">EDIT</button>
                            <button onclick="deleteTask('${task.id}')" class="px-4 py-2 bg-rose-500 text-white rounded-lg text-xs font-black hover:bg-rose-600 transition-all shadow-md">DEL</button>
                        </div>
                    </div>
                    ${task.note ? `<p class="text-[10px] text-slate-400 italic">Note: ${task.note}</p>` : ''}
                </li>`;
        });
    }
}

async function editTask(taskId, currentName, currentNote) {
    const newName = prompt("Enter new Skill Name:", currentName);
    if (newName === null) return;
    
    const newNote = prompt("Enter new Note (optional):", currentNote);
    if (newNote === null) return;

    const res = await fetch(`${API_URL}/automation/tasks/${taskId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-Token": token },
        body: JSON.stringify({ name: newName, note: newNote })
    });
    
    if (res.status === 200) {
        showAlert("Skill updated!");
        loadTrainedTasks();
    } else {
        const data = await res.json();
        showAlert(data.detail || "Update failed");
    }
}

function startTraining() {
    document.getElementById("floatingToolbar").style.display = "flex";
}

async function ftStartTraining() {
    const res = await fetch(`${API_URL}/automation/training/start`, {
        method: "POST", headers: { "X-Token": token }
    });
    if (res.status === 200) {
        document.getElementById("ftStartBtn").style.display = "none";
        document.getElementById("ftFinishBtn").style.display = "inline-block";
    }
}

function ftFinishTraining() {
    document.getElementById("floatingToolbar").style.display = "none";
    document.getElementById("saveTaskDiv").style.display = "block";
}

function ftClose() {
    document.getElementById("floatingToolbar").style.display = "none";
}

async function saveTask() {
    const name = document.getElementById("taskNameInput").value;
    if (!name) { showAlert("Enter name"); return; }
    const res = await fetch(`${API_URL}/automation/training/stop`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-Token": token },
        body: JSON.stringify({ name: name })
    });
    if (res.status === 200) {
        showAlert("Task will be saved when agent finishes!");
        document.getElementById("saveTaskDiv").style.display = "none";
        document.getElementById("taskNameInput").value = "";
        setTimeout(() => loadTrainedTasks(), 1500); // Wait for agent to upload data via WS
    }
}

async function executeTrainedTask(taskId) {
    setAvatarState('thinking');
    const res = await fetch(`${API_URL}/automation/execute/${taskId}`, {
        method: "POST", headers: { "X-Token": token }
    });
    const data = await res.json();
    if (res.status === 200) {
        setAvatarState('acting');
        setTimeout(() => setAvatarState('idle'), 3000); // Back to idle after a while
        alert("Skill Result: " + data.message);
    } else {
        setAvatarState('error');
        setTimeout(() => setAvatarState('idle'), 3000);
        alert("Error: " + (data.detail || data.message));
    }
}

async function deleteTask(taskId) {
    if (!confirm("Delete skill?")) return;
    const res = await fetch(`${API_URL}/automation/tasks/${taskId}`, {
        method: "DELETE", headers: { "X-Token": token }
    });
    if (res.status === 200) loadTrainedTasks();
}

async function sendMessage() {
    const msg = document.getElementById("messageInput").value;
    if (!msg) return;
    const chatBox = document.getElementById("chatBox");
    appendChatMessage(chatBox, "user", "You", msg);
    document.getElementById("messageInput").value = "";
    
    setAvatarState('thinking');
    document.getElementById("agentLogsContainer").classList.remove("hidden");
    const logsUl = document.getElementById("agentLogs");
    logsUl.innerHTML = ""; // clear previous logs
    
    try {
        const res = await fetch(`${API_URL}/agent/chat`, {
            method: "POST", headers: { "Content-Type": "application/json", "X-Token": token },
            body: JSON.stringify({ message: msg })
        });
        
        if (res.status === 400 || res.status === 500) {
            const data = await res.json();
            setAvatarState('error');
            setTimeout(() => setAvatarState('idle'), 3000);
            showAlert(data.detail || "Error starting agent loop.");
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                if (document.getElementById("avatarLabel").innerText !== 'WAITING_CONFIRMATION') {
                    setAvatarState('idle');
                }
                break;
            }
            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
            const lines = buffer.split('\n');
            buffer = lines.pop(); // keep the last incomplete line in buffer
            
            for (let line of lines) {
                if (!line.trim()) continue;
                try {
                    const data = JSON.parse(line);
                    
                    // Update state
                    if (data.state) {
                        setAvatarState(data.state);
                    }
                    
                    // Update logs
                    if (data.message) {
                        const li = document.createElement("li");
                        li.innerText = `> ${data.message}`;
                        if (data.type === "error") li.className = "text-rose-500";
                        if (data.type === "final") li.className = "text-amber-300 font-bold";
                        logsUl.appendChild(li);
                        
                        // Limit to 50 logs
                        while (logsUl.children.length > 50) {
                            logsUl.removeChild(logsUl.firstChild);
                        }
                        logsUl.scrollTop = logsUl.scrollHeight;
                        
                        if (data.type === 'final') {
                            appendChatMessage(chatBox, "ai", "AI", data.message);
                            
                            const utterance = new SpeechSynthesisUtterance(data.message);
                            utterance.onstart = () => document.getElementById("stopSpeakBtn").style.display = "block";
                            utterance.onend = () => document.getElementById("stopSpeakBtn").style.display = "none";
                            window.speechSynthesis.speak(utterance);
                            
                            // Hide confirmation box if it was showing
                            document.getElementById("confirmationBox").classList.add("hidden");
                        }
                    }
                    
                    if (data.state === 'waiting_confirmation') {
                        const confBox = document.getElementById("confirmationBox");
                        confBox.classList.remove("hidden");
                        document.getElementById("confirmationText").innerText = data.message || "AI needs confirmation to proceed.";
                    } else {
                        document.getElementById("confirmationBox").classList.add("hidden");
                    }
                } catch(e) {
                    console.error("Error parsing JSON chunk", line, e);
                }
            }
        }
        
    } catch (e) {
        setAvatarState('error');
        setTimeout(() => setAvatarState('idle'), 3000);
        showAlert("Connection error.");
    }
}

async function stopAgent() {
    try {
        const res = await fetch(`${API_URL}/agent/stop`, {
            method: "POST", headers: { "X-Token": token }
        });
        if (res.status === 200) {
            showAlert("Agent stop signal sent.");
            document.getElementById("confirmationBox").classList.add("hidden");
        }
    } catch (e) {
        console.error(e);
    }
}

async function confirmAction(action) {
    document.getElementById("confirmationBox").classList.add("hidden");
    try {
        await fetch(`${API_URL}/agent/confirm`, {
            method: "POST", headers: { "Content-Type": "application/json", "X-Token": token },
            body: JSON.stringify({ action: action })
        });
    } catch (e) {
        console.error(e);
    }
}

async function clearChat() {
    if (!confirm("Clear the current chat history?")) return;

    try {
        const res = await fetch(`${API_URL}/history`, {
            method: "DELETE",
            headers: { "X-Token": token }
        });

        if (res.status === 200) {
            document.getElementById("chatBox").innerHTML = "";
            document.getElementById("agentLogs").innerHTML = "";
            document.getElementById("agentLogsContainer").classList.add("hidden");
            document.getElementById("confirmationBox").classList.add("hidden");
            showAlert("Chat cleared.");
            return;
        }

        const data = await res.json();
        showAlert(data.detail || data.message || "Unable to clear chat.");
    } catch (e) {
        console.error(e);
        showAlert("Connection error.");
    }
}

async function loadHistory() {
    const res = await fetch(`${API_URL}/history`, { headers: { "X-Token": token } });
    if (res.status === 200) {
        const data = await res.json();
        const chatBox = document.getElementById("chatBox");
        chatBox.innerHTML = "";
        data.reverse().forEach(item => {
            appendChatMessage(chatBox, "user", "You", item.message);
            appendChatMessage(chatBox, "ai", "AI", item.response);
        });
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

async function upgradePro() {
    const res = await fetch(`${API_URL}/payment/create_url`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-Token": token },
        body: JSON.stringify({ amount: 50000 })
    });
    if (res.status === 200) {
        const data = await res.json();
        window.location.href = data.url;
    }
}

function stopSpeaking() {
    window.speechSynthesis.cancel();
    document.getElementById("stopSpeakBtn").style.display = "none";
}

let recognition;
let isRecording = false;
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = 'vi-VN';
    recognition.onstart = () => {
        setAvatarState('listening');
        const btn = document.getElementById("recordBtn");
        btn.innerText = "🛑 Recording...";
        btn.className = "flex-1 py-2.5 bg-rose-500 text-white rounded-lg text-xs font-bold";
        isRecording = true;
    };
    recognition.onresult = (event) => {
        document.getElementById("messageInput").value = event.results[0][0].transcript;
        sendMessage();
    };
    recognition.onend = () => {
        if (document.getElementById("avatarLabel").innerText === 'LISTENING') {
            setAvatarState('idle');
        }
        const btn = document.getElementById("recordBtn");
        btn.innerText = "🎤 Speak Command";
        btn.className = "flex-1 btn-outline py-2.5 text-xs";
        isRecording = false;
    };
}
function toggleRecording() {
    if (!recognition) return;
    if (!isRecording) recognition.start();
    else recognition.stop();
}

function togglePassword() {
    const pwd = document.getElementById("password");
    const eyeIcon = document.getElementById("eyeIcon");
    if (pwd.type === "password") {
        pwd.type = "text";
        eyeIcon.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line>';
    } else {
        pwd.type = "password";
        eyeIcon.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle>';
    }
}

const API_URL = "http://localhost:8000";
let token = localStorage.getItem("token");

// --- Canvas Particle System ---
const canvas = document.getElementById('bgCanvas');
const ctx = canvas.getContext('2d');
let particles = [];

function initCanvas() {
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
    particles = [];
    const count = (canvas.width * canvas.height) / 15000;
    for (let i = 0; i < count; i++) {
        particles.push(new Particle());
    }
}

function animateParticles() {
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
        showAlert("Task saved!");
        document.getElementById("saveTaskDiv").style.display = "none";
        document.getElementById("taskNameInput").value = "";
        loadTrainedTasks();
    }
}

async function executeTrainedTask(taskId) {
    const res = await fetch(`${API_URL}/automation/execute/${taskId}`, {
        method: "POST", headers: { "X-Token": token }
    });
    const data = await res.json();
    alert("Skill Result: " + data.message);
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
    chatBox.innerHTML += `<div class="user-message"><b>You:</b> ${msg}</div>`;
    document.getElementById("messageInput").value = "";
    const res = await fetch(`${API_URL}/chat`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-Token": token },
        body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    if (res.status === 200) {
        chatBox.innerHTML += `<div class="ai-message"><b>AI:</b> ${data.response}</div>`;
        const utterance = new SpeechSynthesisUtterance(data.response);
        utterance.onstart = () => document.getElementById("stopSpeakBtn").style.display = "block";
        utterance.onend = () => document.getElementById("stopSpeakBtn").style.display = "none";
        window.speechSynthesis.speak(utterance);
    }
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function loadHistory() {
    const res = await fetch(`${API_URL}/history`, { headers: { "X-Token": token } });
    if (res.status === 200) {
        const data = await res.json();
        const chatBox = document.getElementById("chatBox");
        chatBox.innerHTML = "";
        data.reverse().forEach(item => {
            chatBox.innerHTML += `<div class="user-message"><b>You:</b> ${item.message}</div>`;
            chatBox.innerHTML += `<div class="ai-message"><b>AI:</b> ${item.response}</div>`;
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

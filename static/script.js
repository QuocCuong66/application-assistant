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

let lastUserPrompt = "";
let chatRequestInFlight = false;

const FEEDBACK_STORAGE_KEY = "chat_message_feedback";

function configureMarkdown() {
    if (!window.marked) return;
    window.marked.setOptions({
        breaks: true,
        gfm: true,
        headerIds: false,
        mangle: false
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", configureMarkdown);
} else {
    configureMarkdown();
}

function renderMarkdown(value) {
    const source = String(value ?? "").trim();
    if (!source) return "";

    if (!window.marked || !window.DOMPurify) {
        return escapeHtml(source).replace(/\n/g, "<br>");
    }

    const html = window.marked.parse(source);
    return window.DOMPurify.sanitize(html, {
        USE_PROFILES: { html: true }
    });
}

function getChatFeedbackMap() {
    try {
        return JSON.parse(localStorage.getItem(FEEDBACK_STORAGE_KEY) || "{}");
    } catch {
        return {};
    }
}

function saveMessageFeedback(messageId, value) {
    const map = getChatFeedbackMap();
    map[messageId] = value;
    localStorage.setItem(FEEDBACK_STORAGE_KEY, JSON.stringify(map));
}

function scrollChatToBottom() {
    const chatBox = document.getElementById("chatBox");
    if (!chatBox) return;
    chatBox.scrollTop = chatBox.scrollHeight;
}

const SKILL_STATUS_LABELS = {
    ready: "Ready",
    active: "Active",
    training: "Training",
    locked: "Locked",
    disabled: "Disabled"
};

function setSkillStatus(skillId, status) {
    if (!skillId || !status) return;
    const normalized = status === "running" ? "training" : status;
    const card = document.querySelector(`.skill-card[data-skill="${skillId}"]`);
    if (!card) return;
    card.dataset.status = normalized;
    const label = card.querySelector(".skill-status");
    if (label) {
        label.textContent = SKILL_STATUS_LABELS[normalized] || normalized;
    }
}

function resetAllSkillStatuses() {
    document.querySelectorAll(".skill-card[data-skill]").forEach((card) => {
        setSkillStatus(card.dataset.skill, "ready");
    });
}

function handleStreamIntentEvent(data) {
    if (data.skill_id && data.skill_status) {
        setSkillStatus(data.skill_id, data.skill_status);
    }
}

let streamingAiRow = null;

function ensureStreamingAiBubble(chatBox, userPrompt) {
    if (streamingAiRow) return streamingAiRow;
    const row = document.createElement("div");
    row.className = "chat-row ai-row streaming-row";
    row.dataset.userPrompt = userPrompt || lastUserPrompt;

    const avatar = document.createElement("span");
    avatar.className = "chat-avatar";
    avatar.textContent = "AI";

    const wrap = document.createElement("div");
    wrap.className = "chat-bubble-wrap";

    const messageEl = document.createElement("div");
    messageEl.className = "ai-message chat-message";

    const labelEl = document.createElement("strong");
    labelEl.className = "message-label";
    labelEl.textContent = "AI";

    const contentEl = document.createElement("div");
    contentEl.className = "message-content markdown-body";
    contentEl.dataset.rawText = "";

    messageEl.append(labelEl, contentEl);
    wrap.appendChild(messageEl);
    row.append(avatar, wrap);
    chatBox.appendChild(row);
    streamingAiRow = row;
    scrollChatToBottom();
    return row;
}

function updateStreamingAiBubble(chatBox, text, userPrompt) {
    const row = ensureStreamingAiBubble(chatBox, userPrompt);
    const contentEl = row.querySelector(".message-content");
    if (!contentEl) return;
    contentEl.dataset.rawText = text;
    contentEl.innerHTML = renderMarkdown(text);
    scrollChatToBottom();
}

function finalizeStreamingAiBubble(chatBox, text, userPrompt) {
    if (!streamingAiRow) {
        appendChatMessage(chatBox, "ai", "AI", text, { userPrompt: userPrompt || lastUserPrompt });
        return;
    }
    const row = streamingAiRow;
    const messageId = `ai-${Date.now()}`;
    row.classList.remove("streaming-row");
    row.dataset.messageId = messageId;
    row.dataset.userPrompt = userPrompt || lastUserPrompt;

    const contentEl = row.querySelector(".message-content");
    if (contentEl) {
        contentEl.dataset.rawText = text;
        contentEl.innerHTML = renderMarkdown(text);
    }

    const wrap = row.querySelector(".chat-bubble-wrap");
    if (wrap && !wrap.querySelector(".message-actions")) {
        const actions = document.createElement("div");
        actions.className = "message-actions";
        actions.append(
            createMessageActionButton("Copy", "Copy response", () => copyMessageText(text)),
            createMessageActionButton("↻", "Regenerate response", () =>
                regenerateFromPrompt(userPrompt || lastUserPrompt, row)
            ),
            (() => {
                const likeBtn = createMessageActionButton("♥", "Like response", () => {
                    saveMessageFeedback(messageId, "like");
                    setFeedbackButtonState(actions, messageId);
                });
                likeBtn.dataset.action = "like";
                return likeBtn;
            })(),
            (() => {
                const dislikeBtn = createMessageActionButton("♡", "Dislike response", () => {
                    saveMessageFeedback(messageId, "dislike");
                    setFeedbackButtonState(actions, messageId);
                });
                dislikeBtn.dataset.action = "dislike";
                return dislikeBtn;
            })()
        );
        setFeedbackButtonState(actions, messageId);
        wrap.appendChild(actions);
    }
    streamingAiRow = null;
    scrollChatToBottom();
}

function setChatTyping(visible) {
    const typing = document.getElementById("chatTyping");
    if (!typing) return;
    typing.classList.toggle("hidden", !visible);
    if (visible) scrollChatToBottom();
}

function createMessageActionButton(label, title, onClick) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "msg-action-btn";
    btn.textContent = label;
    btn.title = title;
    btn.setAttribute("aria-label", title);
    btn.addEventListener("click", onClick);
    return btn;
}

function copyMessageText(text) {
    const value = String(text ?? "");
    if (!value) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(value).then(() => showAlert("Copied to clipboard.")).catch(() => fallbackCopy(value));
    } else {
        fallbackCopy(value);
    }
}

function fallbackCopy(text) {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.left = "-9999px";
    document.body.appendChild(area);
    area.select();
    try {
        document.execCommand("copy");
        showAlert("Copied to clipboard.");
    } catch {
        showAlert("Unable to copy.");
    }
    document.body.removeChild(area);
}

function setFeedbackButtonState(actionsEl, messageId) {
    const feedback = getChatFeedbackMap()[messageId];
    actionsEl.querySelectorAll(".msg-action-btn").forEach((btn) => {
        btn.classList.remove("active-like", "active-dislike");
    });
    if (feedback === "like") {
        actionsEl.querySelector('[data-action="like"]')?.classList.add("active-like");
    }
    if (feedback === "dislike") {
        actionsEl.querySelector('[data-action="dislike"]')?.classList.add("active-dislike");
    }
}

function appendChatMessage(chatBox, role, label, message, options = {}) {
    const isUser = role === "user";
    const row = document.createElement("div");
    row.className = `chat-row ${isUser ? "user-row" : "ai-row"}`;

    const avatar = document.createElement("span");
    avatar.className = "chat-avatar";
    avatar.textContent = isUser ? "You" : "AI";
    avatar.setAttribute("aria-hidden", "true");

    const wrap = document.createElement("div");
    wrap.className = "chat-bubble-wrap";

    const messageEl = document.createElement("div");
    messageEl.className = `${role}-message chat-message`;

    const labelEl = document.createElement("strong");
    labelEl.className = "message-label";
    labelEl.textContent = label;

    const contentEl = document.createElement("div");
    contentEl.className = "message-content markdown-body";
    contentEl.innerHTML = renderMarkdown(message);

    messageEl.append(labelEl, contentEl);
    wrap.appendChild(messageEl);

    if (!isUser) {
        const messageId = options.messageId || `ai-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
        const userPrompt = options.userPrompt || "";
        row.dataset.messageId = messageId;
        if (userPrompt) row.dataset.userPrompt = userPrompt;

        const actions = document.createElement("div");
        actions.className = "message-actions";

        actions.append(
            createMessageActionButton("Copy", "Copy response", () => copyMessageText(message)),
            createMessageActionButton("↻", "Regenerate response", () => regenerateFromPrompt(userPrompt || lastUserPrompt, row)),
            (() => {
                const likeBtn = createMessageActionButton("♥", "Like response", () => {
                    saveMessageFeedback(messageId, "like");
                    setFeedbackButtonState(actions, messageId);
                });
                likeBtn.dataset.action = "like";
                return likeBtn;
            })(),
            (() => {
                const dislikeBtn = createMessageActionButton("♡", "Dislike response", () => {
                    saveMessageFeedback(messageId, "dislike");
                    setFeedbackButtonState(actions, messageId);
                });
                dislikeBtn.dataset.action = "dislike";
                return dislikeBtn;
            })()
        );

        setFeedbackButtonState(actions, messageId);
        wrap.appendChild(actions);
    }

    row.append(avatar, wrap);
    chatBox.appendChild(row);
    scrollChatToBottom();
}

async function regenerateFromPrompt(prompt, aiRow) {
    const text = String(prompt || "").trim();
    if (!text || chatRequestInFlight) {
        if (!text) showAlert("No previous prompt to regenerate.");
        return;
    }
    if (aiRow && aiRow.parentElement) {
        aiRow.remove();
    }
    document.getElementById("messageInput").value = text;
    await sendMessage(text, { skipUserBubble: true });
}

function toggleAssistantWidget(widgetName, forceOpen) {
    const widget = document.querySelector(`.assistant-widget[data-widget="${widgetName}"]`);
    if (!widget) return;

    const shouldOpen = typeof forceOpen === "boolean"
        ? forceOpen
        : !widget.classList.contains("open");

    document.querySelectorAll(".assistant-widget").forEach((item) => {
        const isTarget = item === widget;
        item.classList.toggle("open", isTarget && shouldOpen);
    });

    document.querySelectorAll("[data-widget-toggle]").forEach((button) => {
        const isTarget = button.dataset.widgetToggle === widgetName;
        button.classList.toggle("active", isTarget && shouldOpen);
        button.setAttribute("aria-expanded", String(isTarget && shouldOpen));
    });

    if (widgetName === "chat" && shouldOpen) {
        setTimeout(() => {
            document.getElementById("messageInput")?.focus();
            scrollChatToBottom();
        }, 120);
    }
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
        statusEl.innerText = "Pro Account";
        statusEl.className = "status-pro";
        if (upgradeBtn) upgradeBtn.style.display = "none";
    } else {
        statusEl.innerText = "Free Access";
        statusEl.className = "status-free";
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
    toggleAssistantWidget("chat", false);
    toggleAssistantWidget("skill", false);
    updateStatusUI(false);
}

async function showApp() {
    document.getElementById("authSection").classList.add("hidden");
    document.getElementById("appSection").classList.remove("hidden");
    document.getElementById("trainingSection").classList.remove("hidden");
    toggleAssistantWidget("chat", true);
    toggleAssistantWidget("skill", false);

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

async function sendMessage(presetMessage, options = {}) {
    const input = document.getElementById("messageInput");
    const msg = String(presetMessage ?? input?.value ?? "").trim();
    if (!msg || chatRequestInFlight) return;

    const chatBox = document.getElementById("chatBox");
    lastUserPrompt = msg;

    if (!options.skipUserBubble) {
        appendChatMessage(chatBox, "user", "You", msg);
    }
    if (input) input.value = "";

    chatRequestInFlight = true;
    streamingAiRow = null;
    setChatTyping(true);
    setAvatarState("thinking");
    document.getElementById("agentLogsContainer").classList.remove("hidden");
    const logsUl = document.getElementById("agentLogs");
    logsUl.innerHTML = "";

    try {
        const res = await fetch(`${API_URL}/agent/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Token": token },
            body: JSON.stringify({ message: msg })
        });

        if (res.status === 400 || res.status === 500) {
            const data = await res.json().catch(() => ({}));
            setAvatarState("error");
            setTimeout(() => setAvatarState("idle"), 3000);
            showAlert(data.detail || "Chat request failed.");
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                if (document.getElementById("avatarLabel").innerText !== "WAITING_CONFIRMATION") {
                    setAvatarState("idle");
                }
                break;
            }
            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
            const lines = buffer.split("\n");
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const data = JSON.parse(line);

                    if (data.type === "intent") {
                        handleStreamIntentEvent(data);
                    }

                    if (data.state) {
                        setAvatarState(data.state);
                    }

                    if (data.type === "partial" && data.message) {
                        setChatTyping(false);
                        updateStreamingAiBubble(chatBox, data.message, msg);
                    }

                    if (data.message) {
                        const li = document.createElement("li");
                        li.innerText = `> ${data.message}`;
                        if (data.type === "error") li.style.color = "var(--danger)";
                        if (data.type === "final") li.style.color = "var(--warning)";
                        if (data.type !== "partial") {
                            logsUl.appendChild(li);
                            while (logsUl.children.length > 50) {
                                logsUl.removeChild(logsUl.firstChild);
                            }
                            logsUl.scrollTop = logsUl.scrollHeight;
                        }

                        if (data.type === "final") {
                            setChatTyping(false);
                            finalizeStreamingAiBubble(chatBox, data.message, msg);

                            const utterance = new SpeechSynthesisUtterance(data.message);
                            utterance.onstart = () => {
                                document.getElementById("stopSpeakBtn").style.display = "block";
                            };
                            utterance.onend = () => {
                                document.getElementById("stopSpeakBtn").style.display = "none";
                            };
                            window.speechSynthesis.speak(utterance);

                            if (data.state !== "waiting_confirmation") {
                                document.getElementById("confirmationBox").classList.add("hidden");
                            }
                        }
                    }

                    if (data.state === "waiting_confirmation") {
                        const confBox = document.getElementById("confirmationBox");
                        confBox.classList.remove("hidden");
                        document.getElementById("confirmationText").innerText =
                            data.message || "AI needs confirmation to proceed.";
                    } else if (data.type === "final" && data.state !== "waiting_confirmation") {
                        document.getElementById("confirmationBox").classList.add("hidden");
                    }
                } catch (e) {
                    console.error("Error parsing JSON chunk", line, e);
                }
            }
        }
    } catch (e) {
        setAvatarState("error");
        setTimeout(() => setAvatarState("idle"), 3000);
        showAlert("Connection error.");
    } finally {
        chatRequestInFlight = false;
        setChatTyping(false);
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
    const confBox = document.getElementById("confirmationBox");
    try {
        const res = await fetch(`${API_URL}/agent/confirm`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Token": token },
            body: JSON.stringify({ action })
        });
        const data = await res.json().catch(() => ({}));
        confBox.classList.add("hidden");

        if (data.skill_id && data.skill_status) {
            setSkillStatus(data.skill_id, data.skill_status);
        }

        if (data.executed && data.message) {
            const chatBox = document.getElementById("chatBox");
            appendChatMessage(chatBox, "ai", "AI", data.message, {
                userPrompt: lastUserPrompt,
                messageId: `ai-confirm-${Date.now()}`
            });
            setAvatarState("acting");
            setTimeout(() => setAvatarState("idle"), 2000);
            return;
        }

        if (data.message && action === "cancel") {
            const chatBox = document.getElementById("chatBox");
            appendChatMessage(chatBox, "ai", "AI", data.message, { userPrompt: lastUserPrompt });
        }

        if (action === "confirm" && !data.executed && data.message?.includes("received")) {
            return;
        }
    } catch (e) {
        console.error(e);
        confBox.classList.add("hidden");
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
        data.reverse().forEach((item, index) => {
            appendChatMessage(chatBox, "user", "You", item.message);
            appendChatMessage(chatBox, "ai", "AI", item.response, {
                userPrompt: item.message,
                messageId: `hist-${index}-${item.id || index}`
            });
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

document.addEventListener("DOMContentLoaded", () => {
    const messageInput = document.getElementById("messageInput");
    if (messageInput) {
        messageInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
});

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

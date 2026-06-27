if (!window.APP_CONFIG || !window.APP_CONFIG.API_URL) {
    console.error("Missing frontend config. Please check static/config.js");
    alert("System Error: Missing APP_CONFIG. Please check static/config.js");
}

const API_URL = window.APP_CONFIG ? window.APP_CONFIG.API_URL : null;
const WS_URL = window.APP_CONFIG ? window.APP_CONFIG.WS_URL : null;

console.log("🚀 Using API_URL:", API_URL);
console.log("🔌 Using WS_URL:", WS_URL);

let token = localStorage.getItem("token");

// --- Canvas Particle System Disabled ---
function initCanvas() {}
function createParticles() {}
function animateParticles() {}


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
    if (widgetName === "chat") {
        setTimeout(() => {
            document.getElementById("messageInput")?.focus();
            scrollChatToBottom();
        }, 120);
    }
}


// --- Xử lý Cold Start cho máy chủ Render (Free Tier) ---
async function pingBackend() {
    let isSlow = false;
    // Nếu sau 1.2s chưa phản hồi, chứng tỏ server đang cold-start (ngủ đông)
    const slowTimer = setTimeout(() => {
        isSlow = true;
        showColdStartBanner();
    }, 1200);

    try {
        const res = await fetch(`${API_URL}/health`);
        if (res.ok) {
            console.log("❇️ Backend is awake!");
        }
    } catch (err) {
        console.warn("⚠️ Failed to ping backend:", err);
    } finally {
        clearTimeout(slowTimer);
        if (isSlow) {
            hideColdStartBanner();
        }
    }
}

function showColdStartBanner() {
    let banner = document.getElementById("coldStartBanner");
    if (!banner) {
        banner = document.createElement("div");
        banner.id = "coldStartBanner";
        banner.style.position = "fixed";
        banner.style.bottom = "20px";
        banner.style.right = "20px";
        banner.style.padding = "12px 20px";
        banner.style.background = "linear-gradient(135deg, #fffbeb, #fef3c7)";
        banner.style.border = "1px solid #fde68a";
        banner.style.borderRadius = "12px";
        banner.style.boxShadow = "0 4px 12px rgba(0,0,0,0.05)";
        banner.style.zIndex = "9999";
        banner.style.fontFamily = "'Inter', sans-serif";
        banner.style.fontSize = "13px";
        banner.style.color = "#b45309";
        banner.style.display = "flex";
        banner.style.alignItems = "center";
        banner.style.gap = "8px";
        banner.style.animation = "slideIn 0.3s ease-out";
        
        banner.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="animation: spin 1.5s linear infinite;">
                <circle cx="12" cy="12" r="10" stroke="#b45309" stroke-width="3" stroke-dasharray="30 10" fill="none"></circle>
            </svg>
            <span>Máy chủ Render đang thức dậy... (khoảng 30-50s)</span>
        `;
        
        if (!document.getElementById("coldStartStyle")) {
            const style = document.createElement("style");
            style.id = "coldStartStyle";
            style.innerHTML = `
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                @keyframes slideIn { from { transform: translateY(50px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
            `;
            document.head.appendChild(style);
        }
        
        document.body.appendChild(banner);
    }
}

function hideColdStartBanner() {
    const banner = document.getElementById("coldStartBanner");
    if (banner) {
        banner.style.animation = "slideIn 0.3s ease-out reverse";
        setTimeout(() => {
            if (banner.parentNode) {
                banner.parentNode.removeChild(banner);
            }
        }, 280);
    }
}

// --- App Logic ---
window.onload = () => {
    // Đánh thức máy chủ Render
    pingBackend();

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

const STATE_DISPLAY_NAMES = {
    idle: "Ready",
    thinking: "Thinking",
    acting: "Executing",
    waiting_confirmation: "Waiting",
    listening: "Listening",
    error: "Error"
};

function setAvatarState(state) {
    const container = document.getElementById("avatarContainer");
    const label = document.getElementById("avatarLabel");
    if (!container || !label) return;
    container.className = `avatar-container state-${state}`;
    const displayName = STATE_DISPLAY_NAMES[state] || (state.charAt(0).toUpperCase() + state.slice(1));
    label.innerText = displayName;
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
        if (!taskList) return;
        taskList.innerHTML = "";
        if (tasks.length === 0) {
            taskList.innerHTML = `<li class="project-empty">No skills trained</li>`;
            return;
        }
        tasks.forEach(task => {
            const safeName = task.name.replace(/'/g, "\\'");
            const safeNote = (task.note || '').replace(/'/g, "\\'");
            taskList.innerHTML += `
                <li class="project-item">
                    <div class="project-info" title="${task.note || task.name}">
                        <span class="project-name">${task.name}</span>
                        ${task.note ? `<span class="project-note">${task.note}</span>` : ''}
                    </div>
                    <div class="project-actions">
                        <button onclick="executeTrainedTask('${task.id}')" class="btn-proj-run" title="Run skill">▶</button>
                        <button onclick="editTask('${task.id}', '${safeName}', '${safeNote}')" class="btn-proj-edit" title="Edit skill">✎</button>
                        <button onclick="deleteTask('${task.id}')" class="btn-proj-delete" title="Delete skill">✕</button>
                    </div>
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

function renderRecentConversations(data) {
    const list = document.getElementById("recentConversations");
    if (!list) return;
    list.innerHTML = "";
    
    const recentItems = data.slice(0, 10);
    if (recentItems.length === 0) {
        list.innerHTML = `<li class="recent-empty">No recent chats</li>`;
        return;
    }
    
    recentItems.forEach((item) => {
        const li = document.createElement("li");
        li.className = "recent-item";
        
        const icon = document.createElement("span");
        icon.className = "recent-icon";
        icon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
        
        const text = document.createElement("span");
        text.className = "recent-text";
        text.textContent = item.message.length > 28 ? item.message.slice(0, 25) + "..." : item.message;
        text.title = item.message;
        
        li.append(icon, text);
        li.addEventListener("click", () => {
            const input = document.getElementById("messageInput");
            if (input) {
                input.value = item.message;
                input.focus();
            }
        });
        list.appendChild(li);
    });
}

async function loadHistory() {
    const res = await fetch(`${API_URL}/history`, { headers: { "X-Token": token } });
    if (res.status === 200) {
        const data = await res.json();
        
        renderRecentConversations(data);
        
        const chatBox = document.getElementById("chatBox");
        chatBox.innerHTML = "";
        const displayData = [...data].reverse();
        displayData.forEach((item, index) => {
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
        if (btn) {
            btn.classList.add("recording");
            btn.setAttribute("aria-label", "Stop recording");
        }
        isRecording = true;
    };
    recognition.onresult = (event) => {
        document.getElementById("messageInput").value = event.results[0][0].transcript;
        sendMessage();
    };
    recognition.onend = () => {
        const labelText = document.getElementById("avatarLabel")?.innerText;
        if (labelText === 'LISTENING' || labelText === 'Listening') {
            setAvatarState('idle');
        }
        const btn = document.getElementById("recordBtn");
        if (btn) {
            btn.classList.remove("recording");
            btn.setAttribute("aria-label", "Speak voice command");
        }
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

function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebarOverlay");
    if (sidebar) sidebar.classList.toggle("open");
    if (overlay) overlay.classList.toggle("active");
}


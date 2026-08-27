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

// --- Meta Messenger-Style Reply Context ---
let activeReplyContext = null;

function startReply(sender, text, messageId) {
    activeReplyContext = {
        id: messageId || "",
        sender: sender || "Message",
        text: String(text || "").trim()
    };
    const bar = document.getElementById("replyPreviewBar");
    const senderEl = document.getElementById("replyPreviewSender");
    const textEl = document.getElementById("replyPreviewText");
    if (bar && senderEl && textEl) {
        senderEl.textContent = `Đang trả lời ${activeReplyContext.sender}`;
        textEl.textContent = activeReplyContext.text.length > 80 ? activeReplyContext.text.slice(0, 77) + "..." : activeReplyContext.text;
        bar.classList.remove("hidden");
    }
    const input = document.getElementById("messageInput");
    if (input) input.focus();
}

function cancelReply() {
    activeReplyContext = null;
    const bar = document.getElementById("replyPreviewBar");
    if (bar) bar.classList.add("hidden");
}

function scrollToMessage(messageId) {
    if (!messageId) return;
    const target = document.querySelector(`[data-message-id="${messageId}"]`) || document.getElementById(messageId);
    if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "center" });
        target.classList.add("message-highlight-flash");
        setTimeout(() => target.classList.remove("message-highlight-flash"), 1800);
    }
}

// --- Editable & Persistent Chat Title (Inline Word-style) ---
let isEditingChatTitle = false;
let originalChatTitle = "";

function editChatTitle() {
    const titleEl = document.getElementById("chatTitle");
    const btnEl = document.querySelector(".btn-edit-title");
    if (!titleEl) return;

    if (isEditingChatTitle) {
        // Đang sửa mà bấm nút lần nữa thì Lưu lại
        finishEditingChatTitle(true);
        return;
    }

    isEditingChatTitle = true;
    originalChatTitle = titleEl.innerText.trim();
    titleEl.contentEditable = "true";
    titleEl.spellcheck = false;
    titleEl.classList.add("chat-title-editing");
    titleEl.focus();

    // Bôi đen toàn bộ text giống Microsoft Word để người dùng có thể gõ đè ngay
    try {
        const range = document.createRange();
        range.selectNodeContents(titleEl);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    } catch (e) {
        console.error(e);
    }

    // Đổi icon sang dấu tích xanh (Checkmark) để xác nhận
    if (btnEl) {
        btnEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
        btnEl.title = "Lưu tên trợ lý (Nhấn Enter)";
    }

    // Phím Enter để lưu, Escape để hủy
    titleEl.onkeydown = (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            finishEditingChatTitle(true);
        } else if (e.key === "Escape") {
            e.preventDefault();
            finishEditingChatTitle(false);
        }
    };

    // Khi click chuột ra ngoài (blur) thì tự động lưu
    titleEl.onblur = () => {
        setTimeout(() => {
            if (isEditingChatTitle) {
                finishEditingChatTitle(true);
            }
        }, 150);
    };
}

function finishEditingChatTitle(shouldSave) {
    const titleEl = document.getElementById("chatTitle");
    const btnEl = document.querySelector(".btn-edit-title");
    if (!titleEl) return;

    isEditingChatTitle = false;
    titleEl.contentEditable = "false";
    titleEl.classList.remove("chat-title-editing");

    // Khôi phục lại icon bút chì
    if (btnEl) {
        btnEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>`;
        btnEl.title = "Đổi tên trợ lý";
    }

    if (shouldSave) {
        const newTitle = titleEl.innerText.trim();
        if (newTitle && newTitle !== originalChatTitle) {
            saveChatTitle(newTitle);
        } else if (!newTitle) {
            titleEl.innerText = originalChatTitle || "Application Assistant";
        }
    } else {
        titleEl.innerText = originalChatTitle;
    }
}

function saveChatTitle(title) {
    const titleEl = document.getElementById("chatTitle");
    if (titleEl) titleEl.innerText = title;
    document.title = title;
    localStorage.setItem("custom_chat_title", title);
    showAlert(`Đã đổi tên trợ lý thành "${title}"`);
}

function loadChatTitle() {
    const saved = localStorage.getItem("custom_chat_title");
    if (saved) {
        const titleEl = document.getElementById("chatTitle");
        if (titleEl) titleEl.innerText = saved;
        document.title = saved;
    }
}

// --- Interactive Agent Skills ---
const SKILL_PROMPT_EXAMPLES = {
    DC: "Mở ứng dụng Google Chrome",
    VC: "Bật chế độ điều khiển bằng giọng nói",
    WA: "Tìm kiếm trên Google thông tin về công nghệ AI mới nhất",
    SA: "Chụp màn hình và phân tích nội dung đang hiển thị",
    RA: "Tự động hóa: Mở Notepad và ghi chú 'Xin chào tôi là AI Assistant'",
    TM: "Nhắc lại tác vụ gần nhất mà chúng ta vừa thực hiện",
    AT: "start_training"
};

function initSkillCardInteractions() {
    document.querySelectorAll(".skill-card[data-skill]").forEach(card => {
        const skillId = card.dataset.skill;
        card.style.cursor = "pointer";
        card.setAttribute("role", "button");
        card.title = `Click để dùng tính năng ${card.querySelector('.skill-name')?.textContent || skillId}`;
        card.onclick = () => {
            if (skillId === "AT") {
                startTraining();
                showAlert("Đã mở phòng huấn luyện Skill (AI Training Lab)!");
                return;
            }
            if (skillId === "VC") {
                toggleRecording();
                return;
            }
            const promptText = SKILL_PROMPT_EXAMPLES[skillId] || "";
            const input = document.getElementById("messageInput");
            if (input && promptText) {
                input.value = promptText;
                input.focus();
                showAlert(`Đã chọn tính năng: ${card.querySelector('.skill-name')?.textContent || skillId}`);
            }
        };
    });
}

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
            createMessageActionButton("↩", "Trả lời tin nhắn này", () => startReply("AI", text, messageId)),
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

async function deleteSingleMessage(dbId, aiRow) {
    if (!confirm("Delete this message?")) return;
    if (!dbId) {
        const prevRow = aiRow?.previousElementSibling;
        if (prevRow && prevRow.classList.contains("user-row")) {
            prevRow.remove();
        }
        if (aiRow) aiRow.remove();
        return;
    }
    try {
        const res = await fetch(`${API_URL}/history/${dbId}`, {
            method: "DELETE",
            headers: { "X-Token": token }
        });
        if (res.status === 200) {
            const prevRow = aiRow?.previousElementSibling;
            if (prevRow && prevRow.classList.contains("user-row")) {
                prevRow.remove();
            }
            if (aiRow) aiRow.remove();
            showAlert("Message deleted.");
            loadHistory();
        } else {
            const data = await res.json().catch(() => ({}));
            showAlert(data.detail || "Failed to delete message.");
        }
    } catch (e) {
        console.error(e);
        showAlert("Connection error.");
    }
}

function appendChatMessage(chatBox, role, label, message, options = {}) {
    const isUser = role === "user";
    const row = document.createElement("div");
    row.className = `chat-row ${isUser ? "user-row" : "ai-row"}`;
    const messageId = options.messageId || `${role}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    row.dataset.messageId = messageId;
    row.id = messageId;

    const avatar = document.createElement("span");
    avatar.className = "chat-avatar";
    avatar.textContent = isUser ? "You" : "AI";
    avatar.setAttribute("aria-hidden", "true");

    const wrap = document.createElement("div");
    wrap.className = "chat-bubble-wrap";

    // If this message is a reply to another message, render Meta Messenger quote card!
    if (options.replyTo && options.replyTo.text) {
        const quoteBox = document.createElement("div");
        quoteBox.className = "chat-reply-quote";
        quoteBox.setAttribute("role", "button");
        quoteBox.title = "Click để cuộn tới tin nhắn gốc";
        
        const quoteSender = document.createElement("span");
        quoteSender.className = "reply-quote-sender";
        quoteSender.textContent = options.replyTo.sender ? `Trả lời ${options.replyTo.sender}` : "Trả lời";

        const quoteText = document.createElement("span");
        quoteText.className = "reply-quote-snippet";
        quoteText.textContent = options.replyTo.text.length > 90 ? options.replyTo.text.slice(0, 87) + "..." : options.replyTo.text;

        quoteBox.append(quoteSender, quoteText);
        if (options.replyTo.id) {
            quoteBox.onclick = () => scrollToMessage(options.replyTo.id);
        }
        wrap.appendChild(quoteBox);
    }

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
        const userPrompt = options.userPrompt || "";
        const dbId = options.dbId || null;
        if (userPrompt) row.dataset.userPrompt = userPrompt;

        const actions = document.createElement("div");
        actions.className = "message-actions";

        actions.append(
            createMessageActionButton("↩", "Trả lời tin nhắn này", () => startReply("AI", message, messageId)),
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
            })(),
            createMessageActionButton("🗑️", "Delete message", () => deleteSingleMessage(dbId, row))
        );

        setFeedbackButtonState(actions, messageId);
        wrap.appendChild(actions);
    } else {
        // User message actions (Reply + Copy)
        const actions = document.createElement("div");
        actions.className = "message-actions user-actions";
        actions.append(
            createMessageActionButton("↩", "Trả lời tin nhắn này", () => startReply("You", message, messageId)),
            createMessageActionButton("Copy", "Copy text", () => copyMessageText(message))
        );
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
// Render free tier spins down after 15 min of inactivity.
// We ping /health every 5 minutes to keep it warm.

const KEEP_ALIVE_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
let keepAliveTimer = null;

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

/** Start recurring keep-alive pings to Render backend */
function startKeepAlive() {
    stopKeepAlive(); // Prevent duplicate timers
    keepAliveTimer = setInterval(() => {
        fetch(`${API_URL}/health`).catch(() => {});
        console.log("🏓 Keep-alive ping sent to Render backend");
    }, KEEP_ALIVE_INTERVAL_MS);
    console.log(`🟢 Keep-alive started (every ${KEEP_ALIVE_INTERVAL_MS / 1000}s)`);
}

/** Stop recurring keep-alive pings (e.g., when tab is hidden) */
function stopKeepAlive() {
    if (keepAliveTimer) {
        clearInterval(keepAliveTimer);
        keepAliveTimer = null;
        console.log("🔴 Keep-alive stopped");
    }
}

// Pause keep-alive when user hides tab (saves battery/data),
// resume when they come back.
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
        // Tab is active again — send an immediate ping + restart the interval
        pingBackend();
        startKeepAlive();
    } else {
        stopKeepAlive();
    }
});

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
    // Đánh thức máy chủ Render + bắt đầu keep-alive định kỳ
    pingBackend();
    startKeepAlive();

    loadChatTitle();
    initSkillCardInteractions();

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
    const starSvg = `<svg class="pro-star-icon" xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="#F59E0B" stroke="#D97706" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>`;
    const proHtml = `${starSvg}<span>Pro Account</span>${starSvg}`;

    const statusEl = document.getElementById("userStatus");
    if (statusEl) {
        statusEl.innerHTML = proHtml;
        statusEl.className = "user-tier status-pro";
    }

    const headerStatusEl = document.getElementById("headerUserStatus");
    if (headerStatusEl) {
        headerStatusEl.innerHTML = proHtml;
        headerStatusEl.className = "user-tier status-pro chat-header-pro";
    }

    const upgradeBtn = document.querySelector(".btn-pro");
    if (upgradeBtn) upgradeBtn.style.display = "none";
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
    document.getElementById("authSection")?.classList.remove("hidden");
    document.getElementById("appSection")?.classList.add("hidden");
    document.getElementById("trainingSection")?.classList.add("hidden");
    document.getElementById("downloadAgentBanner")?.classList.add("hidden");
    const chatBox = document.getElementById("chatBox");
    if (chatBox) chatBox.innerHTML = "";
    toggleAssistantWidget("chat", false);
    toggleAssistantWidget("skill", false);
    updateStatusUI(false);
}

function checkDownloadAgentBanner(userId) {
    if (!userId) return;
    const downloaded = localStorage.getItem(`agent_downloaded_${userId}`);
    const banner = document.getElementById("downloadAgentBanner");
    if (!banner) return;

    if (downloaded === "true") {
        banner.classList.add("hidden");
    } else {
        banner.classList.remove("hidden");
    }
}

function downloadDesktopAgent() {
    const userId = document.getElementById("userIdDisplay")?.innerText;
    if (userId) {
        localStorage.setItem(`agent_downloaded_${userId}`, "true");
    }
    const banner = document.getElementById("downloadAgentBanner");
    if (banner) {
        banner.classList.add("hidden");
    }
    showAlert("Starting Desktop Agent download...");
    window.location.href = `${API_URL}/automation/download_agent`;
}

function dismissDownloadAgentBanner() {
    const userId = document.getElementById("userIdDisplay")?.innerText;
    if (userId) {
        localStorage.setItem(`agent_downloaded_${userId}`, "true");
    }
    const banner = document.getElementById("downloadAgentBanner");
    if (banner) {
        banner.classList.add("hidden");
    }
}

async function showApp() {
    document.getElementById("authSection")?.classList.add("hidden");
    document.getElementById("appSection")?.classList.remove("hidden");
    document.getElementById("trainingSection")?.classList.remove("hidden");
    toggleAssistantWidget("chat", true);
    toggleAssistantWidget("skill", false);

    const res = await fetch(`${API_URL}/auth/me`, {
        headers: { "X-Token": token }
    });
    if (res.status === 200) {
        const data = await res.json();
        const userDisplay = document.getElementById("userIdDisplay");
        if (userDisplay) userDisplay.innerText = data.id;
        updateStatusUI(data.is_pro);
        checkDownloadAgentBanner(data.id);
    } else if (res.status === 401) {
        logout();
        return;
    }
    loadHistory();
    loadTrainedTasks();
    loadChatTitle();
    initSkillCardInteractions();
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

    const replyContext = activeReplyContext;
    cancelReply();

    if (!options.skipUserBubble) {
        appendChatMessage(chatBox, "user", "You", msg, { replyTo: replyContext });
    }
    if (input) input.value = "";

    chatRequestInFlight = true;
    streamingAiRow = null;
    setChatTyping(true);
    setAvatarState("thinking");
    document.getElementById("agentLogsContainer").classList.remove("hidden");
    const logsUl = document.getElementById("agentLogs");
    logsUl.innerHTML = "";

    const outboundMessage = replyContext
        ? `[Trả lời ${replyContext.sender}: "${replyContext.text.slice(0, 120)}"]\n${msg}`
        : msg;

    try {
        const res = await fetch(`${API_URL}/agent/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-Token": token },
            body: JSON.stringify({ message: outboundMessage })
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
            renderRecentConversations([]);
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

async function deleteRecentItem(itemId) {
    if (!itemId) return;
    try {
        const res = await fetch(`${API_URL}/history/${itemId}`, {
            method: "DELETE",
            headers: { "X-Token": token }
        });
        if (res.status === 200) {
            showAlert("Đã xóa cuộc trò chuyện khỏi lịch sử.");
            // Reload history in background to keep data in sync
            const histRes = await fetch(`${API_URL}/history`, { headers: { "X-Token": token } });
            if (histRes.status === 200) {
                const data = await histRes.json();
                renderRecentConversations(data);
            }
        } else {
            const data = await res.json().catch(() => ({}));
            showAlert(data.detail || "Không thể xóa tin nhắn.");
            loadHistory();
        }
    } catch (e) {
        console.error(e);
        showAlert("Lỗi kết nối khi xóa.");
    }
}

function renderRecentConversations(data) {
    const list = document.getElementById("recentConversations");
    if (!list) return;
    list.innerHTML = "";
    
    const recentItems = (data || []).slice(0, 15);
    if (recentItems.length === 0) {
        list.innerHTML = `<li class="recent-empty">Chưa có cuộc trò chuyện</li>`;
        return;
    }
    
    recentItems.forEach((item) => {
        const li = document.createElement("li");
        li.className = "recent-item";
        
        const icon = document.createElement("span");
        icon.className = "recent-icon";
        icon.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`;
        
        const text = document.createElement("span");
        text.className = "recent-text";
        text.textContent = item.message.length > 28 ? item.message.slice(0, 25) + "..." : item.message;
        text.title = item.message;
        
        const delBtn = document.createElement("button");
        delBtn.className = "btn-recent-delete";
        delBtn.title = "Xóa cuộc trò chuyện này";
        delBtn.setAttribute("aria-label", "Delete recent chat");
        // Biểu tượng thùng rác xóa trực quan
        delBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>`;
        
        delBtn.onclick = async (e) => {
            e.stopPropagation();
            const previewMsg = item.message.length > 20 ? item.message.slice(0, 18) + "..." : item.message;
            if (!confirm(`Bạn có chắc muốn xóa "${previewMsg}" khỏi lịch sử?`)) return;
            
            // Hiệu ứng mờ dần và trượt mượt lập tức trên giao diện
            li.style.transition = "all 0.2s ease";
            li.style.opacity = "0";
            li.style.transform = "translateX(-12px)";
            setTimeout(() => {
                li.remove();
                if (list.children.length === 0) {
                    list.innerHTML = `<li class="recent-empty">Chưa có cuộc trò chuyện</li>`;
                }
            }, 200);

            const targetId = item.id || encodeURIComponent(item.message);
            await deleteRecentItem(targetId);
        };

        li.append(icon, text, delBtn);
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
                messageId: `hist-${index}-${item.id || index}`,
                dbId: item.id || null
            });
        });
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}


async function upgradePro() {
    showAlert("Tài khoản của bạn đã có đặc quyền Pro vĩnh viễn!");
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


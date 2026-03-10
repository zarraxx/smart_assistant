const messagesEl = document.getElementById('messages');
const userIdInputEl = document.getElementById('userIdInput');
const currentSessionLabelEl = document.getElementById('currentSessionLabel');
const messageInputEl = document.getElementById('messageInput');
const sendButtonEl = document.getElementById('sendButton');
const resetConversationButtonEl = document.getElementById('resetConversationButton');
const statusTextEl = document.getElementById('statusText');
const debugSessionIdInputEl = document.getElementById('debugSessionIdInput');
const debugPayloadInputEl = document.getElementById('debugPayloadInput');
const sendDebugMessageButtonEl = document.getElementById('sendDebugMessageButton');
const clearDebugLogButtonEl = document.getElementById('clearDebugLogButton');
const debugLogEl = document.getElementById('debugLogEl');
const socketFunctionHandlers = { showDepartmentAppointment, showPatientReportModal, showQueueModal };

let isSending = false;
let currentSessionId = '';
let currentSessionUserId = '';
let socketClient = null;

function buildAppUrl(path) {
    return path.replace(/^\/+/,'');
}

function openModal(modalId) {
    const modalEl = document.getElementById(modalId);
    if (modalEl) {
        modalEl.classList.add('is-open');
    }
}

function closeModal(modalId) {
    const modalEl = document.getElementById(modalId);
    if (modalEl) {
        modalEl.classList.remove('is-open');
    }
}

function getOpenModalId() {
    return document.querySelector('.modal-mask.is-open')?.id || null;
}

function showExclusiveModal(modalId) {
    const activeModalId = getOpenModalId();
    if (activeModalId === modalId) { return; }
    if (activeModalId) { closeModal(activeModalId); }
    openModal(modalId);
}

function handleModalMaskClick(event, modalId) {
    if (event.target.id === modalId) { closeModal(modalId); }
}

function showDepartmentAppointment() { showExclusiveModal('departmentAppointmentModal'); }
function showDepartmentAppointmentModal() { showDepartmentAppointment(); }
function showPatientReportModal() { showExclusiveModal('patientReportModal'); }
function showQueueModal() { showExclusiveModal('queueModal'); }

function setStatus(text) { statusTextEl.textContent = `\u72b6\u6001\uff1a${text}`; }

function appendMessage(role, text) {
    const messageEl = document.createElement('div');
    messageEl.className = `message message-${role}`;
    messageEl.textContent = text;
    messagesEl.appendChild(messageEl);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return messageEl;
}

function appendDebugLog(direction, payload) {
    const prefix = direction === 'out' ? '>>' : '<<';
    const renderedPayload = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
    if (debugLogEl.textContent === '\u7b49\u5f85 Socket.IO \u6d88\u606f...') { debugLogEl.textContent = ''; }
    debugLogEl.textContent += `${prefix} ${renderedPayload}\n\n`;
    debugLogEl.scrollTop = debugLogEl.scrollHeight;
}

function syncSessionDisplay() {
    debugSessionIdInputEl.value = currentSessionId;
    currentSessionLabelEl.value = currentSessionId;
}

function setSendingState(sending) {
    isSending = sending;
    sendButtonEl.disabled = sending;
    messageInputEl.disabled = sending;
    userIdInputEl.disabled = sending;
    resetConversationButtonEl.disabled = sending;
}

function disconnectSocketSession() {
    if (!socketClient) { return; }
    socketClient.off('message', handleSocketMessage);
    socketClient.disconnect();
    socketClient = null;
}

function clearSocketSession() {
    disconnectSocketSession();
    currentSessionId = '';
    currentSessionUserId = '';
    syncSessionDisplay();
}

function connectSocketSession(sessionId) {
    if (typeof io !== 'function') {
        appendMessage('system', '\u0053ocket.IO \u5ba2\u6237\u7aef\u672a\u52a0\u8f7d\u3002');
        setStatus('Socket.IO \u5ba2\u6237\u7aef\u672a\u52a0\u8f7d');
        return;
    }
    disconnectSocketSession();
    const socketPath = window.location.pathname.replace(/\/?$/, '/socket.io/');
    console.log("Connecting Socket.IO with session ID:", sessionId, "at path:", socketPath);
    socketClient = io({
        path: socketPath,
        auth: { sessionId },
       // transports: ['websocket', 'polling'],
    });
    socketClient.on('connect', () => setStatus(`Socket.IO \u5df2\u8fde\u63a5\uff08${sessionId}\uff09`));
    socketClient.on('disconnect', () => setStatus('Socket.IO \u5df2\u65ad\u5f00'));
    socketClient.on('connect_error', (error) => {
        appendMessage('system', `Socket.IO \u8fde\u63a5\u5931\u8d25\uff1a${error.message}`);
        setStatus('Socket.IO \u8fde\u63a5\u5931\u8d25');
    });
    socketClient.on('message', handleSocketMessage);
}

async function createChatSession(userId) {
    const response = await fetch(buildAppUrl('/chat/create'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
        body: JSON.stringify({ user_id: userId, client_capabilities: ['socket.io'] }),
    });
    if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || `\u521b\u5efa\u4f1a\u8bdd\u5931\u8d25\uff1a${response.status}`);
    }
    const result = await response.json();
    const sessionId = result?.data?.session_id;
    if (!sessionId) { throw new Error('\u670d\u52a1\u7aef\u672a\u8fd4\u56de session_id'); }
    currentSessionId = sessionId;
    currentSessionUserId = userId;
    syncSessionDisplay();
    appendMessage('system', `\u5df2\u521b\u5efa Session\uff1a${sessionId}`);
    connectSocketSession(sessionId);
    return sessionId;
}

async function ensureChatSession(userId) {
    if (currentSessionUserId && currentSessionUserId !== userId) { clearSocketSession(); }
    if (!currentSessionId) { return createChatSession(userId); }
    if (!socketClient || !socketClient.connected) { connectSocketSession(currentSessionId); }
    return currentSessionId;
}

function handleSocketMessage(message) {
    appendDebugLog('in', message);
    if (!message || message.type !== 'function' || typeof message.name !== 'string') { return; }
    const handler = socketFunctionHandlers[message.name];
    if (!handler) {
        appendMessage('system', `\u6536\u5230\u672a\u652f\u6301\u7684\u51fd\u6570\u6d88\u606f\uff1a${message.name}`);
        return;
    }
    handler(message.params || {});
}

function resetConversation() {
    clearSocketSession();
    appendMessage('system', '\u5df2\u91cd\u7f6e\u5f53\u524d Session\uff0c\u4e0b\u6b21\u53d1\u9001\u65f6\u4f1a\u91cd\u65b0\u521b\u5efa\u3002');
    setStatus('\u7a7a\u95f2');
}

async function sendDebugSocketMessage() {
    const userId = userIdInputEl.value.trim();
    if (!userId) {
        appendMessage('system', '\u8bf7\u8f93\u5165\u7528\u6237 ID\u3002');
        userIdInputEl.focus();
        return;
    }
    await ensureChatSession(userId);
    if (!socketClient) { throw new Error('Socket.IO \u5c1a\u672a\u5efa\u7acb\u8fde\u63a5'); }
    let payload;
    try { payload = JSON.parse(debugPayloadInputEl.value); }
    catch (error) { throw new Error(`\u8c03\u8bd5\u6d88\u606f JSON \u65e0\u6cd5\u89e3\u6790\uff1a${error.message}`); }
    appendDebugLog('out', payload);
    socketClient.emit('message', payload);
}

async function sendMessage() {
    if (isSending) { return; }
    const userId = userIdInputEl.value.trim();
    const query = messageInputEl.value.trim();
    if (!userId) { appendMessage('system', '\u8bf7\u8f93\u5165\u7528\u6237 ID\u3002'); userIdInputEl.focus(); return; }
    if (!query) { appendMessage('system', '\u8bf7\u8f93\u5165\u804a\u5929\u5185\u5bb9\u3002'); messageInputEl.focus(); return; }
    const payload = { session_id: '', inputs: {}, query, user: userId, response_mode: 'streaming' };
    appendMessage('user', query);
    messageInputEl.value = '';
    const assistantMessageEl = appendMessage('assistant', '');
    setSendingState(true);
    setStatus('\u53d1\u9001\u4e2d');
    try {
        payload.session_id = await ensureChatSession(userId);
        const response = await fetch(buildAppUrl('/chat/completion'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json; charset=utf-8' },
            body: JSON.stringify(payload),
        });
        if (!response.ok || !response.body) {
            const errorText = await response.text();
            throw new Error(errorText || `\u8bf7\u6c42\u5931\u8d25\uff1a${response.status}`);
        }
        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';
        let answerText = '';
        while (true) {
            const { value, done } = await reader.read();
            if (done) { break; }
            buffer += decoder.decode(value, { stream: true });
            const events = buffer.split('\n\n');
            buffer = events.pop() || '';
            for (const eventBlock of events) {
                const lines = eventBlock.split('\n').map((line) => line.trim()).filter(Boolean);
                for (const line of lines) {
                    if (!line.startsWith('data:')) { continue; }
                    const rawData = line.slice(5).trim();
                    if (!rawData || rawData === '[DONE]') { continue; }
                    let chunk;
                    try { chunk = JSON.parse(rawData); } catch (error) { continue; }
                    if (chunk.event === 'message' && typeof chunk.answer === 'string') {
                        answerText += chunk.answer;
                        assistantMessageEl.textContent = answerText;
                        messagesEl.scrollTop = messagesEl.scrollHeight;
                    }
                }
            }
        }
        if (!assistantMessageEl.textContent.trim()) { assistantMessageEl.textContent = '\u672c\u6b21\u6ca1\u6709\u8fd4\u56de\u53ef\u5c55\u793a\u7684\u6587\u672c\u5185\u5bb9\u3002'; }
        setStatus('\u5b8c\u6210');
    } catch (error) {
        assistantMessageEl.textContent = `\u8bf7\u6c42\u5931\u8d25\uff1a${error.message}`;
        setStatus('\u5931\u8d25');
    } finally {
        setSendingState(false);
    }
}

sendButtonEl.addEventListener('click', sendMessage);
resetConversationButtonEl.addEventListener('click', resetConversation);
sendDebugMessageButtonEl.addEventListener('click', async () => {
    try {
        await sendDebugSocketMessage();
    } catch (error) {
        appendMessage('system', `\u8c03\u8bd5\u6d88\u606f\u53d1\u9001\u5931\u8d25\uff1a${error.message}`);
        appendDebugLog('in', { error: error.message });
    }
});
clearDebugLogButtonEl.addEventListener('click', () => { debugLogEl.textContent = '\u7b49\u5f85 Socket.IO \u6d88\u606f...'; });
messageInputEl.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); }
});
syncSessionDisplay();
window.addEventListener('beforeunload', disconnectSocketSession);
window.openModal = openModal;
window.closeModal = closeModal;
window.handleModalMaskClick = handleModalMaskClick;
window.showDepartmentAppointment = showDepartmentAppointment;
window.showDepartmentAppointmentModal = showDepartmentAppointmentModal;
window.showPatientReportModal = showPatientReportModal;
window.showQueueModal = showQueueModal;
window.sendDebugSocketMessage = sendDebugSocketMessage;

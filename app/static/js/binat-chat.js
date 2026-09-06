// Global variables (USER_NAME, USER_ID, PDN_CODE are set by inline script in the HTML template)
// STORAGE_PREFIX can be set by the template before loading this script to namespace localStorage keys.
// Defaults to 'binat' for backward compatibility with the original binat chat.
const _STORAGE_PREFIX = (typeof STORAGE_PREFIX !== 'undefined') ? STORAGE_PREFIX : 'binat';

let messageQueue = [];
let isProcessing = false;
let currentController = null;

// Session timer
let sessionStartTime = Date.now();

// Voice recording variables
let speechRecognition = null;
let isListening = false;
let existingTextBeforeRecording = '';

// Utility functions
function getCurrentTime() {
    const now = new Date();
    const hours = now.getHours().toString().padStart(2, '0');
    const minutes = now.getMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
}

// Initialize Web Speech API
function initializeSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        return null;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'he-IL';
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
        isListening = true;
        finalTranscript = '';
        interimTranscript = '';
        // Store existing text before recording
        const userInput = document.getElementById('userInput');
        existingTextBeforeRecording = userInput.value;
        updateMicrophoneUI(true);
    };

    recognition.onresult = (event) => {
        let interimTranscript = '';
        let finalTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += transcript;
            } else {
                interimTranscript += transcript;
            }
        }

        // Append new transcription to existing text
        const userInput = document.getElementById('userInput');
        const separator = existingTextBeforeRecording ? ' ' : '';
        userInput.value = existingTextBeforeRecording + separator + finalTranscript + interimTranscript;
    };

    recognition.onerror = (event) => {
        isListening = false;
        updateMicrophoneUI(false);
        hideTranscriptionFeedback();

        let errorMessage = 'שגיאה בהקלטה';
        switch (event.error) {
            case 'no-speech':
                errorMessage = 'לא זוהתה דיבור';
                break;
            case 'audio-capture':
                errorMessage = 'בעיה במיקרופון';
                break;
            case 'not-allowed':
                errorMessage = 'אין הרשאה למיקרופון';
                break;
            case 'network':
                errorMessage = 'בעיית רשת';
                break;
        }
        showError(errorMessage);
    };

    recognition.onend = () => {
        isListening = false;
        updateMicrophoneUI(false);
        hideTranscriptionFeedback();

        // Focus on input for potential editing
        const userInput = document.getElementById('userInput');
        if (userInput.value.trim()) {
            userInput.focus();
            userInput.setSelectionRange(userInput.value.length, userInput.value.length);
        }
    };

    return recognition;
}

// Update microphone button UI
function updateMicrophoneUI(isActive) {
    const micBtn = document.getElementById('micBtn');
    const micIcon = micBtn.querySelector('i');
    const micText = document.getElementById('micBtnText');
    const sendBtn = document.getElementById('sendBtn');

    if (isActive) {
        micBtn.classList.add('recording');
        micIcon.className = 'fas fa-stop';
        micText.textContent = 'סיים';
        micBtn.title = 'עצור הקלטה';
        micBtn.setAttribute('aria-label', 'עצור הקלטה');
        sendBtn.disabled = true;
    } else {
        micBtn.classList.remove('recording');
        micIcon.className = 'fas fa-microphone';
        micText.textContent = 'הקלטה';
        micBtn.title = 'הקלטה קולית';
        micBtn.setAttribute('aria-label', 'הקלטה קולית');
        sendBtn.disabled = false;
    }
}

// Show transcription feedback
function showTranscriptionFeedback(message) {
    let feedback = document.getElementById('transcriptionFeedback');
    if (!feedback) {
        feedback = document.createElement('div');
        feedback.id = 'transcriptionFeedback';
        feedback.className = 'transcription-feedback';
        document.body.appendChild(feedback);
    }

    feedback.textContent = message;
    feedback.classList.add('show');
}

// Hide transcription feedback
function hideTranscriptionFeedback() {
    const feedback = document.getElementById('transcriptionFeedback');
    if (feedback) {
        feedback.classList.remove('show');
    }
}

// Voice recording and speech recognition functionality
function toggleMicrophone() {
    // Don't allow voice recording during message processing
    if (isProcessing) {
        showError('אנא המתן עד שההודעה הנוכחית תסיים עיבוד');
        return;
    }

    if (!speechRecognition) {
        speechRecognition = initializeSpeechRecognition();
        if (!speechRecognition) {
            showError('הדפדפן שלך אינו תומך בהקלטה קולית');
            return;
        }
    }

    if (isListening) {
        // Stop listening
        speechRecognition.stop();
    } else {
        // Start listening
        try {
            speechRecognition.start();
        } catch (error) {
            showError('שגיאה בהתחלת ההקלטה');
        }
    }
}

// Security: Input sanitization function
function sanitizeInput(input) {
    const div = document.createElement('div');
    div.textContent = input;
    return div.innerHTML;
}

// Security: XSS prevention for markdown with enhanced formatting
function safeMarkdownParse(text) {
    if (!text) return '';

    // Replace all placeholders with actual values
    let processedText = text;

    // Replace user name placeholders
    processedText = processedText.replace(/\$המשתמש_name/g, USER_NAME || 'המשתמש');
    processedText = processedText.replace(/\$user_name/g, USER_NAME || 'המשתמש');
    processedText = processedText.replace(/\$נעים להכיר/g, USER_NAME || 'המשתמש');

    // Replace PDN code placeholders
    processedText = processedText.replace(/\$user_code_name/g, PDN_CODE || 'קוד המקור');
    processedText = processedText.replace(/\$user_code_title/g, getPDNCodeTitle(PDN_CODE) || 'הקוד האישי שלך');


    // First sanitize the input
    const sanitized = sanitizeInput(processedText);

    // Check if marked is available
    if (typeof marked === 'undefined') {
        return `<div class="formatted-content">${sanitized}</div>`;
    }

    try {
        // Configure marked options for better formatting
        marked.setOptions({
            breaks: true,
            gfm: true,
            headerIds: false,
            mangle: false,
            sanitize: false, // We handle sanitization manually
            smartLists: true,
            smartypants: true
        });

        // Parse with marked
        const parsed = marked.parse(sanitized);
       // Check if markdown was actually parsed (not just returned as-is)
        if (parsed === sanitized || parsed.includes('##') || parsed.includes('**')) {
            const fallbackParsed = parseMarkdownFallback(sanitized);
            return `<div class="formatted-content">${fallbackParsed}</div>`;
        }

        // Wrap in a container with enhanced styling
        return `<div class="formatted-content">${parsed}</div>`;
    } catch (error) {
        const fallbackParsed = parseMarkdownFallback(sanitized);
        return `<div class="formatted-content">${fallbackParsed}</div>`;
    }
}

// Get PDN code title based on code
function getPDNCodeTitle(pdnCode) {
    const codeTitles = {
        'E5': 'קבלה והנהגה',
        'A7': 'עוצמה ושליטה',
        'P6': 'פיתוח וצמיחה',
        'M3': 'מנהיגות ויצירה',
        'S4': 'שירות ותמיכה',
        'C2': 'יצירה וחיבור',
        'L8': 'לימוד והתפתחות',
        'R1': 'מחקר וחקירה'
    };

    return codeTitles[pdnCode] || 'הקוד האישי שלך';
}

// Fallback markdown parser for basic formatting
function parseMarkdownFallback(text) {
    if (!text) return '';

    let parsed = text;

    // Convert headers (## Header -> <h2>Header</h2>)
    parsed = parsed.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    parsed = parsed.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    parsed = parsed.replace(/^#### (.+)$/gm, '<h4>$1</h4>');

    // Convert bold text (**text** -> <strong>text</strong>)
    parsed = parsed.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Convert italic text (*text* -> <em>text</em>)
    parsed = parsed.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Convert line breaks
    parsed = parsed.replace(/\n/g, '<br>');

    // Convert horizontal rules (--- -> <hr>)
    parsed = parsed.replace(/^---$/gm, '<hr>');

    // Convert lists
    parsed = parsed.replace(/^[\s]*\* (.+)$/gm, '<li>$1</li>');
    parsed = parsed.replace(/^[\s]*\- (.+)$/gm, '<li>$1</li>');
    parsed = parsed.replace(/^[\s]*\d+\. (.+)$/gm, '<li>$1</li>');

    // Wrap consecutive list items in ul/ol
    parsed = parsed.replace(/(<li>.*<\/li>)/gs, (match) => {
        const listItems = match.match(/<li>.*?<\/li>/g);
        if (listItems && listItems.length > 0) {
            return `<ul>${match}</ul>`;
        }
        return match;
    });

    return parsed;
}

// Conversation history management
function saveMessageToHistory(message) {
    try {
        const history = getConversationHistory();
        history.push(message);
        localStorage.setItem(`${_STORAGE_PREFIX}_chat_history`, JSON.stringify(history));
    } catch (error) {
        // Error saving message to history
    }
}

function getConversationHistory() {
    try {
        const history = localStorage.getItem(`${_STORAGE_PREFIX}_chat_history`);
        return history ? JSON.parse(history) : [];
    } catch (error) {
        return [];
    }
}

function clearConversationHistory() {
    try {
        localStorage.removeItem(`${_STORAGE_PREFIX}_chat_history`);
    } catch (error) {
        // Error clearing conversation history
    }
}

function restoreConversationHistory() {
    try {
        const history = getConversationHistory();
        const chatContainer = document.getElementById('chatContainer');

        if (!chatContainer || history.length === 0) {
            return;
        }

        // Find the initial welcome message (the last one with "בינת קוד המקור:" header)
        const existingMessages = Array.from(chatContainer.querySelectorAll('.chat-bubble'));
        const welcomeMessage = existingMessages.find(msg => {
            const header = msg.querySelector('.message-header');
            return header && header.textContent.includes('בינת קוד המקור:') &&
                   msg.querySelector('.message-content').textContent.includes('שלום');
        });

        // Remove all messages except the welcome message
        existingMessages.forEach(msg => {
            if (msg !== welcomeMessage) {
                msg.remove();
            }
        });

        // Restore messages from history
        history.forEach(messageData => {
            const messageElement = createMessageElement(messageData);
            if (messageElement) {
                chatContainer.appendChild(messageElement);
            }
        });

        // Scroll to bottom after restoring
        scrollToBottom(true);
    } catch (error) {
        // Error restoring conversation history
    }
}

function createMessageElement(messageData) {
    try {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-bubble ${messageData.type} animated`;

        if (messageData.type === 'user') {
            messageDiv.innerHTML = `
                <div class="message-content">${messageData.content}</div>
                <div class="message-time">${messageData.timestamp}</div>
            `;
        } else if (messageData.type === 'bot') {
            messageDiv.innerHTML = `
                <div class="message-header">${messageData.header || 'בינת קוד המקור:'}</div>
                <div class="message-content">${messageData.content}</div>
                <div class="message-time">${messageData.timestamp}</div>
            `;
        }

        return messageDiv;
    } catch (error) {
        return null;
    }
}

// Error handling utility
function showError(message, duration = 5000) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> ${sanitizeInput(message)}`;

    const chatContainer = document.getElementById('chatContainer');
    chatContainer.appendChild(errorDiv);
    scrollToBottom();

    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.remove();
        }
    }, duration);
}

// Success handling utility
function showSuccess(message, duration = 5000) {
    const successDiv = document.createElement('div');
    successDiv.className = 'success-message';
    successDiv.innerHTML = `<i class="fas fa-check-circle"></i> ${sanitizeInput(message)}`;

    const chatContainer = document.getElementById('chatContainer');
    chatContainer.appendChild(successDiv);
    scrollToBottom();

    setTimeout(() => {
        if (successDiv.parentNode) {
            successDiv.remove();
        }
    }, duration);
}

// Enhanced scroll management
let userScrolledUp = false;
let lastScrollTop = 0;

// UI state management
function disableUI() {
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const micBtn = document.getElementById('micBtn');

    if (userInput) {
        userInput.disabled = true;
        userInput.placeholder = 'מעבד הודעה...';
    }

    if (micBtn) {
        micBtn.disabled = true;
        micBtn.style.opacity = '0.5';
    }

    // Disable all quick reply buttons
    const quickReplyBtns = document.querySelectorAll('.quick-reply-btn');
    quickReplyBtns.forEach(btn => {
        btn.disabled = true;
        btn.style.opacity = '0.5';
        btn.style.cursor = 'not-allowed';
    });
}

function enableUI() {
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('sendBtn');
    const micBtn = document.getElementById('micBtn');

    if (userInput) {
        userInput.disabled = false;
        userInput.placeholder = 'כתוב לי עכשיו...';
    }

    if (sendBtn) {
        sendBtn.disabled = false;
    }

    if (micBtn) {
        micBtn.disabled = false;
        micBtn.style.opacity = '1';
    }

    // Enable all quick reply buttons
    const quickReplyBtns = document.querySelectorAll('.quick-reply-btn');
    quickReplyBtns.forEach(btn => {
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.style.cursor = 'pointer';
    });
}

// Check if user has manually scrolled up
function checkUserScroll() {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;

    const currentScrollTop = chatContainer.scrollTop;
    const scrollHeight = chatContainer.scrollHeight;
    const clientHeight = chatContainer.clientHeight;

    // User is considered to have scrolled up if they're not at the bottom
    const atBottom = currentScrollTop + clientHeight >= scrollHeight - 50;
    userScrolledUp = !atBottom;

    // Show/hide scroll-to-bottom button
    const btn = document.getElementById('scrollToBottomBtn');
    if (btn) {
        if (userScrolledUp) btn.classList.remove('hidden');
        else btn.classList.add('hidden');
    }

    lastScrollTop = currentScrollTop;
}

// Enhanced scroll to bottom with smart behavior
function scrollToBottom(force = false) {
    const chatContainer = document.getElementById('chatContainer');
    if (!chatContainer) return;

    // Don't auto-scroll if user manually scrolled up (unless forced)
    if (userScrolledUp && !force) {
        return;
    }

    // Use requestAnimationFrame to ensure DOM is updated
    requestAnimationFrame(() => {
        chatContainer.scrollTop = chatContainer.scrollHeight;
        userScrolledUp = false; // Reset flag after auto-scrolling
    });
}


function handleKeyPress(event) {
    if (event.key === 'Enter') {
        if (event.shiftKey) {
            // Allow new line on Shift+Enter
            return;
        } else {
            // Send message on Enter
            event.preventDefault();
            if (!isProcessing) {
                sendMessage();
            } else {
                showError('אנא המתן עד שההודעה הנוכחית תסיים עיבוד');
            }
        }
    } else if (event.key === 'Tab') {
        event.preventDefault();
        // Navigate between controls
        const controls = ['userInput', 'micBtn', 'sendBtn'];
        const currentIndex = controls.indexOf(document.activeElement.id);
        const nextIndex = (currentIndex + 1) % controls.length;
        document.getElementById(controls[nextIndex]).focus();
    }
}

// Auto-resize textarea based on content
function autoResizeTextarea(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
}


// Simple text export function
function exportAsText() {
    try {
        const chatContainer = document.getElementById('chatContainer');
        if (!chatContainer) {
            showError('לא נמצא השיחה');
            return;
        }

        // Get all chat bubbles
        const messages = chatContainer.querySelectorAll('.chat-bubble');

        if (messages.length === 0) {
            showError('אין הודעות לייצוא');
            return;
        }

        // Build simple text content
        let text = 'שיחת בינת קוד המקור\n';
        text += 'משתמש: ' + USER_NAME + '\n';
        text += 'תאריך: ' + new Date().toLocaleDateString('he-IL') + '\n';
        text += '========================================\n\n';

        // Process each message
        for (let i = 0; i < messages.length; i++) {
            const msg = messages[i];
            const isUser = msg.classList.contains('user');

            // Get message content - try different selectors
            let content = '';
            let time = '';

            // Try to find content
            const contentEl = msg.querySelector('.message-content');
            if (contentEl) {
                content = contentEl.innerText || contentEl.textContent || '';
            } else {
                // Fallback: get all text content
                content = msg.innerText || msg.textContent || '';
            }

            // Try to find time
            const timeEl = msg.querySelector('.message-time');
            if (timeEl) {
                time = timeEl.innerText || timeEl.textContent || '';
            }

            // Clean up content
            content = content.replace(/\n\s*\n/g, '\n').trim();

            if (content) {
                const sender = isUser ? USER_NAME : 'בינת קוד המקור';
                text += '[' + time + '] ' + sender + ':\n';
                text += content + '\n\n';
            }
        }

        text += '========================================\n';
        text += `© ${new Date().getFullYear()} PDN Center\n`;

        // Create and download file
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = 'chat-export-' + USER_NAME + '-' + new Date().toISOString().split('T')[0] + '.txt';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        showSuccess('השיחה יוצאה בהצלחה!');

    } catch (error) {
        showError('שגיאה בייצוא השיחה: ' + error.message);
    }
}


// Enhanced send message function with queue and error handling
function toggleSendStop() {
    if (isProcessing) {
        stopMessage();
    } else {
        sendMessage();
    }
}

function stopMessage() {
    if (currentController) {
        currentController.abort();
    }
    isProcessing = false;
    enableUI();
    updateSendButton();
    
    // Add cancellation message
    const chatContainer = document.getElementById("chatContainer");
    const cancelBubble = document.createElement("div");
    cancelBubble.className = "chat-bubble bot animated";
    const currentTime = getCurrentTime();
    cancelBubble.innerHTML = `
        <div class="message-header">בינת:</div>
        <div class="message-content">השליחה בוטלה על ידי המשתמש</div>
        <div class="message-time">${currentTime}</div>
    `;
    chatContainer.appendChild(cancelBubble);
    
    // Remove typing indicator if exists
    const typing = document.querySelector('.typing-indicator');
    if (typing) {
        typing.remove();
    }
    
    scrollToBottom();
}

function updateSendButton() {
    const sendBtn = document.getElementById('sendBtn');
    if (isProcessing) {
        sendBtn.innerHTML = '<i class="fas fa-stop"></i> עצור';
        sendBtn.setAttribute('aria-label', 'עצור שליחה');
    } else {
        sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i> שלח';
        sendBtn.setAttribute('aria-label', 'שלח הודעה');
    }
}

async function sendMessage() {
    const input = document.getElementById("userInput");
    const message = input.value.trim();

    if (message === "" || isProcessing) {
        if (isProcessing) {
            showError('אנא המתן עד שההודעה הנוכחית תסיים עיבוד');
        }
        return;
    }

    // Check if user typed "סיים שיחה" manually
    if (message.toLowerCase().includes("סיים שיחה") ||
        message.toLowerCase().includes("סיים") && message.toLowerCase().includes("שיחה")) {
        handleThankYouClick();
        return;
    }

    // Add to queue
    messageQueue.push(message);
    input.value = "";
    
    // Reset textarea height
    autoResizeTextarea(input);

    // Process queue
    if (!isProcessing) {
        processMessageQueue();
    }
}

// Typewriter effect for bot responses
function typewriterEffect(element, html, speed = 15) {
    return new Promise(resolve => {
        element.innerHTML = '';
        let i = 0;
        const chars = html.split('');
        const interval = setInterval(() => {
            element.innerHTML = chars.slice(0, i + 1).join('');
            i++;
            if (i >= chars.length) {
                clearInterval(interval);
                resolve();
            }
        }, speed);
    });
}

// Session timer update
function updateSessionTimer() {
    const elapsed = Math.floor((Date.now() - sessionStartTime) / 1000);
    const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
    const seconds = (elapsed % 60).toString().padStart(2, '0');
    const el = document.getElementById('sessionTime');
    if (el) el.textContent = `${minutes}:${seconds}`;
}

// Bookmark functionality with localStorage persistence
function getBookmarks() {
    try {
        return JSON.parse(localStorage.getItem(`${_STORAGE_PREFIX}_bookmarks`) || '[]');
    } catch { return []; }
}

function saveBookmarks(bookmarks) {
    localStorage.setItem(`${_STORAGE_PREFIX}_bookmarks`, JSON.stringify(bookmarks));
}

function toggleBookmark(btn) {
    const bubble = btn.closest('.chat-bubble');
    const content = bubble.querySelector('.message-content');
    const time = bubble.querySelector('.message-time');
    const text = content ? (content.innerText || '').trim() : '';
    const timestamp = time ? (time.innerText || '').trim() : getCurrentTime();

    btn.classList.toggle('bookmarked');
    const icon = btn.querySelector('i');
    const bookmarks = getBookmarks();

    if (btn.classList.contains('bookmarked')) {
        icon.className = 'fas fa-bookmark';
        btn.title = 'הסר סימנייה';
        bookmarks.push({ text, timestamp, date: new Date().toISOString() });
        saveBookmarks(bookmarks);
    } else {
        icon.className = 'far fa-bookmark';
        btn.title = 'שמור הודעה';
        const filtered = bookmarks.filter(b => b.text !== text);
        saveBookmarks(filtered);
    }
}

function showBookmarks() {
    const bookmarks = getBookmarks();
    const modal = document.createElement('div');
    modal.className = 'confirmation-modal show';
    modal.style.zIndex = '10000';
    modal.onclick = (e) => { if (e.target === modal) modal.remove(); };

    let listHtml = '';
    if (bookmarks.length === 0) {
        listHtml = '<p class="bookmarks-empty">אין הודעות שמורות עדיין</p>';
    } else {
        listHtml = bookmarks.map((b, i) => `
            <div class="bookmark-item">
                <p class="bookmark-item-text">${b.text.substring(0, 200)}${b.text.length > 200 ? '...' : ''}</p>
                <div class="bookmark-item-footer">
                    <span class="bookmark-item-time">${b.timestamp}</span>
                    <button onclick="removeBookmark(${i}, this)" class="bookmark-remove-btn">
                        <i class="fas fa-trash"></i> הסר
                    </button>
                </div>
            </div>
        `).join('');
    }

    modal.innerHTML = `
        <div class="confirmation-content bookmarks-modal-content">
            <h3 class="confirmation-title bookmarks-modal-title">הודעות שמורות (${bookmarks.length})</h3>
            ${listHtml}
            <div class="bookmarks-actions">
                ${bookmarks.length > 0 ? '<button onclick="exportBookmarks()" class="confirmation-btn confirm" style="font-size:13px;padding:8px 16px;"><i class="fas fa-download"></i> ייצוא</button>' : ''}
                <button onclick="this.closest(\'.confirmation-modal\').remove()" class="confirmation-btn cancel" style="font-size:13px;padding:8px 16px;">סגור</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function removeBookmark(index, btn) {
    const bookmarks = getBookmarks();
    bookmarks.splice(index, 1);
    saveBookmarks(bookmarks);
    btn.closest('.confirmation-modal').remove();
    showBookmarks();
}

function exportBookmarks() {
    const bookmarks = getBookmarks();
    if (bookmarks.length === 0) return;
    let text = `הודעות שמורות - ${USER_NAME}\nתאריך: ${new Date().toLocaleDateString('he-IL')}\n${'='.repeat(40)}\n\n`;
    bookmarks.forEach((b, i) => { text += `${i + 1}. [${b.timestamp}]\n${b.text}\n\n`; });
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `bookmarks-${USER_NAME}-${new Date().toISOString().split('T')[0]}.txt`;
    link.click();
    URL.revokeObjectURL(url);
}

// Dark mode toggle
function toggleChatTheme() {
    document.body.classList.toggle('dark-mode');
    const isDark = document.body.classList.contains('dark-mode');

    // Update fab menu theme icon and text
    const fabThemeIcon = document.getElementById('fabThemeIcon');
    const fabThemeText = document.getElementById('fabThemeText');
    if (fabThemeIcon) fabThemeIcon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
    if (fabThemeText) fabThemeText.textContent = isDark ? 'מצב בהיר' : 'מצב כהה';

    localStorage.setItem(`${_STORAGE_PREFIX}_dark_mode`, isDark);
}

// Floating Action Menu
function toggleFabMenu() {
    const toggle = document.getElementById('fabToggle');
    const dropdown = document.getElementById('fabDropdown');
    const isOpen = dropdown.classList.contains('open');

    if (isOpen) {
        closeFabMenu();
    } else {
        toggle.classList.add('open');
        dropdown.classList.add('open');
    }
}

function closeFabMenu() {
    const toggle = document.getElementById('fabToggle');
    const dropdown = document.getElementById('fabDropdown');
    if (toggle) toggle.classList.remove('open');
    if (dropdown) dropdown.classList.remove('open');
}

async function processMessageQueue() {
    if (messageQueue.length === 0) return;

    isProcessing = true;
    updateSendButton();
    const message = messageQueue.shift();

    const chatContainer = document.getElementById("chatContainer");

    // Disable UI elements
    disableUI();

    // Create user message bubble
    const userBubble = document.createElement("div");
    userBubble.className = "chat-bubble user animated";
    const currentTime = getCurrentTime();
    userBubble.innerHTML = `
            <div class="message-header">${USER_NAME}:</div>
            <div class="message-content">${safeMarkdownParse(message)}</div>
            <div class="message-time">${currentTime}</div>
        `;

    // Save user message to history
    saveMessageToHistory({
        type: 'user',
        content: safeMarkdownParse(message),
        timestamp: currentTime
    });

    chatContainer.appendChild(userBubble);
    scrollToBottom(true); // Force scroll for new user message

    // Show typing indicator
    const typing = document.createElement("div");
    typing.className = "typing-indicator";
    typing.innerHTML = `
            בינת קוד המקור
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
    chatContainer.appendChild(typing);
    scrollToBottom(true); // Force scroll for typing indicator

    try {
        currentController = new AbortController();
        const res = await fetch("/pdn-binat/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify({
                message: sanitizeInput(message),
                user_name: USER_NAME,
                user_id: USER_ID,
                pdn_code: PDN_CODE
            }),
            signal: currentController.signal
        });

        if (!res.ok) {
            // Handle unauthorized access specifically
            if (res.status === 403) {
                const errorData = await res.json();
                typing.remove();
                showError(errorData.response || 'אין לך הרשאה לגשת למערכת');
                return;
            }
            throw new Error(`HTTP error! status: ${res.status}`);
        }

        const data = await res.json();
        typing.remove();

        // Check if response contains error (unauthorized access)
        if (data.error === "Unauthorized access") {
            showError(data.response || 'אין לך הרשאה לגשת למערכת');
            return;
        }

        // Create bot message bubble
        const botBubble = document.createElement("div");
        botBubble.className = "chat-bubble bot animated";
        const botTime = getCurrentTime();
        const botContent = safeMarkdownParse(data.message || data.response || 'מצטער, אירעה שגיאה. אנא נסה שוב.');
        botBubble.innerHTML = `
                <div class="message-header"><img src="/static/images/pdn_logo.png" class="bot-avatar-inline" alt=""> בינת קוד המקור:</div>
                <div class="message-content"></div>
                <div class="message-time">${botTime}</div>
                <div class="message-actions">
                    <button class="bookmark-btn" onclick="toggleBookmark(this)" title="שמור הודעה" aria-label="שמור הודעה">
                        <i class="fas fa-bookmark"></i> שמור
                    </button>
                </div>
            `;

        // Save bot message to history
        saveMessageToHistory({
            type: 'bot',
            content: botContent,
            timestamp: botTime,
            header: 'בינת קוד המקור:'
        });

        chatContainer.appendChild(botBubble);

        // Typewriter effect for bot message
        const contentEl = botBubble.querySelector('.message-content');
        await typewriterEffect(contentEl, botContent, 10);

        scrollToBottom(true); // Force scroll for bot message

        // Add quick reply buttons for bot messages (not first welcome)
        addQuickReplies(botBubble, true);
        scrollToBottom(true); // Force scroll after quick replies

    } catch (error) {
        typing.remove();
        if (error.name === 'AbortError') {
            // Request was aborted by user
        } else {
            showError('שגיאה בשליחת ההודעה לשרת');
        }
    } finally {
        // Re-enable UI elements
        enableUI();
        isProcessing = false;
        currentController = null;
        updateSendButton();

        // Process next message in queue
        if (messageQueue.length > 0) {
            setTimeout(processMessageQueue, 100);
        }
    }
}

// Add quick reply buttons
function addQuickReplies(botBubble, skipCodeInfo = false) {
    const quickReplies = [
       /* "אתגר 21 יום",
        "אימון יומי",*/
        "ספר לי על הקוד שלי"
    ].filter(r => !(skipCodeInfo && r === "ספר לי על הקוד שלי"));

    const quickRepliesDiv = document.createElement("div");
    quickRepliesDiv.className = "quick-replies";

    quickReplies.forEach(reply => {
        const button = document.createElement("button");
        button.className = "quick-reply-btn";
        button.textContent = reply;
        button.onclick = () => {
            // Special handling for "אתגר 21 יום" - show modal
            if (reply === "אתגר 21 יום") {
                // Show 21-day plan modal
                show21PlanModal();
                scrollToBottom(true);
            } else if (reply === "אימון יומי") {
                // Show daily training modal
                showDailyTrainingModal();
                scrollToBottom(true);
            } else {
                // Disable UI before sending message
                if (!isProcessing) {
                    document.getElementById("userInput").value = reply;
                    sendMessage();
                }
            }
        };
        quickRepliesDiv.appendChild(button);
    });

    botBubble.appendChild(quickRepliesDiv);
}

// Handle "תודה על השיחה" click - redirect to login page
function handleThankYouClick() {
    // Show custom confirmation modal
    showConfirmationModal();
}

// Custom confirmation modal functions
function showConfirmationModal() {
    const modal = document.getElementById('confirmationModal');
    modal.classList.add('show');
    document.body.style.overflow = 'hidden';

    // Focus on the first button for accessibility
    setTimeout(() => {
        modal.querySelector('.confirmation-btn.cancel').focus();
    }, 100);
}


function hideConfirmationModal() {
    const modal = document.getElementById('confirmationModal');
    modal.classList.remove('show');
    document.body.style.overflow = '';
}

async function confirmLogout() {
    hideConfirmationModal();

    const logoutEndpoint = (typeof LOGOUT_ENDPOINT !== 'undefined') ? LOGOUT_ENDPOINT : '/pdn-binat/logout';
    const loginPage = (typeof LOGIN_PAGE !== 'undefined') ? LOGIN_PAGE : '/pdn-binat/';

    try {
        // Call logout endpoint to clear server session
        const response = await fetch(logoutEndpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (!response.ok) {
            // Logout failed on server — continue with client cleanup
        }
    } catch (error) {
        // Error during logout
    }

    // Clear session storage for user credentials
    sessionStorage.removeItem('binat_username');
    sessionStorage.removeItem('binat_user_id');
    sessionStorage.removeItem('binat_pdn_code');
    clearConversationHistory();

    // Clear server-side chat history

    // Clear all chat messages visually
    const chatContainer = document.getElementById("chatContainer");
    if (chatContainer) {
        // Remove all existing messages except the initial welcome message
        const existingMessages = Array.from(chatContainer.querySelectorAll('.chat-bubble'));
        existingMessages.forEach(msg => {
            const header = msg.querySelector('.message-header');
            const isWelcomeMessage = header &&
                header.textContent.includes('בינת קוד המקור:') &&
                msg.querySelector('.message-content').textContent.includes('שלום');

            if (!isWelcomeMessage) {
                msg.remove();
            }
        });
    }

    // Show goodbye message before redirecting
    const goodbyeBubble = document.createElement("div");
    goodbyeBubble.className = "chat-bubble bot animated";
    goodbyeBubble.innerHTML = `
            <div class="message-header"><img src="/static/images/pdn_logo.png" class="bot-avatar-inline" alt=""> בינת קוד המקור:</div>
            <div class="message-content">
                <span style="color: #c9a96e;">🌿</span> תודה לך על השיחה היפה!<br>
                בינת קוד המקור תמיד כאן בשבילך.<br>
                עד הפעם הבאה... <span style="color: #c9a96e;">💛</span>
            </div>
            <div class="message-time">${getCurrentTime()}</div>
        `;

    chatContainer.appendChild(goodbyeBubble);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Redirect after a short delay to show the goodbye message
    setTimeout(() => {
        window.location.href = loginPage;
    }, 2000);
}


// Handle escape key to close modal
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        hideConfirmationModal();
    }
});

// Handle click outside modal to close
document.addEventListener('click', function (e) {
    const modal = document.getElementById('confirmationModal');
    if (e.target === modal) {
        hideConfirmationModal();
    }

    // Close fab menu on outside click
    const fabMenu = document.getElementById('fabMenu');
    if (fabMenu && !fabMenu.contains(e.target)) {
        closeFabMenu();
    }
});

// Initialize chat with proper error handling
document.addEventListener("DOMContentLoaded", function () {
    try {
        // Load theme preference
        if (localStorage.getItem(`${_STORAGE_PREFIX}_dark_mode`) === 'true') {
            document.body.classList.add('dark-mode');
            const fabThemeIcon = document.getElementById('fabThemeIcon');
            const fabThemeText = document.getElementById('fabThemeText');
            if (fabThemeIcon) fabThemeIcon.className = 'fas fa-sun';
            if (fabThemeText) fabThemeText.textContent = 'מצב בהיר';
        }

        // Start session timer
        setInterval(updateSessionTimer, 1000);

        // Set up scroll tracking
        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
            chatContainer.addEventListener('scroll', checkUserScroll);
        }

        // Ensure we have the PDN code
        let finalPdnCode = PDN_CODE;
        if (!finalPdnCode || finalPdnCode === 'לא ידוע') {
            const storedPdnCode = sessionStorage.getItem('binat_pdn_code');
            if (storedPdnCode) {
                finalPdnCode = storedPdnCode;
            }
        }

        // Add welcome message (only for binat, not relationship module)
        if (_STORAGE_PREFIX === 'binat') {
        const initialBot = document.createElement("div");
        initialBot.className = "chat-bubble bot animated";

        initialBot.innerHTML = `
                <div class="message-header"><img src="/static/images/pdn_logo.png" class="bot-avatar-inline" alt=""> בינת קוד המקור:</div>
                <div class="message-content">
                    <p class="welcome-greeting"><span style="color: #c9a96e;">🌿</span> שלום ${USER_NAME.toUpperCase()}, קוד המקור שלך הינו <strong>${finalPdnCode.toUpperCase()}</strong></p>
                    <p>בינת קוד המקור ממתינה לך כאן, בקצב שלך.</p>
                    <p class="welcome-closing">אני כאן להזכיר לך – הכוח כבר בתוכך. <span style="color: #c9a96e;">💛</span></p>
                </div>
                <div class="message-time">${getCurrentTime()}</div>
            `;

        chatContainer.appendChild(initialBot);
        addQuickReplies(initialBot, false); // first message - show "ספר לי"
        scrollToBottom(true);
        } // end binat-only welcome message

        // Restore conversation history
        restoreConversationHistory();

        // Focus on input
        document.getElementById("userInput").focus();

    } catch (error) {
        showError('שגיאה בטעינת הממשק');
    }
});


// 21-Day Plan Modal Functions
function show21PlanModal() {
    const modal = document.getElementById('planModal');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Focus on the first input for accessibility
    setTimeout(() => {
        document.getElementById('planGoal').focus();
    }, 100);
}

function hidePlanModal() {
    const modal = document.getElementById('planModal');
    modal.style.display = 'none';
    document.body.style.overflow = '';

    // Reset form
    document.getElementById('planForm').reset();
}

function autoFillPlanForm() {
    // Fill the goal field
    const goalField = document.getElementById('planGoal');
    if (goalField) {
        goalField.value = 'אני רוצה לצעוד בסיום האתגר כל יום 1000 צעדים';
    }
}

async function submitPlanRequest(event) {
    event.preventDefault();

    const submitBtn = document.getElementById('submitPlanBtn');
    const originalText = submitBtn.innerHTML;

    // PDN code data for loading animation (shared with daily training)
    if (!window.PDN_DATA) window.PDN_DATA = {
        'e1':  { name: 'אומץ והעזה',    element: 'Empower - אדנות ומנהיגות',  eng1: 'E1',  eng2: 'A7',  eng3: 'P2',
                 fear: 'פחד משעבוד ואיבוד שליטה',
                 best: 'מנהיגות טבעית, יוזמה ותעוזה, חיבור לאינטואיציה',
                 warn: 'חוסר סבלנות, תגובות חדות לביקורת, התבצרות בעמדות',
                 strengths: ['אומץ ותעוזה לפרוץ גבולות', 'יכולת להנהיג באותנטיות', 'אינטואיציה חדה בהחלטות', 'מיקוד ובהירות במטרה', 'כריזמה סוחפת ומעניקה השראה', 'ראיית חזון ויכולת מימוש'] },
        'e5':  { name: 'קבלה והנהגה',   element: 'Empower - אדנות ומנהיגות',  eng1: 'E5',  eng2: 'A11', eng3: 'P6',
                 fear: 'איבוד שליטה ואובדן חירות פנימית',
                 best: 'סמכות שקטה עם חמלה, תכנון לטווח ארוך, השראת צמיחה',
                 warn: 'אחריות עודפת, צורך בשליטה, עקשנות',
                 strengths: ['סמכות שקטה עם הכלה', 'ראייה רחבה וסדרי עדיפויות', 'מנהיגות אסטרטגית', 'עוגן שמחבר אנשים', 'ביטחון באינטואיציה', 'מיקוד בהשגת יעד', 'חיבור לשמחת חיים'] },
        'e9':  { name: 'חוכמה והתנסות', element: 'Empower - אדנות ומנהיגות',  eng1: 'E9',  eng2: 'A3',  eng3: 'P10',
                 fear: 'פחד משעבוד ואיבוד החופש',
                 best: 'שיתוף חוכמה מניסיון, מנטורינג מתוך חמלה, חופש פנימי',
                 warn: 'ירידה בערך עצמי, עייפות מחוסר הכרה, שינויי כיוון תכופים',
                 strengths: ['הנהגה מתוך תכלית', 'מנטורינג מניסיון אישי', 'יכולת הכוונה מחוכמת הניסיון', 'אופטימיות ואמונה ביכולות', 'יכולת ללמד בסבלנות', 'חיבור לחופש פנימי', 'שמירה על מוניטין והשראת אמון'] },
        'a3':  { name: 'תקשורת ותקווה', element: 'Achievement - הישגיות והצלחה', eng1: 'A3',  eng2: 'E9',  eng3: 'T4',
                 fear: 'פחד מכישלון',
                 best: 'זיהוי הזדמנויות, תקשורת מעוררת השראה, קשרים כמפתח',
                 warn: 'פיזור, צורך באישור, קושי בהתמדה',
                 strengths: ['כושר ביטוי גבוה', 'שנינות וסקרנות', 'חוכמת ניסיון ומנטורינג', 'יכולת שיווקית', 'זיהוי הזדמנויות דרך קשרים', 'איזון עבודה-משפחה', 'השראה טבעית ופתרונות מעשיים'] },
        'a7':  { name: 'תבונה והצלחה',  element: 'Achievement - הישגיות והצלחה', eng1: 'A7',  eng2: 'E1',  eng3: 'T8',
                 fear: 'פחד מכישלון',
                 best: 'הסקת מסקנות מהירה, פיתוח חדשנות, ראיית התמונה הרחבה',
                 warn: 'עיכוב בהחלטות, פרפקציוניזם, רגישות לביקורת',
                 strengths: ['חשיבה תבונית רחבה', 'חיבור ידע, רעיונות וחדשנות', 'תרגום רעיונות ליישום מעשי', 'זיהוי מהיר של הזדמנויות', 'יכולת ייעוץ וראיית הצלחה עתידית', 'אופטימיות ואמונה בהצלחה', 'יכולת ביטוי גבוהה וניתוח מהיר'] },
        'a11': { name: 'הארה וחדשנות',  element: 'Achievement - הישגיות והצלחה', eng1: 'A11', eng2: 'E5',  eng3: 'T12',
                 fear: 'פחד מכישלון',
                 best: 'תרגום תובנות לפתרונות מעשיים, חזון רחב, השראה',
                 warn: 'היצמדות לרעיונות לא מציאותיים, דחיינות, חשדנות',
                 strengths: ['ראיית חזון רחב ורצון לשפר מציאות', 'חשיבה חדשנית ומקורית', 'רצון אמיתי להיטיב עם העולם', 'אמון בחזון ללא סייג', 'השראה טבעית ופתרונות מעשיים'] },
        't4':  { name: 'ביטחון והגנה',  element: 'Trust - ביטחון והרמוניה',    eng1: 'T4',  eng2: 'P10', eng3: 'A3',
                 fear: 'פחד מסכנות ואי ודאות',
                 best: 'פעולה מתוך שקט, חשיבה לוגית, עוגן יציבות לסביבה',
                 warn: 'דאגנות יתר, חשדנות, הסתגרות',
                 strengths: ['יציבות, אחריות ונאמנות גבוהה', 'רגישות לפרטים ולתחושות אחרים', 'ראיית סיכונים והיערכות מראש', 'יכולת להעניק שקט בעת משבר', 'יצירת מרחב מוגן', 'הגנה על הבית, המשפחה והערכים'] },
        't8':  { name: 'צדק ושמירה',    element: 'Trust - ביטחון והרמוניה',    eng1: 'T8',  eng2: 'P2',  eng3: 'A7',
                 fear: 'פחד מסכנות ואי ודאות',
                 best: 'הובלה מתוך ערכים ויושרה, פעולה עקבית ומאוזנת',
                 warn: 'שחור-לבן, שיפוטיות, קושי לסלוח',
                 strengths: ['עמוד שדרה מוסרי וחוק פנימי יציב', 'הבחנה חדה בין נכון ללא נכון', 'הגנה על זכויות ופרטיות', 'ראייה יסודית וחקירה לעומק', 'נאמנות ועמידה בהתחייבויות', 'שליטה עצמית ונחישות', 'שאיפה לצדק חברתי'] },
        't12': { name: 'אחדות והרמוניה',element: 'Trust - ביטחון והרמוניה',    eng1: 'T12', eng2: 'P6',  eng3: 'A11',
                 fear: 'פחד מאובדן ואי ודאות',
                 best: 'הקשבה אותנטית, גישור, שלווה פנימית בחוסר ודאות',
                 warn: 'ויתור על רצונות, ריצוי יתר, קושי בהצבת גבולות',
                 strengths: ['הקשבה עמוקה ואמיתית', 'אמפתיה חמלה וסובלנות', 'אצילות ושלווה במצבי לחץ', 'הבחנה בסכנות מבלי לייצר פחד', 'הרמוניה בבית ובעבודה', 'מענה מאוזן למצבים רגישים', 'גשר ואחדות בין דעות ותרבויות'] },
        'p2':  { name: 'אפשור ועשייה',  element: 'Pleasure - הנאה ושפע',       eng1: 'P2',  eng2: 'T8',  eng3: 'E1',
                 fear: 'פחד מדחייה ואובדן הנאה',
                 best: 'יציבות ובהירות, אמפתיה ונתינה, שביעות רצון ביומיום',
                 warn: 'ביקורת עצמית, היאחזות בשגרה, הימנעות מהזדמנויות',
                 strengths: ['אמינות גבוהה, יציבות ותמיכה', 'יכולת ביצוע מדויקת', 'הקשבה, סבלנות ואמפתיה', 'איזון בין עשייה להנאה', 'השראה באמצעות עקביות ונאמנות'] },
        'p6':  { name: 'צמיחה והדרכה',  element: 'Pleasure - הנאה ושפע',       eng1: 'P6',  eng2: 'T12', eng3: 'E5',
                 fear: 'איבוד אהבה ושייכות',
                 best: 'הדרכה סבלנית, גבולות עדינים עם הרמוניה, ניהול לצמיחה',
                 warn: 'נתינת יתר עד תשישות, ביקורתיות עצמית, קושי לבקש עזרה',
                 strengths: ['ארגון, אבחנה ויעילות', 'הדרכה סבלנית מכילה ומכוונת צמיחה', 'איזון בין עבודה, הנאה ושמחת חיים', 'אחריות אמינות ומחויבות מאוזנת', 'ראיית האסתטיקה והיופי שבחיים'] },
        'p10': { name: 'שפע ונתינה',    element: 'Pleasure - הנאה ושפע',       eng1: 'P10', eng2: 'T4',  eng3: 'E9',
                 fear: 'פחד מדחייה ונטישה',
                 best: 'ביצוע גבוה, נתינה מתוך שמחה, שיתופי פעולה הרמוניים',
                 warn: 'נתינת יתר עד מחסור, ביקורתיות עצמית, קושי לבקש עזרה',
                 strengths: ['יכולת ביצוע גבוהה והתמדה', 'נתינה מתוך שמחה', 'בניית תשתיות ותוצרים איכותיים', 'עבודת צוות והרמוניה', 'חוש אחריות ומנהיגות יציבה', 'שמחת חיים ויכולת לחגוג הצלחות'] },
    };

    const LOADING_MSGS = [
        'בונה תוכנית מותאמת אישית...',
        'מנתח את הצופן שלך...',
        'מתאים משימות למנועים שלך...',
        'יוצר חוויה אישית...',
        'עוד רגע קצר...',
    ];

    function showPlanLoading() {
        const code = (PDN_CODE || 'e5').toLowerCase();
        const data = PDN_DATA[code] || PDN_DATA['e5'];
        document.getElementById('loadingCode').textContent = (PDN_CODE || 'E5').toUpperCase();
        document.getElementById('loadingCodeName').textContent = data.name;
        document.getElementById('loadingElement').textContent = data.element;
        document.getElementById('eng1').textContent = data.eng1;
        document.getElementById('eng2').textContent = data.eng2;
        document.getElementById('eng3').textContent = data.eng3;

        // Make code show popup on hover
        const codeEl = document.getElementById('loadingCode');
        codeEl.style.cursor = 'default';
        codeEl.title = '';

        let hoverPopup = null;

        codeEl.addEventListener('mouseenter', () => {
            if (hoverPopup) return;
            const popup = document.createElement('div');
            popup.id = 'codePopup';
            popup.className = 'code-summary-popup';
            popup.innerHTML = `
                <div class="csp-header">
                    <span class="csp-code">${(PDN_CODE || 'E5').toUpperCase()}</span>
                    <span class="csp-name">${data.name}</span>
                </div>
                <div class="csp-element">${data.element}</div>
                <div class="csp-row">
                    <div class="csp-label">בשיאך</div>
                    <div class="csp-val good">${data.best}</div>
                </div>
                <div class="csp-row">
                    <div class="csp-label">פחד שורשי</div>
                    <div class="csp-val fear">${data.fear}</div>
                </div>
                <div class="csp-row">
                    <div class="csp-label">כשפחד פעיל</div>
                    <div class="csp-val warn">${data.warn}</div>
                </div>
                <div class="csp-engines">
                    <span class="csp-eng dom">${data.eng1} <small>50%</small></span>
                    <span class="csp-eng stab">${data.eng2} <small>30%</small></span>
                    <span class="csp-eng trans">${data.eng3} <small>20%</small></span>
                </div>
            `;
            codeEl.parentElement.appendChild(popup);
            hoverPopup = popup;
        });

        codeEl.addEventListener('mouseleave', (e) => {
            // Small delay so user can move into the popup itself
            setTimeout(() => {
                const popup = document.getElementById('codePopup');
                if (popup && !popup.matches(':hover')) {
                    popup.remove();
                    hoverPopup = null;
                }
            }, 120);
        });

        // Also remove when leaving the popup itself
        codeEl.parentElement.addEventListener('mouseleave', () => {
            const popup = document.getElementById('codePopup');
            if (popup) {
                popup.remove();
                hoverPopup = null;
            }
        });

        // Cycle messages
        let msgIdx = 0;
        let strengthIdx = 0;
        const strengths = data.strengths || [];
        if (strengths.length) {
            document.getElementById('loadingStrength').textContent = strengths[0];
        }
        window._loadingMsgInterval = setInterval(() => {
            msgIdx = (msgIdx + 1) % LOADING_MSGS.length;
            const el = document.getElementById('loadingMsg');
            if (el) el.textContent = LOADING_MSGS[msgIdx];

            if (strengths.length) {
                strengthIdx = (strengthIdx + 1) % strengths.length;
                const sel = document.getElementById('loadingStrength');
                if (sel) {
                    sel.style.animation = 'none';
                    sel.offsetHeight; // reflow to restart animation
                    sel.style.animation = '';
                    sel.textContent = strengths[strengthIdx];
                }
            }
        }, 3000);

        document.getElementById('planLoadingScreen').style.display = 'flex';
        document.getElementById('planContent').style.visibility = 'hidden';
    }

    function hidePlanLoading() {
        clearInterval(window._loadingMsgInterval);
        const screen = document.getElementById('planLoadingScreen');
        if (screen) screen.style.display = 'none';
        const content = document.getElementById('planContent');
        if (content) content.style.visibility = '';
    }

    try {
        // Disable button and show PDN loading animation
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>בונה אתגר 21 יום...';
        showPlanLoading();


        // Get form data
        const formData = new FormData(event.target);
        const goal = formData.get('goal').trim();

        if (!goal) {
            showError('אנא מלא את השדה הנדרש');
            return;
        }

        // Send request to backend with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 150000);

        const response = await fetch('/pdn-binat/21-day-plan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                goal: goal,
                user_name: USER_NAME,
                user_id: USER_ID,
                pdn_code: PDN_CODE
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (response.ok) {
            let data;
            try {
                data = await response.json();
            } catch (jsonError) {
                showError('שגיאה בעיבוד התגובה מהשרת');
                return;
            }

            // Hide modal
            hidePlanLoading();
            hidePlanModal();

            // Add user message to chat
            const chatContainer = document.getElementById("chatContainer");
            const userBubble = document.createElement("div");
            userBubble.className = "chat-bubble user animated";
            const userTime = getCurrentTime();
            const userContent = safeMarkdownParse(goal);
            userBubble.innerHTML = `
                <div class="message-header">${USER_NAME}:</div>
                <div class="message-content">${userContent}</div>
                <div class="message-time">${userTime}</div>

            `;

            // Save user message to history
            saveMessageToHistory({
                type: 'user',
                content: userContent,
                timestamp: userTime
            });

            chatContainer.appendChild(userBubble);

            // Add bot response to chat
            const botBubble = document.createElement("div");
            botBubble.className = "chat-bubble bot animated";
            const botTime = getCurrentTime();
            let botContent;
            // Plan response is HTML - render directly, don't parse as markdown
            const raw = data.response || '';
            if (raw.trim().startsWith('<')) {
                botContent = raw; // already HTML from the LLM
            } else {
                // Fallback: parse as markdown if somehow plain text came back
                botContent = safeMarkdownParse(raw);
            }


            botBubble.innerHTML = `
                <div class="message-header"><img src="/static/images/pdn_logo.png" class="bot-avatar-inline" alt=""> בינת קוד המקור:</div>
                <div class="message-content">${botContent}</div>
                <div class="message-actions">
                    <button class="copy-plan-btn" onclick="downloadPlan(this)" title="הורד את התוכנית">
                        <i class="fas fa-download"></i>
                        <span>הורד תוכנית</span>
                    </button>
                    <button class="bookmark-btn" onclick="toggleBookmark(this)" title="שמור הודעה" aria-label="שמור הודעה">
                        <i class="fas fa-bookmark"></i> שמור
                    </button>
                </div>
                <div class="message-time">${botTime}</div>
            `;

            // Save bot message to history
            saveMessageToHistory({
                type: 'bot',
                content: botContent,
                timestamp: botTime,
                header: 'בינת קוד המקור:'
            });

            chatContainer.appendChild(botBubble);

            // Add quick reply buttons
            addQuickReplies(botBubble);
            scrollToBottom(true);
        } else {
            // Handle unauthorized access specifically
            if (response.status === 403) {
                try {
                    const errorData = await response.json();
                    showError(errorData.response || 'אין לך הרשאה לגשת למערכת');
                } catch (jsonError) {
                    showError('אין לך הרשאה לגשת למערכת');
                }
                return;
            }

            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.error || errorMessage;
            } catch (jsonError) {
                // Error response is not JSON — use HTTP status message
            }
            showError(errorMessage);
        }

    } catch (error) {
        if (error.name === 'AbortError') {
            showError('הבקשה ארכה יותר מדי זמן. אנא נסה שוב או פנה לתמיכה אם הבעיה נמשכת.');
        } else if (error.message && error.message.includes('timeout')) {
            showError('הבקשה ארכה יותר מדי זמן. זה יכול להיות בגלל עומס על השרת. אנא נסה שוב בעוד כמה רגעים.');
        } else {
            showError('שגיאה בשליחת הבקשה לשרת');
        }
    } finally {
        // Restore button and hide loading
        hidePlanLoading();
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

// Copy plan to clipboard function
async function copyPlanToClipboard(button) {
    try {
        // Find the message content in the same chat bubble
        const chatBubble = button.closest('.chat-bubble');
        const messageContent = chatBubble.querySelector('.message-content');

        if (!messageContent) {
            showError('לא ניתן למצוא את תוכן התוכנית');
            return;
        }

        // Get the text content (without HTML tags)
        const textToCopy = messageContent.innerText || messageContent.textContent;

        // Copy to clipboard
        await navigator.clipboard.writeText(textToCopy);

        // Show success feedback
        const originalText = button.querySelector('span').textContent;
        const originalIcon = button.querySelector('i').className;

        button.querySelector('span').textContent = 'הועתק!';
        button.querySelector('i').className = 'fas fa-check';
        button.style.background = '#28a745';

        // Reset after 2 seconds
        setTimeout(() => {
            button.querySelector('span').textContent = originalText;
            button.querySelector('i').className = originalIcon;
            button.style.background = '';
        }, 2000);

    } catch (error) {
        showError('שגיאה בהעתקה ללוח. אנא נסה שוב.');
    }
}

// Download plan as HTML file
function downloadPlan(button) {
    try {
        const chatBubble = button.closest('.chat-bubble');
        const messageContent = chatBubble.querySelector('.message-content');

        if (!messageContent) {
            showError('לא ניתן למצוא את תוכן התוכנית');
            return;
        }

        const planHtml = messageContent.innerHTML;
        const date = new Date().toLocaleDateString('he-IL');
        const fileName = `תוכנית-21-יום-${USER_NAME}-${new Date().toISOString().split('T')[0]}.html`;

        const fileContent = `<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>תוכנית 21 יום - ${USER_NAME}</title>
<style>
  body { font-family: Arial, sans-serif; background: #f0f4f8; direction: rtl; padding: 32px 20px; margin: 0; }
  .wrapper { max-width: 680px; margin: 0 auto; }
  .cover { background: linear-gradient(135deg,#1a2540,#2d3a5e); border-radius: 16px; padding: 22px 26px; color: white; margin-bottom: 24px; text-align: right; }
  .cover h1 { font-size: 1.3rem; font-weight: 800; margin: 0 0 4px; }
  .cover p { font-size: 0.85rem; color: rgba(255,255,255,0.65); margin: 0; }
  .cover .meta { font-size: 0.78rem; color: #c9a96e; margin-top: 6px; }
  .content { background: white; border-radius: 16px; padding: 24px; box-shadow: 0 2px 12px rgba(0,0,0,0.07); }
  footer { text-align: center; font-size: 12px; color: #94a3b8; margin-top: 24px; }
</style>
</head>
<body>
<div class="wrapper">
  <div class="cover">
    <h1>תוכנית 21 יום - ${USER_NAME}</h1>
    <p>קוד המקור: ${(PDN_CODE || '').toUpperCase()}</p>
    <div class="meta">תאריך הפקה: ${date} | PDN Center - בינת קוד המקור</div>
  </div>
  <div class="content">
    ${planHtml}
  </div>
  <footer>&copy; ${new Date().getFullYear()} PDN Center - בינת קוד המקור</footer>
</div>
</body>
</html>`;

        const blob = new Blob([fileContent], { type: 'text/html;charset=utf-8' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = fileName;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        // Show success feedback
        const originalText = button.querySelector('span').textContent;
        const originalIcon = button.querySelector('i').className;

        button.querySelector('span').textContent = 'הורד!';
        button.querySelector('i').className = 'fas fa-check';
        button.style.background = '#28a745';

        // Reset after 2 seconds
        setTimeout(() => {
            button.querySelector('span').textContent = originalText;
            button.querySelector('i').className = originalIcon;
            button.style.background = '';
        }, 2000);

    } catch (error) {
        showError('שגיאה בהורדת התוכנית. אנא נסה שוב.');
    }
}

// Handle Enter key press in 21-day plan form
function handlePlanFormKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        const form = document.getElementById('planForm');
        if (form) {
            form.requestSubmit();
        }
    }
}

// Daily Training Modal Functions
function showDailyTrainingModal() {
    const modal = document.getElementById('dailyTrainingModal');
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';

    // Focus on the task input for accessibility
    setTimeout(() => {
        document.getElementById('trainingTask').focus();
    }, 100);
}

function hideDailyTrainingModal() {
    const modal = document.getElementById('dailyTrainingModal');
    modal.style.display = 'none';
    document.body.style.overflow = '';

    // Reset form
    document.getElementById('dailyTrainingForm').reset();
}

function autoFillDailyTrainingForm() {
    // Fill the task field with a sample
    const taskField = document.getElementById('trainingTask');
    if (taskField) {
        taskField.value = 'לרוץ 5 ק״מ';
    }

}

async function submitDailyTrainingRequest(event) {
    event.preventDefault();

    const submitBtn = document.getElementById('submitDailyTrainingBtn');
    const originalText = submitBtn.innerHTML;

    try {
        // Disable button and show PDN loading animation
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>שולח...';

        // Show loading screen
        const DAILY_MSGS = ['מכין אימון יומי מותאם...', 'מנתח את הצופן שלך...', 'בונה משימה אישית...', 'עוד רגע...'];
        const code = (PDN_CODE || 'e5').toLowerCase();
        const dailyData = PDN_DATA[code] || PDN_DATA['e5'];
        document.getElementById('dailyLoadingCode').textContent = (PDN_CODE || 'E5').toUpperCase();
        document.getElementById('dailyLoadingCodeName').textContent = dailyData.name;
        document.getElementById('dailyLoadingElement').textContent = dailyData.element;
        document.getElementById('dailyEng1').textContent = dailyData.eng1;
        document.getElementById('dailyEng2').textContent = dailyData.eng2;
        document.getElementById('dailyEng3').textContent = dailyData.eng3;
        let dailyMsgIdx = 0;
        let dailyStrengthIdx = 0;
        const dailyStrengths = dailyData.strengths || [];
        if (dailyStrengths.length) {
            document.getElementById('dailyLoadingStrength').textContent = dailyStrengths[0];
        }
        window._dailyMsgInterval = setInterval(() => {
            dailyMsgIdx = (dailyMsgIdx + 1) % DAILY_MSGS.length;
            const el = document.getElementById('dailyLoadingMsg');
            if (el) el.textContent = DAILY_MSGS[dailyMsgIdx];

            if (dailyStrengths.length) {
                dailyStrengthIdx = (dailyStrengthIdx + 1) % dailyStrengths.length;
                const sel = document.getElementById('dailyLoadingStrength');
                if (sel) {
                    sel.style.animation = 'none';
                    sel.offsetHeight;
                    sel.style.animation = '';
                    sel.textContent = dailyStrengths[dailyStrengthIdx];
                }
            }
        }, 2500);
        document.getElementById('dailyLoadingScreen').style.display = 'flex';
        document.getElementById('dailyTrainingContent').style.visibility = 'hidden';

        // Get form data
        const formData = new FormData(event.target);
        const task = formData.get('task').trim();

        if (!task) {
            showError('אנא מלא את השדה הנדרש');
            return;
        }

        // Send request to backend
        const response_data = await fetch('/pdn-binat/daily-training', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                task: task,
                user_name: USER_NAME,
                user_id: USER_ID,
                pdn_code: PDN_CODE
            })
        });

        if (response_data.ok) {
            let data;
            try {
                data = await response_data.json();
            } catch (jsonError) {
                showError('שגיאה בעיבוד התגובה מהשרת');
                return;
            }

            // Hide modal
            clearInterval(window._dailyMsgInterval);
            document.getElementById('dailyLoadingScreen').style.display = 'none';
            document.getElementById('dailyTrainingContent').style.visibility = '';
            hideDailyTrainingModal();

            // Add user message to chat
            const chatContainer = document.getElementById("chatContainer");
            const userBubble = document.createElement("div");
            userBubble.className = "chat-bubble user animated";
            const userTime = getCurrentTime();
            const userContent = safeMarkdownParse(`אימון יומי:\n\n**המשימה שלי:**\n${task}`);
            userBubble.innerHTML = `
                <div class="message-header">${USER_NAME}:</div>
                <div class="message-content">${userContent}</div>
                <div class="message-time">${userTime}</div>
            `;

            // Save user message to history
            saveMessageToHistory({
                type: 'user',
                content: userContent,
                timestamp: userTime
            });

            chatContainer.appendChild(userBubble);

            // Add bot response to chat
            const botBubble = document.createElement("div");
            botBubble.className = "chat-bubble bot animated";
            const botTime = getCurrentTime();
            let botContent = safeMarkdownParse(data.response || 'תודה על השיתוף! המשיכה בדרך שלך.');

            botBubble.innerHTML = `
                <div class="message-header"><img src="/static/images/pdn_logo.png" class="bot-avatar-inline" alt=""> בינת קוד המקור:</div>
                <div class="message-content">${botContent}</div>
                <div class="message-actions">
                    <button class="bookmark-btn" onclick="toggleBookmark(this)" title="שמור הודעה" aria-label="שמור הודעה">
                        <i class="fas fa-bookmark"></i> שמור
                    </button>
                </div>
                <div class="message-time">${botTime}</div>
            `;

            // Save bot message to history
            saveMessageToHistory({
                type: 'bot',
                content: botContent,
                timestamp: botTime,
                header: 'בינת קוד המקור:'
            });

            chatContainer.appendChild(botBubble);

            // Add quick reply buttons
            addQuickReplies(botBubble);
            scrollToBottom(true);

        } else {
            // Handle unauthorized access specifically
            if (response_data.status === 403) {
                try {
                    const errorData = await response_data.json();
                    showError(errorData.response || 'אין לך הרשאה לגשת למערכת');
                } catch (jsonError) {
                    showError('אין לך הרשאה לגשת למערכת');
                }
                return;
            }

            let errorMessage = `HTTP ${response_data.status}: ${response_data.statusText}`;
            try {
                const errorData = await response_data.json();
                errorMessage = errorData.error || errorMessage;
            } catch (jsonError) {
                // Error response is not JSON — use HTTP status message
            }
            showError(errorMessage);
        }

    } catch (error) {
        showError('שגיאה בשליחת הבקשה לשרת');
    } finally {
        // Restore button and hide loading
        clearInterval(window._dailyMsgInterval);
        const dl = document.getElementById('dailyLoadingScreen');
        if (dl) dl.style.display = 'none';
        const dc = document.getElementById('dailyTrainingContent');
        if (dc) dc.style.visibility = '';
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
}

// Handle Enter key press in daily training form
function handleDailyTrainingFormKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        const form = document.getElementById('dailyTrainingForm');
        if (form) {
            form.requestSubmit();
        }
    }
}

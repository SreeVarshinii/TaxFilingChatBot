document.addEventListener('DOMContentLoaded', () => {
    const chatContainer = document.getElementById('chat-container');
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const skipDateBtn = document.getElementById('skip-date-btn');
    const saveDateBtn = document.getElementById('save-date-btn');
    const entryDateInput = document.getElementById('entry-date-input');
    const resetBtn = document.getElementById('reset-btn');
    
    let entryDate = null;
    let isWaitingForResponse = false;
    
    // Auto-resize textarea
    userInput.addEventListener('input', function() {
        this.style.height = 'auto';
        const newHeight = Math.min(this.scrollHeight, 150);
        this.style.height = newHeight + 'px';
        sendBtn.disabled = this.value.trim() === '' || isWaitingForResponse;
    });

    // Enter to send
    userInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            if (!sendBtn.disabled) sendQuery();
        }
    });

    sendBtn.addEventListener('click', sendQuery);
    
    skipDateBtn.addEventListener('click', () => completeOnboarding(null));
    saveDateBtn.addEventListener('click', () => {
        const val = entryDateInput.value;
        if(val) completeOnboarding(val);
    });
    
    resetBtn.addEventListener('click', () => {
        if(confirm('Are you sure you want to reset the context?')) {
            location.reload();
        }
    });

    function completeOnboarding(dateStr) {
        entryDate = dateStr;
        document.getElementById('onboarding-controls').style.display = 'none';
        
        let msg = "Got it! ";
        if(dateStr) {
            msg += `Your entry date (${dateStr}) is saved. `;
        } else {
            msg += `We will proceed without determining your residency based on the 5-year rule. `;
        }
        msg += "What is your tax question?";
        
        appendSystemMessage(msg);
        
        // Enable chat inputs
        userInput.disabled = false;
        userInput.focus();
    }

    async function sendQuery() {
        const question = userInput.value.trim();
        if(!question) return;
        
        // Lock UI
        userInput.value = '';
        userInput.style.height = 'auto';
        userInput.disabled = true;
        sendBtn.disabled = true;
        isWaitingForResponse = true;
        
        appendUserMessage(question);
        
        const loadingId = appendSystemMessage('<span class="loading-dots">Thinking<span>.</span><span>.</span><span>.</span></span>', true);
        
        try {
            const apiEndpoint = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
                ? 'http://localhost:7071/api/chat' 
                : '/api/chat';
                
            const response = await fetch(apiEndpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question, entry_date: entryDate })
            });
            
            removeMessage(loadingId);
            
            if(!response.ok) {
                const errText = await response.text();
                throw new Error(errText || `Server error: ${response.status}`);
            }
            
            const data = await response.json();
            appendSystemMessage(data.answer, false, data.context);
            
        } catch(e) {
            removeMessage(loadingId);
            appendSystemMessage(`**Error:** Unable to reach the server. ${e.message}`);
        } finally {
            isWaitingForResponse = false;
            userInput.disabled = false;
            userInput.focus();
        }
    }
    
    function appendUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'message user';
        div.innerHTML = `
            <div class="avatar">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            </div>
            <div class="message-content">
                <p>${escapeHtml(text)}</p>
            </div>
        `;
        chatContainer.appendChild(div);
        scrollToBottom();
    }
    
    function appendSystemMessage(textHtml, isHtml=false, contextData=null) {
        const id = 'msg-' + Date.now();
        const div = document.createElement('div');
        div.className = 'message system';
        div.id = id;
        
        // Basic markdown parser (bold)
        const parsedText = isHtml ? textHtml : escapeHtml(textHtml).replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>').replace(/\\n/g, '<br/>');
        
        let contextHtml = '';
        if(contextData && contextData.length > 0) {
            contextHtml = '<div class="sources-container"><div class="sources-title">Retrieved Sources</div>';
            contextData.forEach((ctx, idx) => {
                const title = ctx.metadata?.title || `Source ${idx+1}`;
                const formType = ctx.metadata?.form_type ? `[${ctx.metadata.form_type}]` : '';
                contextHtml += `
                 <div class="source-citation">
                    <button class="source-toggle" onclick="this.classList.toggle('active'); this.nextElementSibling.style.display = this.nextElementSibling.style.display === 'none' ? 'block' : 'none';">
                        <span class="source-title">${escapeHtml(title)} ${formType}</span>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="chevron"><polyline points="6 9 12 15 18 9"></polyline></svg>
                    </button>
                    <div class="source-content" style="display: none;">
                        <p class="source-text">${escapeHtml(ctx.content)}</p>
                    </div>
                </div>
                `;
            });
            contextHtml += '</div>';
        }
        
        div.innerHTML = `
            <div class="avatar">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="10" rx="2"></rect><circle cx="12" cy="5" r="2"></circle><path d="M12 7v4"></path></svg>
            </div>
            <div class="message-content glass-panel">
                <p>${parsedText}</p>
                ${contextHtml}
            </div>
        `;
        chatContainer.appendChild(div);
        scrollToBottom();
        return id;
    }
    
    function removeMessage(id) {
        const el = document.getElementById(id);
        if(el) el.remove();
    }
    
    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    function escapeHtml(unsafe) {
        if(!unsafe) return "";
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
});

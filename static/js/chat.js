const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const chatBox = document.getElementById('chat-box');

function setExample(example) {
    userInput.value = example;
}

function createThinkingIndicator() {
    const thinkingDiv = document.createElement('div');
    thinkingDiv.className = 'chat-bubble bot-message thinking-indicator';
    thinkingDiv.innerHTML = 'thinking<span class="dots">...</span>';
    return thinkingDiv;
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message) return;
    
    // Disable input and button while processing
    userInput.disabled = true;
    sendButton.disabled = true;
    
    // Display user message
    const userMessage = document.createElement('div');
    userMessage.className = 'chat-bubble user-message';
    userMessage.textContent = message;
    chatBox.appendChild(userMessage);
    
    // Clear input
    userInput.value = '';
    
    // Create and show thinking indicator in the message flow
    const thinkingIndicator = createThinkingIndicator();
    chatBox.appendChild(thinkingIndicator);
    chatBox.scrollTop = chatBox.scrollHeight;
    
    let lastContent = '';  // Track last content to avoid duplicates
    
    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `query=${encodeURIComponent(message)}`
        });
        
        // Handle 401 Unauthorized
        if (response.status === 401) {
            const json = await response.json();
            thinkingIndicator.innerHTML = `<a href="${json.redirect}">Session expired. Log in again</a>`;
            showError(json.error || 'Session expired. Please log in again.');
            return;
        }
        
        // Handle other non-OK responses
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // Create bot message container to replace thinking indicator
        const botMessage = document.createElement('div');
        botMessage.className = 'chat-bubble bot-message';
        
        // Replace thinking indicator with actual message container
        chatBox.replaceChild(botMessage, thinkingIndicator);
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let fullMessage = '';
        
        while (true) {
            const {done, value} = await reader.read();
            if (done) {
                console.log("Stream done");
                break;
            }
            
            const chunk = decoder.decode(value, {stream: true});
            console.log("Raw chunk:", chunk);
            var cleanChunk = chunk;
            if (cleanChunk && cleanChunk !== '[DONE]') {
                if (cleanChunk !== lastContent) {
                    fullMessage += cleanChunk;
                    botMessage.innerHTML = marked.parse(fullMessage);
                    lastContent = cleanChunk;
                }
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }
    } catch (error) {
        console.error('Error:', error);
        // Replace thinking indicator with error message
        thinkingIndicator.innerHTML = 'Sorry, there was an error processing your request.';
        showError('An error occurred while processing your request.');
    } finally {
        // Re-enable input and button
        userInput.disabled = false;
        sendButton.disabled = false;
        userInput.focus();
    }
}

function showError(message) {
    const errorMessage = document.getElementById('error-message');
    errorMessage.style.display = 'block';
    errorMessage.textContent = message;
    
    // Hide error after 5 seconds
    setTimeout(() => {
        errorMessage.style.display = 'none';
    }, 5000);
}

function checkEnter(event) {
    if (event.key === 'Enter' && !event.shiftKey && !userInput.disabled) {
        event.preventDefault();
        sendMessage();
    }
}
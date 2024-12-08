const userInput = document.getElementById('user-input');
const sendButton = document.getElementById('send-button');
const chatBox = document.getElementById('chat-box');

function setExample(example) {
    userInput.value = example;
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

    // Create bot message container
    const botMessage = document.createElement('div');
    botMessage.className = 'chat-bubble bot-message';
    chatBox.appendChild(botMessage);

    let lastContent = '';  // Track last content to avoid duplicates

    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `query=${encodeURIComponent(message)}`
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const {done, value} = await reader.read();
            if (done) {
                console.log("Stream done");
                break;
            }

            const chunk = decoder.decode(value, {stream: true});
            console.log("Raw chunk:", chunk);  // Keep for debugging
            //var message = chunk.trim();
            var cleanChunk = chunk
            if (cleanChunk && cleanChunk !== '[DONE]') {
                try {
                    // First try to parse as JSON
                    const jsonData = JSON.parse(cleanChunk);
                    const content = jsonData.content || jsonData.chunk || jsonData;
                    if (content !== lastContent) {  // Only update if content changed
                        botMessage.innerHTML = content;
                        lastContent = content;
                    }
                } catch (e) {
                    // Not JSON, handle as HTML from markdown
                    if (cleanChunk !== lastContent) {  // Only update if content changed
                        botMessage.innerHTML = cleanChunk;
                        lastContent = cleanChunk;
                    }
                }
                chatBox.scrollTop = chatBox.scrollHeight;
            }
        }
    } catch (error) {
        console.error('Error:', error);
        showError('An error occurred while processing your request.');
        botMessage.innerHTML = 'Sorry, there was an error processing your request.';
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
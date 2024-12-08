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
    userMessage.textContent = message;  // Keep this as textContent for user message
    chatBox.appendChild(userMessage);

    // Clear input
    userInput.value = '';

    // Create bot message container
    const botMessage = document.createElement('div');
    botMessage.className = 'chat-bubble bot-message';
    chatBox.appendChild(botMessage);

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
        let responseText = '';

        while (true) {
            const {done, value} = await reader.read();
            if (done) {
                console.log("Stream done");
                break;
            }
            
            // Decode the chunk and clean up the data
            const chunk = decoder.decode(value, {stream: true});
            console.log("Raw chunk:", chunk); // Debug log
            
            const messages = chunk.split('\n\n');
            for (const message of messages) {
                if (message.startsWith('data: ')) {
                    const cleanChunk = message.replace('data: ', '').trim();
                    console.log("Clean chunk:", cleanChunk); // Debug log
                    
                    if (cleanChunk && cleanChunk !== '[DONE]') {
                        try {
                            // Try parsing the chunk as JSON if it's JSON data
                            const jsonData = JSON.parse(cleanChunk);
                            botMessage.innerHTML = jsonData.content || jsonData.message || jsonData;
                        } catch (e) {
                            // If it's not JSON, use it directly
                            botMessage.innerHTML = cleanChunk;
                        }
                        chatBox.scrollTop = chatBox.scrollHeight;
                    }
                }
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
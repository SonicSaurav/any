// Global variable to keep track of the current chat ID.
let currentChatId = null;

/**
 * Updates the chat ID display on the frontend.
 */
function updateChatIdDisplay() {
    const chatIdSpan = document.getElementById('chat-id');
    // Show the chat ID if available; otherwise, display a placeholder.
    chatIdSpan.textContent = currentChatId !== null ? currentChatId : 'None';
}

/**
 * Start a new chat session and store the chat ID.
 */
async function startNewChat() {
    try {
        const response = await fetch("/assistant/chat/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const data = await response.json();
        if (data.chat_id) {
            currentChatId = data.chat_id;
            updateChatIdDisplay();
        }
    } catch (error) {
        console.error("Error starting a new chat:", error);
    }
}


/**
 * If second assistant is enabled, we add a button below both assistant messages.
 * Clicking this "Prefer" button will mark that output as preferred.
 * Then we hide the other assistant output from the same parent message.
 *
 * We'll call /assistant/chat/<chat_id>/message/<message_id>/prefer.
 * This route requires { preferred_output: 1 or 2 } in the POST body.
 * On success, we hide the sibling message.
 */
async function preferOutput(parentMessageId, outputNumber) {
    if (!currentChatId) {
        console.warn('No current chat for preferOutput.');
        return;
    }
    try {
        const response = await fetch(`/assistant/chat/${currentChatId}/message/${parentMessageId}/prefer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preferred_output: outputNumber })
        });
        const data = await response.json();
        if (data.error) {
            console.error('Error preferring message:', data.error);
            return;
        }
        console.log('Preferred output updated:', data);

        // Hide the sibling message in the UI.
        // The sibling has the same data-parent-id but a different data-output-number.
        const otherOutputNumber = outputNumber === 1 ? 2 : 1;
        const sibling = document.querySelector(
            `[data-parent-id='${parentMessageId}'][data-output-number='${otherOutputNumber}']`
        );
        if (sibling) {
            sibling.style.display = 'none';
        }
    } catch (err) {
        console.error('Failed to prefer output:', err);
    }
}

/**
 * Appends a message bubble to the messages container.
 * Each message now includes a unique ID for identification.
 * If the message is from the assistant and includes a critic score,
 * a small circle with the score is added.
 * If second assistant is enabled, we also add a "Prefer" button.
 *
 * @param {string} id            - The unique assistant_message ID.
 * @param {string} text          - The message content.
 * @param {string} role          - 'assistant' or 'user'.
 * @param {string} [criticScore] - (Optional) The critic score.
 * @param {boolean} [isDummy]    - (Optional) If this message is a placeholder.
 * @param {string} [parentId]    - The parent Message ID.
 * @param {number} [outputNumber]- The assistant output number (1 or 2).
 */
function addMessageToChat(
    id,
    text,
    role,
    criticScore,
    isDummy = false,
    parentId = null,
    outputNumber = null
) {
    const messagesContainer = document.getElementById('messages');

    // Check if the message already exists
    let existingMessage = document.querySelector(`[data-message-id='${id}']`);
    if (existingMessage) {
        // Update the critic score if needed
        if (criticScore !== undefined) {
            let criticCircle = existingMessage.querySelector('.critic-score');
            if (!criticCircle) {
                criticCircle = document.createElement('div');
                criticCircle.className = 'critic-score absolute top-0 right-0 mt-1 mr-1 text-xs text-white bg-red-500 rounded-full w-5 h-5 flex items-center justify-center';
                existingMessage.appendChild(criticCircle);
            }
            criticCircle.textContent = criticScore;
        }
        return;
    }

    // Create the message bubble container.
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'p-4 rounded-lg max-w-[75%] min-w-[25%] break-words flex flex-col relative';
    bubbleDiv.setAttribute('data-message-id', id);
    if (parentId) {
        bubbleDiv.setAttribute('data-parent-id', parentId);
    }
    if (outputNumber) {
        bubbleDiv.setAttribute('data-output-number', outputNumber.toString());
    }

    // Mark this bubble as a dummy if requested.
    if (isDummy) {
        bubbleDiv.classList.add('dummy-message');
    }

    // Create an element for the message text.
    const textSpan = document.createElement('span');
    textSpan.textContent = text;
    bubbleDiv.appendChild(textSpan);

    // If assistant + critic score, add small circle.
    if (role === 'assistant' && criticScore !== undefined) {
        const criticCircle = document.createElement('div');
        criticCircle.textContent = criticScore;
        criticCircle.className = 'critic-score absolute top-0 right-0 mt-1 mr-1 text-xs text-white bg-red-500 rounded-full w-5 h-5 flex items-center justify-center';
        bubbleDiv.appendChild(criticCircle);
    }

    // If second assistant is enabled AND role===assistant AND outputNumber is valid,
    // add a "Prefer" button to choose this output.
    const secondAssistantToggle = document.getElementById('second-assistant-toggle');
    const secondAssistantEnabled = secondAssistantToggle && secondAssistantToggle.checked;
    if (role === 'assistant' && secondAssistantEnabled && outputNumber) {
        const preferBtn = document.createElement('button');
        preferBtn.textContent = 'Prefer';
        preferBtn.className = 'mt-2 text-xs self-end bg-blue-500 hover:bg-blue-600 text-white px-2 py-1 rounded';
        preferBtn.onclick = () => {
            if (!parentId) {
                console.warn('No parent message ID to prefer.');
                return;
            }
            preferOutput(parentId, outputNumber);
        };
        bubbleDiv.appendChild(preferBtn);
    }

    // Assign classes for styling.
    bubbleDiv.classList.add(role === 'assistant' ? 'assistant-message' : 'user-message');

    messagesContainer.appendChild(bubbleDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Polls the server every 5 seconds to update critic scores.
 */
async function pollCriticScores() {
    if (!currentChatId) return;

    try {
        const response = await fetch(`/assistant/chat/score/${currentChatId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (data.scores) {
            data.scores.forEach(scoreObj => {
                // Update existing messages without modifying text
                let existingMessage = document.querySelector(`[data-message-id='${scoreObj.id}']`);
                if (existingMessage) {
                    let criticCircle = existingMessage.querySelector('.critic-score');
                    if (!criticCircle) {
                        criticCircle = document.createElement('div');
                        criticCircle.className = 'critic-score absolute top-0 right-0 mt-1 mr-1 text-xs text-white bg-red-500 rounded-full w-5 h-5 flex items-center justify-center';
                        existingMessage.appendChild(criticCircle);
                    }
                    // Check if the score has changed
                    if (scoreObj.critic_score !== null && criticCircle.textContent !== scoreObj.critic_score.toString()) {
                        criticCircle.textContent = scoreObj.critic_score;

                        // Force a DOM update by toggling opacity
                        existingMessage.style.opacity = '0.99';
                        setTimeout(() => {
                            existingMessage.style.opacity = '1';
                        }, 10);
                    }
                }
            });
        }
    } catch (err) {
        console.error('Error fetching critic scores:', err);
    }
}

/**
 * Removes only the dummy messages from the messages container.
 */
function removeDummyMessages() {
    const dummyMessages = document.querySelectorAll('.dummy-message');
    dummyMessages.forEach(dummy => dummy.remove());
}

/**
 * Clears all messages from the messages container.
 */
function clearAllMessages() {
    const messagesContainer = document.getElementById('messages');
    messagesContainer.innerHTML = '';
}

/**
 * Sends a POST /assistant/chat request to the server with the user_input and, if available, the chat_id.
 * The server returns a JSON object with the message dump (including assistant messages).
 *
 * @param {string} userInput
 */
async function sendToServer(userInput) {
    try {
        const payload = { user_input: userInput };
        if (currentChatId) {
            payload.chat_id = currentChatId;
        }
        console.log("Sending payload:", payload);
        
        const response = await fetch('/assistant/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();
        console.log("Received data:", data);

        if (data.error) {
            removeDummyMessages();
            addMessageToChat('error', data.error, 'assistant');
            return;
        }

        // Update the global currentChatId if the server returns one.
        if (data.chat_id) {
            currentChatId = data.chat_id;
            updateChatIdDisplay();
        }

        // Wait one second before updating the UI.
        setTimeout(() => {
            removeDummyMessages();

            // user_message
            if (data.user_message) {
                addMessageToChat(
                    data.user_message.id,
                    data.user_message.content,
                    'user',
                    undefined,
                    false,
                    null, // parent ID not needed for user message
                    null  // no outputNumber
                );
            }

            // assistant_message (primary)
            if (data.assistant_message) {
                addMessageToChat(
                    data.assistant_message.id,
                    data.assistant_message.content,
                    'assistant',
                    data.assistant_message.critic_score,
                    false,
                    data.id, // use the parent 'Message' id
                    data.assistant_message.output_number // might be 1
                );
            }

            // assistant_message2 (secondary)
            if (data.assistant_message2) {
                addMessageToChat(
                    data.assistant_message2.id,
                    data.assistant_message2.content,
                    'assistant',
                    data.assistant_message2.critic_score,
                    false,
                    data.id, // same parent message ID
                    data.assistant_message2.output_number // might be 2
                );
            }
        }, 1000);

    } catch (err) {
        console.error('Error sending to server:', err);
        removeDummyMessages();
        addMessageToChat('error', "Error: Failed to get response from server.", 'assistant');
    }
}

// DOM elements
const userInputEl = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const refreshBtn = document.getElementById('refresh-btn');
const secondAssistantToggle = document.getElementById('second-assistant-toggle');

/**
 * Handles sending the user's message.
 */
function handleSend() {
    const text = userInputEl.value.trim();
    if (!text) return;

    userInputEl.value = '';
    addMessageToChat('temp-user', text, 'user', undefined, true);
    addMessageToChat('temp-assistant', "Assistant is typing...", 'assistant', undefined, true);

    setTimeout(() => {
        sendToServer(text);
    }, 1000);
}

/**
 * Refreshes the current chat session.
 */
function refreshSession() {
    currentChatId = null;
    updateChatIdDisplay();
    clearAllMessages();
    addMessageToChat('system-refresh', "Session refreshed.", 'assistant');
}

/**
 * Toggles the second assistant by calling the appropriate API endpoint.
 * @param {boolean} enable
 */
async function toggleSecondAssistant(enable) {
    if (!currentChatId) {
        console.warn('No current chat. Create or join a chat first.');
        secondAssistantToggle.checked = false;
        return;
    }

    const url = enable
        ? `/assistant/chat/enable_second_assistant/${currentChatId}`
        : `/assistant/chat/disable_second_assistant/${currentChatId}`;

    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        // If the backend returns success
        if (data.error) {
            console.warn('Toggling second assistant failed:', data.error);
            secondAssistantToggle.checked = !enable; // revert
        } else if (data.success !== undefined && data.success !== true) {
            console.warn('Unexpected response:', data);
            secondAssistantToggle.checked = !enable;
        } else {
            console.log('Second assistant toggled:', data);
        }
    } catch (e) {
        console.error('Error toggling second assistant:', e);
        secondAssistantToggle.checked = !enable;
    }
}

// Event listeners
sendBtn.addEventListener('click', handleSend);
userInputEl.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        handleSend();
    }
});
refreshBtn.addEventListener('click', refreshSession);
secondAssistantToggle.addEventListener('change', (e) => {
    toggleSecondAssistant(e.target.checked);
});

// Start polling for critic scores every 5 seconds
setInterval(pollCriticScores, 5000);

document.addEventListener("DOMContentLoaded", startNewChat);
updateChatIdDisplay();
// Automatically start a new chat on DOM load



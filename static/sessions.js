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
 * Appends a message bubble to the messages container.
 * If the message is from the assistant and includes a critic score,
 * a small button with the score is added inside the bubble.
 *
 * @param {string} text         - The message content.
 * @param {string} role         - 'assistant' or 'user'.
 * @param {string} [criticScore]- (Optional) The critic score for assistant messages.
 */
function addMessageToChat(text, role, criticScore) {
    const messagesContainer = document.getElementById('messages');

    // Create the message bubble container.
    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'p-4 rounded-lg max-w-[75%] min-w-[25%] break-words flex flex-col';

    // Create an element for the message text.
    const textSpan = document.createElement('span');
    textSpan.textContent = text;
    bubbleDiv.appendChild(textSpan);

    // If this is an assistant message with a critic score, add a small button.
    if (role === 'assistant' && criticScore !== undefined) {
        const criticBtn = document.createElement('button');
        criticBtn.textContent = criticScore;
        criticBtn.className = 'mt-2 text-xs text-gray-500 rounded bg-gray-200 px-2 py-1';
        bubbleDiv.appendChild(criticBtn);
    }

    // Add a role-specific class for further styling.
    bubbleDiv.classList.add(role === 'assistant' ? 'assistant-message' : 'user-message');

    // Append to the container and scroll to the bottom
    messagesContainer.appendChild(bubbleDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

/**
 * Clears all messages from the messages container.
 */
function clearAllMessages() {
    const messagesContainer = document.getElementById('messages');
    messagesContainer.innerHTML = '';
}

/**
 * Fetches and loads chat history for a specific session.
 * @param {number} chatId - The ID of the chat session to load.
 */
async function loadChatHistory(chatId) {
    try {
        const response = await fetch(`/assistant/chat/${chatId}`);
        const data = await response.json();
        console.log(data);

        if (data.error) {
            console.error("Error fetching chat history:", data.error);
            return;
        }

        // Update the global currentChatId and display it
        currentChatId = data.id;
        updateChatIdDisplay();

        // Clear existing messages
        clearAllMessages();

        // Render chat history
        data.messages.forEach((msg) => {
            if (msg.role === 'assistant' && msg.assistant_message) {
                addMessageToChat(msg.assistant_message.content, 'assistant', null);
            } else if (msg.role === 'user' && msg.user_message) {
                addMessageToChat(msg.user_message.content, 'user');
            }
        });
    } catch (err) {
        console.error("Error loading chat history:", err);
    }
}

// Attach click event listeners to session buttons
document.addEventListener("DOMContentLoaded", () => {
    const sessionButtons = document.querySelectorAll(".top-right-pannel .button");
    sessionButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const chatId = button.textContent.match(/\d+/)[0]; // Extract chat ID from button text
            console.log("Loading chat history for session:", chatId);
            
            loadChatHistory(chatId);
        });
    });
});
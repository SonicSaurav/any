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
// Then update the pollCriticScores function to show critique and regeneration
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
                // Update existing messages with critic scores
                let existingMessage = document.querySelector(`[data-message-id='${scoreObj.id}']`);
                if (existingMessage) {
                    // Add critic score circle
                    let criticCircle = existingMessage.querySelector('.critic-score');
                    if (!criticCircle) {
                        criticCircle = document.createElement('div');
                        criticCircle.className = 'critic-score absolute top-0 right-0 mt-1 mr-1 text-xs text-white bg-red-500 rounded-full w-5 h-5 flex items-center justify-center';
                        existingMessage.appendChild(criticCircle);
                    }
                    
                    // Update critic score if changed
                    if (scoreObj.critic_score !== null && criticCircle.textContent !== scoreObj.critic_score.toString()) {
                        criticCircle.textContent = scoreObj.critic_score;

                        // Force a DOM update by toggling opacity
                        existingMessage.style.opacity = '0.99';
                        setTimeout(() => {
                            existingMessage.style.opacity = '1';
                        }, 10);
                        
                        // Check for critique and regeneration
                        let displayedCritique = existingMessage.getAttribute('data-critique-displayed');
                        if (!displayedCritique && scoreObj.id) {
                            // Fetch the message details to check for critique and regeneration
                            fetch(`/assistant/chat/message/${scoreObj.id}`)
                                .then(res => res.json())
                                .then(msgData => {
                                    if (msgData && msgData.search_output) {
                                        displayCritiqueAndRegeneration(msgData);
                                        existingMessage.setAttribute('data-critique-displayed', 'true');
                                    }
                                })
                                .catch(err => console.error('Error fetching message details:', err));
                        }
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

function displayCritiqueInSteps(searchData, stepsContainer, messageId) {
    let html = '';
    
    // Add critique section
    if (searchData.critique) {
        const critique = searchData.critique;
        const totalScore = critique.total_score || 0;
        
        html += `
        <div class="mb-3 border-t pt-3">
            <div class="flex items-center">
                <span class="inline-block w-6 h-6 bg-green-500 text-white rounded-full text-center mr-2">✓</span>
                <h4 class="font-bold">Response Evaluation</h4>
            </div>
            <div class="mt-2 ml-8">
                <div class="flex items-center mb-2">
                    <div class="rounded-full w-10 h-10 flex items-center justify-center mr-2 text-white font-bold ${getScoreColorClass(totalScore)}">
                        ${parseFloat(totalScore).toFixed(1)}
                    </div>
                    <span>Overall Score (out of 10)</span>
                </div>
                
                <div class="mt-2">`;
        
        // Add each critique section directly (no toggle)
        if (critique.adherence_to_search) {
            html += createCritiqueSection('Adherence to Search', critique.adherence_to_search);
        }
        
        // Add common sections
        const commonSections = [
            {key: 'question_format', title: 'Question Format & Pacing'},
            {key: 'conversational_quality', title: 'Conversational Quality'},
            {key: 'contextual_intelligence', title: 'Contextual Intelligence'},
            {key: 'overall_effectiveness', title: 'Overall Effectiveness'}
        ];
        
        commonSections.forEach(section => {
            if (critique[section.key]) {
                html += createCritiqueSection(section.title, critique[section.key]);
            }
        });
        
        // Add summary
        if (critique.summary) {
            html += `
                <div class="mb-2 p-2 bg-gray-100 rounded">
                    <div class="font-bold">Summary</div>
                    <p>${critique.summary}</p>
                </div>`;
        }
        
        html += `
                </div>
            </div>
        </div>`;
    }
    
    // Add regenerated content if available (directly visible)
    if (searchData.regenerated_content) {
        const regenScore = searchData.regenerated_critique?.total_score || 0;
        const originalScore = searchData.critique?.total_score || 0;
        
        html += `
        <div class="mb-3 border-t pt-3">
            <div class="flex items-center">
                <span class="inline-block w-6 h-6 bg-green-500 text-white rounded-full text-center mr-2">✓</span>
                <h4 class="font-bold">Improved Response Available</h4>
            </div>
            <div class="mt-2 ml-8">
                <div class="flex items-center justify-between p-2 bg-gray-100 rounded mb-2">
                    <div class="text-center">
                        <div class="text-sm text-gray-600">Original</div>
                        <div class="text-xl font-bold ${getScoreColorClass(originalScore)}">${parseFloat(originalScore).toFixed(1)}</div>
                    </div>
                    <div class="text-xl">→</div>
                    <div class="text-center">
                        <div class="text-sm text-gray-600">Improved</div>
                        <div class="text-xl font-bold ${getScoreColorClass(regenScore)}">${parseFloat(regenScore).toFixed(1)}</div>
                    </div>
                </div>
                
                <div class="mt-2 p-3 border border-green-300 bg-green-50 rounded">
                    ${searchData.regenerated_content}
                </div>
            </div>
        </div>`;
    }
    
    // Append the critique HTML to the steps container
    stepsContainer.innerHTML += html;
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

// Update sendToServer function to avoid duplicate user messages
async function sendToServer(userInput) {
    try {
        // Remove existing user input from the input field immediately to prevent double sends
        userInputEl.value = '';
        
        // Show temporary message
        const tempUserId = 'temp-user-' + Date.now();
        addMessageToChat(tempUserId, userInput, 'user', undefined, true);
        
        const tempAssistantId = 'temp-assistant-' + Date.now();
        addMessageToChat(tempAssistantId, "Assistant is thinking...", 'assistant', undefined, true);
        
        const payload = { user_input: userInput };
        if (currentChatId) {
            payload.chat_id = currentChatId;
        }
        
        const response = await fetch('/assistant/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await response.json();

        if (data.error) {
            removePlaceholders();
            addMessageToChat('error', data.error, 'assistant');
            return;
        }

        if (data.chat_id) {
            currentChatId = data.chat_id;
            updateChatIdDisplay();
        }
        
        // Remove temporary placeholders when we get a response
        removePlaceholders();
        
        // Show actual user message
        if (data.user_message) {
            addMessageToChat(
                data.user_message.id,
                data.user_message.content,
                'user'
            );
        }
        
        // Start polling for status
        if (data.message_id) {
            startStatusPolling(data.message_id);
        }

    } catch (err) {
        console.error('Error sending to server:', err);
        removePlaceholders();
        addMessageToChat('error', "Error: Failed to get response from server.", 'assistant');
    }
}

// Function to remove all placeholder messages
function removePlaceholders() {
    // Remove "Assistant is typing..." message
    const typingPlaceholders = document.querySelectorAll('.dummy-message');
    typingPlaceholders.forEach(placeholder => placeholder.remove());
    
    // Remove "Processing your request..." message if it exists
    const processingPlaceholders = document.querySelectorAll('.assistant-message:not([data-message-id])');
    processingPlaceholders.forEach(placeholder => placeholder.remove());
}
// Function to update the critic score badge
function updateCriticBadge(messageId, score) {
    const messageElement = document.querySelector(`[data-message-id='${messageId}']`);
    if (!messageElement) return;
    
    let criticCircle = messageElement.querySelector('.critic-score');
    if (!criticCircle) {
        criticCircle = document.createElement('div');
        criticCircle.className = 'critic-score absolute top-0 right-0 mt-1 mr-1 text-xs text-white rounded-full w-5 h-5 flex items-center justify-center';
        
        // Color based on score
        if (score >= 9.0) {
            criticCircle.classList.add('bg-green-500');
        } else if (score >= 8.0) {
            criticCircle.classList.add('bg-blue-500');
        } else if (score >= 7.0) {
            criticCircle.classList.add('bg-yellow-500');
        } else {
            criticCircle.classList.add('bg-red-500');
        }
        
        messageElement.appendChild(criticCircle);
    }
    
    criticCircle.textContent = parseFloat(score).toFixed(1);
}

// Function to poll for status updates - completely rewritten
async function startStatusPolling(messageId) {
    // Create a container for processing steps
    const stepsContainer = document.createElement('div');
    stepsContainer.id = 'processing-steps-' + messageId;
    stepsContainer.className = 'processing-steps p-4 rounded-lg max-w-[90%] min-w-[25%] break-words mt-2 mb-4';
    stepsContainer.innerHTML = '<h3 class="text-lg font-bold">Processing Your Request</h3><div class="mt-2 flex items-center"><div class="animate-spin mr-2 h-5 w-5 border-t-2 border-b-2 border-blue-500 rounded-full"></div>Initializing...</div>';
    
    // Add to messages container
    const messagesContainer = document.getElementById('messages');
    messagesContainer.appendChild(stepsContainer);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    
    let lastStatus = '';
    let finalResponseShown = false;
    
    // Set up polling interval - more frequent at first, then slower
    const pollInterval = setInterval(async () => {
        try {
            const response = await fetch(`/assistant/chat/status/${messageId}`);
            if (!response.ok) {
                clearInterval(pollInterval);
                return;
            }
            
            const statusData = await response.json();
            
            // Only update display if status changed or we have new data
            if (statusData.status !== lastStatus || !lastStatus) {
                console.log("Status update:", statusData);
                updateProcessingStepsDisplay(statusData, stepsContainer);
                lastStatus = statusData.status;
                
                // Scroll to show the updated steps
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
            
            // If response is generated, show it and stop polling for status
            // But continue polling for critic if needed
            if ((statusData.status === 'response_generated' || 
                statusData.status === 'completed' || 
                statusData.status === 'error') && 
                !finalResponseShown && statusData.content) {
                
                // Remove any remaining placeholders
                removePlaceholders();
                
                // Add the actual assistant message
                addMessageToChat(
                    statusData.message_id,
                    statusData.content,
                    'assistant',
                    statusData.critic_score
                );
                
                finalResponseShown = true;
                
                // Stop status polling
                clearInterval(pollInterval);
                
                // Start polling for critic updates
                startCriticPolling(messageId, stepsContainer);
            }
        } catch (err) {
            console.error('Error polling for status:', err);
        }
    }, 700); // Poll slightly faster for more responsive updates
    
    // After 3 minutes, stop polling regardless of status
    setTimeout(() => {
        clearInterval(pollInterval);
    }, 180000);
}
// Replace the function with this simpler version that always shows the content
function updateProcessingStepsDisplay(statusData, container) {
    if (!statusData.processing_data) {
        container.innerHTML = '<h3 class="text-lg font-bold">Processing Your Request</h3><div class="p-2 bg-blue-100 rounded">Status: ' + formatStatus(statusData.status) + '</div>';
        return;
    }
    
    const data = statusData.processing_data;
    
    // Build HTML for the processing steps display
    let html = '<h3 class="text-lg font-bold mb-2">Processing Steps</h3>';
    
    // Status indicator
    html += `<div class="mb-3 p-2 ${getStatusColorClass(statusData.status)} rounded">
        <span class="font-medium">Status:</span> ${formatStatus(statusData.status)}
    </div>`;
    
    // NER Results - Always show, not hidden
    if (data.ner_results) {
        html += `
        <div class="mb-3 border-b pb-2">
            <div class="flex items-center">
                <span class="inline-block w-6 h-6 bg-green-500 text-white rounded-full text-center mr-2">✓</span>
                <h4 class="font-bold">Named Entity Recognition</h4>
            </div>
            <div class="mt-1 ml-8">
                <div class="bg-gray-100 p-2 rounded text-xs overflow-auto">
                    <pre>${JSON.stringify(data.ner_results, null, 2)}</pre>
                </div>
            </div>
        </div>`;
    }
    
    // Search Call - Always show, not hidden
    if (data.search_call) {
        html += `
        <div class="mb-3 border-b pb-2">
            <div class="flex items-center">
                <span class="inline-block w-6 h-6 bg-green-500 text-white rounded-full text-center mr-2">✓</span>
                <h4 class="font-bold">Search Query</h4>
            </div>
            <div class="mt-1 ml-8">
                <div class="bg-gray-100 p-2 rounded text-xs overflow-auto">
                    <pre>${data.search_call}</pre>
                </div>
            </div>
        </div>`;
    }
    
    // Search Results - Always show, not hidden
    if (data.search_results) {
        const numMatches = data.search_results.num_matches || 'Unknown';
        const shownToAgent = data.search_results.show_results_to_actor ? 'Yes' : 'No';
        
        html += `
        <div class="mb-3 border-b pb-2">
            <div class="flex items-center">
                <span class="inline-block w-6 h-6 bg-green-500 text-white rounded-full text-center mr-2">✓</span>
                <h4 class="font-bold">Search Results</h4>
            </div>
            <div class="mt-1 ml-8">
                <p><span class="font-medium">Number of matches:</span> ${numMatches}</p>
                <p><span class="font-medium">Shown to assistant:</span> ${shownToAgent}</p>
                <div class="bg-gray-100 p-2 rounded text-xs overflow-auto">
                    <pre>${data.search_results.results || ''}</pre>
                </div>
            </div>
        </div>`;
    }
    
    // Thinking - Always show, not hidden
    if (data.thinking) {
        html += `
        <div class="mb-3 border-b pb-2">
            <div class="flex items-center">
                <span class="inline-block w-6 h-6 bg-green-500 text-white rounded-full text-center mr-2">✓</span>
                <h4 class="font-bold">Assistant Thinking</h4>
            </div>
            <div class="mt-1 ml-8">
                <div class="bg-gray-100 p-2 rounded text-xs overflow-auto">
                    <pre>${data.thinking}</pre>
                </div>
            </div>
        </div>`;
    }
    
    container.innerHTML = html;
}

// Helper function to format status
function formatStatus(status) {
    const statusMap = {
        'processing_started': 'Starting Processing...',
        'ner_started': 'Extracting Travel Preferences...',
        'ner_completed': 'Preferences Extracted',
        'ner_error': 'Error Extracting Preferences',
        'search_started': 'Generating Search Query...',
        'search_call_completed': 'Search Query Generated',
        'search_completed': 'Search Results Retrieved',
        'search_error': 'Error in Search Processing',
        'generating_response': 'Generating Assistant Response...',
        'response_generated': 'Response Generated',
        'response_error': 'Error Generating Response',
        'completed': 'Processing Complete',
        'error': 'Error Occurred'
    };
    
    return statusMap[status] || status;
}

// Helper function to toggle sections
function toggleSection(id) {
    const element = document.getElementById(id);
    if (element) {
        element.classList.toggle('hidden');
    }
}

// Function to poll for critic updates
function startCriticPolling(messageId, stepsContainer) {
    let criticShown = false;
    
    const criticInterval = setInterval(async () => {
        try {
            // Get the message details including critic score and regeneration
            const response = await fetch(`/assistant/chat/message/${messageId}`);
            if (!response.ok) {
                clearInterval(criticInterval);
                return;
            }
            
            const msgData = await response.json();
            if (!msgData.search_output) {
                return;
            }
            
            // Try to parse the search_output to get critique
            try {
                const searchData = JSON.parse(msgData.search_output);
                
                // If we have critique data and haven't shown it yet
                if ((searchData.critique || searchData.regenerated_content) && !criticShown) {
                    console.log("Critic data found:", searchData);
                    
                    // Display the critique in the steps container
                    displayCritiqueInSteps(searchData, stepsContainer, messageId);
                    
                    // Mark as shown so we don't do it again
                    criticShown = true;
                    clearInterval(criticInterval);
                }
                
                // Update the badge regardless
                if (msgData.critic_score) {
                    updateCriticBadge(msgData.id, msgData.critic_score);
                }
            } catch (e) {
                console.error('Error parsing search output:', e);
            }
        } catch (err) {
            console.error('Error polling for critic updates:', err);
        }
    }, 2000); // Check every 2 seconds
    
    // Stop after 2 minutes
    setTimeout(() => {
        clearInterval(criticInterval);
    }, 120000);
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


// Add this function to display the processing steps
function displayProcessingSteps(steps) {
    const messagesContainer = document.getElementById('messages');
    
    // Create a container for the processing steps
    const stepsContainer = document.createElement('div');
    stepsContainer.className = 'processing-steps p-4 rounded-lg max-w-[75%] min-w-[25%] break-words';
    
    // Add a header
    const header = document.createElement('h3');
    header.textContent = 'Assistant Processing Steps';
    header.className = 'text-lg font-bold mb-2';
    stepsContainer.appendChild(header);
    
    // Display NER results if available
    if (steps.NER) {
        const nerSection = document.createElement('div');
        nerSection.className = 'mb-3';
        
        const nerTitle = document.createElement('h4');
        nerTitle.textContent = 'Named Entity Recognition (Extracted Preferences)';
        nerTitle.className = 'font-bold mb-1';
        nerSection.appendChild(nerTitle);
        
        const nerContent = document.createElement('pre');
        nerContent.className = 'bg-gray-100 p-2 rounded text-xs overflow-auto';
        nerContent.textContent = JSON.stringify(steps.NER, null, 2);
        nerSection.appendChild(nerContent);
        
        stepsContainer.appendChild(nerSection);
    }
    
    // Display search call if available
    if (steps.search_call) {
        const searchCallSection = document.createElement('div');
        searchCallSection.className = 'mb-3';
        
        const searchCallTitle = document.createElement('h4');
        searchCallTitle.textContent = 'Search Query Generation';
        searchCallTitle.className = 'font-bold mb-1';
        searchCallSection.appendChild(searchCallTitle);
        
        const searchCallContent = document.createElement('pre');
        searchCallContent.className = 'bg-gray-100 p-2 rounded text-xs overflow-auto';
        searchCallContent.textContent = steps.search_call;
        searchCallSection.appendChild(searchCallContent);
        
        stepsContainer.appendChild(searchCallSection);
    }
    
    // Display search results if available
    if (steps.search_results) {
        const searchResultsSection = document.createElement('div');
        searchResultsSection.className = 'mb-3';
        
        const searchResultsTitle = document.createElement('h4');
        searchResultsTitle.textContent = 'Search Results';
        searchResultsTitle.className = 'font-bold mb-1';
        searchResultsSection.appendChild(searchResultsTitle);
        
        // Number of matches
        const numMatches = document.createElement('p');
        numMatches.textContent = `Number of matches: ${steps.search_results.num_matches || 'Unknown'}`;
        numMatches.className = 'mb-1';
        searchResultsSection.appendChild(numMatches);
        
        // Shown to agent?
        const shownToAgent = document.createElement('p');
        shownToAgent.textContent = `Shown to agent: ${steps.search_results.show_results_to_actor ? 'Yes' : 'No'}`;
        shownToAgent.className = 'mb-1';
        searchResultsSection.appendChild(shownToAgent);
        
        // Results (collapsible)
        const resultsToggle = document.createElement('button');
        resultsToggle.textContent = 'Show/Hide Results';
        resultsToggle.className = 'bg-blue-500 text-white px-2 py-1 rounded text-xs mb-1';
        searchResultsSection.appendChild(resultsToggle);
        
        const resultsContent = document.createElement('pre');
        resultsContent.className = 'bg-gray-100 p-2 rounded text-xs overflow-auto hidden';
        resultsContent.textContent = steps.search_results.results || '';
        searchResultsSection.appendChild(resultsContent);
        
        resultsToggle.addEventListener('click', () => {
            resultsContent.classList.toggle('hidden');
        });
        
        stepsContainer.appendChild(searchResultsSection);
    }
    
    // Display thinking if available
    if (steps.thinking) {
        const thinkingSection = document.createElement('div');
        thinkingSection.className = 'mb-3';
        
        const thinkingTitle = document.createElement('h4');
        thinkingTitle.textContent = 'Assistant Thinking Process';
        thinkingTitle.className = 'font-bold mb-1';
        thinkingSection.appendChild(thinkingTitle);
        
        const thinkingToggle = document.createElement('button');
        thinkingToggle.textContent = 'Show/Hide Thinking';
        thinkingToggle.className = 'bg-blue-500 text-white px-2 py-1 rounded text-xs mb-1';
        thinkingSection.appendChild(thinkingToggle);
        
        const thinkingContent = document.createElement('pre');
        thinkingContent.className = 'bg-gray-100 p-2 rounded text-xs overflow-auto hidden';
        thinkingContent.textContent = steps.thinking;
        thinkingSection.appendChild(thinkingContent);
        
        thinkingToggle.addEventListener('click', () => {
            thinkingContent.classList.toggle('hidden');
        });
        
        stepsContainer.appendChild(thinkingSection);
    }
    
    messagesContainer.appendChild(stepsContainer);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Function to display critique and regeneration
function displayCritiqueAndRegeneration(message) {
    if (!message || !message.search_output) return;
    
    try {
        // Try to parse the search_output as JSON
        const searchData = JSON.parse(message.search_output);
        
        // Check if we have critique or regenerated content
        if (!searchData.critique && !searchData.regenerated_content) return;
        
        const messagesContainer = document.getElementById('messages');
        
        // Create the critique container
        const critiqueContainer = document.createElement('div');
        critiqueContainer.className = 'critique-container p-4 rounded-lg max-w-[90%] min-w-[25%] break-words';
        
        // Add critique section if available
        if (searchData.critique) {
            const critiqueSection = document.createElement('div');
            critiqueSection.className = 'mb-3';
            
            const critiqueTitle = document.createElement('h3');
            critiqueTitle.textContent = 'Response Evaluation';
            critiqueTitle.className = 'text-lg font-bold mb-2';
            critiqueSection.appendChild(critiqueTitle);
            
            // Total Score
            if (searchData.critique.total_score !== undefined) {
                const scoreDiv = document.createElement('div');
                scoreDiv.className = 'flex items-center mb-2';
                
                const scoreBadge = document.createElement('div');
                scoreBadge.className = 'rounded-full w-10 h-10 flex items-center justify-center mr-2 text-white font-bold';
                
                // Color based on score
                const score = searchData.critique.total_score;
                if (score >= 9.0) {
                    scoreBadge.classList.add('bg-green-500');
                } else if (score >= 8.0) {
                    scoreBadge.classList.add('bg-blue-500');
                } else if (score >= 7.0) {
                    scoreBadge.classList.add('bg-yellow-500');
                } else {
                    scoreBadge.classList.add('bg-red-500');
                }
                
                scoreBadge.textContent = score.toFixed(1);
                scoreDiv.appendChild(scoreBadge);
                
                const scoreLabel = document.createElement('span');
                scoreLabel.textContent = 'Overall Score (out of 10)';
                scoreLabel.className = 'text-sm';
                scoreDiv.appendChild(scoreLabel);
                
                critiqueSection.appendChild(scoreDiv);
            }
            
            // Toggle for detailed critique
            const detailsToggle = document.createElement('button');
            detailsToggle.textContent = 'Show Detailed Critique';
            detailsToggle.className = 'bg-blue-500 text-white px-2 py-1 rounded text-xs mb-2';
            critiqueSection.appendChild(detailsToggle);
            
            // Detailed critique (collapsible)
            const detailsContent = document.createElement('div');
            detailsContent.className = 'bg-gray-100 p-3 rounded text-sm overflow-auto hidden';
            
            // Format the critique content based on the actual structure
            let critiqueSections = '';
            const critique = searchData.critique;
            
            // Handle search results present case
            if (critique.adherence_to_search) {
                critiqueSections += createCritiqueSection('Adherence to Search Result Handling', 
                                                         critique.adherence_to_search.score,
                                                         critique.adherence_to_search.reason);
            }
            
            // Process common sections that exist in both formats
            const commonSections = [
                {key: 'question_format', title: 'Question Format & Pacing'},
                {key: 'conversational_quality', title: 'Conversational Quality'},
                {key: 'contextual_intelligence', title: 'Contextual Intelligence'},
                {key: 'overall_effectiveness', title: 'Overall Effectiveness'}
            ];
            
            commonSections.forEach(section => {
                if (critique[section.key]) {
                    critiqueSections += createCritiqueSection(section.title, 
                                                             critique[section.key].score,
                                                             critique[section.key].reason);
                }
            });
            
            // Add summary section
            if (critique.summary) {
                critiqueSections += `
                <div class="mb-3 border-t pt-2">
                    <h4 class="font-bold text-lg">Summary</h4>
                    <p>${critique.summary}</p>
                </div>`;
            }
            
            detailsContent.innerHTML = critiqueSections;
            critiqueSection.appendChild(detailsContent);
            
            detailsToggle.addEventListener('click', () => {
                detailsContent.classList.toggle('hidden');
                detailsToggle.textContent = detailsContent.classList.contains('hidden') ? 
                    'Show Detailed Critique' : 'Hide Detailed Critique';
            });
            
            critiqueContainer.appendChild(critiqueSection);
        }
        
        // Add regenerated content if available
        if (searchData.regenerated_content) {
            const regenSection = document.createElement('div');
            regenSection.className = 'mb-3 mt-4 border-t pt-3';
            
            const regenTitle = document.createElement('h3');
            regenTitle.textContent = 'Improved Response Available';
            regenTitle.className = 'text-lg font-bold mb-2';
            regenSection.appendChild(regenTitle);
            
            // Score comparison if available
            if (searchData.regenerated_critique && searchData.regenerated_critique.total_score !== undefined && 
                searchData.critique && searchData.critique.total_score !== undefined) {
                const oldScore = parseFloat(searchData.critique.total_score).toFixed(1);
                const newScore = parseFloat(searchData.regenerated_critique.total_score).toFixed(1);
                
                const scoreComp = document.createElement('div');
                scoreComp.className = 'flex items-center justify-between mb-3 p-3 bg-gray-100 rounded';
                
                const oldScoreDiv = document.createElement('div');
                oldScoreDiv.className = 'text-center';
                oldScoreDiv.innerHTML = `
                    <div class="text-sm text-gray-600">Original Score</div>
                    <div class="text-xl font-bold ${getScoreColorClass(oldScore)}">${oldScore}</div>`;
                
                const arrow = document.createElement('div');
                arrow.innerHTML = '→';
                arrow.className = 'text-xl text-gray-500 mx-4';
                
                const newScoreDiv = document.createElement('div');
                newScoreDiv.className = 'text-center';
                newScoreDiv.innerHTML = `
                    <div class="text-sm text-gray-600">Improved Score</div>
                    <div class="text-xl font-bold ${getScoreColorClass(newScore)}">${newScore}</div>`;
                
                scoreComp.appendChild(oldScoreDiv);
                scoreComp.appendChild(arrow);
                scoreComp.appendChild(newScoreDiv);
                
                regenSection.appendChild(scoreComp);
            }
            
            // Toggle button for regenerated content
            const regenToggle = document.createElement('button');
            regenToggle.textContent = 'Show Improved Response';
            regenToggle.className = 'bg-green-500 text-white px-3 py-2 rounded text-sm font-medium';
            regenSection.appendChild(regenToggle);
            
            // Regenerated content (collapsible)
            const regenContent = document.createElement('div');
            regenContent.className = 'hidden p-4 border border-green-300 bg-green-50 rounded-lg my-3';
            regenContent.textContent = searchData.regenerated_content;
            regenSection.appendChild(regenContent);
            
            regenToggle.addEventListener('click', () => {
                regenContent.classList.toggle('hidden');
                regenToggle.textContent = regenContent.classList.contains('hidden') ? 
                    'Show Improved Response' : 'Hide Improved Response';
            });
            
            critiqueContainer.appendChild(regenSection);
        }
        
        messagesContainer.appendChild(critiqueContainer);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
    } catch (err) {
        console.error('Error displaying critique and regeneration:', err);
    }
}

// Helper function to create a critique section
function createCritiqueSection(title, data) {
    return `
    <div class="mb-2 p-2 bg-gray-100 rounded">
        <div class="flex justify-between">
            <div class="font-bold">${title}</div>
            <div class="${getScoreColorClass(data.score)}">${parseFloat(data.score).toFixed(1)}/10</div>
        </div>
        <p>${data.reason}</p>
    </div>`;
}

// Helper function to get score color class
function getScoreColorClass(score) {
    score = parseFloat(score);
    if (score >= 9.0) return 'text-green-600';
    if (score >= 8.0) return 'text-blue-600';
    if (score >= 7.0) return 'text-yellow-600';
    return 'text-red-600';
}


// Helper function to get status color class
function getStatusColorClass(status) {
    if (status === 'error' || status.includes('error')) {
        return 'bg-red-100';
    } else if (status === 'completed' || status === 'response_generated') {
        return 'bg-green-100';
    } else {
        return 'bg-blue-100';
    }
}

// Helper function to create a loading section
function createLoadingSection(message) {
    return `
    <div class="mb-3">
        <div class="flex items-center">
            <span class="inline-block w-6 h-6 bg-blue-500 text-white rounded-full text-center mr-2 animate-pulse">⧗</span>
            <h4 class="font-bold">${message}</h4>
        </div>
    </div>`;
}

// Helper function to create a processing section
function createProcessingSection(title, isComplete, toggleId, content) {
    return `
    <div class="mb-3">
        <div class="flex items-center">
            <span class="inline-block w-6 h-6 ${isComplete ? 'bg-green-500' : 'bg-yellow-500'} text-white rounded-full text-center mr-2">${isComplete ? '✓' : '⌛'}</span>
            <h4 class="font-bold">${title}</h4>
        </div>
        <div class="mt-1 ml-8">
            <button class="bg-blue-500 text-white px-2 py-1 rounded text-xs mb-1" 
                onclick="toggleSection('${toggleId}')">
                Show Details
            </button>
            <pre id="${toggleId}" class="bg-gray-100 p-2 rounded text-xs overflow-auto hidden">
${content}
            </pre>
        </div>
    </div>`;
}

// Make toggleSection available globally
window.toggleSection = function(id) {
    const element = document.getElementById(id);
    if (element) {
        element.classList.toggle('hidden');
    }
};
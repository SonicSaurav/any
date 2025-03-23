
// ==================================================
// Utility to add user/assistant messages to the chat
// ==================================================
function addMessageToChat(text, role) {
  const messagesContainer = document.getElementById('messages');
  const bubbleDiv = document.createElement('div');
  bubbleDiv.className = 'p-4 rounded-lg max-w-[75%] min-w-[25%] break-words text-bubble';

  if (role === 'assistant') {
    // Regex to find all <search_output>...</search_output> occurrences
    const regex = /<search_output>([\s\S]*?)<\/search_output>/g;
    let matches = [...text.matchAll(regex)]; // Extract all matches

    let searchOutputContents = matches.map(match => match[1].trim()); // Extract text inside tags
    let cleanedText = text.replace(regex, '').trim(); // Remove all <search_output> tags from the main text

    // Append the cleaned text to the message bubble.
    bubbleDiv.appendChild(document.createTextNode(cleanedText));

    // If there are extracted search results, add toggle buttons for each
    if (searchOutputContents.length > 0) {
      searchOutputContents.forEach((content, index) => {
        // Create a button to toggle the visibility of search output
        const toggleButton = document.createElement('button');
        toggleButton.textContent = `Show Search Output ${index + 1}`;
        toggleButton.style.marginTop = '10px';
        toggleButton.className = 'toggle-search-output';

        // Create a container for the search output content and hide it initially
        const searchOutputContainer = document.createElement('div');
        searchOutputContainer.style.display = 'none';
        searchOutputContainer.textContent = content;
        searchOutputContainer.className = 'search-output-content';

        // Append a line break, the button, and the hidden content to the message bubble
        bubbleDiv.appendChild(document.createElement('br'));
        bubbleDiv.appendChild(toggleButton);
        bubbleDiv.appendChild(searchOutputContainer);

        // Add an event listener to toggle visibility
        toggleButton.addEventListener('click', function () {
          if (searchOutputContainer.style.display === 'none') {
            searchOutputContainer.style.display = 'block';
            toggleButton.textContent = `Hide Search Output ${index + 1}`;
          } else {
            searchOutputContainer.style.display = 'none';
            toggleButton.textContent = `Show Search Output ${index + 1}`;
          }
        });
      });
    }

    bubbleDiv.classList.add('assistant-message');
  } else if (role === 'user') {
    // For user messages, simply add the text.
    bubbleDiv.appendChild(document.createTextNode(text));
    bubbleDiv.classList.add('user-message');
  }

  messagesContainer.appendChild(bubbleDiv);
  // Uncomment the next line to automatically scroll to the bottom of the messages container.
  // messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
// =========================================
// Critic Score
// =========================================
async function fetchCriticScore() {
  try {
    const response = await fetch('/critic');
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
    const data = await response.json();
    document.getElementById('critic-score').textContent = `${data.score}`;
  } catch (error) {
    console.error('Error fetching critic score:', error);
  }
}

// ==========================================================
// Polling intervals and global variables
// ==========================================================
let lastMessageCount = 0;
let simulationInterval = null;
const POLL_INTERVAL = 1000; // 1 second
let currentStatus = "stopped"; // Track current status to optimize polling


// ==========================================================
// Separate endpoints for status & typing
// ==========================================================
async function fetchSimulationStatus() {
  await fetchRunningStatus();
  
  if (currentStatus === "running") {
    await fetchSimulationMessages();
    await fetchTypingStatus();
  }
}
// ---------------------------------------
// 1) Running status: /simulation/status/running
// ---------------------------------------
async function fetchRunningStatus() {
  try {
    const response = await fetch('/simulation/status/running');
    if (!response.ok) throw new Error('Network response was not ok');

    const result = await response.json();
    console.log('Running status:', result);

    const status = result.status || 'unknown';
    
    // If status has changed, log the transition
    if (status !== currentStatus) {
      console.log(`Simulation status changed: ${currentStatus} → ${status}`);
    }

    currentStatus = status; // Update the tracked status

    if (status === "stopped") {
      clearInterval(simulationInterval);
      simulationInterval = null;
      resetStartButton();
    } else if (status === "killed") {
      clearInterval(simulationInterval);
      simulationInterval = null;
      resetStartButton();
      showFlashMessage('error', 'Simulation was killed after waiting too long');
      stopSimulation();
    }

    // Update the UI based on the new status
    updateUIBasedOnStatus(status);
  } catch (error) {
    console.error('Error fetching running status:', error);
  }
}
// -----------------------------------------
// 2) Typing status: /simulation/status/typing
// -----------------------------------------
async function fetchTypingStatus() {
  try {
    if (currentStatus !== "running") return; // Skip if not running

    const response = await fetch('/simulation/status/typing');
    if (!response.ok) throw new Error('Network response was not ok');

    const typingResult = await response.json();
    console.log('Typing status:', typingResult);

    updateUIWithTyping(typingResult);
  } catch (error) {
    console.error('Error fetching typing status:', error);
  }
}
// ------------------------------------------------------------
// function for updating UI for paused/running/stopped/killed
// ------------------------------------------------------------
function updateUIBasedOnStatus(status) {
  const startButton = document.getElementById('start-simulation');
  const stopButton = document.getElementById('end-simulation');
  const continueButton = document.getElementById('continue-simulation');

  if (status === 'running') {
    startButton.style.display = 'none';
    stopButton.style.display = 'block';
    continueButton.style.display = 'none';
  } else if (status === 'paused') {
    startButton.style.display = 'none';
    stopButton.style.display = 'block';
    continueButton.style.display = 'block';
  } else {
    startButton.style.display = 'block';
    stopButton.style.display = 'none';
    continueButton.style.display = 'none';
    resetStartButton();
  }
}

// ------------------------------------------------------------
// function for updating UI regarding typing states
// ------------------------------------------------------------
function updateUIWithTyping(typingResult) {
  // typingResult has user_typing, assistant_typing, creating_persona
  const { user_typing, assistant_typing, creating_persona } = typingResult;

  if (creating_persona) {
    showSystemMessage('A persona is being generated, please wait...', 'loading');
  } else {
    removeSystemMessage('loading');
  }

  if (user_typing) {
    showSystemMessage('User is typing...', 'user_typing');
  } else {
    removeSystemMessage('user_typing');
  }

  if (assistant_typing) {
    showSystemMessage('Assistant is typing...', 'assistant_typing');
  } else {
    removeSystemMessage('assistant_typing');
  }
}

// ------------------------------------------------------------
// Function that fetches latest messages from the conversation
// ------------------------------------------------------------
async function fetchSimulationMessages() {
  try {
    if (currentStatus !== "running") return; // Skip if not running

    const response = await fetch('/simulation/messages');
    if (!response.ok) throw new Error('Network response was not ok');

    const result = await response.json();
    console.log('Fetched messages:', result);

    let messages = Array.isArray(result) ? result : (result.messages || []);

    if (messages.length > lastMessageCount) {
      const newMessages = messages.slice(lastMessageCount);
      newMessages.forEach(msg => addMessageToChat(msg.content, msg.role));

      if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
        fetchCriticScore();
      }
      lastMessageCount = messages.length;
    }
  } catch (error) {
    console.error('Error fetching simulation messages:', error);
  }
}

// ==================================================================
// Optimized Polling Logic
// ==================================================================
function startPolling() {
  if (!simulationInterval) {
    simulationInterval = setInterval(() => {
      fetchSimulationStatus();
    }, POLL_INTERVAL);
  }
}

// ==================================================================
// System messages for events like 'persona creation' or 'typing'
// ==================================================================
function showSystemMessage(message, id) {
  let existingMessage = document.getElementById(id);
  if (!existingMessage) {
    const messagesContainer = document.getElementById('messages');
    const messageDiv = document.createElement('div');
    messageDiv.id = id;
    messageDiv.className = 'p-4 rounded-lg max-w-[75%] min-w-[25%] break-words text-bubble system-message';
    messageDiv.textContent = message;
    messagesContainer.appendChild(messageDiv);
  }
}

function removeSystemMessage(id) {
  let existingMessage = document.getElementById(id);
  if (existingMessage) {
    existingMessage.remove();
  }
}

// Reset start button UI
function resetStartButton() {
  const startButton = document.getElementById('start-simulation');
  startButton.innerHTML = 'Start Simulation';
  startButton.classList.remove('cursor-wait');
}

// Clear messages container
function clearMessages() {
  const messagesContainer = document.getElementById('messages');
  while (messagesContainer.firstChild) {
    messagesContainer.removeChild(messagesContainer.firstChild);
  }
  lastMessageCount = 0;
  document.getElementById('critic-score').textContent = '';
}

// ==================================================================
// Start, Continue, Stop Simulation
// ==================================================================
async function startSimulation() {
  try {
    clearMessages();

    const response = await fetch('/start');
    if (!response.ok) throw new Error('Network response was not ok');

    const data = await response.json();
    console.log('Simulation started:', data);
    showFlashMessage('success', data.message || 'Simulation started successfully!');

    startPolling();
    return true;
  } catch (error) {
    console.error('Error starting simulation:', error);
    showFlashMessage('error', error.message);
    return false;
  }
}

async function continueSimulation() {
  try {
    const response = await fetch('/continue');
    if (!response.ok) throw new Error('Network response was not ok');

    const data = await response.json();
    console.log('Simulation resumed:', data);
    showFlashMessage('success', data.message || 'Simulation resumed successfully!');

    startPolling();
  } catch (error) {
    console.error('Error continuing simulation:', error);
    showFlashMessage('error', error.message);
  }
}

async function stopSimulation() {
  try {
    const response = await fetch('/stop');
    if (response.ok) {
      const data = await response.json();
      console.log('Simulation stopped:', data);
      showFlashMessage('success', data.message || 'Simulation stopped successfully!');

      clearInterval(simulationInterval);
      simulationInterval = null;
      updateUIBasedOnStatus('stopped');
    } else {
      const errorData = await response.json();
      showFlashMessage('error', errorData.message || 'Failed to stop simulation');
    }
  } catch (error) {
    console.error('Error stopping simulation:', error);
    showFlashMessage('error', error.message);
  } finally {
    resetStartButton();
  }
}
// ==================================================================
// Flash Message
// ==================================================================
function showFlashMessage(type, message) {
  let flashContainer = document.getElementById('flash-container');
  if (!flashContainer) {
    flashContainer = document.createElement('div');
    flashContainer.id = 'flash-container';
    flashContainer.style.position = 'fixed';
    flashContainer.style.top = '20px';
    flashContainer.style.right = '20px';
    flashContainer.style.zIndex = '9999';
    document.body.appendChild(flashContainer);
  }

  const flashMessage = document.createElement('div');
  flashMessage.className = `flash-message ${type}`;
  flashMessage.textContent = message;
  flashMessage.style.backgroundColor = type === 'success' 
    ? 'green' 
    : (type === 'info' 
       ? 'blue' 
       : 'red');
  flashMessage.style.color = 'white';
  flashMessage.style.padding = '10px';
  flashMessage.style.marginBottom = '10px';
  flashMessage.style.borderRadius = '5px';

  flashContainer.appendChild(flashMessage);

  setTimeout(() => {
    flashMessage.remove();
  }, 3000);
}

// ==================================================================
// Page load: attach event listeners & start polling
// ==================================================================
document.addEventListener('DOMContentLoaded', () => {
  const startButton = document.getElementById('start-simulation');
  const stopButton = document.getElementById('end-simulation');
  const continueButton = document.getElementById('continue-simulation');

  startButton.addEventListener('click', async () => {
    if (simulationInterval !== null) {
      showFlashMessage('info', 'Simulation already running.');
      return;
    }
    startButton.innerHTML = 'Simulation Running...';
    startButton.classList.add('cursor-wait');

    const started = await startSimulation();
    if (!started) {
      startButton.innerHTML = 'Start Simulation';
      startButton.classList.remove('cursor-wait');
    }
  });

  stopButton.addEventListener('click', async () => {
    await stopSimulation();
  });

  continueButton.addEventListener('click', async () => {
    await continueSimulation();
  });

  // Start polling when page loads
  startPolling();
});

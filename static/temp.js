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
// 2) Typing status: /simulation/status/typing (only when running)
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
// Function to update UI for running/paused/stopped/killed
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
// Function to update UI regarding typing states
// ------------------------------------------------------------
function updateUIWithTyping(typingResult) {
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
// Flash Message & UI Event Listeners
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

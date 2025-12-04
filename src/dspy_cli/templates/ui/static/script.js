// DSPy UI JavaScript

// ===== Authentication Functions =====

/**
 * Save API key to localStorage
 */
function saveApiKey() {
    const input = document.getElementById('apiKey');
    const key = input.value.trim();

    if (!key) {
        alert('Please enter an API key');
        return;
    }

    // Store in localStorage
    localStorage.setItem('dspy_api_key', key);

    // Clear input for security
    input.value = '';

    // Update status
    updateAuthStatus(true);

    // Show success message
    showMessage('API key saved successfully', 'success');
}

/**
 * Clear API key from localStorage
 */
function clearApiKey() {
    localStorage.removeItem('dspy_api_key');
    updateAuthStatus(false);
    showMessage('API key cleared', 'info');
}

/**
 * Update authentication status indicator
 */
function updateAuthStatus(authenticated) {
    const status = document.getElementById('authStatus');
    if (!status) return;

    if (authenticated) {
        status.textContent = '✓ Authenticated';
        status.className = 'auth-status authenticated';
    } else {
        status.textContent = '✗ Not authenticated';
        status.className = 'auth-status not-authenticated';
    }
}

/**
 * Show a temporary message to the user
 */
function showMessage(message, type = 'info') {
    // Create message element
    const messageEl = document.createElement('div');
    messageEl.className = `message message-${type}`;
    messageEl.textContent = message;
    messageEl.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 24px;
        background: ${type === 'success' ? '#27ae60' : type === 'error' ? '#e74c3c' : '#3498db'};
        color: white;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;

    document.body.appendChild(messageEl);

    // Remove after 3 seconds
    setTimeout(() => {
        messageEl.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => messageEl.remove(), 300);
    }, 3000);
}

// ===== Theme Functions =====

/**
 * Initialize theme on page load
 * Reads theme preference from localStorage or falls back to system preference
 */
function initTheme() {
    // Check localStorage for saved preference
    const savedTheme = localStorage.getItem('theme');

    if (savedTheme) {
        // Use saved preference
        document.documentElement.setAttribute('data-theme', savedTheme);
    } else {
        // Use system preference if no saved preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const theme = prefersDark ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', theme);
    }

    // Update toggle button icon if it exists
    updateThemeIcon();
}

/**
 * Toggle between light and dark themes
 */
function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    // Update theme
    document.documentElement.setAttribute('data-theme', newTheme);

    // Save preference
    localStorage.setItem('theme', newTheme);

    // Update icon
    updateThemeIcon();
}

/**
 * Update theme toggle button icon
 */
function updateThemeIcon() {
    const themeIcon = document.getElementById('themeIcon');
    if (!themeIcon) return;

    const currentTheme = document.documentElement.getAttribute('data-theme');
    // Show moon for light mode (click to go dark), sun for dark mode (click to go light)
    themeIcon.textContent = currentTheme === 'dark' ? '☀️' : '🌙';
}

/**
 * Initialize the program page with event handlers and log loading
 */
function initProgramPage(programName, moduleType = 'Predict') {
    // Load logs on page load
    loadLogs(programName);

    // Auto-enable streaming based on module type
    // Complex modules: ChainOfThought, ReAct, ProgramOfThought, Refine, MultiChainComparison
    const complexModules = ['ChainOfThought', 'ReAct', 'ProgramOfThought', 'Refine', 'MultiChainComparison'];
    const autoEnableStreaming = complexModules.includes(moduleType);

    // Check localStorage override or use auto-detection
    const streamingEnabled = localStorage.getItem('streamingEnabled') !== null
        ? localStorage.getItem('streamingEnabled') === 'true'
        : autoEnableStreaming;

    // Set toggle state
    const streamingToggle = document.getElementById('streamingToggle');
    if (streamingToggle) {
        streamingToggle.checked = streamingEnabled;

        // Listen for toggle changes
        streamingToggle.addEventListener('change', (e) => {
            localStorage.setItem('streamingEnabled', e.target.checked);
        });
    }

    // Set up form submission
    const form = document.getElementById('programForm');
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();

            // Check if streaming is enabled
            const currentStreamingSetting = streamingToggle ? streamingToggle.checked : false;

            if (currentStreamingSetting) {
                submitProgramStreaming(programName);
            } else {
                submitProgram(programName);
            }
        });

        // Add keyboard shortcut: Cmd+Enter (Mac) or Ctrl+Enter (Windows/Linux)
        form.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();

                // Check if streaming is enabled
                const currentStreamingSetting = streamingToggle ? streamingToggle.checked : false;

                if (currentStreamingSetting) {
                    submitProgramStreaming(programName);
                } else {
                    submitProgram(programName);
                }
            }
        });
    }

    // Set up refresh button
    const refreshBtn = document.getElementById('refreshLogs');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadLogs(programName);
        });
    }

    // Initialize image input handlers
    initImageInputs();

    // Initialize checkbox handlers
    initCheckboxes();

    // Set up copy API call button
    const copyBtn = document.getElementById('copyApiBtn');
    if (copyBtn) {
        copyBtn.addEventListener('click', () => {
            copyApiCall(programName);
        });
    }
}

/**
 * Submit the program form
 */
async function submitProgram(programName) {
    const form = document.getElementById('programForm');
    const submitBtn = form.querySelector('button[type="submit"]');
    const resultBox = document.getElementById('result');
    const errorBox = document.getElementById('error');

    // Hide previous results
    resultBox.style.display = 'none';
    errorBox.style.display = 'none';

    // Disable submit button
    submitBtn.disabled = true;
    submitBtn.textContent = 'Running...';

    // Collect form data
    const formData = new FormData(form);
    const data = {};
    const missingFields = [];

    // Get all form inputs to check for required fields
    const formInputs = form.querySelectorAll('input, textarea, select');

    // Handle checkboxes explicitly (they don't appear in FormData when unchecked)
    const checkboxes = form.querySelectorAll('input[type="checkbox"]');
    const checkboxNames = new Set();
    checkboxes.forEach(checkbox => {
        checkboxNames.add(checkbox.name);
        data[checkbox.name] = checkbox.checked;
    });

    for (const [key, value] of formData.entries()) {
        // Skip checkboxes (already handled above)
        if (checkboxNames.has(key)) {
            continue;
        }

        // Check if value is empty (but allow false for booleans)
        const trimmedValue = typeof value === 'string' ? value.trim() : value;

        // Check if field is optional
        const inputElement = form.querySelector(`[name="${key}"]`);
        const isOptional = inputElement && inputElement.hasAttribute('data-optional');

        if (!trimmedValue && trimmedValue !== false) {
            // Only flag as missing if not optional
            if (!isOptional) {
                missingFields.push(key);
            }
            // Skip adding to data if empty (don't send empty optional fields)
            continue;
        }

        // Try to parse as JSON for arrays/objects
        if (typeof value === 'string' && (value.trim().startsWith('[') || value.trim().startsWith('{'))) {
            try {
                data[key] = JSON.parse(value);
            } catch (e) {
                data[key] = value;
            }
        } else if (value === 'true') {
            data[key] = true;
        } else if (value === 'false') {
            data[key] = false;
        } else {
            data[key] = value;
        }
    }

    // Check for missing required fields
    if (missingFields.length > 0) {
        const fieldList = missingFields.join(', ');
        document.getElementById('errorContent').textContent =
            `Missing required input${missingFields.length > 1 ? 's' : ''}: ${fieldList}\n\nPlease provide a value for ${missingFields.length > 1 ? 'these fields' : 'this field'} before running the program.`;
        errorBox.style.display = 'block';
        errorBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        // Re-enable submit button
        submitBtn.disabled = false;
        submitBtn.textContent = 'Run Program';
        return;
    }

    try {
        // Get API key from localStorage
        const apiKey = localStorage.getItem('dspy_api_key');

        // Build headers
        const headers = {
            'Content-Type': 'application/json'
        };

        // Add API key header if available
        if (apiKey) {
            headers['X-API-Key'] = apiKey;
        }

        const response = await fetch(`/${programName}`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            // Handle 401 specifically
            if (response.status === 401) {
                showMessage('Authentication failed. Please check your API key.', 'error');
                updateAuthStatus(false);
            }

            let errorMessage = 'Request failed';
            try {
                const errorData = await response.json();

                // Handle different error formats
                if (typeof errorData.detail === 'string') {
                    errorMessage = errorData.detail;
                } else if (Array.isArray(errorData.detail)) {
                    // Handle Pydantic validation errors (FastAPI format)
                    const errors = errorData.detail.map(err => {
                        const field = err.loc ? err.loc.slice(1).join('.') : 'unknown';
                        const message = err.msg || 'Invalid value';
                        return `  • ${field}: ${message}`;
                    }).join('\n');
                    errorMessage = `Validation Error:\n\n${errors}`;
                } else if (typeof errorData.detail === 'object') {
                    // If detail is an object, stringify it nicely
                    errorMessage = JSON.stringify(errorData.detail, null, 2);
                } else if (errorData.message) {
                    errorMessage = errorData.message;
                } else if (errorData.error) {
                    errorMessage = errorData.error;
                } else {
                    // Show the whole error object if we can't find a specific message
                    errorMessage = JSON.stringify(errorData, null, 2);
                }
            } catch (e) {
                // If we can't parse the error response, use status text
                errorMessage = `Request failed: ${response.statusText || response.status}`;
            }
            throw new Error(errorMessage);
        }

        const result = await response.json();

        // Display result
        document.getElementById('resultContent').textContent = JSON.stringify(result, null, 2);
        resultBox.style.display = 'block';

        // Scroll to result
        resultBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        // Reload logs to show the new inference
        setTimeout(() => loadLogs(programName), 500);

    } catch (error) {
        // Display error with better formatting
        let errorText = error.message;

        // If error message looks like JSON, try to format it nicely
        if (errorText.startsWith('{') || errorText.startsWith('[')) {
            try {
                const parsed = JSON.parse(errorText);
                errorText = JSON.stringify(parsed, null, 2);
            } catch (e) {
                // Keep original if parsing fails
            }
        }

        document.getElementById('errorContent').textContent = errorText;
        errorBox.style.display = 'block';

        // Scroll to error
        errorBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } finally {
        // Re-enable submit button
        submitBtn.disabled = false;
        submitBtn.textContent = 'Run Program';
    }
}

/**
 * Copy API call as curl command
 */
async function copyApiCall(programName) {
    const form = document.getElementById('programForm');
    const copyBtn = document.getElementById('copyApiBtn');

    // Collect form data (same logic as submitProgram)
    const formData = new FormData(form);
    const data = {};

    // Handle checkboxes explicitly
    const checkboxes = form.querySelectorAll('input[type="checkbox"]');
    const checkboxNames = new Set();
    checkboxes.forEach(checkbox => {
        checkboxNames.add(checkbox.name);
        data[checkbox.name] = checkbox.checked;
    });

    for (const [key, value] of formData.entries()) {
        // Skip checkboxes (already handled above)
        if (checkboxNames.has(key)) {
            continue;
        }

        // Check if value is empty
        const trimmedValue = typeof value === 'string' ? value.trim() : value;

        // Check if field is optional
        const inputElement = form.querySelector(`[name="${key}"]`);
        const isOptional = inputElement && inputElement.hasAttribute('data-optional');

        if (!trimmedValue && trimmedValue !== false) {
            // Skip adding to data if empty (don't send empty optional fields)
            if (!isOptional) {
                // For required fields, still add empty value to show what's missing
                data[key] = "";
            }
            continue;
        }

        // Try to parse as JSON for arrays/objects
        if (typeof value === 'string' && (value.trim().startsWith('[') || value.trim().startsWith('{'))) {
            try {
                data[key] = JSON.parse(value);
            } catch (e) {
                data[key] = value;
            }
        } else if (value === 'true') {
            data[key] = true;
        } else if (value === 'false') {
            data[key] = false;
        } else {
            data[key] = value;
        }
    }

    // Check for data URIs (uploaded files) - these cannot be copied to curl commands
    const hasDataUri = Object.values(data).some(value => {
        if (typeof value === 'string' && value.startsWith('data:')) {
            return true;
        }
        // Check nested arrays
        if (Array.isArray(value)) {
            return value.some(item => typeof item === 'string' && item.startsWith('data:'));
        }
        // Check nested objects
        if (typeof value === 'object' && value !== null) {
            return Object.values(value).some(item => typeof item === 'string' && item.startsWith('data:'));
        }
        return false;
    });

    if (hasDataUri) {
        // Show error feedback for data URIs
        const originalText = copyBtn.textContent;
        copyBtn.textContent = 'Use image URLs instead';
        copyBtn.style.background = '#e74c3c';

        setTimeout(() => {
            copyBtn.textContent = originalText;
            copyBtn.style.background = '';
        }, 3000);
        return;
    }

    // Generate curl command
    const url = `${window.location.protocol}//${window.location.host}/${programName}`;
    const jsonData = JSON.stringify(data, null, 2);
    const curlCommand = `curl -X POST ${url} \\\n  -H "Content-Type: application/json" \\\n  -d '${jsonData}'`;

    // Copy to clipboard with fallback
    try {
        // Try modern Clipboard API first
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(curlCommand);
        } else {
            // Fallback to old method
            const textarea = document.createElement('textarea');
            textarea.value = curlCommand;
            textarea.style.position = 'fixed';
            textarea.style.opacity = '0';
            document.body.appendChild(textarea);
            textarea.select();
            const success = document.execCommand('copy');
            document.body.removeChild(textarea);

            if (!success) {
                throw new Error('execCommand copy failed');
            }
        }

        // Show success feedback
        const originalText = copyBtn.textContent;
        copyBtn.textContent = 'Copied!';
        copyBtn.style.background = '#27ae60';

        // Reset button after 2 seconds
        setTimeout(() => {
            copyBtn.textContent = originalText;
            copyBtn.style.background = '';
        }, 2000);
    } catch (error) {
        console.error('Failed to copy to clipboard:', error);

        // Show error feedback
        const originalText = copyBtn.textContent;
        copyBtn.textContent = 'Copy failed';
        setTimeout(() => {
            copyBtn.textContent = originalText;
        }, 2000);
    }
}

/**
 * Load and display logs for a program
 */
async function loadLogs(programName) {
    const logsContainer = document.getElementById('logs');

    // Show loading
    logsContainer.innerHTML = '<p class="loading">Loading logs...</p>';

    try {
        const response = await fetch(`/api/logs/${programName}`);

        if (!response.ok) {
            throw new Error('Failed to load logs');
        }

        const data = await response.json();
        const logs = data.logs || [];

        if (logs.length === 0) {
            logsContainer.innerHTML = '<p class="loading">No inference logs yet. Run the program to see logs here.</p>';
            return;
        }

        // Render logs
        logsContainer.innerHTML = logs.map(log => renderLogEntry(log)).join('');

    } catch (error) {
        logsContainer.innerHTML = `<p class="loading">Error loading logs: ${error.message}</p>`;
    }
}

/**
 * Render a single log entry
 */
function renderLogEntry(log) {
    const isError = !log.success;
    const statusClass = isError ? 'error' : 'success';
    const statusText = isError ? 'ERROR' : 'SUCCESS';

    // Format timestamp
    const timestamp = new Date(log.timestamp).toLocaleString();

    // Format duration
    const duration = log.duration_ms ? `${log.duration_ms.toFixed(2)}ms` : 'N/A';

    // Format inputs and outputs
    const inputsJson = JSON.stringify(log.inputs || {}, null, 2);
    const outputsJson = JSON.stringify(log.outputs || {}, null, 2);

    let errorHtml = '';
    if (isError && log.error) {
        errorHtml = `
            <div class="log-section">
                <div class="log-section-title">Error:</div>
                <div class="log-json">${escapeHtml(log.error)}</div>
            </div>
        `;
    }

    return `
        <div class="log-entry ${statusClass}">
            <div class="log-header">
                <div class="log-timestamp">${timestamp}</div>
                <div>
                    <span class="log-status ${statusClass}">${statusText}</span>
                    <span class="log-duration">${duration}</span>
                </div>
            </div>
            <div class="log-content">
                <div class="log-section">
                    <div class="log-section-title">Inputs:</div>
                    <div class="log-json">${escapeHtml(inputsJson)}</div>
                </div>
                <div class="log-section">
                    <div class="log-section-title">Outputs:</div>
                    <div class="log-json">${escapeHtml(outputsJson)}</div>
                </div>
                ${errorHtml}
            </div>
        </div>
    `;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Initialize image input handlers (tabs, drag-drop, file upload)
 */
function initImageInputs() {
    // Set up tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const fieldName = this.dataset.field;
            const tab = this.dataset.tab;

            // Update active tab button
            this.parentElement.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            // Show corresponding pane
            document.querySelectorAll(`[id^="${fieldName}_"][id$="_pane"]`).forEach(pane => {
                pane.classList.remove('active');
            });
            document.getElementById(`${fieldName}_${tab}_pane`).classList.add('active');
        });
    });

    // Set up file upload buttons
    document.querySelectorAll('.file-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const fieldName = this.dataset.field;
            document.getElementById(`${fieldName}_file`).click();
        });
    });

    // Set up file input change handlers
    document.querySelectorAll('input[type="file"]').forEach(input => {
        input.addEventListener('change', function() {
            const fieldName = this.id.replace('_file', '');
            if (this.files && this.files[0]) {
                handleImageFile(fieldName, this.files[0]);
            }
        });
    });

    // Set up drag and drop
    document.querySelectorAll('.image-dropzone').forEach(dropzone => {
        const fieldName = dropzone.dataset.field;

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });

        dropzone.addEventListener('dragleave', () => {
            dropzone.classList.remove('dragover');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');

            if (e.dataTransfer.files && e.dataTransfer.files[0]) {
                handleImageFile(fieldName, e.dataTransfer.files[0]);
            }
        });
    });

    // Set up clear buttons
    document.querySelectorAll('.clear-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const fieldName = this.dataset.field;
            clearImage(fieldName);
        });
    });
}

/**
 * Handle image file selection (upload or drag-drop)
 */
function handleImageFile(fieldName, file) {
    // Validate file type
    if (!file.type.startsWith('image/')) {
        alert('Please select an image file');
        return;
    }

    // Read file as data URI
    const reader = new FileReader();
    reader.onload = function(e) {
        const dataUri = e.target.result;

        // Set the data URI as the field value
        const input = document.getElementById(fieldName);
        input.value = dataUri;

        // Show preview
        const preview = document.getElementById(`${fieldName}_preview`);
        const previewImg = document.getElementById(`${fieldName}_preview_img`);
        previewImg.src = dataUri;
        preview.style.display = 'block';

        // Hide dropzone content
        const dropzone = document.getElementById(`${fieldName}_dropzone`);
        dropzone.querySelector('.dropzone-content').style.display = 'none';
    };

    reader.readAsDataURL(file);
}

/**
 * Clear image selection
 */
function clearImage(fieldName) {
    // Clear input value
    const input = document.getElementById(fieldName);
    input.value = '';

    // Clear file input
    const fileInput = document.getElementById(`${fieldName}_file`);
    if (fileInput) {
        fileInput.value = '';
    }

    // Hide preview
    const preview = document.getElementById(`${fieldName}_preview`);
    preview.style.display = 'none';

    // Show dropzone content
    const dropzone = document.getElementById(`${fieldName}_dropzone`);
    if (dropzone) {
        dropzone.querySelector('.dropzone-content').style.display = 'block';
    }
}

/**
 * Initialize checkbox handlers to update labels
 */
function initCheckboxes() {
    // Find all checkboxes and their corresponding labels
    const checkboxes = document.querySelectorAll('input[type="checkbox"]');

    checkboxes.forEach(checkbox => {
        const label = document.querySelector(`.checkbox-label[data-checkbox="${checkbox.name}"]`);
        if (!label) return;

        // Update label based on initial state
        label.textContent = checkbox.checked ? 'True' : 'False';

        // Add change event listener
        checkbox.addEventListener('change', function() {
            label.textContent = this.checked ? 'True' : 'False';
        });
    });
}

// ===== Streaming Functions =====

/**
 * Submit the program with real-time streaming updates via SSE
 */
async function submitProgramStreaming(programName) {
    const form = document.getElementById('programForm');
    const submitBtn = form.querySelector('button[type="submit"]');
    const resultBox = document.getElementById('result');
    const errorBox = document.getElementById('error');
    const streamingContainer = document.getElementById('streamingContainer');
    const streamingEvents = document.getElementById('streamingEvents');

    // Hide previous results
    resultBox.style.display = 'none';
    errorBox.style.display = 'none';

    // Clear and show streaming container
    streamingEvents.innerHTML = '';
    streamingContainer.style.display = 'block';

    // Clear module stack for new request
    moduleStack.length = 0;

    // Disable submit button
    submitBtn.disabled = true;
    submitBtn.textContent = 'Running...';

    // Collect form data (reuse logic from submitProgram)
    const data = collectFormData(form);
    if (data === null) {
        // Missing required fields - error already displayed
        submitBtn.disabled = false;
        submitBtn.textContent = 'Run Program';
        streamingContainer.style.display = 'none';
        return;
    }

    try {
        // Get API key from localStorage
        const apiKey = localStorage.getItem('dspy_api_key');

        // Build headers
        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream'
        };

        // Add API key header if available
        if (apiKey) {
            headers['X-API-Key'] = apiKey;
        }

        const response = await fetch(`/${programName}/stream`, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            // Handle errors same as sync
            if (response.status === 401) {
                showMessage('Authentication failed. Please check your API key.', 'error');
                updateAuthStatus(false);
            }

            let errorMessage = 'Request failed';
            try {
                const errorData = await response.json();
                if (typeof errorData.detail === 'string') {
                    errorMessage = errorData.detail;
                } else if (Array.isArray(errorData.detail)) {
                    const errors = errorData.detail.map(err => {
                        const field = err.loc ? err.loc.slice(1).join('.') : 'unknown';
                        const message = err.msg || 'Invalid value';
                        return `  • ${field}: ${message}`;
                    }).join('\n');
                    errorMessage = `Validation Error:\n\n${errors}`;
                }
            } catch (e) {
                errorMessage = `Request failed: ${response.statusText || response.status}`;
            }
            throw new Error(errorMessage);
        }

        // Process streaming response
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n\n');
            buffer = lines.pop(); // Keep incomplete line in buffer

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;

                const jsonStr = line.replace('data: ', '');
                try {
                    const event = JSON.parse(jsonStr);
                    console.log('[Streaming] Received event:', event.type, event);

                    if (event.type === 'stream_start') {
                        console.log('[Streaming] Stream connected');
                        continue;
                    }

                    handleStreamingEvent(event, streamingEvents);

                    if (event.type === 'complete') {
                        // Display final result
                        document.getElementById('resultContent').textContent = JSON.stringify(event.result, null, 2);
                        resultBox.style.display = 'block';
                        resultBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

                        // Reload logs
                        setTimeout(() => loadLogs(programName), 500);
                    } else if (event.type === 'error') {
                        throw new Error(event.error);
                    }
                } catch (e) {
                    console.error('Failed to parse SSE event:', e, 'Line:', line);
                }
            }
        }

    } catch (error) {
        // Display error
        document.getElementById('errorContent').textContent = error.message;
        errorBox.style.display = 'block';
        errorBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } finally {
        // Re-enable submit button
        submitBtn.disabled = false;
        submitBtn.textContent = 'Run Program';
    }
}

/**
 * Handle a streaming event by creating and appending UI element
 */
// Track module hierarchy for nesting
const moduleStack = [];

function handleStreamingEvent(event, container) {
    if (event.type === 'module_start') {
        handleModuleStart(event, container);
    } else if (event.type === 'module_end') {
        handleModuleEnd(event, container);
    } else {
        // All other events go into the current module's content
        const eventDiv = createEventElement(event);
        if (eventDiv) {
            const currentModule = moduleStack.length > 0 ? moduleStack[moduleStack.length - 1] : null;
            if (currentModule) {
                currentModule.contentContainer.appendChild(eventDiv);
            } else {
                // No active module, append to main container
                container.appendChild(eventDiv);
            }
            container.scrollTop = container.scrollHeight; // Auto-scroll
        }
    }
}

function handleModuleStart(event, container) {
    // Create module start event item
    const startDiv = document.createElement('div');
    startDiv.className = 'event-item module-start';

    startDiv.innerHTML = `
        <div class="event-content-inline">
            <span>📦 Module started: <strong>${escapeHtml(event.module_name)}</strong></span>
        </div>
    `;

    // Append to current module's content or main container
    const currentModule = moduleStack.length > 0 ? moduleStack[moduleStack.length - 1] : null;
    if (currentModule) {
        currentModule.contentContainer.appendChild(startDiv);
    } else {
        container.appendChild(startDiv);
    }

    // Create a container for child events of this module
    const contentDiv = document.createElement('div');
    contentDiv.className = 'module-events-container';
    contentDiv.dataset.callId = event.call_id;

    if (currentModule) {
        currentModule.contentContainer.appendChild(contentDiv);
    } else {
        container.appendChild(contentDiv);
    }

    // Push to stack
    moduleStack.push({
        callId: event.call_id,
        contentContainer: contentDiv,
        startTime: event.timestamp
    });

    container.scrollTop = container.scrollHeight; // Auto-scroll
}

function handleModuleEnd(event, container) {
    // Find the matching module_start in the stack
    const moduleIndex = moduleStack.findIndex(m => m.callId === event.call_id);

    if (moduleIndex === -1) {
        console.warn('module_end without matching module_start:', event.call_id);
        return;
    }

    const module = moduleStack[moduleIndex];

    // Calculate duration
    const duration = ((event.timestamp - module.startTime) * 1000).toFixed(0);

    // Create module end event item
    const endDiv = document.createElement('div');
    endDiv.className = 'event-item module-end';

    // Build the content based on success/failure
    if (event.success === false) {
        endDiv.innerHTML = `
            <div class="event-content-inline">
                <span>❌ Module failed: <strong>${duration}ms</strong></span>
            </div>
        `;
    } else if (event.outputs) {
        // Module completed with outputs
        const eventId = `module-output-${event.call_id}`;

        // Try to parse outputs
        let parsedOutputs = event.outputs;
        if (typeof event.outputs === 'string') {
            try {
                parsedOutputs = JSON.parse(event.outputs);
            } catch (e) {
                parsedOutputs = event.outputs;
            }
        }

        const outputStr = typeof parsedOutputs === 'string'
            ? parsedOutputs
            : JSON.stringify(parsedOutputs);
        const preview = truncate(outputStr, 80);

        endDiv.innerHTML = `
            <div class="event-content-inline">
                <span>✅ Module completed: <strong>${duration}ms</strong> • Output: <code>${escapeHtml(preview)}</code></span>
                <button class="expand-btn-inline" onclick="toggleDetails('${eventId}')">expand</button>
            </div>
            <div id="${eventId}" class="event-details" style="display: none;">
                <pre>${escapeHtml(typeof parsedOutputs === 'string' ? parsedOutputs : JSON.stringify(parsedOutputs, null, 2))}</pre>
            </div>
        `;
    } else {
        // Module completed without outputs
        endDiv.innerHTML = `
            <div class="event-content-inline">
                <span>✅ Module completed: <strong>${duration}ms</strong></span>
            </div>
        `;
    }

    // Append to current module's content or main container
    module.contentContainer.appendChild(endDiv);

    // Remove from stack
    moduleStack.splice(moduleIndex, 1);

    container.scrollTop = container.scrollHeight; // Auto-scroll
}


/**
 * Create a DOM element for a streaming event
 */
function createEventElement(event) {
    const div = document.createElement('div');
    div.className = `event-item event-${event.type}`;
    const eventId = `event-${event.call_id}-${Date.now()}`;

    switch (event.type) {
        case 'module_start':
            // Module start is now handled in handleModuleStart
            return null;

        case 'lm_start':
            const msgCount = Array.isArray(event.messages) ? event.messages.length : 1;
            const preview = getMessagePreview(event.messages);
            div.innerHTML = `
                <div class="event-content-inline">
                    <span>🤖 LM: <code>${escapeHtml(event.model)}</code> • "${escapeHtml(preview)}"</span>
                    <button class="expand-btn-inline" onclick="toggleDetails('${eventId}')">prompt</button>
                </div>
                <div id="${eventId}" class="event-details" style="display: none;">${formatMessages(event.messages)}</div>
            `;
            break;

        case 'lm_end':
            const responsePreview = getOutputPreview(event.outputs);
            const tokenInfo = event.token_count ? ` • ${event.token_count} tokens` : '';
            div.innerHTML = `
                <div class="event-content-inline">
                    <span>✅ Response: "${escapeHtml(responsePreview)}"${escapeHtml(tokenInfo)}</span>
                    <button class="expand-btn-inline" onclick="toggleDetails('${eventId}')">expand</button>
                </div>
                <div id="${eventId}" class="event-details" style="display: none;"><pre>${escapeHtml(String(event.outputs))}</pre></div>
            `;
            break;

        case 'tool_start':
            const argPreview = getArgumentPreview(event.args);
            div.innerHTML = `
                <div class="event-content-inline">
                    <span>🔧 Tool: <code>${escapeHtml(event.tool_name)}</code> • ${escapeHtml(argPreview)}</span>
                    <button class="expand-btn-inline" onclick="toggleDetails('${eventId}')">expand</button>
                </div>
                <div id="${eventId}" class="event-details" style="display: none;"><pre>${escapeHtml(JSON.stringify(event.args, null, 2))}</pre></div>
            `;
            break;

        case 'tool_end':
            div.innerHTML = `
                <div class="event-content-inline">
                    <span>✅ Tool result</span>
                    <button class="expand-btn-inline" onclick="toggleDetails('${eventId}')">expand</button>
                </div>
                <div id="${eventId}" class="event-details" style="display: none;"><pre>${escapeHtml(JSON.stringify(event.outputs, null, 2))}</pre></div>
            `;
            break;

        case 'module_end':
            // Module end is now handled in handleModuleEnd
            return null;

        case 'adapter_format_start':
        case 'adapter_format_end':
        case 'adapter_parse_start':
        case 'adapter_parse_end':
            // Filter out adapter events - they add noise and aren't useful to users
            return null;

        default:
            // Skip unknown event types
            return null;
    }

    return div;
}

/**
 * Toggle expanded details visibility
 */
function toggleDetails(elementId, evt) {
    const details = document.getElementById(elementId);
    const btn = evt ? evt.target : event.target;

    if (details.style.display === 'none') {
        details.style.display = 'block';
        btn.textContent = 'collapse';
    } else {
        details.style.display = 'none';
        btn.textContent = 'expand';
    }
}

/**
 * Helper: Get input field names (not full values)
 */
function getInputFieldNames(inputs) {
    return Object.keys(inputs).join(', ');
}

/**
 * Helper: Get message preview (first 50 chars)
 */
function getMessagePreview(messages) {
    if (Array.isArray(messages)) {
        const firstContent = messages[0]?.content || '';
        return truncate(firstContent, 50);
    }
    return truncate(String(messages), 50);
}

/**
 * Helper: Get output preview (first 50 chars)
 */
function getOutputPreview(outputs) {
    const str = typeof outputs === 'string' ? outputs : JSON.stringify(outputs);
    return truncate(str, 50);
}

/**
 * Helper: Truncate text to max length
 */
function truncate(text, maxLen) {
    return text.length > maxLen ? text.substring(0, maxLen) + '...' : text;
}

/**
 * Helper: Generate smart preview for tool arguments
 * Shows actual values for primitives, type info for complex types
 */
function getArgumentPreview(args) {
    const previews = [];

    for (const [key, value] of Object.entries(args)) {
        let preview;

        if (value === null || value === undefined) {
            preview = `${key}=${value}`;
        } else if (typeof value === 'string') {
            // For strings: show first 30 chars with char count if truncated
            const truncated = truncate(value, 30);
            const charInfo = value.length > 30 ? ` (${value.length} chars)` : '';
            preview = `${key}="${truncated}"${charInfo}`;
        } else if (typeof value === 'number') {
            // For numbers: show full value
            preview = `${key}=${value}`;
        } else if (typeof value === 'boolean') {
            // For booleans: show full value
            preview = `${key}=${value}`;
        } else if (Array.isArray(value)) {
            // For arrays: show type and count
            preview = `${key}=[Array with ${value.length} item${value.length !== 1 ? 's' : ''}]`;
        } else if (typeof value === 'object') {
            // For objects: show type and key count
            const keyCount = Object.keys(value).length;
            preview = `${key}={Object with ${keyCount} key${keyCount !== 1 ? 's' : ''}}`;
        } else {
            // Fallback for other types
            preview = `${key}=(${typeof value})`;
        }

        previews.push(preview);
    }

    return previews.join(', ');
}

/**
 * Helper: Format messages array as HTML
 */
function formatMessages(messages) {
    if (Array.isArray(messages)) {
        return messages.map(m => {
            const role = escapeHtml(m.role || 'unknown');
            const content = escapeHtml(m.content || '');
            return `<div class="message-${role}"><strong>${role}:</strong> ${content}</div>`;
        }).join('');
    }
    return `<pre>${escapeHtml(String(messages))}</pre>`;
}

/**
 * Helper: Collect form data with validation (reusable)
 */
function collectFormData(form) {
    const formData = new FormData(form);
    const data = {};
    const missingFields = [];

    // Handle checkboxes explicitly
    const checkboxes = form.querySelectorAll('input[type="checkbox"]');
    const checkboxNames = new Set();
    checkboxes.forEach(checkbox => {
        checkboxNames.add(checkbox.name);
        data[checkbox.name] = checkbox.checked;
    });

    for (const [key, value] of formData.entries()) {
        if (checkboxNames.has(key)) continue;

        const trimmedValue = typeof value === 'string' ? value.trim() : value;
        const inputElement = form.querySelector(`[name="${key}"]`);
        const isOptional = inputElement && inputElement.hasAttribute('data-optional');

        if (!trimmedValue && trimmedValue !== false) {
            if (!isOptional) {
                missingFields.push(key);
            }
            continue;
        }

        // Try to parse as JSON for arrays/objects
        if (typeof value === 'string' && (value.trim().startsWith('[') || value.trim().startsWith('{'))) {
            try {
                data[key] = JSON.parse(value);
            } catch (e) {
                data[key] = value;
            }
        } else if (value === 'true') {
            data[key] = true;
        } else if (value === 'false') {
            data[key] = false;
        } else {
            data[key] = value;
        }
    }

    // Check for missing required fields
    if (missingFields.length > 0) {
        const fieldList = missingFields.join(', ');
        const errorBox = document.getElementById('error');
        document.getElementById('errorContent').textContent =
            `Missing required input${missingFields.length > 1 ? 's' : ''}: ${fieldList}\n\nPlease provide a value for ${missingFields.length > 1 ? 'these fields' : 'this field'} before running the program.`;
        errorBox.style.display = 'block';
        errorBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        return null;
    }

    return data;
}

// Initialize auth status on page load
document.addEventListener('DOMContentLoaded', () => {
    const apiKey = localStorage.getItem('dspy_api_key');
    updateAuthStatus(!!apiKey);
});

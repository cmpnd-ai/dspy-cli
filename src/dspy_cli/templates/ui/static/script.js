// DSPy UI JavaScript

/**
 * Initialize the program page with event handlers and log loading
 */
function initProgramPage(programName) {
    // Load logs on page load
    loadLogs(programName);

    // Set up form submission
    const form = document.getElementById('programForm');
    if (form) {
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            submitProgram(programName);
        });

        // Add keyboard shortcut: Cmd+Enter (Mac) or Ctrl+Enter (Windows/Linux)
        form.addEventListener('keydown', (e) => {
            if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                e.preventDefault();
                submitProgram(programName);
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

    for (const [key, value] of formData.entries()) {
        // Try to parse as JSON for arrays/objects
        if (value.trim().startsWith('[') || value.trim().startsWith('{')) {
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

    try {
        const response = await fetch(`/${programName}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Request failed');
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
        // Display error
        document.getElementById('errorContent').textContent = error.message;
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

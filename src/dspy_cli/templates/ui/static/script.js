// DSPy UI JavaScript

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
function initProgramPage(programName) {
    // Load logs and metrics on page load
    loadLogs(programName);
    loadProgramMetrics(programName);

    // Initialize collapsible sections
    initCollapsibleSections();

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
        const response = await fetch(`/${programName}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
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

        // Reload logs and metrics to show the new inference
        setTimeout(() => {
            loadLogs(programName);
            loadProgramMetrics(programName);
        }, 500);

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
    
    // Include Authorization header placeholder if auth is enabled
    let headers = '-H "Content-Type: application/json"';
    if (typeof authEnabled !== 'undefined' && authEnabled) {
        headers += ' \\\n  -H "Authorization: Bearer <DSPY_API_KEY>"';
    }
    const curlCommand = `curl -X POST ${url} \\\n  ${headers} \\\n  -d '${jsonData}'`;

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

// ===== METRICS FUNCTIONS =====

let currentSortBy = 'calls';
let currentOrder = 'desc';

/**
 * Initialize metrics display and sorting on the index page
 */
async function initIndexMetrics() {
    const sortSelect = document.getElementById('sortSelect');
    const sortOrderBtn = document.getElementById('sortOrderBtn');

    if (!sortSelect) return; // Not on index page

    // Load initial metrics
    await loadAndDisplayMetrics();

    // Set up sort select handler
    sortSelect.addEventListener('change', async () => {
        currentSortBy = sortSelect.value;
        await loadAndDisplayMetrics();
    });

    // Set up sort order toggle
    sortOrderBtn.addEventListener('click', async () => {
        currentOrder = currentOrder === 'desc' ? 'asc' : 'desc';
        sortOrderBtn.textContent = currentOrder === 'desc' ? '↓' : '↑';
        await loadAndDisplayMetrics();
    });
}

/**
 * Load metrics from API and update the UI
 */
async function loadAndDisplayMetrics() {
    try {
        const response = await fetch(`/api/metrics?sort_by=${currentSortBy}&order=${currentOrder}`);
        if (!response.ok) throw new Error('Failed to load metrics');

        const data = await response.json();
        const metricsMap = {};

        // Build a map of program name to metrics
        data.programs.forEach(m => {
            metricsMap[m.program] = m;
        });

        // Update each program card with metrics
        document.querySelectorAll('.program-card').forEach(card => {
            const programName = card.dataset.program;
            const metrics = metricsMap[programName];
            if (!metrics) return;

            const callsEl = card.querySelector('.metric-calls');
            const latencyEl = card.querySelector('.metric-latency');
            const costEl = card.querySelector('.metric-cost');
            const lastCallEl = card.querySelector('.metric-last-call');

            if (callsEl) {
                callsEl.textContent = `${metrics.call_count} calls`;
            }
            if (latencyEl) {
                latencyEl.textContent = metrics.avg_latency_ms != null
                    ? `${Math.round(metrics.avg_latency_ms)}ms avg`
                    : '—';
            }
            if (costEl) {
                costEl.textContent = metrics.total_cost_usd != null
                    ? `$${metrics.total_cost_usd.toFixed(4)}`
                    : '—';
            }
            if (lastCallEl) {
                lastCallEl.textContent = metrics.last_call_ts
                    ? formatRelativeTime(metrics.last_call_ts)
                    : 'never';
            }
        });

        // Reorder cards based on API response order
        reorderCards(data.programs.map(m => m.program));

    } catch (error) {
        console.error('Error loading metrics:', error);
    }
}

/**
 * Reorder program cards in the DOM to match the sorted order
 */
function reorderCards(orderedProgramNames) {
    const grid = document.getElementById('programsGrid');
    if (!grid) return;

    const cards = Array.from(grid.querySelectorAll('.program-card'));
    const cardMap = {};
    cards.forEach(card => {
        cardMap[card.dataset.program] = card;
    });

    // Reorder by appending in the new order
    orderedProgramNames.forEach(name => {
        const card = cardMap[name];
        if (card) {
            grid.appendChild(card);
        }
    });
}

/**
 * Format a timestamp as relative time (e.g., "5m ago", "2h ago")
 */
function formatRelativeTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    if (diffDay < 7) return `${diffDay}d ago`;
    return date.toLocaleDateString();
}

/**
 * Initialize collapsible sections with localStorage persistence
 */
function initCollapsibleSections() {
    document.querySelectorAll('.section-header').forEach(header => {
        const section = header.dataset.section;
        const content = header.nextElementSibling;
        const icon = header.querySelector('.collapse-icon');

        if (!content || !section) return;

        // Restore state from localStorage
        const isCollapsed = localStorage.getItem(`section-${section}-collapsed`) === 'true';
        if (isCollapsed) {
            content.classList.add('collapsed');
            icon.textContent = '▶';
        }

        // Add click handler
        header.addEventListener('click', (e) => {
            // Don't toggle if clicking the refresh button
            if (e.target.closest('.refresh-btn')) return;

            const isNowCollapsed = content.classList.toggle('collapsed');
            icon.textContent = isNowCollapsed ? '▶' : '▼';
            localStorage.setItem(`section-${section}-collapsed`, isNowCollapsed);
        });
    });
}

/**
 * Load and display metrics for a specific program page
 */
async function loadProgramMetrics(programName) {
    const container = document.getElementById('metricsContainer');
    const breakdownSection = document.getElementById('lmBreakdown');
    const breakdownContent = document.getElementById('lmBreakdownContent');

    if (!container) return;

    try {
        const response = await fetch(`/api/metrics/${programName}`);
        if (!response.ok) throw new Error('Failed to load metrics');

        const data = await response.json();
        const m = data.metrics;

        container.innerHTML = `
            <div class="metrics-grid">
                <div class="metric-item">
                    <span class="metric-value">${m.call_count}</span>
                    <span class="metric-label">Total Calls</span>
                </div>
                <div class="metric-item">
                    <span class="metric-value">${m.success_count}</span>
                    <span class="metric-label">Successful</span>
                </div>
                <div class="metric-item">
                    <span class="metric-value">${m.error_count}</span>
                    <span class="metric-label">Errors</span>
                </div>
                <div class="metric-item">
                    <span class="metric-value">${m.avg_latency_ms != null ? Math.round(m.avg_latency_ms) + 'ms' : '—'}</span>
                    <span class="metric-label">Avg Latency</span>
                </div>
                <div class="metric-item">
                    <span class="metric-value">${m.p95_latency_ms != null ? Math.round(m.p95_latency_ms) + 'ms' : '—'}</span>
                    <span class="metric-label">P95 Latency</span>
                </div>
                <div class="metric-item">
                    <span class="metric-value">${m.total_tokens.toLocaleString()}</span>
                    <span class="metric-label">Total Tokens</span>
                </div>
                <div class="metric-item">
                    <span class="metric-value">${m.total_cost_usd != null ? '$' + m.total_cost_usd.toFixed(4) : '—'}</span>
                    <span class="metric-label">Total Cost</span>
                </div>
            </div>
        `;

        // Show LM breakdown if available
        if (m.lm_call_breakdown && Object.keys(m.lm_call_breakdown).length > 0) {
            let breakdownHtml = '<table class="breakdown-table"><thead><tr><th>Model</th><th>Calls</th><th>Prompt Tokens</th><th>Completion Tokens</th><th>Cost</th></tr></thead><tbody>';

            for (const [model, stats] of Object.entries(m.lm_call_breakdown)) {
                breakdownHtml += `
                    <tr>
                        <td>${escapeHtml(model)}</td>
                        <td>${stats.call_count}</td>
                        <td>${stats.total_prompt_tokens.toLocaleString()}</td>
                        <td>${stats.total_completion_tokens.toLocaleString()}</td>
                        <td>${stats.total_cost_usd > 0 ? '$' + stats.total_cost_usd.toFixed(4) : '—'}</td>
                    </tr>
                `;
            }

            breakdownHtml += '</tbody></table>';
            breakdownContent.innerHTML = breakdownHtml;
            breakdownSection.style.display = 'block';
        }

    } catch (error) {
        container.innerHTML = `<p class="loading">Error loading metrics: ${error.message}</p>`;
    }
}

"""HTML templates for the web UI."""

from typing import List, Dict, Any
from dspy_cli.config import get_program_model
from dspy_cli.discovery.module_finder import get_module_fields


def render_index(modules: List[Any], config: Dict) -> str:
    """Render the index page with a list of all programs.

    Args:
        modules: List of DiscoveredModule objects
        config: Configuration dictionary

    Returns:
        HTML string for the index page
    """
    programs_html = ""

    if modules:
        # Sort modules alphabetically by name (initial render, JS will re-sort based on metrics)
        sorted_modules = sorted(modules, key=lambda m: m.name)

        # Hide docstrings when there are multiple modules (2+)
        show_docstrings = len(modules) == 1

        for module in sorted_modules:

            model_alias = get_program_model(config, module.name)

            # Extract adapter type from model alias (e.g., "openai" from "openai:gpt-5-mini")
            adapter = model_alias.split(':')[0] if ':' in model_alias else 'default'

            # Get signature docstring if available (only when showing docstrings)
            signature_doc = ""
            if show_docstrings and module.signature and module.signature.__doc__:
                full_doc = module.signature.__doc__.strip()
                # Truncate to approximately 3 lines (roughly 200 characters)
                if len(full_doc) > 200:
                    signature_doc = full_doc[:200].rsplit(' ', 1)[0] + '...'
                else:
                    signature_doc = full_doc

            # Build description HTML
            description_html = f'<p class="program-description">{signature_doc}</p>' if signature_doc else ''

            # Build error message if not typed
            error_html = ''
            if not module.is_forward_typed:
                error_html = '<p class="program-error" style="color: #e74c3c;">This module\'s forward function isn\'t typed</p>'

            programs_html += f"""
            <div class="program-card" data-url="/ui/{module.name}" data-program="{module.name}">
                <div class="program-header">
                    <h3><a href="/ui/{module.name}">{module.name}</a></h3>
                    <span class="model-badge" data-adapter="{adapter}">{model_alias}</span>
                </div>
                {description_html}
                {error_html}
                <div class="program-metrics">
                    <span class="metric metric-calls" title="Total calls">—</span>
                    <span class="metric metric-latency" title="Average latency">—</span>
                    <span class="metric metric-cost" title="Total cost">—</span>
                    <span class="metric metric-last-call" title="Last called">—</span>
                </div>
            </div>
            """
    else:
        programs_html = '<p class="no-programs">No programs discovered</p>'

    # Get project name from config
    project_name = config.get("app_id", "DSPy Project")
    # Capitalize and format the project name nicely
    display_name = project_name.replace("-", " ").replace("_", " ").title()

    # Get optional description from config
    description = config.get("description", "")
    description_html = f'<p class="project-description">{description}</p>' if description else ''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{display_name}</title>
    <link rel="stylesheet" href="/static/style.css">
    <script>
        // Apply theme immediately to prevent flash
        (function() {{
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme) {{
                document.documentElement.setAttribute('data-theme', savedTheme);
            }} else {{
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
            }}
        }})();
    </script>
</head>
<body>
    <div class="container">
        <header>
            <h1>{display_name}</h1>
            {description_html}
            <button class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle dark mode">
                <span id="themeIcon" class="theme-toggle-icon">🌙</span>
            </button>
        </header>

        <main>
            <div class="sort-controls">
                <label for="sortSelect">Sort by:</label>
                <select id="sortSelect">
                    <option value="calls" selected>Calls</option>
                    <option value="latency">Latency</option>
                    <option value="cost">Cost</option>
                    <option value="last_call">Last Called</option>
                    <option value="name">Name</option>
                </select>
                <button id="sortOrderBtn" class="sort-order-btn" title="Toggle sort order">↓</button>
            </div>
            <div class="programs-grid" id="programsGrid">
                {programs_html}
            </div>
        </main>

        <footer>
            <p>API endpoint: <code>GET /programs</code> for JSON schema</p>
        </footer>
    </div>

    <script src="/static/script.js"></script>
    <script>
        // Update icon after page loads
        updateThemeIcon();

        // Make program cards clickable
        document.querySelectorAll('.program-card').forEach(card => {{
            card.addEventListener('click', (e) => {{
                // Don't navigate if clicking on the link itself (to avoid double navigation)
                if (e.target.tagName === 'A' || e.target.closest('a')) {{
                    return;
                }}
                const url = card.dataset.url;
                if (url) {{
                    window.location.href = url;
                }}
            }});
        }});

        // Initialize metrics on index page
        initIndexMetrics();
    </script>
</body>
</html>"""


def render_program(module: Any, config: Dict, program_name: str, auth_enabled: bool = False) -> str:
    """Render the program detail page with form and logs.

    Args:
        module: DiscoveredModule object
        config: Configuration dictionary
        program_name: Name of the program
        auth_enabled: Whether authentication is enabled

    Returns:
        HTML string for the program page
    """
    model_alias = get_program_model(config, program_name)

    # Extract adapter type from model alias
    adapter = model_alias.split(':')[0] if ':' in model_alias else 'default'

    # Get program docstring
    program_docstring = ""
    if module.signature and module.signature.__doc__:
        program_docstring = module.signature.__doc__.strip()

    # Build signature string and form fields
    signature_string = ""
    form_fields = ""

    # Check if forward is typed
    if not module.is_forward_typed:
        # Forward method is not properly typed - show error
        signature_string = '<span style="color: #e74c3c;">This module\'s forward function isn\'t typed</span>'
        form_fields = '''
        <div class="warning-box">
            <h3>⚠️ Module Not Properly Typed</h3>
            <p>This module's <code>forward()</code> method doesn't have proper type annotations.</p>
            <p>To use this module via the API or web UI, please add type hints:</p>
            <pre><code>def forward(self, input_field: str) -> YourOutputType:
    # Your implementation
    return result</code></pre>
            <p>The forward method must have:</p>
            <ul>
                <li>Typed parameters (no **kwargs)</li>
                <li>A typed return value (TypedDict, NamedTuple, or dataclass)</li>
            </ul>
        </div>
        '''
    else:
        # Get field information
        fields = get_module_fields(module)
        input_names = list(fields["inputs"].keys())
        output_names = list(fields["outputs"].keys())
        input_str = ", ".join(input_names) if input_names else "no inputs"
        output_str = ", ".join(output_names) if output_names else "no outputs"
        signature_string = f"{input_str} → {output_str}"

        # Build form fields
        for field_name, field_info in fields["inputs"].items():
            field_type = field_info.get("type", "str")
            description = field_info.get("description", "").strip()

            # Filter out placeholder descriptions (like "${field_name}" or just the field name)
            if description.startswith("${") or description == field_name or not description:
                description = ""

            # Check if field is optional
            is_optional = "Optional[" in field_type or "optional" in field_type.lower()

            # Determine input type
            optional_attr = ' data-optional="true"' if is_optional else ''

            if "Literal[" in field_type:
                # Parse Literal type to extract options
                import re
                # Extract values from Literal['option1', 'option2', ...]
                match = re.search(r"Literal\[(.*?)\]", field_type)
                if match:
                    options_str = match.group(1)
                    # Split by comma and clean up quotes
                    options = [opt.strip().strip("'\"") for opt in options_str.split(",")]
                    # Add empty option first, then mark first real option as selected
                    options_html = '<option value=""></option>\n'
                    options_html += "\n".join([
                        f'<option value="{opt}"{" selected" if i == 0 else ""}>{opt}</option>'
                        for i, opt in enumerate(options)
                    ])
                    input_html = f'''
                <select id="{field_name}" name="{field_name}"{optional_attr}>
                    {options_html}
                </select>
                '''
                else:
                    # Fallback if parsing fails
                    input_html = f'<textarea id="{field_name}" name="{field_name}" rows="3" placeholder="Enter {field_type}"{optional_attr}></textarea>'
            elif field_type == "dspy.Image":
                # Special image input widget with URL, upload, and drag-drop
                input_html = f'''
                <div class="image-input-container" id="{field_name}_container">
                    <div class="image-input-tabs">
                        <button type="button" class="tab-btn active" data-tab="url" data-field="{field_name}">URL</button>
                        <button type="button" class="tab-btn" data-tab="upload" data-field="{field_name}">Upload</button>
                    </div>
                    <div class="image-input-tab-content">
                        <div class="tab-pane active" id="{field_name}_url_pane">
                            <input type="text" id="{field_name}" name="{field_name}" placeholder="Paste image URL here" class="image-url-input"{optional_attr}>
                        </div>
                        <div class="tab-pane" id="{field_name}_upload_pane">
                            <div class="image-dropzone" id="{field_name}_dropzone" data-field="{field_name}">
                                <input type="file" id="{field_name}_file" accept="image/*" style="display: none;">
                                <div class="dropzone-content">
                                    <p class="dropzone-text">Drag and drop an image here</p>
                                    <p class="dropzone-or">or</p>
                                    <button type="button" class="file-btn" data-field="{field_name}">Choose File</button>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="image-preview" id="{field_name}_preview" style="display: none;">
                        <img id="{field_name}_preview_img" alt="Preview">
                        <button type="button" class="clear-btn" data-field="{field_name}">×</button>
                    </div>
                </div>
                '''
            elif "list" in field_type.lower():
                input_html = f'<textarea id="{field_name}" name="{field_name}" rows="4" placeholder="Enter JSON array, e.g., [\\"item1\\", \\"item2\\"]"{optional_attr}></textarea>'
            elif "bool" in field_type.lower():
                input_html = f'''
                <div class="checkbox-wrapper">
                    <input type="checkbox" id="{field_name}" name="{field_name}"{optional_attr}>
                    <span class="checkbox-label" data-checkbox="{field_name}">False</span>
                </div>
                '''
            else:
                input_html = f'<textarea id="{field_name}" name="{field_name}" rows="3" placeholder="Enter {field_type}"{optional_attr}></textarea>'

            form_fields += f"""
            <div class="form-group">
                <label for="{field_name}">
                    {field_name}
                    <span class="field-type">{field_type}</span>
                </label>
                {f'<p class="field-description">{description}</p>' if description else ''}
                {input_html}
            </div>
            """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{program_name} - DSPy Program</title>
    <link rel="stylesheet" href="/static/style.css">
    <script>
        // Apply theme immediately to prevent flash
        (function() {{
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme) {{
                document.documentElement.setAttribute('data-theme', savedTheme);
            }} else {{
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
            }}
        }})();
    </script>
</head>
<body>
    <div class="container">
        <header>
            <button class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle dark mode">
                <span id="themeIcon" class="theme-toggle-icon">🌙</span>
            </button>
            <nav>
                <a href="/" class="back-link">← All Programs</a>
            </nav>
            <h1>{program_name} <span class="model-badge" data-adapter="{adapter}">{model_alias}</span></h1>
            {f'<p class="program-description">{program_docstring}</p>' if program_docstring else ''}
            {f'<p class="field-info">{signature_string}</p>' if signature_string else ''}
        </header>

        <main>
            <section class="test-section">
                <div class="section-card">
                    <h2>Inputs</h2>
                    <form id="programForm">
                        {form_fields}
                        <div class="button-row">
                            <button type="submit" class="submit-btn">Run Program</button>
                            <span class="copy-btn-wrapper">
                                <button type="button" class="copy-btn" id="copyApiBtn">Copy API Call</button>
                                {'<span class="auth-hint">Replace <code>&lt;DSPY_API_KEY&gt;</code> with your API key</span>' if auth_enabled else ''}
                            </span>
                        </div>
                    </form>

                    <div id="result" class="result-box" style="display: none;">
                        <h3>Result</h3>
                        <div id="resultContent"></div>
                    </div>

                    <div id="error" class="error-box" style="display: none;">
                        <h3>Error</h3>
                        <div id="errorContent"></div>
                    </div>
                </div>
            </section>

            <section class="metrics-section">
                <div class="section-card collapsible">
                    <h2 class="section-header" data-section="metrics">
                        <span class="collapse-icon">▼</span>
                        Metrics
                    </h2>
                    <div id="metricsContent" class="section-content">
                        <div id="metricsContainer" class="metrics-container">
                            <p class="loading">Loading metrics...</p>
                        </div>
                        <div id="lmBreakdown" class="lm-breakdown" style="display: none;">
                            <h3>LM Call Breakdown</h3>
                            <div id="lmBreakdownContent"></div>
                        </div>
                    </div>
                </div>
            </section>

            <section class="logs-section">
                <div class="section-card collapsible">
                    <h2 class="section-header" data-section="logs">
                        <span class="collapse-icon">▼</span>
                        Recent Inferences
                        <button id="refreshLogs" class="refresh-btn">Refresh</button>
                    </h2>
                    <div id="logsContent" class="section-content">
                        <div id="logs" class="logs-container">
                            <p class="loading">Loading logs...</p>
                        </div>
                    </div>
                </div>
            </section>
        </main>
    </div>

    <script src="/static/script.js"></script>
    <script>
        // Update icon after page loads
        updateThemeIcon();

        // Initialize the program page
        const programName = "{program_name}";
        const authEnabled = {'true' if auth_enabled else 'false'};
        initProgramPage(programName);
    </script>
</body>
</html>"""

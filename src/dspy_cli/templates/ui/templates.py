"""HTML templates for the web UI."""

from typing import List, Dict, Any


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
        for module in modules:
            from dspy_cli.config import get_program_model
            model_alias = get_program_model(config, module.name)

            # Get input/output field counts
            input_count = len(module.signature.input_fields) if module.signature else 0
            output_count = len(module.signature.output_fields) if module.signature else 0

            programs_html += f"""
            <div class="program-card">
                <h3><a href="/ui/{module.name}">{module.name}</a></h3>
                <p class="program-meta">
                    <span class="model-badge">{model_alias}</span>
                    <span class="field-info">{input_count} input(s) → {output_count} output(s)</span>
                </p>
            </div>
            """
    else:
        programs_html = '<p class="no-programs">No programs discovered</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DSPy Programs</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>DSPy Programs</h1>
            <p class="subtitle">Interactive testing interface for your DSPy modules</p>
        </header>

        <main>
            <div class="programs-grid">
                {programs_html}
            </div>
        </main>

        <footer>
            <p>API endpoint: <code>GET /programs</code> for JSON schema</p>
        </footer>
    </div>
</body>
</html>"""


def render_program(module: Any, config: Dict, program_name: str) -> str:
    """Render the program detail page with form and logs.

    Args:
        module: DiscoveredModule object
        config: Configuration dictionary
        program_name: Name of the program

    Returns:
        HTML string for the program page
    """
    from dspy_cli.config import get_program_model
    from dspy_cli.discovery.module_finder import get_signature_fields

    model_alias = get_program_model(config, program_name)

    # Build form fields
    form_fields = ""
    if module.signature:
        fields = get_signature_fields(module.signature)

        for field_name, field_info in fields["inputs"].items():
            field_type = field_info.get("type", "str")
            description = field_info.get("description", "")

            # Determine input type
            if field_type == "dspy.Image":
                # Special image input widget with URL, upload, and drag-drop
                input_html = f'''
                <div class="image-input-container" id="{field_name}_container">
                    <div class="image-input-tabs">
                        <button type="button" class="tab-btn active" data-tab="url" data-field="{field_name}">URL</button>
                        <button type="button" class="tab-btn" data-tab="upload" data-field="{field_name}">Upload</button>
                    </div>
                    <div class="image-input-tab-content">
                        <div class="tab-pane active" id="{field_name}_url_pane">
                            <input type="text" id="{field_name}" name="{field_name}" placeholder="Paste image URL here" class="image-url-input">
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
                input_html = f'<textarea id="{field_name}" name="{field_name}" rows="4" placeholder="Enter JSON array, e.g., [\\"item1\\", \\"item2\\"]"></textarea>'
            elif "bool" in field_type.lower():
                input_html = f'''
                <select id="{field_name}" name="{field_name}">
                    <option value="true">True</option>
                    <option value="false">False</option>
                </select>
                '''
            else:
                input_html = f'<textarea id="{field_name}" name="{field_name}" rows="3" placeholder="Enter {field_type}"></textarea>'

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

        # Show output fields
        output_fields_html = ""
        for field_name, field_info in fields["outputs"].items():
            field_type = field_info.get("type", "str")
            output_fields_html += f'<li><strong>{field_name}</strong> <span class="field-type">{field_type}</span></li>'
    else:
        form_fields = '<p class="warning">No signature information available</p>'
        output_fields_html = '<li>Unknown</li>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{program_name} - DSPy Program</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <div class="container">
        <header>
            <nav>
                <a href="/" class="back-link">← All Programs</a>
            </nav>
            <h1>{program_name}</h1>
            <p class="program-meta">
                <span class="model-badge">{model_alias}</span>
            </p>
        </header>

        <main>
            <section class="program-info">
                <h2>Schema</h2>
                <div class="schema-info">
                    <div class="schema-section">
                        <h3>Outputs:</h3>
                        <ul>
                            {output_fields_html}
                        </ul>
                    </div>
                </div>
            </section>

            <section class="test-section">
                <h2>Test Program</h2>
                <form id="programForm">
                    {form_fields}
                    <button type="submit" class="submit-btn">Run Program</button>
                </form>

                <div id="result" class="result-box" style="display: none;">
                    <h3>Result</h3>
                    <div id="resultContent"></div>
                </div>

                <div id="error" class="error-box" style="display: none;">
                    <h3>Error</h3>
                    <div id="errorContent"></div>
                </div>
            </section>

            <section class="logs-section">
                <h2>Recent Inferences</h2>
                <button id="refreshLogs" class="refresh-btn">Refresh Logs</button>
                <div id="logs" class="logs-container">
                    <p class="loading">Loading logs...</p>
                </div>
            </section>
        </main>
    </div>

    <script src="/static/script.js"></script>
    <script>
        // Initialize the program page
        const programName = "{program_name}";
        initProgramPage(programName);
    </script>
</body>
</html>"""

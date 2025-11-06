"""
Simple OTLP trace viewer for DSPy programs.
Receives OTLP/HTTP traces, stores them in-memory, and serves a web UI.
"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from collections import OrderedDict, defaultdict
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DSPy Trace Viewer")
store = OrderedDict()
MAX_TRACES = 200


def bytes_hex(b: bytes) -> str:
    """Convert bytes to hex string."""
    return b.hex() if b else ""


def kv_to_py(kv):
    """Convert OTLP KeyValue to Python primitive."""
    v = kv.value
    if v.HasField("string_value"):
        return v.string_value
    if v.HasField("int_value"):
        return v.int_value
    if v.HasField("double_value"):
        return v.double_value
    if v.HasField("bool_value"):
        return v.bool_value
    if v.HasField("bytes_value"):
        return v.bytes_value.decode("utf-8", "ignore")
    if v.HasField("array_value"):
        return [kv_to_py(item) for item in v.array_value.values]
    if v.HasField("kvlist_value"):
        return {kv.key: kv_to_py(kv) for kv in v.kvlist_value.values}
    return None


@app.post("/v1/traces")
async def otlp_http(request: Request):
    """OTLP/HTTP trace receiver endpoint."""
    body = await request.body()
    msg = ExportTraceServiceRequest()
    try:
        msg.ParseFromString(body)
    except Exception as e:
        logger.error(f"Failed to parse OTLP request: {e}")
        return JSONResponse({"error": "invalid protobuf"}, status_code=400)

    spans_received = 0
    for rs in msg.resource_spans:
        rattrs = {kv.key: kv_to_py(kv) for kv in rs.resource.attributes}
        service = rattrs.get("service.name", "unknown")

        for ss in rs.scope_spans:
            for sp in ss.spans:
                trace_id = bytes_hex(sp.trace_id)
                span_id = bytes_hex(sp.span_id)
                parent_id = bytes_hex(sp.parent_span_id) if sp.parent_span_id else ""

                attrs = {kv.key: kv_to_py(kv) for kv in sp.attributes}
                events = [
                    {
                        "name": e.name,
                        "time": e.time_unix_nano,
                        "attrs": {kv.key: kv_to_py(kv) for kv in e.attributes},
                    }
                    for e in sp.events
                ]

                span = {
                    "span_id": span_id,
                    "parent_id": parent_id,
                    "name": sp.name,
                    "start": sp.start_time_unix_nano,
                    "end": sp.end_time_unix_nano,
                    "attrs": attrs,
                    "events": events,
                    "service": service,
                    "status": sp.status.code,
                }

                t = store.get(trace_id)
                if not t:
                    t = {
                        "trace_id": trace_id,
                        "service": service,
                        "spans": {},
                        "children": defaultdict(list),
                        "start": sp.start_time_unix_nano,
                        "end": sp.end_time_unix_nano,
                    }
                    store[trace_id] = t
                    if len(store) > MAX_TRACES:
                        oldest = store.popitem(last=False)
                        logger.info(f"Evicted oldest trace: {oldest[0]}")

                t["spans"][span_id] = span
                if parent_id:
                    if parent_id not in t["children"][parent_id]:
                        t["children"][parent_id].append(span_id)

                t["start"] = min(t["start"], sp.start_time_unix_nano)
                t["end"] = max(t["end"], sp.end_time_unix_nano)
                spans_received += 1

    logger.info(f"Received {spans_received} spans across {len(msg.resource_spans)} resources")
    return JSONResponse({"accepted": True, "spans_received": spans_received})


@app.get("/api/traces")
def list_traces(service: str = None, limit: int = 100):
    """List recent traces with optional service filter."""
    items = []
    for t in reversed(list(store.values())):
        if service and t["service"] != service:
            continue
        items.append(
            {
                "trace_id": t["trace_id"],
                "service": t["service"],
                "start": t["start"],
                "end": t["end"],
                "duration_ms": (t["end"] - t["start"]) / 1_000_000,
                "spans": len(t["spans"]),
            }
        )
        if len(items) >= limit:
            break
    return items


@app.get("/api/traces/{trace_id}")
def get_trace(trace_id: str):
    """Get full trace with hierarchical span tree."""
    t = store.get(trace_id)
    if not t:
        return JSONResponse({"error": "not found"}, status_code=404)

    spans = t["spans"]
    children = t["children"]

    roots = [
        sid for sid, s in spans.items() if not s["parent_id"] or s["parent_id"] not in spans
    ]

    def build_tree(node_id):
        s = spans[node_id]
        return {
            "id": node_id,
            "name": s["name"],
            "start": s["start"],
            "end": s["end"],
            "duration_ms": (s["end"] - s["start"]) / 1_000_000,
            "attrs": s["attrs"],
            "events": s["events"],
            "status": s["status"],
            "children": [build_tree(c) for c in children.get(node_id, [])],
        }

    tree = [build_tree(r) for r in roots]

    return {
        "trace_id": trace_id,
        "service": t["service"],
        "start": t["start"],
        "end": t["end"],
        "duration_ms": (t["end"] - t["start"]) / 1_000_000,
        "tree": tree,
    }


@app.get("/api/stats")
def get_stats():
    """Get viewer statistics."""
    services = set()
    total_spans = 0
    for t in store.values():
        services.add(t["service"])
        total_spans += len(t["spans"])

    return {
        "traces": len(store),
        "services": sorted(list(services)),
        "total_spans": total_spans,
        "max_traces": MAX_TRACES,
    }


@app.post("/api/reset")
def reset_store():
    """Clear all traces."""
    count = len(store)
    store.clear()
    logger.info(f"Cleared {count} traces")
    return {"cleared": count}


@app.get("/", response_class=HTMLResponse)
def index():
    """Serve the UI."""
    return """<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>DSPy Trace Viewer</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font: 14px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; display: flex; height: 100vh; background: #fafafa; }
        #list { width: 360px; overflow: auto; border-right: 1px solid #ddd; padding: 12px; background: #f9f9f9; }
        #detail { flex: 1; overflow: auto; padding: 0; background: white; }
        h2 { font-size: 16px; margin-bottom: 12px; color: #333; }
        h3 { font-size: 18px; margin: 0; color: #333; font-weight: 600; }
        .trace-item { padding: 8px; margin: 4px 0; background: white; border: 1px solid #e0e0e0; border-radius: 4px; cursor: pointer; }
        .trace-item:hover { background: #f0f7ff; border-color: #2196F3; }
        .trace-item.active { background: #e3f2fd; border-color: #2196F3; }
        .service { font-weight: 600; color: #1976D2; }
        .trace-id { font-size: 11px; color: #999; font-family: monospace; }
        .meta { font-size: 12px; color: #666; margin-top: 4px; }
        button { padding: 6px 12px; background: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; margin: 4px; }
        button:hover { background: #1976D2; }
        .stats { font-size: 12px; color: #666; padding: 8px; background: #fff; border-radius: 4px; margin-bottom: 8px; }
        .empty { color: #999; padding: 40px; text-align: center; }
        
        /* Timeline view styles */
        .trace-header { padding: 20px 24px; border-bottom: 1px solid #e0e0e0; background: #fafafa; }
        .trace-meta { color: #666; font-size: 13px; margin-top: 8px; }
        .timeline { padding: 24px; }
        .span-row { display: flex; align-items: stretch; margin-bottom: 2px; position: relative; }
        .span-info { width: 320px; padding: 8px 12px; display: flex; align-items: center; gap: 8px; background: white; border-right: 1px solid #f0f0f0; }
        .span-indent { display: inline-block; }
        .span-expand { cursor: pointer; width: 16px; text-align: center; user-select: none; color: #666; }
        .span-expand.empty { visibility: hidden; }
        .span-name { font-weight: 500; color: #333; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .span-kind { display: inline-block; padding: 2px 6px; font-size: 10px; border-radius: 3px; font-weight: 600; text-transform: uppercase; }
        .kind-LLM, .kind-CHAT_MODEL { background: #ffebee; color: #c62828; }
        .kind-CHAIN { background: #e3f2fd; color: #1565c0; }
        .kind-RETRIEVER { background: #fff3e0; color: #ef6c00; }
        .kind-TOOL { background: #e8f5e9; color: #2e7d32; }
        .kind-AGENT { background: #f3e5f5; color: #6a1b9a; }
        .kind-PARSER { background: #fce4ec; color: #ad1457; }
        .span-timeline { flex: 1; position: relative; height: 32px; }
        .span-bar-container { position: absolute; top: 50%; transform: translateY(-50%); height: 24px; cursor: pointer; }
        .span-bar { height: 100%; border-radius: 3px; display: flex; align-items: center; padding: 0 8px; font-size: 11px; color: white; font-weight: 600; transition: opacity 0.2s; }
        .span-bar:hover { opacity: 0.8; }
        .bar-LLM, .bar-CHAT_MODEL { background: linear-gradient(135deg, #e53935 0%, #c62828 100%); }
        .bar-CHAIN { background: linear-gradient(135deg, #1e88e5 0%, #1565c0 100%); }
        .bar-RETRIEVER { background: linear-gradient(135deg, #fb8c00 0%, #ef6c00 100%); }
        .bar-TOOL { background: linear-gradient(135deg, #43a047 0%, #2e7d32 100%); }
        .bar-AGENT { background: linear-gradient(135deg, #8e24aa 0%, #6a1b9a 100%); }
        .bar-PARSER { background: linear-gradient(135deg, #d81b60 0%, #ad1457 100%); }
        .bar-default { background: linear-gradient(135deg, #757575 0%, #616161 100%); }
        .span-duration { margin-left: 8px; color: #666; font-size: 11px; white-space: nowrap; }
        .span-details { margin-left: 320px; padding: 16px 24px; background: #f9f9f9; border-left: 3px solid #2196F3; display: none; }
        .span-details.open { display: block; }
        .detail-section { margin-bottom: 16px; }
        .detail-label { font-weight: 600; color: #1976D2; margin-bottom: 4px; font-size: 12px; text-transform: uppercase; }
        pre { background: #fff; padding: 12px; border-radius: 4px; font-size: 12px; overflow-x: auto; border: 1px solid #e0e0e0; }
        .span-row.hidden { display: none; }
    </style>
</head>
<body>
    <div id="list">
        <h2>DSPy Traces</h2>
        <div class="stats" id="stats">Loading...</div>
        <button onclick="refresh()">↻ Refresh</button>
        <button onclick="clearTraces()">Clear All</button>
        <div id="trace-list"></div>
    </div>
    <div id="detail">
        <div class="empty">← Select a trace to view details</div>
    </div>
    
    <script>
        let currentTraceId = null;
        let expandedSpans = new Set();
        let selectedSpan = null;
        
        async function loadStats() {
            const r = await fetch('/api/stats');
            const data = await r.json();
            document.getElementById('stats').innerHTML = 
                `<b>${data.traces}</b> traces • <b>${data.total_spans}</b> spans • Services: ${data.services.join(', ') || 'none'}`;
        }
        
        async function loadList() {
            const r = await fetch('/api/traces');
            const data = await r.json();
            const listEl = document.getElementById('trace-list');
            
            if (data.length === 0) {
                listEl.innerHTML = '<div class="empty">No traces yet</div>';
                return;
            }
            
            listEl.innerHTML = data.map(t => {
                const time = new Date(t.start / 1e6).toLocaleTimeString();
                const active = t.trace_id === currentTraceId ? 'active' : '';
                return `
                    <div class="trace-item ${active}" onclick="loadTrace('${t.trace_id}')">
                        <div class="service">${esc(t.service)}</div>
                        <div class="trace-id">${t.trace_id.slice(0, 16)}...</div>
                        <div class="meta">${time} • ${t.duration_ms.toFixed(1)}ms • ${t.spans} spans</div>
                    </div>
                `;
            }).join('');
        }
        
        function esc(s) {
            return ('' + s).replace(/[&<>"']/g, m => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
            }[m]));
        }
        
        function flattenSpans(span, depth = 0, traceStart = 0, traceDuration = 1) {
            const spans = [];
            const kind = span.attrs["openinference.span.kind"] || span.attrs["span.kind"] || "";
            const hasChildren = span.children && span.children.length > 0;
            
            // Calculate position and width as percentage
            const relStart = ((span.start - traceStart) / traceDuration) * 100;
            const relWidth = ((span.end - span.start) / traceDuration) * 100;
            
            spans.push({
                id: span.id,
                name: span.name,
                kind: kind,
                duration_ms: span.duration_ms,
                depth: depth,
                hasChildren: hasChildren,
                attrs: span.attrs,
                events: span.events,
                start: relStart,
                width: relWidth,
                status: span.status
            });
            
            if (hasChildren) {
                for (const child of span.children) {
                    spans.push(...flattenSpans(child, depth + 1, traceStart, traceDuration));
                }
            }
            
            return spans;
        }
        
        function toggleSpan(spanId) {
            if (expandedSpans.has(spanId)) {
                expandedSpans.delete(spanId);
            } else {
                expandedSpans.add(spanId);
            }
            renderCurrentTrace();
        }
        
        function selectSpan(spanId, span) {
            selectedSpan = selectedSpan === spanId ? null : spanId;
            
            // Update all details
            document.querySelectorAll('.span-details').forEach(el => {
                el.classList.remove('open');
            });
            
            if (selectedSpan) {
                document.getElementById('details-' + spanId)?.classList.add('open');
            }
        }
        
        let currentTrace = null;
        
        function renderCurrentTrace() {
            if (!currentTrace) return;
            
            const t = currentTrace;
            const allSpans = t.tree.flatMap(root => flattenSpans(root, 0, t.start, t.end - t.start));
            
            // Build parent map
            const parentMap = new Map();
            const spanMap = new Map();
            allSpans.forEach(s => {
                spanMap.set(s.id, s);
                t.tree.forEach(root => {
                    function buildMap(span, parent = null) {
                        if (parent) parentMap.set(span.id, parent.id);
                        if (span.children) {
                            span.children.forEach(child => buildMap(child, span));
                        }
                    }
                    buildMap(root);
                });
            });
            
            let html = '';
            
            allSpans.forEach((s, idx) => {
                const parentId = parentMap.get(s.id);
                const isHidden = parentId && !expandedSpans.has(parentId);
                const isExpanded = expandedSpans.has(s.id);
                const expandIcon = s.hasChildren ? (isExpanded ? '▼' : '▶') : '';
                const indent = '  '.repeat(s.depth);
                const kindClass = s.kind ? `kind-${s.kind}` : '';
                const barClass = s.kind ? `bar-${s.kind}` : 'bar-default';
                const hasError = s.status !== 0 && s.status !== 1;
                
                const ioKeys = ["input.value", "output.value", "llm.input_messages", "llm.output_messages", 
                               "llm.prompts", "retrieval.documents"];
                const ioHtml = ioKeys
                    .filter(k => s.attrs[k])
                    .map(k => {
                        const val = s.attrs[k];
                        const display = typeof val === 'string' ? val : JSON.stringify(val, null, 2);
                        return `<div class="detail-section"><div class="detail-label">${k}</div><pre>${esc(display)}</pre></div>`;
                    })
                    .join('');
                
                html += `
                    <div class="span-row ${isHidden ? 'hidden' : ''}" data-span-id="${s.id}">
                        <div class="span-info">
                            <span class="span-expand ${s.hasChildren ? '' : 'empty'}" onclick="toggleSpan('${s.id}')">${expandIcon}</span>
                            <span class="span-indent">${indent}</span>
                            <span class="span-name" title="${esc(s.name)}">${esc(s.name)}</span>
                            ${s.kind ? `<span class="span-kind ${kindClass}">${esc(s.kind)}</span>` : ''}
                        </div>
                        <div class="span-timeline">
                            <div class="span-bar-container" style="left: ${s.start}%; width: ${s.width}%;" onclick="selectSpan('${s.id}', ${idx})">
                                <div class="span-bar ${barClass}">
                                    ${s.duration_ms.toFixed(1)}ms
                                </div>
                            </div>
                        </div>
                        <div class="span-duration">${s.duration_ms.toFixed(1)}ms</div>
                    </div>
                    <div id="details-${s.id}" class="span-details">
                        ${ioHtml}
                        ${s.events && s.events.length ? `
                            <div class="detail-section">
                                <div class="detail-label">Events (${s.events.length})</div>
                                <pre>${esc(JSON.stringify(s.events, null, 2))}</pre>
                            </div>
                        ` : ''}
                        <div class="detail-section">
                            <div class="detail-label">All Attributes (${Object.keys(s.attrs).length})</div>
                            <pre>${esc(JSON.stringify(s.attrs, null, 2))}</pre>
                        </div>
                    </div>
                `;
            });
            
            const time = new Date(t.start / 1e6).toLocaleString();
            document.getElementById('detail').innerHTML = `
                <div class="trace-header">
                    <h3>${esc(t.service)}</h3>
                    <div class="trace-meta">
                        <span style="font-family: monospace; color: #999;">${t.trace_id}</span>
                        <span style="margin: 0 8px;">•</span>
                        Started: ${time}
                        <span style="margin: 0 8px;">•</span>
                        Duration: ${t.duration_ms.toFixed(1)}ms
                        <span style="margin: 0 8px;">•</span>
                        ${allSpans.length} spans
                    </div>
                </div>
                <div class="timeline">
                    ${html}
                </div>
            `;
        }
        
        async function loadTrace(id) {
            currentTraceId = id;
            expandedSpans.clear();
            selectedSpan = null;
            
            const r = await fetch('/api/traces/' + id);
            currentTrace = await r.json();
            
            // Auto-expand root spans
            currentTrace.tree.forEach(root => {
                expandedSpans.add(root.id);
            });
            
            renderCurrentTrace();
            loadList();
        }
        
        async function clearTraces() {
            if (!confirm('Clear all traces?')) return;
            await fetch('/api/reset', { method: 'POST' });
            currentTraceId = null;
            currentTrace = null;
            document.getElementById('detail').innerHTML = '<div class="empty">← Select a trace to view details</div>';
            refresh();
        }
        
        async function refresh() {
            await loadStats();
            await loadList();
        }
        
        refresh();
        setInterval(refresh, 3000);
    </script>
</body>
</html>"""


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=4318)

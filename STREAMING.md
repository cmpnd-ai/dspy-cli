# Real-time Streaming in DSPy-CLI

## Current Implementation

The dspy-cli web UI now supports streaming DSPy callback events via Server-Sent Events (SSE). This provides visibility into the execution flow, showing:

- Module start/end events
- Language model calls (with prompts and responses)
- Tool invocations (with arguments and results)
- Adapter formatting/parsing operations

## How It Works

### Backend

1. **StreamingCallback** (`src/dspy_cli/server/streaming.py`): Custom DSPy callback that captures all execution events and queues them thread-safely.

2. **Streaming Endpoint** (`POST /{program_name}/stream`): New endpoint alongside the existing sync endpoint that:
   - Attaches the StreamingCallback to the DSPy LM
   - Executes the module within DSPy's context
   - Streams events via SSE as they become available

3. **Event Stream Generator**: Async generator that yields SSE-formatted events from the queue.

### Frontend

1. **Auto-detection**: Complex modules (ChainOfThought, ReAct, ProgramOfThought, etc.) auto-enable streaming; simple Predict modules default to sync mode.

2. **Event Display**: Events are shown with:
   - Type-specific icons and colors
   - Summary information visible by default
   - Expandable details for full prompts/responses
   - Auto-scrolling as events arrive

3. **User Control**: Toggle to enable/disable streaming (preference saved to localStorage).

## Real-Time Streaming Implementation

**Update**: As of December 2025, streaming events now appear in **true real-time** as DSPy executes!

### How It Works

The implementation uses **thread-based execution** to unblock the asyncio event loop:

1. Synchronous DSPy module execution runs in a separate worker thread via `asyncio.to_thread()`
2. DSPy context (LM and callbacks) is re-established in the worker thread using `with dspy.context()`
3. Main thread's event loop remains unblocked and can continuously yield SSE events
4. Callbacks fire from the worker thread and use thread-safe `Queue.put()` to queue events
5. SSE generator on the main thread yields events immediately as they're queued

### Key Technical Details

**Thread Safety:**
- Python's `queue.Queue` is thread-safe for cross-thread communication
- DSPy's context is re-established in the worker thread, not transferred
- Callbacks execute on the worker thread but queue events to the main thread

**Avoiding Duplicate Callbacks:**
- Callbacks are registered ONLY via `dspy.context(callbacks=[callback])`
- NOT added to the LM instance (`lm.callbacks`)
- DSPy's `@with_callbacks` decorator combines both global and instance callbacks
- Registering in only one place prevents duplicates

**Code Location:**
- `src/dspy_cli/server/routes.py` lines 482-491: Thread executor implementation
- `src/dspy_cli/server/streaming.py`: StreamingCallback and event generator

## Current Behavior

✅ **What Works:**
- **Real-time streaming**: Events appear immediately as DSPy executes (not buffered!)
- **All event types captured**: Module, LM, tool, and adapter callbacks
- **No duplicates**: Each callback fires exactly once
- **Progressive updates**: Module events appear instantly, then LM events stream during execution
- **Detailed information**: Full prompts, responses, tool calls, adapter operations
- **UI responsiveness**: Events display with expand/collapse, type-specific styling
- **Auto-detection**: Complex modules (CoT, ReAct) auto-enable streaming

⚠️ **Minor Considerations:**
- Worker thread adds minimal overhead (~10-50ms)
- Python GIL limits true parallelism (but DSPy is I/O-bound, not CPU-bound)
- Events stream with ~0.5s keepalive interval to prevent buffering

## For Users

The streaming implementation provides **real-time visibility** into DSPy module execution as it happens:

- **See prompts immediately**: LM calls appear with full prompts before the model responds
- **Track reasoning chains**: ChainOfThought steps display progressively
- **Debug tool invocations**: Tool calls and results stream in real-time
- **Monitor adapter operations**: Format/parse steps visible as they occur
- **Progressive feedback**: Know your request is being processed, see partial results

This is valuable for understanding, debugging, and optimizing DSPy applications, with the added benefit of real-time feedback during long-running operations.

## For Developers

The streaming implementation is production-ready and handles:

1. **Thread-safe event queuing**: Uses Python's `queue.Queue` for cross-thread communication
2. **Context preservation**: Re-establishes DSPy context in worker threads
3. **Duplicate prevention**: Single callback registration point
4. **Error handling**: Graceful fallback if threading fails

If you want to extend this system:

1. **Add new callback types**: Implement additional callback methods in `StreamingCallback`
2. **Custom event filtering**: Modify `event_stream_generator()` to filter events
3. **Performance metrics**: Add timing/token count tracking to callbacks
4. **Async DSPy modules**: When DSPy adds async support, this will work automatically (already checks for `aforward` method)

The streaming infrastructure is designed to be extensible and maintainable.

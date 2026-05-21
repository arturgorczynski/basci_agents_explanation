(function () {
    "use strict";

    const escapeHtml = (value) => String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");

    const chapters = [
        { id: "open", label: "Start", firstSlide: 0 },
        { id: "concepts", label: "Concepts", firstSlide: 1 },
        { id: "runtime", label: "Runtime", firstSlide: 4 },
        { id: "execution", label: "Execution", firstSlide: 14 },
        { id: "memory", label: "Memory", firstSlide: 15 },
        { id: "ship", label: "Ship", firstSlide: 19 },
    ];

    const agents = [
        {
            id: "manager",
            label: "manager",
            title: "Coordinator",
            role: "Plans one next move, delegates to specialists, asks clarifying questions, and synthesizes the final answer.",
            tools: "No direct tools. Its capability is controlled delegation.",
            sample: "{\"type\":\"delegate\",\"agent\":\"data_manager\",\"instruction\":\"Find the address in document A.\"}",
        },
        {
            id: "data_manager",
            label: "data_manager",
            title: "Knowledge Retrieval",
            role: "Queries local document vectors and can fetch configured news results.",
            tools: "query_documents_vector_db, check_news",
            sample: "Retrieved chunk: document A mentions Staszica 4/3, Krakow, Poland.",
        },
        {
            id: "secretary",
            label: "secretary",
            title: "File Specialist",
            role: "Locates, reads, parses, and writes allowed local files when exact source evidence matters.",
            tools: "check_if_file_exists, search_files, read_text, read_json, csv_reader, text_writer",
            sample: "Read the source file and returned the exact address excerpt.",
        },
        {
            id: "api",
            label: "api",
            title: "External Services",
            role: "Calls configured APIs for geolocation, weather, and web search.",
            tools: "address_to_geolocation, get_weather_forecast, search_internet",
            sample: "address_to_geolocation -> lat 50.07064, lon 19.93312",
        },
        {
            id: "pythondeveloper",
            label: "pythondeveloper",
            title: "Computation",
            role: "Writes and runs scoped Python scripts inside the project output folder.",
            tools: "write_python_code, run_python_script, list_installed_packages",
            sample: "distance.py -> approx 1.05 km from the given lat/lng.",
        },
    ];

    const conceptTiles = [
        {
            id: "model",
            label: "Model",
            short: "Predicts the next token from the context it receives.",
            detail: "The model does not decide what is allowed to happen in the app. It only returns text, sometimes plain prose and sometimes structured JSON.",
        },
        {
            id: "instructions",
            label: "Instructions",
            short: "Tell the model what role and output shape to follow.",
            detail: "System prompts, task prompts, examples, and JSON contracts constrain the answer before the runtime trusts it.",
        },
        {
            id: "tools",
            label: "Tools",
            short: "Expose real application actions through a controlled menu.",
            detail: "Tools are normal functions owned by the app. They can read files, search documents, call APIs, calculate, or write scoped outputs.",
        },
        {
            id: "memory",
            label: "Memory",
            short: "Stores evidence so later decisions do not start from zero.",
            detail: "Memory is application state: user requests, manager decisions, worker reports, tool observations, summaries, and final answers.",
        },
    ];

    const executionSteps = [
        {
            actor: "manager",
            graphNode: "request",
            paths: [0],
            title: "User Request Enters Runtime",
            text: "The user asks for a concrete result: find the address in document A, geocode it, calculate distance from a starting point, and answer with evidence. The request is the first piece of state the runtime records.",
            event: "planner_action",
            detail: "User request: document A address + geocode + distance + sourced answer",
            snippet: "managerLoop",
            json: {
                user_request: "Based on document A, find the site address, geocode it, and calculate the distance from 50.0647, 19.9450.",
                runtime_records: "user_request",
                next_owner: "manager",
            },
        },
        {
            actor: "manager",
            graphNode: "manager",
            paths: [1],
            title: "Manager Chooses the First Move",
            text: "The manager sees the request, the current memory, and the available agent names. It does not call tools directly; it chooses the next structured action for the runtime.",
            event: "agent_registry",
            detail: "{\"type\":\"delegate\",\"agent\":\"data_manager\",\"instruction\":\"Find the site address in document A.\"}",
            snippet: "cast",
            json: {
                role: "manager",
                sees: ["user request", "available agents", "current memory"],
                decision: "delegate",
                selected_agent: "data_manager",
                reason: "document evidence is needed first",
            },
        },
        {
            actor: "manager",
            graphNode: "registry",
            paths: [2],
            title: "Runtime Resolves Agent Name",
            text: "Delegation only works if the requested worker exists in the registry. The string data_manager is resolved into the actual worker object and its tool access.",
            event: "agent_registry",
            detail: "registry -> data_manager, api, pythondeveloper",
            snippet: "cast",
            json: {
                registry: ["manager", "data_manager", "secretary", "api", "pythondeveloper"],
                requested_agent: "data_manager",
                resolved: true,
            },
        },
        {
            actor: "data_manager",
            graphNode: "data_manager",
            toolNode: "docs_tool",
            paths: [5],
            title: "Manager Delegates Document Search",
            text: "The data manager receives one narrow assignment: search document memory for the site address. It does not need geocoding or Python tools.",
            event: "worker_assignment",
            detail: "query_documents_vector_db -> matching chunks",
            snippet: "workerAction",
            json: {
                type: "tool",
                agent: "data_manager",
                tool: "query_documents_vector_db",
                args: { query: "site address in document A" },
            },
        },
        {
            actor: "data_manager",
            graphNodes: ["docs_tool", "data_manager", "registry", "manager"],
            paths: [5, 2, 1],
            title: "Worker Returns Evidence",
            text: "The worker reports what it found in a done payload. The manager receives usable evidence instead of every internal search detail.",
            event: "worker_done",
            detail: "address excerpt -> Staszica 4/3, Krakow, Poland",
            snippet: "workerLoop",
            json: {
                type: "done",
                agent: "data_manager",
                request_results: "Document A contains Staszica 4/3, Krakow, Poland.",
                raw_data: { source: "document A" },
            },
        },
        {
            actor: "api",
            graphNode: "api",
            toolNode: "api_tool",
            paths: [3, 6],
            title: "Manager Delegates Geocoding",
            text: "With an address in hand, the manager asks the API worker for coordinates. The JSON names the tool and passes arguments the runtime can validate.",
            event: "tool_result",
            detail: "address_to_geolocation -> 50.07064, 19.93312",
            snippet: "dispatch",
            json: {
                type: "tool",
                agent: "api",
                tool: "address_to_geolocation",
                args: { address: "Staszica 4/3, Krakow, Poland" },
            },
        },
        {
            actor: "pythondeveloper",
            graphNode: "pythondeveloper",
            toolNode: "python_tool",
            paths: [4, 7],
            title: "Manager Delegates Calculation",
            text: "The Python worker gets the coordinates and the user's starting point. It writes or runs scoped code and returns the distance result.",
            event: "tool_result",
            detail: "run_python_script -> approx 1.05 km",
            snippet: "toolResult",
            json: {
                type: "tool",
                agent: "pythondeveloper",
                tool: "run_python_script",
                result: { success: true, summary: "approx 1.05 km" },
            },
        },
        {
            actor: "manager",
            graphNodes: ["manager", "answer"],
            paths: [8],
            title: "Manager Produces Answer",
            text: "The manager now has enough evidence: address, coordinates, distance, and source. It stops delegating and returns a user-facing answer.",
            event: "final_answer",
            detail: "answer_user -> sourced answer",
            snippet: "plannerContext",
            json: {
                type: "answer_user",
                includes: ["address", "coordinates", "distance", "source"],
                confidence: "based on retrieved document and tool outputs",
            },
        },
    ];

    const snippets = {
        cast: {
            file: "src/agentic_system/runtime/orchestrator.py:500",
            title: "Agents Creation",
            code: `manager = agents.CommandCentre("manager", [], ...)
python_developer = agents.Agent("pythondeveloper", ["programer"], ...)
secretary = agents.Agent("secretary", ["file_handler"], ...)
data_manager_agent = agents.Agent("data_manager", ["data_manager"], ...)
api_agent = agents.Agent("api", ["apis"], ...)

agents_registry = {
    manager.name: manager,
    python_developer.name: python_developer,
    secretary.name: secretary,
    data_manager_agent.name: data_manager_agent,
    api_agent.name: api_agent,
}`,
            points: [
                ["Manager", "The manager is instantiated first with an empty tool-module list. It cannot directly read files, call APIs, or run Python; its job is to decide which specialist should act next and what instruction that specialist should receive."],
                ["Workers", "Each worker is created with a narrow module list. The Python developer receives programming tools, the API worker receives API tools, and the data manager receives retrieval tools, so capability boundaries stay visible."],
                ["Registry", "The registry is the routing table. When the manager returns a JSON action like delegate to data_manager, the runtime looks up that exact name here before a worker loop can start."],
                ["How it runs", "This construction happens once when the default runtime starts. After that, every delegation is a lookup against these same objects, so changing a name or module list changes what the manager can route."],
            ],
        },
        modelJson: {
            file: "src/agentic_system/agents_training_facility/agents.py:241",
            title: "JSON Based Communication",
            code: `if return_json:
    messages.append({
        "role": "system",
        "content": (
            "Return exactly one valid JSON object. "
            "Do not include markdown fences."
        ),
    })`,
            points: [
                ["JSON mode", "return_json tells the call site it needs a decision the application can parse, not a paragraph for a human. The model still emits text, but the runtime expects that text to be one JSON object."],
                ["Extra instruction", "The extra system message is appended right before the model call. It tightens the output contract at the point where format matters most: no markdown fence, no explanation, no second object."],
                ["Validation target", "The parser now has one clear target. If the model returns invalid JSON, the runtime can treat that as a recoverable formatting failure instead of executing an ambiguous instruction."],
                ["How it runs", "This is the bridge between probabilistic text and deterministic control flow. The model proposes a structured object; the runtime parses and validates it before choosing a branch."],
            ],
        },
        managerAction: {
            file: "src/agentic_system/prompts/prompts.py:57",
            title: "Manager Decisions",
            code: `{"type":"answer_user","answer":"..."}
{"type":"ask_user","question":"..."}
{"type":"delegate","agent":"api","instruction":"..."}
{"type":"finish","reason":"..."}`,
            points: [
                ["Answer", "answer_user is the terminal path for a successful request. The manager should use it only after the execution history contains enough evidence to produce the final response."],
                ["Ask", "ask_user is the pause path. Instead of fabricating missing inputs, the manager can return a question and the UI can wait for the user before continuing the same request."],
                ["Delegate", "delegate is the work-routing path. The manager must name a real worker and give it a bounded instruction, so the worker receives a specific task rather than the whole vague user problem."],
                ["Finish", "finish is a controlled stop signal. It lets the runtime end cleanly when continuing would be useless, unsafe, or impossible, without pretending that a complete answer exists."],
                ["How it runs", "The manager is selecting one allowed action type. The orchestrator then branches on that type in normal application code."],
            ],
        },
        workerAction: {
            file: "src/agentic_system/prompts/prompts.py:1",
            title: "Worker Decisions",
            code: `{"type":"tool","tool":"address_to_geolocation","args":{...}}
{"type":"done","request_results":"...","raw_data":{...}}`,
            points: [
                ["Tool", "A tool action means the worker is asking the runtime to call one named function with explicit arguments. The name must exist in that worker's toolbox or execution returns a structured failure."],
                ["Done", "done means the worker believes the assignment has enough evidence. The worker stops its private loop and hands a compact report back to the manager."],
                ["Raw data", "raw_data preserves structured payloads such as coordinates, file excerpts, search hits, or calculation outputs. The manager can use those facts without relying only on prose summaries."],
                ["How it runs", "A worker loop is a small ReAct cycle: choose one tool, observe the result, update context, and either call another tool or return done to the manager."],
            ],
        },
        managerLoop: {
            file: "src/agentic_system/runtime/orchestrator.py:401",
            title: "Manager Loop",
            code: `for count in range(1, self.max_iterations + 1):
    planner_action = self.manager.plan_next_step(
        user_request=user_request,
        planner_context=planner_context,
    )

    if planner_action["type"] == "delegate":
        self._run_worker_assignment(...)`,
            points: [
                ["Budget", "max_iterations is the outer safety rail. Every pass through this loop spends one manager decision, so the runtime has a hard limit if the manager keeps delegating or failing to converge."],
                ["Context", "planner_context is the selected memory rendered for the manager. It usually contains the user request, visible prior events, worker reports, and the latest tool evidence."],
                ["Action", "plan_next_step asks the manager model for a JSON decision. The next line of application code expects an object with a type field, not a paragraph explaining what the manager might do."],
                ["Branch", "After parsing, ordinary if statements decide the real behavior. delegate starts a worker assignment, answer_user returns to the UI, ask_user pauses for clarification, and finish stops."],
                ["How it runs", "This is the top-level runtime rhythm: render context, get one manager decision, execute one branch, record what happened, then repeat only if more work is needed."],
            ],
        },
        workerLoop: {
            file: "src/agentic_system/runtime/orchestrator.py:276",
            title: "Worker Loop",
            code: `for worker_step in range(1, self.max_worker_steps + 1):
    worker_action = active_agent.choose_tool(...)

    if worker_action["type"] == "done":
        return worker_action

    tool_result = active_agent.execute_tool(worker_action)`,
            points: [
                ["Worker budget", "max_worker_steps limits each specialist separately from the manager. A worker cannot keep searching, coding, or retrying forever inside one delegated assignment."],
                ["Choose", "choose_tool sends the worker its assignment plus recent observations. The worker returns JSON saying either which tool to call next or that the assignment is done."],
                ["Stop point", "When the worker returns done, the loop exits immediately. That done payload becomes the clean handoff back to the manager."],
                ["Execute", "Only tool actions reach execute_tool. This keeps the execution boundary obvious: model text becomes a real function call only after the runtime recognizes the action type."],
                ["How it runs", "The worker gathers evidence in small steps, records observations, and stops as soon as it can report useful results for the manager's broader plan."],
            ],
        },
        dispatch: {
            file: "src/agentic_system/agents_training_facility/agents.py:342",
            title: "Tool Dispatch",
            code: `tool_choice = agent_response_dict.get("tool")
tool_input = agent_response_dict.get("args", {})
tool_spec = self.toolbox.get(tool_choice)

if tool_spec is None:
    return ToolResult.failure(...)

response = tool_spec.func(**tool_input)`,
            points: [
                ["Tool name", "tool_choice is just a string produced by the model. Nothing has executed yet, and the worker cannot escape the list of tools registered in its toolbox."],
                ["Arguments", "tool_input comes from the JSON args object. The runtime passes it as keyword arguments, so the function boundary is explicit and inspectable."],
                ["Lookup", "self.toolbox.get(tool_choice) is the authorization point for this worker. If the tool was not registered for this agent, the lookup fails before any external action happens."],
                ["Failure", "Unknown tools and exceptions are wrapped as ToolResult failures. That means the failure becomes evidence the manager can see, rather than an uncontrolled crash."],
                ["How it runs", "Dispatch is where structured model output becomes real work: parse the tool name, validate access, call the Python function, then package the result."],
            ],
        },
        toolResult: {
            file: "src/agentic_system/runtime/contracts.py:14",
            title: "Result Envelope",
            code: `@dataclass(frozen=True)
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None
    summary: str = ""`,
            points: [
                ["Success flag", "success is the first branch point for callers. The runtime can tell whether the tool worked without scraping natural-language text."],
                ["Data", "data carries machine-usable payloads: coordinates, file content, retrieved chunks, search hits, calculation outputs, or any object that later code can inspect."],
                ["Error", "error gives failures a normal place in the contract. A failed API call or missing file can be recorded and shown without changing the surrounding loop shape."],
                ["Summary", "summary is optimized for humans and future prompt context. It gives the manager a compact description while data keeps the structured details available."],
                ["How it runs", "Because every tool uses the same envelope, the UI, memory layer, worker loop, and manager context renderer can handle results consistently."],
            ],
        },
        history: {
            file: "src/agentic_system/memory/conversation_history.py:9",
            title: "ConversationHistory Stores Events",
            code: `class ConversationHistory:
    def __init__(self, max_completed_requests: int = 5):
        self.completed_requests = []
        self.active_request = None
        self.history_summary = ""

    def record_event(self, event: dict[str, Any]) -> None:
        self.active_request["steps"].append(event)`,
            points: [
                ["State object", "ConversationHistory is ordinary application state. It is not model memory and it does not change the model weights; it stores records the runtime can later render into prompts."],
                ["Active request", "active_request is the live container for the current user task. As the manager delegates and workers return results, each event is attached to this same request record."],
                ["Append", "record_event appends events in order. That ordering matters because later context can show the manager what happened before the current decision."],
                ["How it runs", "Memory becomes useful only when the runtime selects records from this object and includes them in the next model call as readable context."],
            ],
        },
        visibleEvents: {
            file: "src/agentic_system/memory/conversation_history.py:61",
            title: "Manager Visible Events",
            code: `_MANAGER_VISIBLE_EVENTS = frozenset({
    "user_request",
    "planner_action",
    "manager_answer",
    "manager_question",
    "worker_done",
    "final_answer",
})`,
            points: [
                ["Filter list", "_MANAGER_VISIBLE_EVENTS is a deliberate noise filter. The runtime may record many internal events, but the manager only needs the ones that help it choose the next action."],
                ["Worker done", "worker_done is visible because it is the specialist handoff. It should contain the distilled evidence the manager needs, not every low-level tool detail."],
                ["Final answer", "final_answer is visible so completed work can become part of the request record and later summaries. This helps the system remember what it already told the user."],
                ["How it runs", "Filtering is context engineering in code. If a future manager decision seems blind, this set is one of the first places to inspect."],
            ],
        },
        plannerContext: {
            file: "src/agentic_system/memory/conversation_history.py:89",
            title: "Render Planner Context",
            code: `if self.history_summary.strip():
    sections.append("Summary of earlier conversation:")
    sections.append(self.history_summary.strip())

sections.append("Current request:")
sections.append(self._format_request(self.active_request))`,
            points: [
                ["Summary", "history_summary is where older conversation can be compressed before it reaches the model again. That keeps long sessions from dumping every raw event back into context."],
                ["Current request", "The current request is rendered as its own section so the manager can separate the live task from older background information."],
                ["Formatting", "The runtime decides the exact text layout of memory records. That formatting influences what the manager notices, ignores, or misunderstands."],
                ["How it runs", "Stored memory does nothing by itself. It affects behavior only after the app selects records, formats them, and sends them as context in a model call."],
            ],
        },
        pathPolicy: {
            file: "src/agentic_system/tools/path_policy.py:8",
            title: "Path Policy",
            code: `DATA_ROOT = (AGENTIC_ROOT / "data").resolve()
CODING_OUTPUT_ROOT = (AGENTIC_ROOT / "coding_output").resolve()
PYTHONDEVELOPER_CODE_ROOT = (
    CODING_OUTPUT_ROOT / "pythondeveloper_code"
).resolve()

READ_ROOTS = (DATA_ROOT, CODING_OUTPUT_ROOT)
WRITE_ROOTS = (CODING_OUTPUT_ROOT,)`,
            points: [
                ["Data root", "The constants define the project areas the tools are expected to touch. Paths are resolved to absolute locations before the runtime decides whether access is allowed."],
                ["Output root", "Generated files go into a controlled output directory. That keeps tool-created artifacts separate from hand-written source and input data."],
                ["Write roots", "Write permission is narrower than read permission. A tool may inspect allowed input data while still being blocked from modifying arbitrary project files."],
                ["How it runs", "Path-sensitive tools call this policy before reading, writing, or executing. Denied access should become a clear ToolResult failure rather than a silent side effect."],
            ],
        },
    };

    function codeBlock(snippetId, active) {
        const snippet = snippets[snippetId];
        const isActive = active ? " active-snippet" : "";
        return `
            <figure class="code-card${isActive}" data-snippet-card="${snippetId}">
                <figcaption>
                    <span>${snippet.title}</span>
                    <code>${snippet.file}</code>
                </figcaption>
                <pre><code>${escapeHtml(snippet.code)}</code></pre>
            </figure>
        `;
    }

    function codePointRail(snippetId) {
        const snippet = snippets[snippetId];
        return `
            <div class="code-points" data-code-points>
                <div class="point-rail" role="tablist" aria-label="${snippet.title} code explanation points">
                    ${snippet.points.map((point, index) => `
                        <button class="point-dot${index === 0 ? " active" : ""}" type="button" data-point="${index}" aria-label="${point[0]}"></button>
                    `).join("")}
                </div>
                <div class="point-copy">
                    ${snippet.points.map((point, index) => `
                        <section class="point-panel${index === 0 ? " active" : ""}" data-point-panel="${index}">
                            <strong>${point[0]}</strong>
                            <p>${point[1]}</p>
                        </section>
                    `).join("")}
                </div>
            </div>
        `;
    }

    function codeGuide(config) {
        const snippet = snippets[config.snippet];
        return `
            <article class="slide code-guide-slide">
                <div class="guide-copy">
                    <div class="eyebrow">${config.kicker}</div>
                    <h2>${config.title}</h2>
                    <p>${config.body}</p>
                    <div class="guide-section">
                        <span class="card-kicker">Concept support</span>
                        ${config.concept.map((item) => `<div class="notice-item">${item}</div>`).join("")}
                    </div>
                    <div class="guide-section">
                        <span class="card-kicker">What to notice in code</span>
                        ${config.codeNotes.map((item) => `<div class="notice-item">${item}</div>`).join("")}
                    </div>
                </div>
                <div class="guide-code">
                    <span class="card-kicker">${snippet.file}</span>
                    ${codeBlock(config.snippet, true)}
                    <span class="card-kicker">Detailed code walkthrough</span>
                    ${codePointRail(config.snippet)}
                </div>
            </article>
        `;
    }

    function orbitalHero() {
        return `
            <div class="orbital" aria-hidden="true">
                <div class="ring one"></div>
                <div class="ring two"></div>
                <div class="ring three"></div>
                <div class="core-orb">Agentic Runtime</div>
                <div class="orbit-node node-model">Model</div>
                <div class="orbit-node node-tools">Tools</div>
                <div class="orbit-node node-memory">Memory</div>
                <div class="orbit-node node-events">Events</div>
            </div>
        `;
    }

    function conceptSystem() {
        return `
            <div class="agent-concept-map">
                <div class="concept-stack">
                    ${conceptTiles.map((tile) => `
                        <button class="concept-tile ${tile.id}" type="button">
                            <span class="card-kicker">${tile.label}</span>
                            <strong>${tile.short}</strong>
                            <span class="tile-detail">${tile.detail}</span>
                        </button>
                    `).join("")}
                </div>
                <svg class="concept-arrows" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                    <defs>
                        <marker id="conceptArrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                            <path d="M 0 0 L 6 3 L 0 6 z" fill="#67e8f9" />
                        </marker>
                        <linearGradient id="conceptStroke" x1="0%" x2="100%">
                            <stop offset="0%" stop-color="rgba(167, 139, 250, 0.15)" />
                            <stop offset="100%" stop-color="rgba(103, 232, 249, 0.85)" />
                        </linearGradient>
                    </defs>
                    <path d="M 6 14 Q 55 26, 92 50" />
                    <path d="M 6 38 Q 55 42, 92 50" />
                    <path d="M 6 62 Q 55 58, 92 50" />
                    <path d="M 6 86 Q 55 74, 92 50" />
                </svg>
                <button class="concept-agent" type="button">
                    <span class="card-kicker">Runtime wrapper</span>
                    <strong>Agent</strong>
                    <small>The app wraps a model with instructions, allowed tools, selected memory, validation, and loop control.</small>
                    <span class="tile-detail">The model proposes text. The runtime decides whether that text becomes an answer, a tool call, a delegation, or a stop.</span>
                </button>
            </div>
        `;
    }

    function reactLoop() {
        const steps = [
            ["01", "Reason", "Model reads context and chooses what should happen next."],
            ["02", "Act", "Runtime performs one validated action: tool, delegate, ask, answer, or stop."],
            ["03", "Observe", "Result returns as evidence: data, error, summary, or worker report."],
            ["04", "Repeat", "Next model call sees updated evidence and chooses the next move."],
        ];
        return `
            <div class="react-flow" aria-label="ReAct loop">
                <div class="react-track">
                    ${steps.map(([num, title, body], index) => `
                        <div class="react-node">
                            <span class="react-num">${num}</span>
                            <h3>${title}</h3>
                            <p>${body}</p>
                        </div>
                        ${index < steps.length - 1 ? `<div class="react-arrow" aria-hidden="true"></div>` : ""}
                    `).join("")}
                </div>
                <div class="react-feedback" aria-hidden="true">
                    <svg viewBox="0 0 600 70" preserveAspectRatio="none">
                        <defs>
                            <marker id="reactArrowMarker" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                                <path d="M 0 0 L 6 3 L 0 6 z" fill="#67e8f9" />
                            </marker>
                        </defs>
                        <path d="M 580 5 C 580 60, 460 65, 300 65 C 140 65, 20 60, 20 12" marker-end="url(#reactArrowMarker)" />
                    </svg>
                    <span>feedback: each observation becomes the next reason</span>
                </div>
            </div>
        `;
    }

    function runtimeArchitecture() {
        return `
            <div class="arch-diagram" aria-label="Runtime architecture diagram">
                <svg viewBox="0 0 720 510" preserveAspectRatio="xMidYMid meet">
                    <defs>
                        <marker id="archArrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                            <path d="M 0 0 L 6 3 L 0 6 z" fill="#67e8f9" />
                        </marker>
                        <marker id="archArrowBack" markerWidth="6" markerHeight="6" refX="1" refY="3" orient="auto">
                            <path d="M 6 0 L 0 3 L 6 6 z" fill="#67e8f9" />
                        </marker>
                    </defs>

                    <g class="arch-rail">
                        <text x="215" y="155" class="arch-rail-label">planning side</text>
                        <text x="505" y="155" class="arch-rail-label">execution side</text>
                    </g>

                    <path class="arch-link" d="M 360 54 V 84" marker-end="url(#archArrow)" />
                    <path class="arch-link" d="M 295 138 Q 255 156, 220 174" marker-end="url(#archArrow)" />
                    <path class="arch-link" d="M 425 138 Q 465 156, 500 174" marker-end="url(#archArrow)" />
                    <path class="arch-link" d="M 300 200 L 420 200" marker-end="url(#archArrow)" />
                    <path class="arch-link" d="M 420 218 L 300 218" marker-end="url(#archArrow)" />
                    <path class="arch-link" d="M 215 232 V 268" marker-end="url(#archArrow)" />
                    <path class="arch-link" d="M 505 232 V 268" marker-end="url(#archArrow)" />
                    <path class="arch-link" d="M 215 326 V 362" marker-end="url(#archArrow)" />
                    <path class="arch-link" d="M 505 326 V 362" marker-end="url(#archArrow)" />
                    <path class="arch-link arch-link-soft" d="M 300 393 L 420 393" marker-end="url(#archArrow)" marker-start="url(#archArrowBack)" />

                    <g class="arch-box arch-user">
                        <rect x="275" y="10" width="170" height="44" rx="11" />
                        <text x="360" y="30" class="arch-title">User</text>
                        <text x="360" y="44" class="arch-sub">asks for a concrete result</text>
                    </g>

                    <g class="arch-box arch-orch">
                        <rect x="215" y="84" width="290" height="54" rx="14" />
                        <text x="360" y="106" class="arch-title">Orchestrator</text>
                        <text x="360" y="124" class="arch-sub">manager loop · worker loop · budgets</text>
                    </g>

                    <g class="arch-box arch-manager">
                        <rect x="130" y="174" width="170" height="58" rx="13" />
                        <text x="215" y="197" class="arch-title">Manager</text>
                        <text x="215" y="215" class="arch-sub">plans one JSON action</text>
                    </g>

                    <g class="arch-box arch-workers">
                        <rect x="420" y="174" width="170" height="58" rx="13" />
                        <text x="505" y="197" class="arch-title">Workers (4)</text>
                        <text x="505" y="215" class="arch-sub">api · data · secretary · python</text>
                    </g>

                    <g class="arch-box arch-support">
                        <rect x="130" y="268" width="170" height="58" rx="13" />
                        <text x="215" y="291" class="arch-title">Registry</text>
                        <text x="215" y="309" class="arch-sub">name -&gt; agent lookup</text>
                    </g>

                    <g class="arch-box arch-support">
                        <rect x="420" y="268" width="170" height="58" rx="13" />
                        <text x="505" y="291" class="arch-title">Toolbox</text>
                        <text x="505" y="309" class="arch-sub">per-agent function menu</text>
                    </g>

                    <g class="arch-box arch-memory">
                        <rect x="130" y="362" width="170" height="58" rx="13" />
                        <text x="215" y="385" class="arch-title">History</text>
                        <text x="215" y="403" class="arch-sub">event log + rendered context</text>
                    </g>

                    <g class="arch-box arch-tools">
                        <rect x="420" y="362" width="170" height="58" rx="13" />
                        <text x="505" y="385" class="arch-title">Tools</text>
                        <text x="505" y="403" class="arch-sub">files · APIs · Python · search</text>
                    </g>

                    <g class="arch-legend">
                        <rect x="200" y="445" width="320" height="48" rx="10" />
                        <text x="360" y="468" class="arch-legend-title">Manager &lt;-&gt; Workers</text>
                        <text x="360" y="484" class="arch-legend-sub">delegate down, report back · every event logged into History</text>
                    </g>
                </svg>
            </div>
        `;
    }

    function buildingBlocks() {
        const blocks = [
            {
                tag: "loop",
                title: "Orchestrator",
                lead: "Runs the manager loop and starts worker loops.",
                detail: "Owns the iteration budgets, branches on planner action types, and records every event into history.",
                ref: "runtime/orchestrator.py",
            },
            {
                tag: "manager",
                title: "Manager",
                lead: "Plans one step at a time.",
                detail: "Sees only filtered events. Returns one JSON action: delegate, answer, ask, or finish.",
                ref: "prompts/prompts.py",
            },
            {
                tag: "worker",
                title: "Worker",
                lead: "Fulfills one bounded assignment.",
                detail: "Picks a tool, observes the result, and either calls another tool or returns done.",
                ref: "agents.py:think_in_session",
            },
            {
                tag: "registry",
                title: "Registry",
                lead: "Routes names to agent objects.",
                detail: "The manager produces a string; the runtime turns that string into a real worker before any worker code runs.",
                ref: "orchestrator.py:agents_registry",
            },
            {
                tag: "toolbox",
                title: "Toolbox",
                lead: "Per-agent function menu.",
                detail: "Each worker only sees its own scoped tools. The manager has no toolbox at all.",
                ref: "toolbox/toolbox.py",
            },
            {
                tag: "history",
                title: "ConversationHistory",
                lead: "Append-only event log.",
                detail: "Records user requests, planner actions, tool calls, worker reports, and final answers.",
                ref: "memory/conversation_history.py",
            },
            {
                tag: "result",
                title: "ToolResult",
                lead: "Uniform return envelope.",
                detail: "success + data + error + summary. Failures stay inside the loop as inspectable evidence.",
                ref: "runtime/contracts.py",
            },
            {
                tag: "policy",
                title: "Path policy",
                lead: "Read and write boundaries.",
                detail: "Tools resolve paths through one helper. Writes are scoped to coding_output only.",
                ref: "tools/path_policy.py",
            },
        ];
        return `
            <div class="block-grid">
                ${blocks.map((b) => `
                    <article class="block-card block-${b.tag}">
                        <div class="block-tag">${b.tag}</div>
                        <h3>${b.title}</h3>
                        <p class="block-lead">${b.lead}</p>
                        <p class="block-detail">${b.detail}</p>
                        <code class="block-ref">${b.ref}</code>
                    </article>
                `).join("")}
            </div>
        `;
    }

    const slides = [
        {
            chapter: "open",
            render: () => `
                <article class="slide hero-slide">
                    <div class="hero-copy">
                        <div class="eyebrow">Interactive code walkthrough</div>
                        <h1>Agents are runtime systems.</h1>
                        <p class="lede">A manager plans, workers act, tools return evidence, memory records the run, and context expands for the next decision.</p>
                        <p>This version is linear on purpose: first the idea, then the code that makes the idea real.</p>
                        <div class="hero-actions">
                            <button class="cta" data-jump="1">Start the path</button>
                            <button class="ghost-btn" data-jump="14">Jump to execution demo</button>
                        </div>
                    </div>
                    ${orbitalHero()}
                </article>
            `,
        },
        {
            chapter: "concepts",
            render: () => `
                <article class="slide two-col concept-slide">
                    <div class="stack">
                        <div class="eyebrow">Mental model</div>
                        <h2>An agent is a model inside a runtime.</h2>
                        <p class="big-quote">The model predicts text. The runtime turns selected text into controlled application behavior.</p>
                        <p>That wrapper is the important part: it chooses the prompt, validates JSON, exposes only allowed tools, stores observations, and decides when the loop should continue or stop.</p>
                    </div>
                    ${conceptSystem()}
                </article>
            `,
        },
        {
            chapter: "concepts",
            afterRender: "bindAgentCards",
            render: () => `
                <article class="slide">
                    <div>
                        <div class="eyebrow">Cast</div>
                        <h2>Five actors, one chain of custody.</h2>
                        <p>Click a card. The important lesson is capability design: each worker gets a smaller toolbox than the whole system.</p>
                    </div>
                    <div class="agent-grid">
                        ${agents.map((agent, index) => `
                            <button class="agent-card" data-agent-card aria-expanded="${index === 0 ? "true" : "false"}">
                                <span class="tag ${agent.id}">${agent.label}</span>
                                <h3>${agent.title}</h3>
                                <p>${agent.role}</p>
                                <div class="details">
                                    <div>
                                        <p><strong>Tools:</strong> ${agent.tools}</p>
                                        <p><strong>Example:</strong> ${agent.sample}</p>
                                    </div>
                                </div>
                            </button>
                        `).join("")}
                    </div>
                </article>
            `,
        },
        {
            chapter: "concepts",
            render: () => `
                <article class="slide two-col react-slide">
                    <div class="stack">
                        <div class="eyebrow">ReAct loop</div>
                        <h2>Reason. Act. Observe. Repeat.</h2>
                        <p>A one-shot prompt must answer with whatever is already in context. ReAct gives the app a way to gather missing evidence one controlled step at a time.</p>
                        <p>The model chooses what should happen next, but the runtime performs only one validated action. The observation is recorded, rendered into the next context, and the following decision is better informed.</p>
                        <div class="notice-item">The loop is powerful because every move can be inspected: what the model saw, what it chose, what ran, what came back, and why the loop continued or stopped.</div>
                    </div>
                    ${reactLoop()}
                </article>
            `,
        },
        {
            chapter: "runtime",
            render: () => `
                <article class="slide runtime-intro-slide">
                    <div class="stack">
                        <div class="eyebrow">Runtime overview</div>
                        <h2>How the code pieces work together.</h2>
                        <p>The user talks to one process. Inside it, the orchestrator hosts a manager and four workers, a registry to route between them, a toolbox per worker, a history that records every event, and a path policy that fences I/O.</p>
                        <p>Every arrow is a real function call. The next slides walk through each piece in code.</p>
                    </div>
                    ${runtimeArchitecture()}
                </article>
            `,
        },
        {
            chapter: "runtime",
            render: () => `
                <article class="slide runtime-blocks-slide">
                    <div class="stack">
                        <div class="eyebrow">Building blocks</div>
                        <h2>Eight small modules. One clear contract each.</h2>
                        <p>Before the line-by-line walkthrough, here is what each named thing actually does and where it lives.</p>
                    </div>
                    ${buildingBlocks()}
                </article>
            `,
        },
        {
            chapter: "runtime",
            render: () => codeGuide({
                kicker: "Runtime construction",
                title: "Agents Creation",
                body: "There is no hidden swarm. The default runtime constructs one manager and four specialist workers, then puts them in a registry.",
                snippet: "cast",
                concept: ["Agents are ordinary Python objects with names, roles, and tool access.", "The manager coordinates but starts with no direct tool modules.", "Workers receive only the capabilities needed for their specialty."],
                codeNotes: ["The worker names are the public routing surface: pythondeveloper, secretary, data_manager, api.", "The registry is the lookup table used whenever the manager delegates work.", "Changing agent names or module lists changes what the manager can successfully request."],
            }),
            afterRender: "bindCodeDots",
        },
        {
            chapter: "runtime",
            render: () => codeGuide({
                kicker: "Model call",
                title: "JSON Based Communication",
                body: "When the runtime needs a machine-readable decision, it asks the model for one valid JSON object and then validates it.",
                snippet: "modelJson",
                concept: ["The model still outputs text, but the runtime asks for text with a strict shape.", "JSON gives the app something it can parse before taking action.", "Bad format becomes a runtime problem that can be shown, retried, or handled."],
                codeNotes: ["return_json is the switch that adds extra formatting pressure.", "The system message forbids markdown fences because the parser expects a clean object.", "This pattern is used for manager and worker decisions."],
            }),
            afterRender: "bindCodeDots",
        },
        {
            chapter: "runtime",
            render: () => codeGuide({
                kicker: "Manager contract",
                title: "Manager Decisions",
                body: "The manager coordinates the request by choosing one action from a small menu: answer, ask, delegate, or finish.",
                snippet: "managerAction",
                concept: ["The manager is the only actor that talks to the user.", "Delegation creates a bounded worker assignment instead of giving everyone every tool.", "A small action menu keeps planning inspectable and teachable."],
                codeNotes: ["The JSON shape is part of the product interface between prompt and runtime.", "Each type maps to a specific branch in the manager loop.", "Better agent behavior often starts by making this action menu clearer."],
            }),
            afterRender: "bindCodeDots",
        },
        {
            chapter: "runtime",
            render: () => codeGuide({
                kicker: "Worker contract",
                title: "Worker Decisions",
                body: "Workers do not chat with the user. They fulfill one assignment by using tools or returning a done report.",
                snippet: "workerAction",
                concept: ["A worker owns a narrower problem than the manager.", "Tool calls gather evidence from files, APIs, search, or computation.", "Done is the handoff point where the manager receives usable results."],
                codeNotes: ["tool and args come from model-produced JSON.", "request_results is the summary the manager can reason over.", "raw_data keeps structured details available without making the explanation noisy."],
            }),
            afterRender: "bindCodeDots",
        },
        {
            chapter: "runtime",
            render: () => codeGuide({
                kicker: "Outer control loop",
                title: "Manager Loop",
                body: "The manager loop renders current context, asks the manager for one structured next step, validates the action, and branches.",
                snippet: "managerLoop",
                concept: ["This is the top-level ReAct controller for the whole system.", "The manager decides one move at a time instead of inventing a full hidden plan.", "Iteration limits protect the app from runaway planning."],
                codeNotes: ["planner_context is where memory and current evidence become model input.", "planner_action is the JSON decision returned by the model.", "delegate sends work into a worker loop and later resumes manager planning."],
            }),
            afterRender: "bindCodeDots",
        },
        {
            chapter: "runtime",
            render: () => codeGuide({
                kicker: "Worker control loop",
                title: "Worker Loop",
                body: "A worker can call tools repeatedly until it has enough evidence, then returns a done payload to the manager.",
                snippet: "workerLoop",
                concept: ["The worker loop is a smaller ReAct loop inside the larger manager loop.", "It should stop when evidence is sufficient, not when every possible tool was tried.", "Failures can be returned as evidence instead of collapsing the whole request."],
                codeNotes: ["choose_tool asks the worker model for one JSON action.", "done exits the worker loop with a report.", "execute_tool is called only when the worker selected a tool action."],
            }),
            afterRender: "bindCodeDots",
        },
        {
            chapter: "runtime",
            render: () => codeGuide({
                kicker: "Dispatch",
                title: "Tool Dispatch",
                body: "The model names a tool and arguments. The runtime looks up the tool, calls it, and wraps missing tools or exceptions.",
                snippet: "dispatch",
                concept: ["The model never executes Python directly.", "The toolbox decides what is callable for that agent.", "Unknown tools and exceptions become structured results."],
                codeNotes: ["tool_choice is just a string until the toolbox lookup succeeds.", "tool_input becomes keyword arguments for the Python function.", "tool_spec.func is the actual execution boundary."],
            }),
            afterRender: "bindCodeDots",
        },
        {
            chapter: "runtime",
            render: () => codeGuide({
                kicker: "Result shape",
                title: "Result Envelope",
                body: "The loop can record and summarize results consistently because tools return the same structured shape.",
                snippet: "toolResult",
                concept: ["A failed tool call is still useful evidence.", "summary is optimized for humans and future prompt context.", "data carries structured payloads when available."],
                codeNotes: ["Every tool can report success or failure the same way.", "The final answer can include uncertainty when results failed.", "Uniform results make the UI and runtime logic much simpler."],
            }),
            afterRender: "bindCodeDots",
        },
        {
            chapter: "execution",
            afterRender: "bindExecution",
            render: () => window.PresGraphs.executionSlide(),
        },
        {
            chapter: "memory",
            render: () => `
                <article class="slide two-col">
                    <div class="stack">
                        <div class="eyebrow">Memory vs context</div>
                        <h2>Memory is stored. Context is selected.</h2>
                        <p>Memory can contain requests, planner actions, worker assignments, tool calls, observations, summaries, token usage, runtime events, and answers.</p>
                        <p>Context is the slice of memory the app renders into the next model call. Good context is the right evidence, not just more text.</p>
                    </div>
                    <div class="three-col">
                        <div class="metric-card"><span class="card-kicker">Ephemeral</span><h3>Session state</h3><p>Current request, recent turns, active assignments, and observations needed now.</p></div>
                        <div class="metric-card"><span class="card-kicker">Persistent</span><h3>Disk records</h3><p>History, JSONL event files, vector DB artifacts, and saved outputs that can survive restart.</p></div>
                        <div class="metric-card"><span class="card-kicker">Rendered</span><h3>Prompt context</h3><p>Summary plus relevant records formatted for manager or worker model calls.</p></div>
                    </div>
                </article>
            `,
        },
        {
            chapter: "memory",
            render: () => codeGuide({
                kicker: "Recording",
                title: "ConversationHistory is application memory.",
                body: "The model is stateless. The app records events and later chooses which records the manager should see.",
                snippet: "history",
                concept: ["Memory is not inside the model.", "Recording is ordinary application state.", "The active request accumulates ordered steps."],
                codeNotes: ["record_event appends an event into active request steps.", "Completed requests can later be summarized or rendered.", "The model only benefits from memory after the runtime puts it into context."],
            }),
            afterRender: "bindCodeDots",
        },
        {
            chapter: "memory",
            render: () => codeGuide({
                kicker: "Filtering",
                title: "The manager does not see everything.",
                body: "Low-level worker noise can pollute planning. This system exposes selected events to the manager and keeps internal tool chatter scoped.",
                snippet: "visibleEvents",
                concept: ["Filtering is a design choice.", "The manager needs outcomes more than every intermediate detail.", "Worker reports become the clean handoff."],
                codeNotes: ["Visible event names define what reaches planning context.", "Internal tool calls can still exist in app records.", "If the manager misses something, inspect whether it was selected into context."],
            }),
            afterRender: "bindCodeDots",
        },
        {
            chapter: "memory",
            afterRender: "bindMemoryFlow",
            render: () => `
                <article class="slide">
                    <div>
                        <div class="eyebrow">Context rendering</div>
                        <h2>Watch stored events become prompt context.</h2>
                        <p>Play the flow: stored events -> manager-visible records -> rendered context. This is the real memory mechanism.</p>
                    </div>
                    <div class="inline-actions">
                        <button class="small-btn" id="memory-play">Play memory flow</button>
                        <button class="small-btn" id="memory-reset">Reset</button>
                    </div>
                    <div class="memory-flow calm">
                        <div class="glass-card memory-column">
                            <h3>Stored events</h3>
                            <p class="microcopy">Everything the runtime records.</p>
                            <div id="memory-events"></div>
                        </div>
                        <div class="glass-card memory-column">
                            <h3>Manager-visible</h3>
                            <p class="microcopy">Filtered records useful for planning.</p>
                            <div id="memory-selected"></div>
                        </div>
                        <div class="glass-card memory-column">
                            <h3>Rendered context</h3>
                            <p class="microcopy">What the next model call receives.</p>
                            <pre class="prompt-preview" id="memory-context">Waiting for events...</pre>
                        </div>
                    </div>
                </article>
            `,
        },
        {
            chapter: "ship",
            render: () => codeGuide({
                kicker: "Safety",
                title: "Useful tools still need boundaries.",
                body: "The project gives tools real power, then restricts where that power applies. That is the beginning of an agent safety model.",
                snippet: "pathPolicy",
                concept: ["Read, write, and script execution have scoped roots.", "The Python developer writes under coding_output only.", "Repo policy is not the same as OS sandboxing."],
                codeNotes: ["Path resolution centralizes the rule.", "Tool functions call policy helpers before touching files.", "Denied access should become a clear tool failure."],
            }),
            afterRender: "bindCodeDots",
        },
        {
            chapter: "ship",
            render: () => `
                <article class="slide">
                    <div>
                        <div class="eyebrow">Anatomy checklist</div>
                        <h2>What every agentic system needs.</h2>
                    </div>
                    <div class="checklist">
                        ${[
                            ["Brain", "Model client, provider settings, JSON response mode, and token/error handling."],
                            ["Instructions", "Role boundaries, action menu, output contract, and recovery behavior."],
                            ["Tools", "Scoped capabilities with clear descriptions, args, return shape, and failure states."],
                            ["Dispatch", "A controlled runtime that maps model choices to actual callable functions."],
                            ["Memory", "Store events, filter noise, summarize growth, and render context deliberately."],
                            ["Observability", "Show decisions, tool calls, results, raw JSON events, and final synthesis."],
                            ["Safety", "Limit read/write/execute paths and avoid giving every actor every tool."],
                            ["Evals", "Repeatable scenarios that catch regressions when prompts, tools, or memory change."],
                        ].map(([title, text]) => `<div class="info-card check-item"><h3>${title}</h3><p>${text}</p></div>`).join("")}
                    </div>
                </article>
            `,
        },
        {
            chapter: "ship",
            render: () => `
                <article class="slide hero-slide">
                    <div class="hero-copy">
                        <div class="eyebrow">Final debugging lens</div>
                        <h1>Follow the evidence.</h1>
                        <p class="lede">When an agent works, ask: what did it see, what did it choose, what ran, what came back, and what got remembered?</p>
                        <p>That is the difference between a mystical demo and an inspectable system you can improve.</p>
                        <div class="hero-actions">
                            <button class="cta" data-jump="0">Restart</button>
                            <button class="ghost-btn" data-jump="14">Replay execution</button>
                        </div>
                    </div>
                    <div class="stack">
                        <div class="info-card"><span class="card-kicker">Concept</span><h3>Agents are control flow</h3><p>The LLM is one component inside a runtime that chooses, acts, observes, stores, and renders.</p></div>
                        <div class="info-card"><span class="card-kicker">Code</span><h3>Contracts make it teachable</h3><p>JSON action menus, tool registries, and ToolResult envelopes turn decisions into inspectable state.</p></div>
                        <div class="info-card"><span class="card-kicker">Practice</span><h3>Inspect first</h3><p>Before changing prompts, inspect rendered context, chosen action, tool args, result, and memory record.</p></div>
                    </div>
                </article>
            `,
        },
    ];

    window.PresData = {
        chapters,
        agents,
        executionSteps,
        snippets,
        slides,
        escapeHtml,
        codeBlock,
    };
}());

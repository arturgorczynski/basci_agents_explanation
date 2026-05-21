(function () {
    "use strict";

    function renderExecutionGraph() {
        const nodes = [
            ["request", 16, 12, "User request", "task + evidence needed"],
            ["manager", 55, 12, "Manager", "plans one next move"],
            ["answer", 95, 12, "Answer", "sourced response"],
            ["registry", 55, 32, "Agent registry", "valid worker names"],
            ["data_manager", 22, 55, "Data manager", "document worker"],
            ["api", 55, 55, "API worker", "geocoding worker"],
            ["pythondeveloper", 88, 55, "Python worker", "calculation worker"],
            ["docs_tool", 22, 78, "Docs tool", "query_documents"],
            ["api_tool", 55, 78, "Geo API", "address_to_geolocation"],
            ["python_tool", 88, 78, "Python tool", "run_python_script"],
        ];
        const paths = [
            ["M 30 12 L 41 12"],
            ["M 55 21 L 55 23.5"],
            ["M 47 41 Q 36 46.5, 28 46.5"],
            ["M 55 41 L 55 46"],
            ["M 63 41 Q 74 46.5, 82 46.5"],
            ["M 22 64 L 22 69"],
            ["M 55 64 L 55 69"],
            ["M 88 64 L 88 69"],
            ["M 69 12 L 81 12"],
        ];

        return `
            <svg class="execution-graph" viewBox="0 0 110 90" role="img" aria-label="Animated multi-agent execution graph">
                <defs>
                    <linearGradient id="graphGlow" x1="0%" x2="100%">
                        <stop offset="0%" stop-color="#67e8f9" />
                        <stop offset="55%" stop-color="#a78bfa" />
                        <stop offset="100%" stop-color="#86efac" />
                    </linearGradient>
                    <marker id="graphArrow" markerWidth="4" markerHeight="4" refX="3.5" refY="2" orient="auto">
                        <path d="M 0 0 L 4 2 L 0 4 z" fill="#67e8f9" />
                    </marker>
                    <marker id="graphArrowBack" markerWidth="4" markerHeight="4" refX="0.5" refY="2" orient="auto">
                        <path d="M 4 0 L 0 2 L 4 4 z" fill="#67e8f9" />
                    </marker>
                </defs>
                ${paths.map((path, index) => `<path class="graph-path" data-path="${index}" d="${path[0]}" />`).join("")}
                ${nodes.map(([id, x, y, label, subtitle]) => `
                    <g class="graph-node" data-node="${id}" transform="translate(${x} ${y})">
                        <rect x="-13" y="-7.5" width="26" height="15" rx="3.4"></rect>
                        <text class="node-title" y="-1.2">${label}</text>
                        <text class="node-subtitle" y="3.6">${subtitle}</text>
                    </g>
                `).join("")}
            </svg>
        `;
    }

    function executionSlide() {
        const { executionSteps, codeBlock } = window.PresData;
        return `
            <article class="slide execution-slide">
                <div>
                    <div class="eyebrow">Execution simulator</div>
                    <h2>One request becomes JSON decisions.</h2>
                    <p>Click a step or press play. The graph shows responsibility, the middle column lists the steps, and the right column explains who is doing what before the JSON before the code.</p>
                </div>
                <div class="inline-actions">
                    <button class="small-btn" id="exec-play">Play execution</button>
                    <button class="small-btn" id="exec-next">Step</button>
                    <button class="small-btn" id="exec-reset">Reset</button>
                </div>
                <div class="execution-shell code-linked">
                    <div class="graph-panel">
                        ${renderExecutionGraph()}
                    </div>
                    <aside class="step-panel">
                        <div class="step-list" id="exec-steps">
                            ${executionSteps.map((step, index) => `
                                <button class="step-item" data-step="${index}" type="button">
                                    <strong>${index + 1}. ${step.title}</strong>
                                    <p>${step.text}</p>
                                </button>
                            `).join("")}
                        </div>
                    </aside>
                    <div class="execution-code" id="exec-code">
                        <div class="glass-card who-card">
                            <span class="card-kicker">Who is doing what</span>
                            <h3 id="exec-title">Ready</h3>
                            <p id="exec-copy">Press play to animate the execution graph.</p>
                            <p class="exec-detail" id="exec-detail">The manager will receive the request first.</p>
                        </div>
                        <pre class="json-preview" id="exec-event">{"state":"waiting"}</pre>
                        ${codeBlock("managerLoop", true)}
                    </div>
                </div>
            </article>
        `;
    }

    function stepNodes(step) {
        const base = step.graphNodes && step.graphNodes.length
            ? step.graphNodes.slice()
            : [step.graphNode || step.actor];
        if (step.toolNode) base.push(step.toolNode);
        return base.filter(Boolean);
    }

    function stepPaths(step) {
        if (Array.isArray(step.paths)) return step.paths;
        if (step.path != null) return [step.path];
        return [];
    }

    function setGraphStep(stepIndex, active) {
        document.querySelectorAll(".step-item").forEach((item, index) => {
            item.classList.toggle("active", index === stepIndex);
            item.classList.toggle("done", index < stepIndex);
        });

        const allSteps = window.PresData.executionSteps;
        const activeNodes = stepNodes(active);
        const completedNodes = allSteps.slice(0, stepIndex).flatMap(stepNodes);
        const activePaths = stepPaths(active);
        const donePaths = new Set(allSteps.slice(0, stepIndex).flatMap(stepPaths));

        document.querySelectorAll(".graph-node").forEach((node) => {
            const id = node.dataset.node;
            node.classList.toggle("active", activeNodes.includes(id));
            node.classList.toggle("done", completedNodes.includes(id) && !activeNodes.includes(id));
        });

        document.querySelectorAll(".graph-path").forEach((path, index) => {
            const isActive = activePaths.includes(index);
            path.classList.toggle("hot", isActive);
            path.classList.toggle("done", !isActive && donePaths.has(index));
        });
    }

    window.PresGraphs = {
        executionSlide,
        setGraphStep,
    };
}());

(function () {
    "use strict";

    function bindAgentCards() {
        document.querySelectorAll("[data-agent-card]").forEach((card) => {
            card.addEventListener("click", () => {
                const expanded = card.getAttribute("aria-expanded") === "true";
                document.querySelectorAll("[data-agent-card]").forEach((other) => other.setAttribute("aria-expanded", "false"));
                card.setAttribute("aria-expanded", String(!expanded));
            });
        });
    }

    function bindCodeDots() {
        document.querySelectorAll("[data-code-points]").forEach((root) => {
            const dots = Array.from(root.querySelectorAll("[data-point]"));
            const panels = Array.from(root.querySelectorAll("[data-point-panel]"));
            const show = (index) => {
                dots.forEach((dot, dotIndex) => {
                    const active = dotIndex === index;
                    dot.classList.toggle("active", active);
                    dot.setAttribute("aria-selected", active ? "true" : "false");
                });
                panels.forEach((panel, panelIndex) => {
                    panel.classList.toggle("active", panelIndex === index);
                });
            };
            dots.forEach((dot) => {
                dot.addEventListener("click", () => show(Number(dot.dataset.point)));
            });
            show(0);
        });
    }

    function bindExecution(state) {
        state.executionStep = 0;
        const play = document.getElementById("exec-play");
        const step = document.getElementById("exec-next");
        const reset = document.getElementById("exec-reset");
        const codeBox = document.getElementById("exec-code");
        const whoCardHtml = document.querySelector(".who-card").outerHTML;

        const renderStep = () => {
            const active = window.PresData.executionSteps[state.executionStep];
            window.PresGraphs.setGraphStep(state.executionStep, active);
            codeBox.innerHTML = `
                ${whoCardHtml}
                <pre class="json-preview" id="exec-event"></pre>
                ${window.PresData.codeBlock(active.snippet, true)}
            `;
            document.getElementById("exec-title").textContent = active.title;
            document.getElementById("exec-copy").textContent = active.text;
            document.getElementById("exec-detail").textContent = active.detail;
            document.getElementById("exec-event").textContent = JSON.stringify({
                event: active.event,
                actor: active.actor,
                detail: active.detail,
                payload: active.json,
            }, null, 2);
        };

        const renderAndAdvance = () => {
            renderStep();
            if (state.executionStep >= window.PresData.executionSteps.length - 1) {
                window.clearInterval(state.executionTimer);
                state.executionTimer = null;
                return;
            }
            state.executionStep += 1;
        };

        play.addEventListener("click", () => {
            window.clearInterval(state.executionTimer);
            state.executionTimer = null;
            state.executionStep = 0;
            renderAndAdvance();
            state.executionTimer = window.setInterval(renderAndAdvance, 1500);
        });
        step.addEventListener("click", () => {
            window.clearInterval(state.executionTimer);
            state.executionTimer = null;
            renderAndAdvance();
        });
        reset.addEventListener("click", () => {
            window.clearInterval(state.executionTimer);
            state.executionTimer = null;
            state.executionStep = 0;
            renderStep();
        });
        document.querySelectorAll("[data-step]").forEach((button) => {
            button.addEventListener("click", () => {
                window.clearInterval(state.executionTimer);
                state.executionTimer = null;
                state.executionStep = Number(button.dataset.step);
                renderStep();
            });
        });
        renderStep();
    }

    function bindMemoryFlow(state) {
        const events = [
            ["user_request", "Document A address + distance from 50.0647, 19.9450", true],
            ["planner_action", "Manager delegates document lookup to data_manager", true],
            ["tool_call", "data_manager calls query_documents_vector_db", false],
            ["worker_done", "Document chunk confirms Staszica 4/3, Krakow, Poland", true],
            ["tool_result", "api geolocation returns 50.07064, 19.93312", false],
            ["worker_done", "pythondeveloper reports approx 1.05 km", true],
            ["final_answer", "Manager answers with source, coordinates, distance, and assumptions", true],
        ];
        const eventBox = document.getElementById("memory-events");
        const selectedBox = document.getElementById("memory-selected");
        const contextBox = document.getElementById("memory-context");
        let index = 0;

        const reset = () => {
            index = 0;
            eventBox.innerHTML = "";
            selectedBox.innerHTML = "";
            contextBox.textContent = "Waiting for events...";
        };

        const add = () => {
            if (index >= events.length) {
                window.clearInterval(state.memoryTimer);
                return;
            }
            const [type, text, visible] = events[index];
            eventBox.insertAdjacentHTML("beforeend", `<div class="memory-chip"><strong>${type}</strong><br>${text}</div>`);
            if (visible) {
                selectedBox.insertAdjacentHTML("beforeend", `<div class="memory-chip"><strong>${type}</strong><br>${text}</div>`);
            }
            const selected = events
                .slice(0, index + 1)
                .filter((item) => item[2])
                .map((item) => `- ${item[0]}: ${item[1]}`)
                .join("\n");
            contextBox.textContent = `Rendered manager context\n\nCurrent request:\nDocument A address + distance from 50.0647, 19.9450\n\nVisible records:\n${selected || "- none yet"}\n\nInstruction:\nChoose the next manager action or synthesize if enough evidence exists.`;
            index += 1;
        };

        document.getElementById("memory-play").addEventListener("click", () => {
            window.clearInterval(state.memoryTimer);
            add();
            state.memoryTimer = window.setInterval(add, 950);
        });
        document.getElementById("memory-reset").addEventListener("click", reset);
        reset();
    }

    window.PresInteractions = {
        bindAgentCards,
        bindCodeDots,
        bindExecution,
        bindMemoryFlow,
    };
}());

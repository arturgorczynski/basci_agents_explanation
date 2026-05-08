APP_CSS = """
:root {
  --bg: #09111d;
  --bg-2: #0f1a2a;
  --panel: rgba(12, 20, 33, 0.94);
  --panel-2: rgba(16, 26, 42, 0.96);
  --panel-3: rgba(10, 17, 28, 0.98);
  --border: rgba(125, 211, 252, 0.16);
  --border-strong: rgba(94, 234, 212, 0.28);
  --text: #e5edf8;
  --muted: #8ea2bc;
  --accent: #7dd3fc;
  --accent-2: #5eead4;
  --warn: #fbbf24;
  --good: #34d399;
  --bad: #fb7185;
  --shadow: 0 22px 48px rgba(2, 8, 23, 0.34);
  --split-left: 42%;
}

html, body, .gradio-container {
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.06), transparent 32%),
    radial-gradient(circle at bottom right, rgba(245, 158, 11, 0.04), transparent 24%),
    linear-gradient(180deg, #060a12 0%, #08111d 52%, #09121d 100%);
  color: var(--text) !important;
}

.gradio-container {
  max-width: 1680px !important;
  padding: 14px 18px 18px !important;
}

.gradio-container * {
  color: var(--text);
}

.app-shell {
  border: 1px solid var(--border);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(12, 20, 33, 0.98), rgba(10, 16, 28, 0.94));
  box-shadow: var(--shadow);
  overflow: hidden;
  margin-bottom: 10px;
}

.hero {
  padding: 16px 20px 14px;
  background:
    linear-gradient(120deg, rgba(34, 211, 238, 0.08), transparent 42%),
    linear-gradient(300deg, rgba(94, 234, 212, 0.08), transparent 38%);
  border-bottom: 1px solid rgba(125, 211, 252, 0.1);
}

.hero h1 {
  margin: 0;
  font-size: 1.45rem;
  letter-spacing: 0.01em;
  color: #f7fbff;
}

.hero p {
  margin: 6px 0 0;
  max-width: 900px;
  color: var(--muted);
  font-size: 0.94rem;
  line-height: 1.45;
}

.panel {
  background: linear-gradient(180deg, rgba(12, 20, 33, 0.96), rgba(9, 15, 25, 0.96));
  border: 1px solid var(--border);
  border-radius: 18px;
  box-shadow: var(--shadow);
  padding: 10px;
}

.left-panel,
.right-panel {
  min-height: 880px;
}

#main-split {
  display: flex !important;
  gap: 12px;
  align-items: stretch;
  flex-wrap: nowrap !important;
}

#main-split > * {
  min-width: 0;
  width: auto !important;
}

#left-pane,
#right-pane {
  min-width: 0;
  flex: 1 1 0 !important;
}

#main-split.is-resizable {
  display: grid !important;
  grid-template-columns: minmax(320px, var(--split-left)) 14px minmax(420px, 1fr);
  gap: 0;
  align-items: stretch;
}

#main-split.is-resizable #left-pane {
  grid-column: 1;
  width: 100% !important;
  max-width: none !important;
}

#main-split.is-resizable #right-pane {
  grid-column: 3;
  width: 100% !important;
  max-width: none !important;
}

.splitter {
  width: 14px;
  flex: 0 0 14px;
  grid-column: 2;
  height: 100%;
  position: relative;
  cursor: col-resize;
  user-select: none;
  touch-action: none;
}

.splitter::before {
  content: "";
  position: absolute;
  inset: 10px 4px;
  border-radius: 999px;
  background:
    linear-gradient(180deg, rgba(94, 234, 212, 0.08), rgba(125, 211, 252, 0.16)),
    rgba(10, 16, 28, 0.9);
  border: 1px solid rgba(125, 211, 252, 0.12);
}

.splitter::after {
  content: "";
  position: absolute;
  top: 50%;
  left: 50%;
  width: 4px;
  height: 72px;
  transform: translate(-50%, -50%);
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(125, 211, 252, 0.4), rgba(94, 234, 212, 0.6));
  box-shadow: 0 0 18px rgba(94, 234, 212, 0.2);
}

.splitter:hover::after,
.splitter.is-dragging::after {
  background: linear-gradient(180deg, rgba(125, 211, 252, 0.75), rgba(94, 234, 212, 0.9));
}

.status-panel,
.token-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.status-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 6px 11px;
  font-weight: 800;
  letter-spacing: 0.02em;
  background: rgba(18, 28, 43, 0.96);
  border: 1px solid rgba(125, 211, 252, 0.18);
}

.status-running {
  color: var(--accent-2);
}

.status-awaiting_user_input,
.status-completed_request {
  color: var(--warn);
}

.status-ended,
.status-archived {
  color: var(--good);
}

.status-error {
  color: var(--bad);
}

.status-meta,
.status-hint {
  color: var(--muted);
  font-size: 0.9rem;
}

.status-hint {
  width: 100%;
}

.token-total {
  padding: 8px 12px;
  border-radius: 12px;
  background: rgba(17, 24, 39, 0.95);
  border: 1px solid rgba(94, 234, 212, 0.12);
  font-weight: 800;
}

.token-chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  width: 100%;
}

.token-chip {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  padding: 7px 11px;
  border-radius: 12px;
  background: rgba(18, 27, 43, 0.94);
  border: 1px solid rgba(125, 211, 252, 0.12);
}

.token-chip.empty {
  color: var(--muted);
}

.token-chip-title {
  font-weight: 800;
  color: var(--accent);
}

.trace-scroll,
.graph-scroll,
.console-scroll {
  min-height: 720px;
  max-height: calc(100vh - 220px);
  overflow: auto;
  padding-right: 4px;
}

.trace-scroll::-webkit-scrollbar,
.graph-scroll::-webkit-scrollbar,
.console-scroll::-webkit-scrollbar {
  width: 9px;
}

.trace-scroll::-webkit-scrollbar-thumb,
.graph-scroll::-webkit-scrollbar-thumb,
.console-scroll::-webkit-scrollbar-thumb {
  background: rgba(125, 211, 252, 0.18);
  border-radius: 999px;
}

.trace-section {
  margin-bottom: 14px;
}

.trace-section-title {
  font-family: Consolas, "Courier New", monospace;
  font-weight: 800;
  color: #d9faff;
  background: linear-gradient(90deg, rgba(14, 116, 144, 0.32), rgba(17, 24, 39, 0.92));
  border: 1px solid rgba(125, 211, 252, 0.14);
  border-radius: 12px;
  padding: 10px 12px;
  margin-bottom: 8px;
  letter-spacing: 0.01em;
}

.request-section {
  margin-bottom: 18px;
  border: 1px solid rgba(125, 211, 252, 0.14);
  background: linear-gradient(180deg, rgba(8, 14, 24, 0.72), rgba(7, 12, 21, 0.42));
  border-radius: 14px;
  overflow: hidden;
}

.request-section-header {
  padding: 12px 14px;
  background:
    linear-gradient(90deg, rgba(14, 116, 144, 0.34), rgba(15, 23, 42, 0.96)),
    rgba(10, 18, 30, 0.96);
  border-bottom: 1px solid rgba(125, 211, 252, 0.14);
}

.request-section-title {
  font-family: Consolas, "Courier New", monospace;
  font-size: 0.94rem;
  color: #dffbff;
  font-weight: 900;
  letter-spacing: 0.02em;
}

.request-section-text {
  margin-top: 5px;
  color: #b8c7dc;
  line-height: 1.45;
  font-size: 0.9rem;
}

.request-timeline,
.graph-request-section .execution-graph {
  padding: 12px;
}

.trace-card {
  border: 1px solid var(--card-border, rgba(125, 211, 252, 0.12));
  background:
    linear-gradient(90deg, var(--card-tint, rgba(125, 211, 252, 0.05)), transparent 32%),
    linear-gradient(180deg, rgba(16, 24, 39, 0.95), rgba(11, 17, 28, 0.97));
  border-radius: 14px;
  padding: 11px 12px 11px 18px;
  margin-bottom: 8px;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.012);
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.trace-card {
  position: relative;
  overflow: hidden;
}

.trace-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 9px;
  background: var(--card-accent, rgba(125, 211, 252, 0.8));
  box-shadow: 0 0 18px var(--card-accent, rgba(125, 211, 252, 0.3));
}

.trace-card.actor-runtime {
  --card-accent: rgba(125, 211, 252, 0.9);
  --card-border: rgba(125, 211, 252, 0.22);
  --card-tint: rgba(125, 211, 252, 0.08);
}

.trace-card.actor-manager {
  --card-accent: rgba(94, 234, 212, 0.96);
  --card-border: rgba(94, 234, 212, 0.28);
  --card-tint: rgba(94, 234, 212, 0.09);
}

.trace-card.actor-worker {
  --card-accent: rgba(245, 158, 11, 0.96);
  --card-border: rgba(245, 158, 11, 0.28);
  --card-tint: rgba(245, 158, 11, 0.08);
}

.trace-card.actor-tool {
  --card-accent: rgba(129, 140, 248, 0.96);
  --card-border: rgba(129, 140, 248, 0.28);
  --card-tint: rgba(129, 140, 248, 0.08);
}

.trace-card.actor-user {
  --card-accent: rgba(56, 189, 248, 0.96);
  --card-border: rgba(56, 189, 248, 0.28);
  --card-tint: rgba(56, 189, 248, 0.08);
}

.trace-card.actor-error {
  --card-accent: rgba(251, 113, 133, 0.98);
  --card-border: rgba(251, 113, 133, 0.32);
  --card-tint: rgba(251, 113, 133, 0.1);
}

.trace-card.console-entry {
  border-color: rgba(94, 234, 212, 0.14);
  background: linear-gradient(180deg, rgba(12, 19, 31, 0.94), rgba(8, 14, 23, 0.98));
}

.trace-card-header {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}

.trace-card-title {
  font-weight: 800;
  color: #f4f9ff;
  letter-spacing: 0.01em;
}

.trace-card-type {
  display: inline-flex;
  align-items: center;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(125, 211, 252, 0.13);
  border: 1px solid rgba(125, 211, 252, 0.18);
  color: #d9faff;
  font-size: 0.76rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.trace-card-detail {
  color: #c7d7ea;
  font-size: 0.86rem;
  font-weight: 700;
}

.trace-card-subtitle {
  color: var(--muted);
  font-size: 0.86rem;
}

.trace-card-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 9px;
  border-radius: 999px;
  font-size: 0.78rem;
  font-weight: 700;
  background: rgba(11, 18, 29, 0.92);
  border: 1px solid rgba(125, 211, 252, 0.14);
}

.trace-card-chip.status-ok,
.trace-card-chip.status-success {
  color: var(--good);
}

.trace-card-chip.status-invalid_json_response,
.trace-card-chip.status-invalid_json_repair {
  color: var(--warn);
}

.trace-card-chip.status-error,
.trace-card-chip.status-failed,
.trace-card-chip.status-missing_tool {
  color: var(--bad);
}

.trace-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 8px;
  margin-bottom: 8px;
}

.trace-stat {
  padding: 8px 10px;
  border-radius: 12px;
  background: rgba(9, 14, 24, 0.9);
  border: 1px solid rgba(125, 211, 252, 0.08);
}

.trace-stat-label {
  display: block;
  color: var(--muted);
  font-size: 0.75rem;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.trace-stat-value {
  color: #edf6ff;
  font-weight: 700;
  word-break: break-word;
}

.trace-card-body pre {
  margin: 8px 0 0;
  white-space: pre-wrap;
  word-break: break-word;
  background: rgba(7, 11, 19, 0.94);
  color: #e6f1ff;
  border-radius: 10px;
  padding: 10px 11px;
  border: 1px solid rgba(125, 211, 252, 0.1);
  font-family: Consolas, "Courier New", monospace;
  font-size: 0.92rem;
  line-height: 1.45;
}

.trace-card-body details {
  margin-top: 8px;
  border: 1px solid rgba(125, 211, 252, 0.08);
  border-radius: 12px;
  background: rgba(9, 14, 24, 0.62);
  padding: 8px 10px;
}

.trace-card-body summary {
  cursor: pointer;
  color: var(--accent-2);
  font-weight: 800;
  list-style: none;
}

.trace-card-body summary::-webkit-details-marker {
  display: none;
}

.trace-card-body summary::before {
  content: "▸";
  display: inline-block;
  margin-right: 7px;
  transition: transform 0.15s ease;
}

.trace-card-body details[open] summary::before {
  transform: rotate(90deg);
}

.event-row {
  margin: 4px 0;
  color: var(--text);
}

.event-row strong {
  color: #dbeafe;
}

.event-row.error {
  color: var(--bad);
}

.console-entry-meta,
.event-row.muted,
.empty-state {
  color: var(--muted);
}

.console-entry-meta {
  font-size: 0.82rem;
  margin-bottom: 6px;
  font-family: Consolas, "Courier New", monospace;
}

.console-spacer {
  height: 10px;
}

.chatbot-shell {
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(125, 211, 252, 0.12);
}

.prompt-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 8px;
}

.prompt-role {
  border: 1px solid rgba(125, 211, 252, 0.1);
  border-radius: 14px;
  background: rgba(7, 12, 21, 0.86);
  overflow: hidden;
}

.prompt-role.system {
  border-color: rgba(94, 234, 212, 0.22);
}

.prompt-role.user {
  border-color: rgba(125, 211, 252, 0.18);
}

.prompt-role-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: linear-gradient(90deg, rgba(18, 28, 43, 0.98), rgba(10, 17, 29, 0.88));
  border-bottom: 1px solid rgba(125, 211, 252, 0.08);
}

.prompt-role-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 0.74rem;
  font-weight: 800;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.prompt-role.system .prompt-role-badge {
  color: #052e2b;
  background: linear-gradient(135deg, #5eead4, #2dd4bf);
}

.prompt-role.user .prompt-role-badge {
  color: #082f49;
  background: linear-gradient(135deg, #7dd3fc, #38bdf8);
}

.prompt-role-title {
  color: #f3f9ff;
  font-weight: 800;
}

.prompt-role-body {
  padding: 12px;
}

.prompt-section {
  border: 1px solid rgba(125, 211, 252, 0.08);
  border-radius: 12px;
  background: rgba(9, 14, 24, 0.88);
  margin-bottom: 10px;
  overflow: hidden;
}

.prompt-section:last-child {
  margin-bottom: 0;
}

.prompt-section-title {
  padding: 8px 11px;
  font-size: 0.76rem;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--accent-2);
  background: rgba(14, 22, 36, 0.96);
  border-bottom: 1px solid rgba(125, 211, 252, 0.08);
}

.prompt-section-body {
  padding: 10px 11px;
  color: #d8e6f6;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
  font-family: Consolas, "Courier New", monospace;
  font-size: 0.9rem;
}

.execution-graph {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.graph-node {
  --graph-accent: rgba(125, 211, 252, 0.9);
  --graph-border: rgba(125, 211, 252, 0.22);
  position: relative;
  display: grid;
  grid-template-columns: 38px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  padding: 0 0 22px;
}

.graph-node:last-child {
  padding-bottom: 0;
}

.graph-node::before {
  content: "";
  position: absolute;
  top: 38px;
  left: 18px;
  bottom: 0;
  width: 2px;
  background: linear-gradient(180deg, var(--graph-accent), rgba(125, 211, 252, 0.06));
}

.graph-node:last-child::before {
  display: none;
}

.graph-node-number {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  color: #06111d;
  background: var(--graph-accent);
  border: 1px solid rgba(255, 255, 255, 0.25);
  font-weight: 900;
  box-shadow: 0 0 18px rgba(125, 211, 252, 0.14);
  z-index: 1;
}

.graph-node-content {
  min-width: 0;
  border-radius: 12px;
  border: 1px solid var(--graph-border);
  background:
    linear-gradient(90deg, rgba(125, 211, 252, 0.07), transparent 38%),
    rgba(9, 14, 24, 0.9);
  padding: 10px 12px;
}

.graph-node-actor {
  color: var(--graph-accent);
  font-size: 0.76rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.graph-node-title {
  margin-top: 3px;
  color: #f7fbff;
  font-weight: 900;
}

.graph-node-detail {
  margin-top: 4px;
  color: #aebed3;
  line-height: 1.45;
  word-break: break-word;
  font-size: 0.88rem;
}

.graph-node.actor-manager {
  --graph-accent: rgba(94, 234, 212, 0.96);
  --graph-border: rgba(94, 234, 212, 0.24);
}

.graph-node.actor-worker {
  --graph-accent: rgba(245, 158, 11, 0.96);
  --graph-border: rgba(245, 158, 11, 0.24);
}

.graph-node.actor-tool {
  --graph-accent: rgba(129, 140, 248, 0.96);
  --graph-border: rgba(129, 140, 248, 0.24);
}

.graph-node.actor-user {
  --graph-accent: rgba(56, 189, 248, 0.96);
  --graph-border: rgba(56, 189, 248, 0.24);
}

.graph-node.actor-error {
  --graph-accent: rgba(251, 113, 133, 0.98);
  --graph-border: rgba(251, 113, 133, 0.28);
}

.gradio-container .tabitem,
.gradio-container .tabs {
  background: transparent !important;
}

.gradio-container .tabs {
  margin-top: 8px;
  gap: 8px;
}

.gradio-container .tabs button {
  color: var(--muted) !important;
  background: rgba(13, 20, 33, 0.9) !important;
  border: 1px solid rgba(125, 211, 252, 0.1) !important;
  border-radius: 999px !important;
  padding: 8px 12px !important;
}

.gradio-container .tabs button.selected {
  color: #f8fbff !important;
  background: rgba(20, 36, 56, 0.98) !important;
  border-color: rgba(94, 234, 212, 0.4) !important;
}

.gradio-container button,
.gradio-container input,
.gradio-container textarea,
.gradio-container select,
.gradio-container .wrap,
.gradio-container .form,
.gradio-container .block {
  color-scheme: dark;
}

.gradio-container textarea,
.gradio-container input,
.gradio-container select {
  background: rgba(10, 15, 26, 0.96) !important;
  color: var(--text) !important;
  border: 1px solid rgba(125, 211, 252, 0.16) !important;
  border-radius: 12px !important;
}

.gradio-container label,
.gradio-container .label-wrap,
.gradio-container .label-wrap span {
  color: var(--text) !important;
}

.gradio-container button.primary,
.gradio-container button[variant="primary"] {
  background: linear-gradient(135deg, #0891b2, #2563eb) !important;
  color: white !important;
  border: none !important;
}

.gradio-container button.secondary {
  background: rgba(20, 28, 44, 0.96) !important;
  border: 1px solid rgba(125, 211, 252, 0.16) !important;
}

footer,
.gradio-container footer,
.gradio-container .footer {
  display: none !important;
}

@media (max-width: 1100px) {
  #main-split,
  #main-split.is-resizable {
    display: block;
    grid-template-columns: none;
  }

  #main-split.is-resizable #left-pane,
  #main-split.is-resizable #right-pane {
    width: auto;
    flex: 1 1 auto;
  }

  .splitter {
    display: none;
  }

  .left-panel,
  .right-panel {
    min-height: auto;
  }

  .gradio-container {
    padding: 10px 12px 14px !important;
  }
}
"""

APP_JS = """
<script>
(() => {
  const STORAGE_KEY = "multi_agent_trace_split_left";
  const MIN_PERCENT = 25;
  const MAX_PERCENT = 75;

  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const applySplit = (row, left, right, value) => {
    const next = clamp(value, MIN_PERCENT, MAX_PERCENT);
    row.style.setProperty("--split-left", `${next}%`);
    row.style.gridTemplateColumns = `minmax(320px, ${next}%) 14px minmax(420px, 1fr)`;
    left.style.width = `${next}%`;
    left.style.maxWidth = `${next}%`;
    right.style.width = `calc(100% - ${next}% - 14px)`;
    right.style.maxWidth = `calc(100% - ${next}% - 14px)`;
    window.localStorage.setItem(STORAGE_KEY, String(next));
  };

  const initSplit = () => {
    const row = document.getElementById("main-split");
    const left = document.getElementById("left-pane");
    const right = document.getElementById("right-pane");
    if (!row || !left || !right) return;
    if (window.matchMedia("(max-width: 1100px)").matches) return;

    row.classList.add("is-resizable");
    let splitter = row.querySelector(".splitter");
    if (!splitter) {
      splitter = document.createElement("div");
      splitter.className = "splitter";
      splitter.setAttribute("role", "separator");
      splitter.setAttribute("aria-orientation", "vertical");
      splitter.setAttribute("aria-label", "Resize chat and trace panels");
      row.insertBefore(splitter, right);
    }

    const saved = Number(window.localStorage.getItem(STORAGE_KEY));
    const initial = Number.isFinite(saved) && saved > 0 ? saved : 42;
    applySplit(row, left, right, initial);

    if (splitter.dataset.bound === "true") return;
    splitter.dataset.bound = "true";

    const stopDrag = () => {
      splitter.classList.remove("is-dragging");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", stopDrag);
    };

    const onMove = (event) => {
      const rect = row.getBoundingClientRect();
      if (!rect.width) return;
      const next = clamp(((event.clientX - rect.left) / rect.width) * 100, MIN_PERCENT, MAX_PERCENT);
      applySplit(row, left, right, next);
    };

    splitter.addEventListener("pointerdown", (event) => {
      if (window.matchMedia("(max-width: 1100px)").matches) return;
      event.preventDefault();
      splitter.classList.add("is-dragging");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", stopDrag);
    });
  };

  const boot = () => window.requestAnimationFrame(initSplit);
  window.addEventListener("load", boot);
  document.addEventListener("DOMContentLoaded", boot);
  const observer = new MutationObserver(() => boot());
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
</script>
"""

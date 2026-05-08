from __future__ import annotations

from pathlib import Path

try:
    import gradio as gr
except ImportError as exc:  # pragma: no cover - exercised only when Gradio is missing
    raise ImportError(
        "Gradio is required for the trace UI. Install it with "
        "'.\\.venv\\Scripts\\python.exe -m pip install gradio'."
    ) from exc

from agents_training_facility.agents import TOKEN_USAGE_PATH
from runtime.orchestrator import CONVERSATION_HISTORY_PATH, CONVERSATION_RAW_EVENTS_PATH
from runtime.tracing import DEFAULT_TRACE_DIR
from ui.archive import dropdown_choices, load_session, purge_all_traces
from ui.controller import create_controller, get_controller, remove_controller
from ui.formatters import (
    chat_messages_from_events,
    console_html,
    execution_graph_html,
    raw_session_json,
    status_html,
    step_trace_html,
    token_html,
)
from ui.styles import APP_CSS, APP_JS

BUSY_STATUSES = {"starting", "running"}
NEW_LIVE_MODES = {"empty", "archived"}
NEW_LIVE_CONTROLLER_STATUSES = {"ended", "error"}


def _initial_state() -> dict:
    return {
        "mode": "empty",
        "controller_id": None,
        "session_id": None,
        "selected_session_id": None,
    }


def _live_state(controller_id: str | None) -> dict:
    return {
        "mode": "live",
        "controller_id": controller_id,
        "session_id": None,
        "selected_session_id": None,
    }


def should_start_new_live_session(ui_state: dict | None, controller) -> bool:
    mode = (ui_state or {}).get("mode", "empty")
    if mode in NEW_LIVE_MODES:
        return True
    if controller is None:
        return True
    return getattr(controller, "status", None) in NEW_LIVE_CONTROLLER_STATUSES


def acquire_live_session(
    ui_state: dict | None,
    *,
    trace_dir=DEFAULT_TRACE_DIR,
    controller_lookup=get_controller,
    controller_factory=create_controller,
):
    ui_state = dict(ui_state or _initial_state())
    controller = controller_lookup(ui_state.get("controller_id"))
    if should_start_new_live_session(ui_state, controller):
        controller = controller_factory(trace_dir=trace_dir)
        return controller, _live_state(controller.controller_id), True

    ui_state["mode"] = "live"
    ui_state["controller_id"] = controller.controller_id
    return controller, ui_state, False


def resolve_view_state(
    ui_state: dict | None,
    selected_session_value: str | None = None,
    *,
    trace_dir=DEFAULT_TRACE_DIR,
    controller_lookup=get_controller,
    session_loader=load_session,
    choices_loader=dropdown_choices,
) -> dict:
    ui_state = dict(ui_state or _initial_state())
    mode = ui_state.get("mode", "empty")
    selected_session_id = selected_session_value or ui_state.get("selected_session_id")
    controller = controller_lookup(ui_state.get("controller_id")) if mode == "live" else None
    archived = False

    if controller is not None:
        events = controller.events_snapshot()
        status = controller.status
        session_id = controller.session_id
        pending_input_kind = controller.pending_input_kind
        ui_state["mode"] = "live"
        ui_state["session_id"] = session_id
        if session_id:
            selected_session_id = session_id
        ui_state["selected_session_id"] = selected_session_id
    elif selected_session_id:
        events = session_loader(selected_session_id, trace_dir=trace_dir)
        status = "archived"
        session_id = selected_session_id
        pending_input_kind = None
        archived = True
        ui_state = {
            "mode": "archived",
            "controller_id": None,
            "session_id": session_id,
            "selected_session_id": selected_session_id,
        }
    else:
        events = []
        status = "empty"
        session_id = None
        pending_input_kind = None
        selected_session_id = None
        ui_state = _initial_state()

    if status == "awaiting_user_input":
        placeholder = "Answer the manager's clarification here..."
        allow_send = True
    elif status == "completed_request":
        placeholder = "Send the next request..."
        allow_send = True
    elif status in BUSY_STATUSES:
        placeholder = "Execution is running..."
        allow_send = False
    elif status == "archived":
        placeholder = "Archived session loaded. Send a message or click New Session to start a new chat."
        allow_send = True
    elif status in {"ended", "error"}:
        placeholder = "Send a message or click New Session to start again."
        allow_send = True
    else:
        placeholder = "Start the conversation..."
        allow_send = True

    session_choices = choices_loader(trace_dir=trace_dir)
    session_picker_interactive = status not in BUSY_STATUSES

    return {
        "ui_state": ui_state,
        "events": events,
        "status": status,
        "session_id": session_id,
        "selected_session_id": selected_session_id,
        "pending_input_kind": pending_input_kind,
        "archived": archived,
        "placeholder": placeholder,
        "allow_send": allow_send,
        "session_choices": session_choices,
        "session_picker_interactive": session_picker_interactive,
    }


def build_app(*, trace_dir=DEFAULT_TRACE_DIR):
    def refresh_outputs(
        _interval: float | None,
        ui_state: dict | None,
        selected_session_value: str | None,
    ):
        return render_outputs(ui_state, selected_session_value)

    def render_outputs(
        ui_state: dict | None,
        selected_session_value: str | None = None,
    ):
        view = resolve_view_state(
            ui_state,
            selected_session_value,
            trace_dir=trace_dir,
        )

        return (
            view["ui_state"],
            chat_messages_from_events(view["events"]),
            status_html(
                view["events"],
                status=view["status"],
                session_id=view["session_id"],
                pending_input_kind=view["pending_input_kind"],
                archived=view["archived"],
            ),
            token_html(view["events"]),
            f"<div class='trace-scroll'>{step_trace_html(view['events'])}</div>",
            f"<div class='graph-scroll'>{execution_graph_html(view['events'])}</div>",
            f"<div class='console-scroll'>{console_html(view['events'])}</div>",
            raw_session_json(view["events"]),
            gr.update(value="", placeholder=view["placeholder"], interactive=view["allow_send"]),
            gr.update(interactive=view["allow_send"]),
            gr.update(interactive=view["status"] not in BUSY_STATUSES),
            gr.update(
                choices=view["session_choices"],
                value=view["selected_session_id"],
                interactive=view["session_picker_interactive"],
            ),
        )

    def handle_send(message: str, ui_state: dict | None):
        ui_state = dict(ui_state or _initial_state())
        cleaned_message = str(message or "").strip()

        if not cleaned_message:
            yield render_outputs(ui_state)
            return

        controller, ui_state, _created = acquire_live_session(
            ui_state,
            trace_dir=trace_dir,
        )

        controller.submit(cleaned_message)
        yield render_outputs(ui_state)

        while True:
            changed = controller.wait_for_update(timeout=0.2)
            ui_state["session_id"] = controller.session_id
            if changed:
                yield render_outputs(ui_state)
            if controller.status in {"awaiting_user_input", "completed_request", "ended", "error"}:
                yield render_outputs(ui_state)
                break

    def handle_new_session(ui_state: dict | None):
        ui_state = dict(ui_state or _initial_state())
        controller = remove_controller(ui_state.get("controller_id"))
        if controller is not None:
            controller.close()
        return render_outputs(_initial_state())

    def _delete_button_idle():
        return gr.update(value="Delete All History", variant="stop")

    def _delete_button_armed():
        return gr.update(value="Click again to confirm DELETE ALL", variant="stop")

    def handle_delete_all_history(ui_state: dict | None, armed: bool):
        if not armed:
            return (
                *render_outputs(ui_state),
                True,
                _delete_button_armed(),
                gr.update(active=True),
            )

        controller = remove_controller((ui_state or {}).get("controller_id"))
        if controller is not None:
            controller.close()

        purge_all_traces(trace_dir)

        for path_str in (
            CONVERSATION_HISTORY_PATH,
            CONVERSATION_RAW_EVENTS_PATH,
            TOKEN_USAGE_PATH,
        ):
            try:
                Path(path_str).unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass

        return (
            *render_outputs(_initial_state()),
            False,
            _delete_button_idle(),
            gr.update(active=False),
        )

    def handle_disarm_delete():
        return False, _delete_button_idle(), gr.update(active=False)

    def handle_session_select(session_id: str, ui_state: dict | None):
        ui_state = dict(ui_state or _initial_state())
        if not session_id:
            return render_outputs(ui_state)

        controller = remove_controller(ui_state.get("controller_id"))
        if controller is not None:
            controller.close()

        archived_state = {
            "mode": "archived",
            "controller_id": None,
            "session_id": session_id,
            "selected_session_id": session_id,
        }
        return render_outputs(archived_state)

    with gr.Blocks(fill_width=True) as demo:
        state = gr.State(value=_initial_state())
        delete_armed_state = gr.State(value=False)
        refresh_timer = gr.Timer(value=0.35, active=True, render=False)
        delete_disarm_timer = gr.Timer(value=5.0, active=False)
        gr.HTML("", head=f"<style>{APP_CSS}</style>{APP_JS}")

        gr.HTML(
            """
            <div class="app-shell">
              <div class="hero">
                <h1>Multi-Agent Trace Console</h1>
                <p>Chat on the left. Inspect the active session trace, console log, and raw events on the right.</p>
              </div>
            </div>
            """
        )

        with gr.Row(elem_id="main-split"):
            with gr.Column(elem_id="left-pane", elem_classes=["panel", "left-panel"]):
                status_panel = gr.HTML(label="Status")
                token_panel = gr.HTML(label="Token Usage")
                chatbot = gr.Chatbot(
                    value=chat_messages_from_events([]),
                    height=720,
                    label="Conversation",
                    elem_classes=["chatbot-shell"],
                )
                user_input = gr.Textbox(
                    label="Message",
                    placeholder="Start the conversation...",
                    lines=3,
                    max_lines=6,
                )
                with gr.Row():
                    send_button = gr.Button("Send", variant="primary")
                    new_session_button = gr.Button("New Session")
                    delete_history_button = gr.Button("Delete All History", variant="stop")

            with gr.Column(elem_id="right-pane", elem_classes=["panel", "right-panel"]):
                session_picker = gr.Dropdown(
                    label="Saved Sessions",
                    choices=dropdown_choices(trace_dir=trace_dir),
                    value=None,
                )
                with gr.Tabs():
                    with gr.Tab("Step Trace"):
                        trace_panel = gr.HTML("<div class='empty-state'>No execution trace yet.</div>")
                    with gr.Tab("Execution Graph"):
                        graph_panel = gr.HTML("<div class='empty-state'>No execution graph yet.</div>")
                    with gr.Tab("Console"):
                        console_panel = gr.HTML("<div class='empty-state'>No console output yet.</div>")
                    with gr.Tab("Raw Session JSON"):
                        raw_json_panel = gr.Code(value="[]", language="json", label="Trace JSON")

        send_outputs = [
            state,
            chatbot,
            status_panel,
            token_panel,
            trace_panel,
            graph_panel,
            console_panel,
            raw_json_panel,
            user_input,
            send_button,
            new_session_button,
            session_picker,
        ]

        send_button.click(
            handle_send,
            inputs=[user_input, state],
            outputs=send_outputs,
        )
        user_input.submit(
            handle_send,
            inputs=[user_input, state],
            outputs=send_outputs,
        )
        new_session_button.click(
            handle_new_session,
            inputs=[state],
            outputs=send_outputs,
        )
        delete_history_button.click(
            handle_delete_all_history,
            inputs=[state, delete_armed_state],
            outputs=send_outputs + [delete_armed_state, delete_history_button, delete_disarm_timer],
        )
        delete_disarm_timer.tick(
            handle_disarm_delete,
            inputs=None,
            outputs=[delete_armed_state, delete_history_button, delete_disarm_timer],
            queue=False,
            show_progress="hidden",
        )
        session_picker.input(
            handle_session_select,
            inputs=[session_picker, state],
            outputs=send_outputs,
        )
        refresh_timer.tick(
            refresh_outputs,
            inputs=[refresh_timer, state, session_picker],
            outputs=send_outputs,
            queue=False,
            show_progress="hidden",
        )

        demo.queue(max_size=20)

    return demo


def main() -> None:
    app = build_app()
    app.launch()


if __name__ == "__main__":
    main()

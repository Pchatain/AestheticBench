"""Q1-Q4 Annotation TUI for human grading of model responses."""

import json
import subprocess
from typing import Optional

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Static,
    TextArea,
)
from textual.widgets.option_list import Option

from aestheticbench.paths import ANNOTATOR_COMMAND_FILE, ANNOTATOR_STATE_FILE, DB_PATH
from aestheticbench.store.database import AestheticBenchDB
from aestheticbench.benchmark.prompts import DEFAULT_QUESTIONS

STATE_PATH = ANNOTATOR_STATE_FILE
COMMAND_PATH = ANNOTATOR_COMMAND_FILE


QUESTION_ORDER = ["q1_1", "q1_2", "q4_1", "q4_2", "q3", "q4_3", "q2", "q4_4", "q4"]

QUESTION_CONFIG = {
    "q1_1": {"name": "Premise Rejection", "valid": ["0", "1"], "display": "0/1"},
    "q1_2": {"name": "Relativism Appeal",  "valid": ["0", "1"], "display": "0/1"},
    "q2":  {"name": "Preference",    "valid": ["-1", "0", "1"],        "display": "-1/0/1"},
    "q3":  {"name": "Evidence",      "valid": ["-1", "0", "1"],        "display": "-1/0/1"},
    "q4":  {"name": "Justification", "valid": ["1", "2", "3", "4", "5"], "display": "1-5"},
    "q4_1": {"name": "Factual Depth", "valid": ["0", "1"], "display": "0/1"},
    "q4_2": {"name": "Specificity",   "valid": ["0", "1"], "display": "0/1"},
    "q4_3": {"name": "Synthesis",     "valid": ["0", "1"], "display": "0/1"},
    "q4_4": {"name": "Consistency",   "valid": ["0", "1"], "display": "0/1"},
}

# Button label display
QUESTION_LABELS = {
    "q1_1": "Q1.1", "q1_2": "Q1.2", "q2": "Q2", "q3": "Q3", "q4": "Q4",
    "q4_1": "Q4.1", "q4_2": "Q4.2", "q4_3": "Q4.3", "q4_4": "Q4.4",
}


class HelpModal(ModalScreen[None]):
    """Modal showing the prompt for current question."""

    BINDINGS = [Binding("escape", "dismiss", "Close")]

    def __init__(self, question_key: str) -> None:
        super().__init__()
        self.question_key = question_key

    def compose(self) -> ComposeResult:
        q_info = DEFAULT_QUESTIONS.get(self.question_key, {})
        name = q_info.get("name", QUESTION_CONFIG.get(self.question_key, {}).get("name", self.question_key.upper()))
        prompt = q_info.get("prompt", "No prompt available")
        with Container(id="help-modal"):
            yield Label(f"[b]{name}[/b] Grading Criteria", id="help-title")
            yield Static(prompt, id="help-content")
            yield Button("Close (Esc)", id="help-close")

    @on(Button.Pressed, "#help-close")
    def close_modal(self) -> None:
        self.dismiss()

    CSS = """
    #help-modal {
        width: 80%;
        height: 80%;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
    }
    #help-title {
        text-align: center;
        width: 100%;
        padding-bottom: 1;
    }
    #help-content {
        height: auto;
        max-height: 90%;
        overflow-y: auto;
    }
    #help-close {
        dock: bottom;
        width: 100%;
    }
    """


class SummaryModal(ModalScreen[bool]):
    """Summary screen after completing all questions."""

    BINDINGS = [
        Binding("enter", "confirm", "Continue"),
        Binding("escape", "go_back", "Go Back"),
    ]

    def __init__(self, human_scores: dict, llm_scores: dict) -> None:
        super().__init__()
        self.human_scores = human_scores
        self.llm_scores = llm_scores

    def compose(self) -> ComposeResult:
        with Container(id="summary-modal"):
            yield Label("[b]Annotation Summary[/b]", id="summary-title")
            yield Static(self._build_comparison(), id="summary-content")
            with Horizontal(id="summary-buttons"):
                yield Button("Continue (Enter)", id="summary-continue", variant="primary")
                yield Button("Go Back (Esc)", id="summary-back")

    def _build_comparison(self) -> str:
        lines = ["[b]Question        Your Score    LLM Score[/b]"]
        lines.append("─" * 44)
        for q in QUESTION_ORDER:
            human = self.human_scores.get(q, "-")
            llm = self.llm_scores.get(q, "-")
            label = QUESTION_LABELS[q]
            name = QUESTION_CONFIG[q]["name"]
            lines.append(f"{label} {name:<14}  {str(human):<12}  {str(llm)}")
        return "\n".join(lines)

    @on(Button.Pressed, "#summary-continue")
    def confirm(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#summary-back")
    def go_back(self) -> None:
        self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_go_back(self) -> None:
        self.dismiss(False)

    CSS = """
    #summary-modal {
        width: 64;
        height: auto;
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        align: center middle;
    }
    #summary-title {
        text-align: center;
        width: 100%;
        padding-bottom: 1;
    }
    #summary-content {
        padding: 1;
    }
    #summary-buttons {
        width: 100%;
        height: auto;
        align: center middle;
        padding-top: 1;
    }
    #summary-buttons Button {
        margin: 0 1;
    }
    """


class AnnotateTUI(App):
    """TUI for annotating Q1-Q4 scores."""

    CSS = """
    #model-selector {
        height: auto;
        max-height: 50%;
        padding: 1;
    }
    #model-input {
        width: 100%;
    }
    #model-suggestions {
        height: auto;
        max-height: 10;
        display: none;
    }
    #model-suggestions.visible {
        display: block;
    }
    #annotation-view {
        height: 1fr;
        padding: 0 1;
    }
    #top-bar {
        height: auto;
        width: 100%;
    }
    #annotation-view > Horizontal {
        height: 1fr;
    }
    #response-header {
        height: auto;
        padding: 0 0 0 0;
        align: left middle;
    }
    #response-header Button {
        margin: 0 1 0 0;
    }
    #back-to-model-btn {
        min-width: 12;
    }
    #prev-response-btn,
    #next-response-btn {
        min-width: 10;
    }
    #response-prefix {
        padding: 1 0;
    }
    #response-idx-input {
        width: 12;
    }
    #response-total-label {
        padding: 1 1;
    }
    #progress-dots {
        height: auto;
        padding: 0;
    }
    #main-content {
        height: 1fr;
        width: 100%;
    }
    #response-scroll {
        width: 1fr;
        height: 1fr;
    }
    #response-panel {
        padding: 1;
    }
    #right-panel {
        width: 40;
        height: 100%;
        border: solid $secondary;
        padding: 0 1;
    }
    #question-nav {
        height: 3;
        padding: 0 0;
    }
    #question-nav Button {
        min-width: 5;
        margin: 0 0;
    }
    #question-nav Button.active {
        background: $primary;
    }
    #annotation-panel {
        height: auto;
        padding: 1 0;
    }
    #llm-grade {
        height: auto;
        padding: 0 0 1 0;
    }
    #llm-reasoning {
        display: none;
        padding: 0 0 1 0;
        color: $text-muted;
    }
    #llm-reasoning.visible {
        display: block;
    }
    #score-input {
        width: 100%;
    }
    #reasoning-input {
        height: 3;
        width: 100%;
    }
    #shortcuts-info {
        height: auto;
        padding: 1 0 0 0;
        color: $text-muted;
    }
    #status-bar {
        height: 1;
        dock: bottom;
        background: $primary-background;
        padding: 0 1;
    }
    .hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("ctrl+d", "next_question", "Next Q (^D)", show=True, priority=True),
        Binding("ctrl+a", "prev_question", "Prev Q (^A)", show=True, priority=True),
        Binding("ctrl+s", "save_annotation", "Save (^S)", show=True, priority=True),
        Binding("escape", "back_to_model", "Model Select", show=True, priority=True),
        Binding("ctrl+l", "toggle_llm_reasoning", "LLM (^L)", show=True, priority=True),
        Binding("ctrl+k", "skip_response", "Skip (^K)", show=True, priority=True),
        Binding("ctrl+f", "toggle_filter", "Filter (^F)", show=True, priority=True),
        Binding("ctrl+e", "next_response", "Next Resp (^E)", show=True, priority=True),
        Binding("ctrl+q", "prev_response", "Prev Resp (^Q)", show=True, priority=True),
        Binding("ctrl+g", "show_help", "Help (^G)", show=True, priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.db = AestheticBenchDB(DB_PATH)
        self.annotator: str = subprocess.run(
            ["whoami"], capture_output=True, text=True
        ).stdout.strip()
        self.models: list[str] = []
        self.selected_model: Optional[str] = None
        self.responses: list[dict] = []
        self.current_response_idx: int = 0
        self.current_question: str = QUESTION_ORDER[0]  # key from QUESTION_ORDER
        self.show_unannotated_only: bool = False
        self.llm_reasoning_visible: bool = False
        self.human_scores: dict = {}
        self.human_reasoning: dict = {}
        self._last_command_id: str = ""  # Track processed remote commands

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="model-selector"):
            yield Label("Select Model:")
            yield Input(placeholder="Type to search models...", id="model-input")
            yield OptionList(id="model-suggestions")
        with Vertical(id="annotation-view", classes="hidden"):
            with Vertical(id="top-bar"):
                with Horizontal(id="response-header"):
                    yield Button("← Models", id="back-to-model-btn")
                    yield Button("← Prev", id="prev-response-btn")
                    yield Label("Response ", id="response-prefix")
                    yield Input("", id="response-idx-input", restrict=r"\d*")
                    yield Label("", id="response-total-label")
                    yield Button("Next →", id="next-response-btn")
                yield Static("", id="progress-dots")
            with Horizontal(id="main-content"):
                with VerticalScroll(id="response-scroll"):
                    yield Static("", id="response-panel")
                with VerticalScroll(id="right-panel"):
                    with Horizontal(id="question-nav"):
                        for q in QUESTION_ORDER:
                            yield Button(QUESTION_LABELS[q], id=f"{q}-btn",
                                         classes="active" if q == QUESTION_ORDER[0] else "")
                    with Vertical(id="annotation-panel"):
                        yield Label("", id="question-label")
                        yield Label("", id="llm-grade")
                        yield Static("", id="llm-reasoning")
                        yield Label("Your Score:", id="score-label")
                        yield Input(placeholder="", id="score-input")
                        yield Label("Reasoning (optional):")
                        yield TextArea(id="reasoning-input")
                    yield Static(
                        "[dim]^A/^D Prev/Next Q  ^S Save  ^L LLM\n"
                        "^K Skip  ^F Filter  ^Q/^E Prev/Next\n"
                        "^G Help  Esc Model Select[/dim]",
                        id="shortcuts-info"
                    )
        yield Label("", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.models = self.db.get_models()
        self._restore_app_state()
        if self.query_one("#annotation-view").has_class("hidden"):
            self.query_one("#model-input", Input).focus()
        # Start polling for remote commands every 200ms
        self.set_interval(0.2, self._check_for_commands)

    def _restore_app_state(self) -> None:
        if not STATE_PATH.exists():
            return

        try:
            state = json.loads(STATE_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return

        model = state.get("model")
        try:
            response_idx = int(state.get("response_idx", 0))
        except (TypeError, ValueError):
            response_idx = 0
        if model in self.models:
            self.query_one("#model-input", Input).value = model
            self._load_model(model, response_idx=response_idx)

    def _save_app_state(self) -> None:
        if not self.selected_model:
            return

        state = {
            "model": self.selected_model,
            "response_idx": self.current_response_idx,
            "current_question": self.current_question,
            "total_responses": len(self.responses),
            "human_scores": self.human_scores,
            "timestamp": subprocess.run(
                ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                capture_output=True, text=True
            ).stdout.strip(),
        }
        try:
            STATE_PATH.write_text(json.dumps(state, indent=2))
        except OSError:
            self.notify("Unable to save annotator state", severity="warning")

    def _check_for_commands(self) -> None:
        """Poll for remote commands and execute them."""
        if not COMMAND_PATH.exists():
            return

        try:
            command_data = json.loads(COMMAND_PATH.read_text())
        except (json.JSONDecodeError, OSError):
            return

        command_id = command_data.get("command_id", "")
        if command_id and command_id != self._last_command_id:
            self._last_command_id = command_id
            action = command_data.get("action")
            value = command_data.get("value")
            self._execute_remote_command(action, value)
            # Clear command file after processing
            try:
                COMMAND_PATH.unlink()
            except OSError:
                pass

    def _execute_remote_command(self, action: str, value: Optional[str]) -> None:
        """Execute a command received from external process."""
        # Don't process commands if in model selector mode
        if not self.selected_model:
            return

        if action == "next_question":
            self.action_next_question()
        elif action == "prev_question":
            self.action_prev_question()
        elif action == "set_score" and value is not None:
            score_input = self.query_one("#score-input", Input)
            score_input.value = value
            # Trigger auto-save
            self._save_current_input()
        elif action == "save":
            self.action_save_annotation()
        elif action == "next_response":
            self.action_next_response()
        elif action == "prev_response":
            self.action_prev_response()
        elif action == "skip_response":
            self.action_skip_response()

    @on(Input.Changed, "#score-input")
    def auto_save_score(self, event: Input.Changed) -> None:
        """Auto-save when the user enters a valid score."""
        q_key = self.current_question
        value = event.value.strip()
        if not value:
            return
        normalized = self._validate_score(q_key, value)
        if normalized is not None:
            self.human_scores[q_key] = normalized
            self._persist_annotation()
            self.notify(f"{QUESTION_LABELS[q_key]} saved", severity="information")

    @on(Input.Changed, "#model-input")
    def filter_models(self, event: Input.Changed) -> None:
        suggestions = self.query_one("#model-suggestions", OptionList)
        query = event.value.lower()
        suggestions.clear_options()
        if query:
            matches = [m for m in self.models if query in m.lower()]
            for m in matches[:10]:
                suggestions.add_option(Option(m, id=m))
            suggestions.add_class("visible")
        else:
            suggestions.remove_class("visible")

    @on(Input.Submitted, "#model-input")
    def select_model_from_input(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if value in self.models:
            self._load_model(value)
        else:
            matches = [m for m in self.models if value.lower() in m.lower()]
            if len(matches) == 1:
                self._load_model(matches[0])

    @on(OptionList.OptionSelected, "#model-suggestions")
    def select_model_from_list(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            self._load_model(str(event.option_id))

    def _load_model(self, model: str, response_idx: int = 0) -> None:
        self.selected_model = model
        self._refresh_responses()
        if self.responses:
            self.query_one("#model-selector").add_class("hidden")
            self.query_one("#annotation-view").remove_class("hidden")
            self.current_response_idx = min(max(response_idx, 0), len(self.responses) - 1)
            self.current_question = QUESTION_ORDER[0]
            self._display_current()
            self.query_one("#score-input", Input).focus()
        else:
            self.notify(f"No responses found for {model}", severity="warning")

    def _refresh_responses(self) -> None:
        all_responses = self.db.get_responses_for_q1q4_annotation(
            model=self.selected_model, limit=500
        )
        if self.show_unannotated_only:
            self.responses = [r for r in all_responses if r.get("annotation_id") is None]
        else:
            self.responses = all_responses

    def _display_current(self) -> None:
        if not self.responses:
            self.notify("No more responses", severity="warning")
            return

        r = self.responses[self.current_response_idx]
        total = len(self.responses)
        idx = self.current_response_idx + 1

        filter_status = "[unannotated]" if self.show_unannotated_only else "[all]"
        self.query_one("#response-idx-input", Input).value = str(idx)
        self.query_one("#response-total-label", Label).update(
            f"/ {total}  {self.selected_model}  {filter_status}"
        )
        self._update_progress_dots()

        topic = r.get("topic", "")
        question = r.get("question_text", "")
        response_text = r.get("response_text", "")
        panel_text = f"[b]Topic:[/b] {topic}\n\n[b]Question:[/b] {question}\n\n[b]Response:[/b]\n{response_text}"
        self.query_one("#response-panel", Static).update(panel_text)

        self.human_scores = {}
        self.human_reasoning = {}
        for q in QUESTION_ORDER:
            score_key = f"human_{q}_score"
            reasoning_key = f"human_{q}_reasoning"
            if r.get(score_key) is not None:
                self.human_scores[q] = r[score_key]
            if r.get(reasoning_key):
                self.human_reasoning[q] = r[reasoning_key]

        self._display_question()
        self._update_nav_buttons()
        self._save_app_state()

    def _display_question(self) -> None:
        q_key = self.current_question
        q_config = QUESTION_CONFIG[q_key]
        r = self.responses[self.current_response_idx]

        label = f"[b]{QUESTION_LABELS[q_key]} - {q_config['name']}[/b] ({q_config['display']})"
        self.query_one("#question-label", Label).update(label)

        llm_score = r.get(f"llm_{q_key}_score", "-")
        self.query_one("#llm-grade", Label).update(f"LLM Score: {llm_score}")

        llm_reasoning = r.get(f"llm_{q_key}_reasoning", "")
        reasoning_widget = self.query_one("#llm-reasoning", Static)
        reasoning_widget.update(f"[dim]LLM Reasoning: {llm_reasoning}[/dim]" if llm_reasoning else "")
        if self.llm_reasoning_visible:
            reasoning_widget.add_class("visible")
        else:
            reasoning_widget.remove_class("visible")

        score_input = self.query_one("#score-input", Input)
        score_input.placeholder = q_config["display"]
        existing_score = self.human_scores.get(q_key, "")
        score_input.value = str(existing_score) if existing_score != "" else ""

        reasoning_input = self.query_one("#reasoning-input", TextArea)
        reasoning_input.text = self.human_reasoning.get(q_key, "")

    def _update_nav_buttons(self) -> None:
        for q in QUESTION_ORDER:
            btn = self.query_one(f"#{q}-btn", Button)
            if q == self.current_question:
                btn.add_class("active")
            else:
                btn.remove_class("active")

    def _validate_score(self, q_key: str, value: str) -> Optional[str]:
        """Validate and normalize score. Returns normalized value or None if invalid."""
        value = value.strip().lower()
        valid = QUESTION_CONFIG[q_key]["valid"]
        if value in valid:
            return value
        return None

    def action_next_question(self) -> None:
        self._save_current_input()
        idx = QUESTION_ORDER.index(self.current_question)
        if idx < len(QUESTION_ORDER) - 1:
            self.current_question = QUESTION_ORDER[idx + 1]
            self._display_question()
            self._update_nav_buttons()
            self._save_app_state()
            self.query_one("#score-input", Input).focus()
        else:
            self._show_summary()

    def action_prev_question(self) -> None:
        self._save_current_input()
        idx = QUESTION_ORDER.index(self.current_question)
        if idx > 0:
            self.current_question = QUESTION_ORDER[idx - 1]
            self._display_question()
            self._update_nav_buttons()
            self._save_app_state()
            self.query_one("#score-input", Input).focus()

    def _save_current_input(self) -> None:
        """Save current input to memory (not DB yet)."""
        q_key = self.current_question
        score_val = self.query_one("#score-input", Input).value
        reasoning_val = self.query_one("#reasoning-input", TextArea).text

        if score_val.strip():
            normalized = self._validate_score(q_key, score_val)
            if normalized:
                self.human_scores[q_key] = normalized
        self.human_reasoning[q_key] = reasoning_val

    def action_save_annotation(self) -> None:
        """Save current question annotation to database."""
        self._save_current_input()
        q_key = self.current_question

        score_val = self.query_one("#score-input", Input).value
        if score_val.strip():
            normalized = self._validate_score(q_key, score_val)
            if normalized is None:
                valid = QUESTION_CONFIG[q_key]["display"]
                self.notify(f"Invalid score. Expected: {valid}", severity="error")
                return
            self.human_scores[q_key] = normalized

        self._persist_annotation()
        self.notify(f"{QUESTION_LABELS[q_key]} saved", severity="information")

    def _persist_annotation(self) -> None:
        """Write-through: persist annotation to DB and update in-memory cache."""
        r = self.responses[self.current_response_idx]
        response_id = r["response_id"]

        import uuid
        from datetime import datetime

        existing = self.db.get_annotation_by_response_id(response_id, self.selected_model)
        annotation_id = existing.id if existing else str(uuid.uuid4())
        created_at = existing.created_at if existing else datetime.now()

        def _int_or_none(key: str):
            v = self.human_scores.get(key)
            return int(v) if v is not None else None

        self.db.add_annotation(
            annotation_id=annotation_id,
            response_id=response_id,
            model=self.selected_model,
            annotator=self.annotator,
            q1_score=self.human_scores.get("q1"),
            q1_reasoning=self.human_reasoning.get("q1"),
            q2_score=_int_or_none("q2"),
            q2_reasoning=self.human_reasoning.get("q2"),
            q3_score=_int_or_none("q3"),
            q3_reasoning=self.human_reasoning.get("q3"),
            q4_score=_int_or_none("q4"),
            q4_reasoning=self.human_reasoning.get("q4"),
            q4_1_score=_int_or_none("q4_1"),
            q4_1_reasoning=self.human_reasoning.get("q4_1"),
            q4_2_score=_int_or_none("q4_2"),
            q4_2_reasoning=self.human_reasoning.get("q4_2"),
            q4_3_score=_int_or_none("q4_3"),
            q4_3_reasoning=self.human_reasoning.get("q4_3"),
            q4_4_score=_int_or_none("q4_4"),
            q4_4_reasoning=self.human_reasoning.get("q4_4"),
            created_at=created_at,
            updated_at=datetime.now(),
        )

        # Update the in-memory response dict so navigating back shows the saved annotation
        r["annotation_id"] = annotation_id
        for q in QUESTION_ORDER:
            r[f"human_{q}_score"] = self.human_scores.get(q)
            r[f"human_{q}_reasoning"] = self.human_reasoning.get(q)
        self._update_progress_dots()

    def _show_summary(self) -> None:
        """Show summary modal after the last question."""
        self._save_current_input()
        r = self.responses[self.current_response_idx]
        llm_scores = {q: r.get(f"llm_{q}_score", "-") for q in QUESTION_ORDER}

        def on_summary_close(should_advance: bool) -> None:
            if should_advance:
                self._persist_annotation()
                self.action_next_response()
            else:
                self.current_question = QUESTION_ORDER[-1]
                self._display_question()
                self._update_nav_buttons()

        self.push_screen(SummaryModal(self.human_scores, llm_scores), on_summary_close)

    def _annotation_status(self, r: dict) -> str:
        scores = [r.get(f"human_{q}_score") for q in QUESTION_ORDER]
        filled = sum(1 for s in scores if s is not None)
        if filled == 0:
            return "empty"
        elif filled == len(QUESTION_ORDER):
            return "full"
        return "partial"

    def _update_progress_dots(self) -> None:
        n = len(self.responses)
        cur = self.current_response_idx
        cell_width = max(3, len(str(n)) + 1)
        dot_parts = []
        number_parts = []
        for i, r in enumerate(self.responses):
            status = self._annotation_status(r)
            dot = "●" if status == "full" else ("◐" if status == "partial" else "○")
            color = "green" if status == "full" else ("yellow" if status == "partial" else "dim")
            if i == cur:
                dot_markup = f"[bold white on blue]{dot}[/bold white on blue]"
                number_markup = f"[bold white on blue]{i + 1}[/bold white on blue]"
            else:
                dot_markup = f"[{color}]{dot}[/{color}]"
                number_markup = f"[{color}]{i + 1}[/{color}]"

            dot_parts.append(f"{dot_markup}{' ' * (cell_width - 1)}")
            number_parts.append(f"{number_markup}{' ' * (cell_width - len(str(i + 1)))}")

        self.query_one("#progress-dots", Static).update(
            "".join(dot_parts).rstrip() + "\n" + "".join(number_parts).rstrip()
        )

    @on(Input.Submitted, "#response-idx-input")
    def jump_to_response(self, event: Input.Submitted) -> None:
        try:
            n = int(event.value) - 1  # 1-indexed
            if 0 <= n < len(self.responses):
                self.current_response_idx = n
                self.current_question = QUESTION_ORDER[0]
                self._display_current()
                self.query_one("#score-input", Input).focus()
            else:
                self.notify(f"Out of range (1–{len(self.responses)})", severity="error")
        except ValueError:
            pass

    def action_next_response(self) -> None:
        if self.current_response_idx < len(self.responses) - 1:
            self.current_response_idx += 1
            self.current_question = QUESTION_ORDER[0]
            self._display_current()
            self.query_one("#score-input", Input).focus()
        else:
            self.notify("Last response reached", severity="warning")

    def action_prev_response(self) -> None:
        if self.current_response_idx > 0:
            self.current_response_idx -= 1
            self.current_question = QUESTION_ORDER[0]
            self._display_current()
            self.query_one("#score-input", Input).focus()
        else:
            self.notify("First response", severity="warning")

    def action_skip_response(self) -> None:
        self.action_next_response()

    def action_back_to_model(self) -> None:
        self.query_one("#annotation-view").add_class("hidden")
        self.query_one("#model-selector").remove_class("hidden")
        self.query_one("#model-input", Input).value = ""
        self.query_one("#model-input", Input).focus()
        self.query_one("#model-suggestions", OptionList).remove_class("visible")

    def action_toggle_llm_reasoning(self) -> None:
        self.llm_reasoning_visible = not self.llm_reasoning_visible
        reasoning_widget = self.query_one("#llm-reasoning", Static)
        if self.llm_reasoning_visible:
            reasoning_widget.add_class("visible")
        else:
            reasoning_widget.remove_class("visible")

    def action_toggle_filter(self) -> None:
        self.show_unannotated_only = not self.show_unannotated_only
        self._refresh_responses()
        if self.responses:
            self.current_response_idx = 0
            self.current_question = QUESTION_ORDER[0]
            self._display_current()
        else:
            self.notify("No responses match the current filter", severity="warning")
        status = "unannotated only" if self.show_unannotated_only else "all responses"
        self.notify(f"Filter: {status}")

    def action_show_help(self) -> None:
        self.push_screen(HelpModal(self.current_question))

    @on(Button.Pressed)
    def on_nav_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "back-to-model-btn":
            self.action_back_to_model()
            event.stop()
            return

        if btn_id == "prev-response-btn":
            self.action_prev_response()
            event.stop()
            return

        if btn_id == "next-response-btn":
            self.action_next_response()
            event.stop()
            return

        if btn_id.endswith("-btn"):
            q_key = btn_id[:-4]  # strip "-btn"
            if q_key in QUESTION_CONFIG:
                self._save_current_input()
                self.current_question = q_key
                self._display_question()
                self._update_nav_buttons()
                self.query_one("#score-input", Input).focus()
                event.stop()


def main():
    app = AnnotateTUI()
    app.run()


if __name__ == "__main__":
    main()

"""Native Gradio chat and event adapters; document and agent work stays in core."""

import logging
import os
from functools import partial
from pathlib import Path
from urllib.parse import quote

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGSMITH_HIDE_INPUTS", "true")
os.environ.setdefault("LANGSMITH_HIDE_OUTPUTS", "true")

import gradio as gr  # noqa: E402

from core.engine import (  # noqa: E402
    Session,
    answer_message,
    attach_documents,
    close_session,
    create_session,
)

logger = logging.getLogger(__name__)
ASSETS_DIR = Path(__file__).resolve().parent / "docs"
BRAND_ICON = str(ASSETS_DIR / "folio-icon.png")
USER_ICON = str(ASSETS_DIR / "user-icon.png")
COMPOSER_PLACEHOLDER = "Ask a question or attach a file"
SUGGESTIONS = [
    ("Summarize a document", "Summarize the main points of the attached document."),
    (
        "Find a specific detail",
        "What are the key dates, amounts, and requirements in the attached document?",
    ),
    (
        "Compare documents",
        "Compare the attached documents and highlight their main differences.",
    ),
    ("Explore what's possible", "What can you help me do with my documents?"),
]

CSS = """
.gradio-container {max-width: none !important; padding: 0 !important; background: #fff;}
#sidebar {background: #f8fafc; border-right: 1px solid #e2e8f0;}
#sidebar-content {height: calc(100dvh - 48px); gap: 24px; padding: 24px 4px 12px;}
#sidebar-identity, #header {min-height: 84px; box-sizing: border-box;}
#sidebar-identity {flex: 0 0 auto; padding-bottom: 20px !important;
    border-bottom: 1px solid #e2e8f0;}
#sidebar-identity .html-container {padding: 0 !important;}
#sidebar-identity .brand-lockup {display: flex; align-items: center; gap: 10px;}
#sidebar-identity img {display: block; width: 32px; height: 32px;
    flex: 0 0 32px; object-fit: contain;}
#sidebar-identity strong {font-size: 21px; letter-spacing: -0.6px; line-height: 1.2;}
#sidebar-identity p {margin: 8px 0 0; color: #64748b; font-size: 13px;}
#sidebar-note p {color: #64748b; font-size: 13px;}
#sidebar-note {margin-top: auto;}
#workspace {height: calc(100dvh - 32px); box-sizing: border-box; width: 100%;
    max-width: none; margin: 0; padding: 28px 20px 16px; gap: 16px;}
#header {flex: 0 0 auto; padding-bottom: 20px !important;
    border-bottom: 1px solid #e2e8f0;}
#header h1 {font-size: 24px; letter-spacing: -0.6px; margin: 0 0 4px;}
#header p {color: #64748b; margin: 0;}
#welcome {flex: 1 1 0; min-height: 0; justify-content: center; gap: 24px;}
#welcome-heading {text-align: center;}
#welcome-heading h2 {font-size: 28px; letter-spacing: -0.7px;}
#welcome-heading p {color: #64748b;}
#suggestions {flex: 0 0 auto !important; max-width: 720px;
    width: 100%; margin: 0 auto; gap: 12px;}
.suggestion-card {min-height: 76px; padding: 20px; text-align: left;
    background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
    box-shadow: none; color: #334155; font-weight: 500;
    justify-content: flex-start !important; transition: border-color 150ms;}
.suggestion-card:hover {border-color: #94a3b8; background: #f8fafc;}
.suggestion-card:focus-visible {outline: 2px solid #2563eb; outline-offset: 3px;}
#chat-interface, #chat-interface > .column {flex: 1 1 0; min-height: 0;}
#workspace:has(#welcome) #chat-interface,
#workspace:has(#welcome) #chat-interface > .column {flex: 0 0 auto !important; min-height: auto;}
#workspace:has(#welcome) #conversation {display: none !important;}
#conversation {height: auto !important; flex: 1 1 0; min-height: 0;
    border: 0; background: #fff;}
/* Match ASA: reset through New chat so core resources are cleared as well. */
#conversation .icon-button-wrapper.top-panel {display: none !important;}
#conversation .message-buttons button[aria-label="Share" i],
#conversation .message-buttons button[title="Share" i] {display: none !important;}
#composer {border: 1px solid #e2e8f0; border-radius: 16px; background: #fff;}
#composer textarea::placeholder {color: #64748b; opacity: 1;}
/* ChatInterface applies progress to every output; keep it visible only in chat. */
#composer > [data-testid="status-tracker"] {display: none !important;}
#composer button[aria-label="Submit"], #composer button[aria-label="Stop"] {
    width: 32px; height: 32px; min-width: 32px; padding: 6px;
    border: 0; border-radius: 50% !important; background: #e9edf2;
    color: #334155; box-shadow: none; display: inline-flex;
    align-items: center; justify-content: center;
}
#composer button[aria-label="Submit"]:hover,
#composer button[aria-label="Stop"]:hover {background: #dce3ec;}
#composer button[aria-label="Submit"]:focus-visible,
#composer button[aria-label="Stop"]:focus-visible {
    outline: 2px solid #2563eb; outline-offset: 2px;
}
#session-note {flex: 0 0 auto; text-align: center;}
#session-note p {font-size: 12px; color: #64748b; margin: 0;}
@media (max-width: 768px) {
    #workspace {padding: 22px 16px 12px; gap: 12px;}
    #header {padding-left: 28px;}
    #header h1 {font-size: 20px;}
    #header p {font-size: 13px;}
    #welcome {gap: 16px;}
    #welcome-heading h2 {font-size: 24px;}
    .suggestion-card {min-height: 56px; padding: 14px;}
}
"""

# Use Gradio's native light-theme setting, including on dark-mode devices.
LIGHT_THEME_JS = """() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get('__theme') !== 'light') {
        url.searchParams.set('__theme', 'light');
        window.location.replace(url.toString());
    }
}"""

# Clear the browser picker too so selecting the same file emits another change.
RESET_FILE_PICKER_JS = """(...args) => {
    document.querySelectorAll('#composer input[type=file]').forEach(input => {
        input.value = '';
    });
    return args;
}"""


def prefill_message(suggestion: str, message: dict | None) -> dict:
    """Let the user review a suggestion while preserving any pending attachments."""
    return {"text": suggestion, "files": (message or {}).get("files", [])}


def respond(message: dict, history: list[dict], session: Session | None) -> tuple:
    """ChatInterface owns display history; LangChain checkpoints own model history."""
    session = session or create_session()
    text = message.get("text", "").strip()
    paths = message.get("files", [])
    try:
        if paths:
            attach_documents(session, paths)
        if text:
            response = answer_message(session, text)["text"]
        elif paths:
            response = (
                f"Added {len(paths)} document(s) to this chat. "
                "What would you like to know about them?"
            )
        else:
            response = "Send a message or attach a PDF or TXT to get started."
    except (ValueError, RuntimeError) as exc:
        response = str(exc)
    except Exception as exc:
        logger.error("chat_failed session_id=%s error_type=%s", session.id, type(exc).__name__)
        response = "Something went wrong. Please try again or start a new chat."
    return (
        response,
        session,
        gr.update(interactive=True),
        gr.update(visible=False),
        gr.update(placeholder=COMPOSER_PLACEHOLDER),
    )


def reset_session(session: Session | None) -> tuple:
    close_session(session)
    # Reset display history, both ChatInterface history states, pending input,
    # the composer, core resources and welcome cards.
    return (
        [],
        [],
        [],
        None,
        gr.update(value=None, placeholder=COMPOSER_PLACEHOLDER),
        None,
        gr.update(visible=True),
    )


def build_app() -> gr.Blocks:
    gr.set_static_paths(paths=[BRAND_ICON])
    with gr.Blocks(title="Folio · Chat", fill_height=True, delete_cache=(300, 3600)) as demo:
        session = gr.State(None, time_to_live=3600, delete_callback=close_session)
        with gr.Sidebar(label="Workspace", width=260, elem_id="sidebar"):
            with gr.Column(elem_id="sidebar-content"):
                gr.HTML(
                    '<div class="brand-lockup">'
                    f'<img src="/gradio_api/file={quote(BRAND_ICON)}" alt="Folio">'
                    "<strong>Folio</strong></div>"
                    "<p>Your document workspace.</p>",
                    elem_id="sidebar-identity",
                )
                new_chat = gr.Button("+ New chat", variant="primary", elem_id="new-chat")
                gr.Markdown(
                    "Attach a PDF or TXT in the message box to add context to your conversation."
                )
                gr.Markdown(
                    "**Temporary session**\n\n"
                    "Refreshing starts a new chat and clears its documents.",
                    elem_id="sidebar-note",
                )
        with gr.Column(scale=1, elem_id="workspace"):
            gr.Markdown(
                "# Chat with your documents\nAsk questions. Find answers. Keep the context.",
                elem_id="header",
            )
            with gr.Column(elem_id="welcome") as welcome:
                gr.Markdown(
                    "## Where would you like to start?\n"
                    "Choose a suggestion, or write your own message.",
                    elem_id="welcome-heading",
                )
                with gr.Column(elem_id="suggestions"):
                    cards = []
                    for offset in range(0, len(SUGGESTIONS), 2):
                        with gr.Row():
                            for title, suggestion in SUGGESTIONS[offset : offset + 2]:
                                button = gr.Button(title, elem_classes="suggestion-card")
                                cards.append((button, suggestion))
            with gr.Column(elem_id="chat-interface"):
                chat = gr.Chatbot(
                    height=None,
                    show_label=False,
                    container=False,
                    buttons=[],
                    feedback_options=[],
                    avatar_images=(USER_ICON, BRAND_ICON),
                    elem_id="conversation",
                )
                composer = gr.MultimodalTextbox(
                    sources=["upload"],
                    file_types=[".pdf", ".txt"],
                    file_count="multiple",
                    placeholder=COMPOSER_PLACEHOLDER,
                    show_label=False,
                    max_plain_text_length=4000,
                    max_lines=6,
                    stop_btn=True,
                    elem_id="composer",
                )
                interface = gr.ChatInterface(
                    fn=respond,
                    multimodal=True,
                    chatbot=chat,
                    textbox=composer,
                    additional_inputs=[session],
                    additional_outputs=[session, new_chat, welcome, composer],
                    editable=False,
                    flagging_mode="never",
                    save_history=False,
                    stop_btn=True,
                    fill_height=False,
                    concurrency_limit=1,
                    show_progress="minimal",
                    api_visibility="private",
                )
            # Gradio 6.32 has no constructor switches for these actions. Match
            # ASA's adjustment; reassess it when updating Gradio.
            chat._retryable = False
            chat._undoable = False
            for button, suggestion in cards:
                button.click(
                    partial(prefill_message, suggestion),
                    inputs=[composer],
                    outputs=[composer],
                    queue=False,
                    api_visibility="private",
                )
            gr.Markdown(
                "AI can make mistakes. Review key details.",
                elem_id="session-note",
            )
        # Register after ChatInterface so its saved input captures the full files list.
        composer.submit(
            fn=lambda: (gr.update(visible=False), gr.update(interactive=False)),
            outputs=[welcome, new_chat],
            js=RESET_FILE_PICKER_JS,
            queue=False,
            api_visibility="private",
        )
        composer.stop(
            fn=lambda: (
                gr.update(interactive=True, placeholder=COMPOSER_PLACEHOLDER),
                gr.update(interactive=True),
            ),
            outputs=[composer, new_chat],
            queue=False,
            api_visibility="private",
        )
        new_chat.click(
            reset_session,
            inputs=[session],
            outputs=[
                chat,
                interface.chatbot_state,
                interface.chatbot_value,
                interface.saved_input,
                composer,
                session,
                welcome,
            ],
            concurrency_limit=1,
            js=RESET_FILE_PICKER_JS,
            api_visibility="private",
        )
    return demo


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    build_app().queue(max_size=16).launch(
        server_name="0.0.0.0",
        server_port=int(os.getenv("PORT", "7860")),
        share=False,
        show_error=False,
        max_file_size="10mb",
        state_session_capacity=32,
        footer_links=[],
        favicon_path=BRAND_ICON,
        css=CSS,
        js=LIGHT_THEME_JS,
        theme=gr.themes.Soft(
            primary_hue="blue",
            neutral_hue="slate",
            font=["system-ui", "sans-serif"],
            font_mono=["ui-monospace", "monospace"],
        ).set(
            body_background_fill="#ffffff",
            background_fill_secondary="#f8fafc",
            block_background_fill="#ffffff",
            block_border_width="1px",
        ),
    )

"""Native Gradio chat and event adapters; document and agent work stays in core."""

import html
import logging
import os
from collections.abc import Iterator

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

CSS = """
.gradio-container {width: 100% !important; max-width: 1040px !important; margin: auto;}
#header {align-items: center; padding: 22px 0 14px;}
#brand h1 {font-size: 24px; letter-spacing: -0.7px; margin: 0;}
#brand p {color: var(--body-text-color-subdued); margin-top: 4px;}
#new-chat {max-width: 120px; align-self: center;}
#conversation {border: 0; background: transparent;}
/* History changes must also clear the agent checkpoints through New chat. */
#conversation button {display: none;}
#composer {border-radius: 18px;}
#session-note {text-align: center; font-size: 12px; color: var(--body-text-color-subdued);}
"""

# Reset the browser picker too; selecting the same file must emit another change.
RESET_FILE_PICKER_JS = """(...args) => {
    document.querySelectorAll('#composer input[type=file]').forEach(input => {
        input.value = '';
    });
    return args;
}"""


def respond(message: dict, history: list[dict], session: Session | None) -> Iterator[tuple]:
    """Adapt native text/files input. LangChain checkpoints own the model's history."""
    session = session or create_session()
    text = message.get("text", "").strip()
    paths = message.get("files", [])
    messages = list(history or [])
    content = [{"path": path} for path in paths]
    if text:
        content.append(text)
    if content:
        messages.append({"role": "user", "content": content})
    yield (
        messages,
        gr.update(value=None, interactive=False),
        session,
        "",
        gr.update(interactive=False),
    )
    sources = ""
    progress = gr.Progress()
    try:
        if paths:
            progress(0, desc="Preparing your documents")
            attach_documents(session, paths)
        if text:
            progress(0.5, desc="Thinking")
            result = answer_message(session, text)
            response = result["text"]
            sources = "\n\n---\n\n".join(
                f"**[{source['source_id']}] {html.escape(source['name'])}**"
                + (f" · Page {source['page']}" if source["page"] else " · Text file")
                + f"\n\n{html.escape(source['text'])}"
                for source in result["sources"]
            )
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
    messages.append({"role": "assistant", "content": response})
    yield messages, gr.update(interactive=True), session, sources, gr.update(interactive=True)


def reset_session(session: Session | None) -> tuple:
    close_session(session)
    return [], None, None, ""


def build_app() -> gr.Blocks:
    with gr.Blocks(title="NewPage · Chat", delete_cache=(300, 3600)) as demo:
        session = gr.State(None, time_to_live=3600, delete_callback=close_session)
        with gr.Row(elem_id="header"):
            gr.Markdown("# NewPage\nA conversation with more context.", elem_id="brand")
            new_chat = gr.Button(
                "New chat", variant="secondary", scale=0, min_width=112, elem_id="new-chat"
            )
        chat = gr.Chatbot(
            height="min(62vh, 620px)",
            show_label=False,
            container=False,
            buttons=[],
            feedback_options=[],
            placeholder="<strong>How can I help?</strong><br>"
            "Start a conversation. Attach a PDF or TXT whenever you need it.",
            elem_id="conversation",
        )
        composer = gr.MultimodalTextbox(
            sources=["upload"],
            file_types=[".pdf", ".txt"],
            file_count="multiple",
            placeholder="Message NewPage or attach a document…",
            show_label=False,
            max_plain_text_length=4000,
            stop_btn=False,
            elem_id="composer",
        )
        with gr.Accordion("Sources · latest answer", open=False):
            sources = gr.Markdown("")
        gr.Markdown(
            "PDF & TXT · Temporary chat · Refreshing starts fresh",
            elem_id="session-note",
        )
        composer.submit(
            respond,
            inputs=[composer, chat, session],
            outputs=[chat, composer, session, sources, new_chat],
            concurrency_limit=1,
            concurrency_id="chat",
            show_progress="minimal",
            js=RESET_FILE_PICKER_JS,
            api_visibility="private",
        )
        new_chat.click(
            reset_session,
            inputs=[session],
            outputs=[chat, composer, session, sources],
            concurrency_limit=1,
            concurrency_id="chat",
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
        css=CSS,
        theme=gr.themes.Soft(
            primary_hue="slate",
            neutral_hue="slate",
            font=["Inter", "system-ui", "sans-serif"],
            font_mono=["ui-monospace", "monospace"],
        ),
    )

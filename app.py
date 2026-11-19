"""Gradio components and event adapters. All document and agent work lives in core."""

import html
import logging
import os

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

CSS = """
.gradio-container {max-width: 1240px !important; margin: auto;}
#masthead {padding: 26px 4px 20px; border-bottom: 1px solid var(--border-color-primary);}
#masthead h1 {font-size: clamp(28px, 4vw, 42px); letter-spacing: -1.5px; margin: 4px 0 10px;}
#masthead .eyebrow {font-size: 12px; font-weight: 700; letter-spacing: 2px; color: #27827a;}
#masthead p {color: var(--body-text-color-subdued); max-width: 650px;}
#workspace {padding-top: 20px; gap: 24px;}
#library {padding: 18px; border-radius: 16px; background: var(--block-background-fill);}
#library h2 {font-size: 18px;}
#conversation {border-radius: 16px;}
#footnote {text-align: center; font-size: 12px;
color: var(--body-text-color-subdued); padding: 14px;}
"""


def index_files(paths: list[str] | None, session: Session):
    try:
        documents = attach_documents(session, paths or [])
    except (ValueError, RuntimeError) as exc:
        raise gr.Error(str(exc)) from None
    library = "\n\n".join(
        f"**{number}. {html.escape(doc['name'])}** · Ready"
        for number, doc in enumerate(documents, 1)
    )
    return library, f"{len(documents)} document(s) ready. Ask a question to get started.", None


def send_message(question: str, history: list[dict] | None, session: Session):
    try:
        result = answer_message(session, question)
    except (ValueError, RuntimeError) as exc:
        raise gr.Error(str(exc)) from None
    messages = list(history or [])
    messages.extend(
        [
            {"role": "user", "content": question},
            {"role": "assistant", "content": result["text"]},
        ]
    )
    sources = "\n\n---\n\n".join(
        f"**[{source['source_id']}] {html.escape(source['name'])}**"
        + (f" · Page {source['page']}" if source["page"] else " · Text file")
        + f"\n\n{html.escape(source['text'])}"
        for source in result["sources"]
    )
    return messages, "", sources or "No passages retrieved for this response."


def build_app() -> gr.Blocks:
    with gr.Blocks(title="NewPage · Chat with your documents", delete_cache=(300, 3600)) as demo:
        session = gr.State(None, time_to_live=3600, delete_callback=close_session)
        gr.HTML("""<header id="masthead">
          <div class="eyebrow">NEWPAGE / DOCUMENT WORKSPACE</div>
          <h1>Your documents. A clearer answer.</h1>
          <p>Bring your PDFs and notes. Ask questions, connect ideas, and inspect
          the passages behind each answer.</p>
        </header>""")
        with gr.Row(elem_id="workspace"):
            with gr.Column(scale=1, min_width=280, elem_id="library"):
                gr.Markdown("## Your library\nAdd documents to this conversation.")
                files = gr.File(
                    label="Attach PDF or TXT",
                    file_count="multiple",
                    file_types=[".pdf", ".txt"],
                    type="filepath",
                )
                index_button = gr.Button(
                    "Add to conversation", variant="primary", interactive=False
                )
                status = gr.Markdown("Choose your files, then add them to the conversation.")
                library = gr.Markdown("*Your documents will appear here.*")
                reset = gr.Button("New session", variant="secondary", interactive=False)
                gr.Markdown(
                    "Files and chat are temporary. Refreshing this page starts a new session."
                )
            with gr.Column(scale=3, min_width=320):
                chat = gr.Chatbot(
                    label="Conversation",
                    height=470,
                    elem_id="conversation",
                    placeholder="<strong>What would you like to understand?</strong><br>"
                    "Add a document, then ask about its key ideas or compare your files.",
                    buttons=["copy"],
                )
                with gr.Row():
                    question = gr.Textbox(
                        placeholder="Ask a question about your documents…",
                        label="Your question",
                        show_label=False,
                        scale=8,
                        max_lines=4,
                    )
                    send = gr.Button("Ask →", variant="primary", scale=1, interactive=False)
                with gr.Accordion("Retrieved passages · latest answer", open=False):
                    sources = gr.Markdown("Supporting passages will appear here after a search.")
        gr.Markdown(
            "Grounded in your files. Verify important claims against the sources.",
            elem_id="footnote",
        )

        def initialize():
            return create_session(), *(gr.update(interactive=True) for _ in range(3))

        def reset_session(current: Session):
            close_session(current)
            return (
                create_session(),
                [],
                "",
                None,
                "*Your documents will appear here.*",
                "New session ready. Add a document to begin.",
                "Supporting passages will appear here after a search.",
            )

        demo.load(
            initialize, outputs=[session, index_button, send, reset], api_visibility="private"
        )
        index_button.click(
            index_files,
            [files, session],
            [library, status, files],
            concurrency_limit=1,
            concurrency_id="workspace",
            api_visibility="private",
        )
        gr.on(
            triggers=[question.submit, send.click],
            fn=send_message,
            inputs=[question, chat, session],
            outputs=[chat, question, sources],
            concurrency_limit=1,
            concurrency_id="workspace",
            api_visibility="private",
        )
        reset.click(
            reset_session,
            [session],
            [session, chat, question, files, library, status, sources],
            concurrency_limit=1,
            concurrency_id="workspace",
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
            primary_hue="teal", neutral_hue="slate", font=["Inter", "system-ui", "sans-serif"]
        ),
    )

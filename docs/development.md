# How Folio took shape

Folio grew through small, reviewed increments: agree on a behavior, implement it,
check it, and decide what comes next. The priority was a working local document chat
with understandable code and visible trade-offs.

## Start with a working agreement

Before implementing features, we defined how to collaborate in [AGENTS.md](../AGENTS.md).
Meaningful decisions needed discussion before code; changes needed a clear scope,
relevant checks, and an honest account of their limitations.

The developer chose the product direction and approved implementation decisions.
Codex helped explore alternatives, implement changes, and investigate failures.
Feedback from using the application guided refinements. The developer remains
responsible for reviewing the code and the rationale presented here.

The agreement favors explicit functions, preserved work, secrets outside Git, and
abstractions only when needed. Commits should be small, in English, and explicitly
approved. Routine iterations use focused tests; builds and broader checks are
reserved for changes that need them and release preparation.

## Build the first useful flow

The first idea was to pass extracted document text directly to Gemini. Before the
initial implementation, we chose agentic RAG: one agent decides when to search,
while a deterministic tool retrieves document passages. This supports selecting
and comparing documents without placing every uploaded file in each model request.
The trade-off is extra model calls and less predictable latency.

The first functional prototype connected upload, text extraction, indexing, search,
and an answer. We then allowed conversation before any upload and documents to be
added later without resetting the chat. Each new attachment extends the session's
catalog and index; existing files keep their embeddings.

The interface settled on one workspace with native Gradio components, attachments
in the message box, starter suggestions, and New chat in a sidebar. This keeps the
interaction together and limits custom UI behavior.

## Keep the architecture proportional

| Decision | Reason and trade-off |
|---|---|
| One Python application, UI separated from core functions | Keeps document and agent logic independent of Gradio without introducing a separate backend service. |
| One LangChain agent with one retrieval tool | Gives the model autonomy over searches while keeping the tool surface small and understandable. |
| Gemini for chat and embeddings | Keeps provider configuration simple. Model selection is configurable and has not been benchmarked against alternatives. |
| Session memory and vectors in RAM | Avoids database setup for the prototype. Refreshing or restarting loses state, and this design does not support multiple instances as-is. |
| Docker for execution | Provides a consistent runtime. It adds a build step when packaging changes. |

PDF extraction uses pypdf. Chunks start at 1,200 characters with 180-character
overlap, and each search returns up to four passages. These are initial parameters,
not measured optima. PDF page metadata supports citations, but chunks do not span
pages; scanned files and complex layouts need further work.

## Refine behavior and learn from failures

The prompt uses short ROLE, GOAL, INSTRUCTIONS, and STYLE sections. It asks for
concise Markdown answers, evidence for document claims, and acknowledgment of
uncertainty or conflicting sources. Citations use file names and pages. These are
model instructions; the backend does not yet validate their factual support.

Usage exposed provider timeouts and temporary service failures. Model requests now
allow up to three total SDK attempts. Retries can recover transient failures, but
increase waiting time. Failed agent runs clear conversation checkpoints to avoid
retaining incomplete tool exchanges; indexed documents remain available.

Application logs record operational metadata. LangSmith adds model and tool traces.
Capturing inputs and outputs is an explicit choice because they can contain document
and conversation content. Automated tests use synthetic data and model doubles,
with tracing disabled.

## What is verified, and what comes next

Offline tests exercise extraction, the real agent/tool loop, session isolation,
incremental uploads, limits, and failure recovery. Focused browser checks covered
the main chat interactions and responsive layout. Manual sessions exercised Gemini
and document uploads, but they do not constitute a repeatable quality benchmark.

The next quality step is a small evaluation set: factual questions, summaries,
conflicting documents, missing evidence, and follow-ups. Results should guide
retrieval and prompt changes. Structured responses and backend citation validation
remain future improvements.

Further work includes authentication, durable documents and history, vector storage
selection, OCR, and stronger document-instruction defenses. Public GCP hosting also
needs access controls, shared state, retention rules, and deployment checks.

The initial image audit found unresolved high-severity Debian findings. That audit
describes the image examined at the time; a release needs a fresh audit and resolution
of applicable findings before public deployment.

See the [README](../README.md) for setup, architecture, and current prototype limits.

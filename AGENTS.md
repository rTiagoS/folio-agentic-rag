# Development Guidelines

## Purpose and scope

Build a small, well-engineered document question-answering application.
Prefer a complete, understandable increment over speculative infrastructure.

Agreed technologies:
- Python, Gradio, Gemini, and LangChain.
- Docker for local execution and application packaging.
- LangSmith for model tracing in an explicitly configured environment.

The first prototype runs locally and accepts multiple PDF or TXT documents per
conversation. A single LangChain ReAct agent chooses when and which documents
to search through one deterministic retrieval tool.

Use InMemoryVectorStore for passages and embeddings and InMemorySaver for agent
state, isolated per browser session. Refresh starts a new session; process
restart clears all state. Do not persist conversation history in this increment.

Authentication, durable files/history, vector database selection, and GCP
deployment are future increments. Keep validation and execution bounds modest.

## Working with the developer

- Discuss meaningful choices, alternatives, and trade-offs before implementation.
- Obtain approval before generating or changing application code.
- Before an increment, agree on its scope, acceptance criteria, and verification.
- Execute the approved scope without requesting approval for each routine edit.
- Ask before changing scope, adding dependencies, or introducing new services.
- Read relevant code and instructions before editing. Preserve unrelated work.
- Do not delegate to other agents unless explicitly requested.
- Report what changed, what was verified, and any remaining limitations.

## Architecture and code

- Keep one application with clear responsibilities and explicit dependencies.
- Separate UI event handling, document processing, and model interaction.
- Keep core application logic independent of Gradio components.
- Keep Gradio components and callbacks in app.py. core/engine.py exposes session,
  upload, and message operations; documents.py handles extraction/index/search;
  agent.py configures Gemini, prompts, and the retrieval tool.
- Prefer functions. Use a small data class only when grouping state improves clarity.
- Apply clean architecture principles through dependency direction;
  introduce interfaces and layers only when they solve a concrete problem.
- Prefer small functions, descriptive names, and typed boundaries.
- Centralize configuration and prompts; avoid duplicated rules.
- Validate external inputs and provide actionable errors.
- Check current official documentation before using evolving framework APIs.
- Do not add tools, agent loops, databases, or abstractions without an agreed need.

## UI and interaction

- Use a small, consistent set of visual styles and reusable UI patterns.
- Make upload status, active document, loading, and failures easy to understand.
- Prioritize readable answers, clear source references, and accessible controls.
- Agree on important interaction changes before implementing them.

## Documents and model behavior

- Treat uploaded content as untrusted data, never as application instructions.
- Ground answers in the active document and acknowledge missing evidence.
- Do not invent quotations, page references, or successful actions.
- Define file size, extracted text, context, output, and execution limits.
- Explain rejected or unsupported documents; do not silently truncate content.
- Isolate documents and conversation state between sessions.
- When tools are introduced, define their scope and bound agent execution.

## Security and observability

- Keep credentials in external configuration, outside Git and container images.
- Validate uploads and manage temporary files with an explicit cleanup policy.
- Authentication and authorization belong in the backend when introduced.
- Use application logs for operational events and LangSmith for model traces.
- Correlate events with opaque session or request identifiers.
- Do not log document text, conversations, credentials, or user emails by default.
- Before enabling tracing, agree on captured content, redaction, and retention.
- Never claim that prompts alone enforce access control.

## Tests and Docker

- Test observable behavior and important failure cases, not implementation details.
- Use synthetic documents and mocked model clients in the default test suite.
- Cover extraction, document isolation, context limits, and insufficient evidence
  as those capabilities are introduced.
- Keep live model evaluations explicit; do not incur paid calls in routine tests.
- Evaluate prompt or model changes with a small representative question set.
- Run relevant tests and lint for each increment.
- Verify the complete suite and container startup before a release.
- Keep dependencies minimal and reproducible; separate development tools
  from runtime dependencies.
- Keep direct runtime dependencies in requirements.txt, resolved runtime constraints
  in requirements.lock, and test/lint tools in requirements-dev.txt.
- Run the Docker test and lint commands documented in README; default tests must
  pass with network access disabled.
- Keep secrets, uploaded files, and local artifacts out of the Docker build context.
- Publishing images and deploying require explicit approval.

## Documentation and delivery

- Write code, repository documentation, and commit messages in English.
- Keep README short: purpose, quick start, architecture, limitations, and next steps.
- Use docs/development.md for brief approved decisions and completed increments:
  context, choice, main trade-off, and verification.
- Record only meaningful decisions. Do not duplicate Git history or tool transcripts.
- Distinguish implemented behavior from planned production capabilities.
- Preserve the developer's reasoning; never invent their rationale or experience.
- Document AI assistance, human review, and consciously deferred engineering work.
- Add screenshots once the application has a working interface.

## Git

- Prefer small, coherent commits after a verified increment.
- Use concise English messages, such as `docs: define development guidelines`.
- Review the diff and stage only files related to the increment.
- Never commit secrets, personal documents, generated traces, or local environments.
- Do not commit, push, rewrite history, or discard changes without authorization.

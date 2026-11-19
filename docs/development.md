# Development notes

## 2026-11-19 — First functional prototype

### Decisions agreed with the developer

- Use one LangChain ReAct agent with a deterministic document search tool.
  The initial direct-context idea was superseded by agentic RAG before implementation.
- Keep UI and core logically separate in one Python application. Functions and
  three core modules are enough; one data class groups session resources.
- Keep documents and embeddings within a browser session. Refresh starts fresh;
  durable files, chat history, authentication, and vector database selection are deferred.
- Use Docker for execution and checks. No cloud resources or public endpoints
  are provisioned by this increment.

### Implementation choices

- Use `create_agent` directly. The approved tool surface is limited to document
  retrieval; planning, filesystem tools, and subagent delegation are out of scope.
  Deep Agents was considered and its additional harness was not adopted.
- Use Gemini Flash for response latency and text-only Gemini embeddings for one
  provider setup. The exact defaults are configurable, not benchmark winners.
  [Model catalog](https://ai.google.dev/gemini-api/docs/models) and
  [embedding documentation](https://ai.google.dev/gemini-api/docs/embeddings).
- Use pypdf for text extraction, retaining page metadata. Scanned PDFs require
  future OCR; layout-heavy PDFs may extract poorly.
- One `InMemoryVectorStore` per session holds all document chunks. Metadata lets
  the model choose particular files. Search returns evidence, not another LLM answer.
- Start with 1,200-character chunks, 180-character overlap, and four passages
  per search. These are tunable starting values, not evaluated optima.
- Keep bounds proportional to a local demo. Three tool calls and SDK timeouts
  limit each run; this is not a hard wall-clock deadline. Sessions expire after
  one hour without state updates. Gradio cleans aged upload-cache files periodically.
- Fail indexing without publishing a partial catalog. Reset failed agent
  checkpoints to avoid retaining an unfinished tool exchange.
- Render actual retrieved passages separately from the answer. This makes evidence
  inspectable; it does not prove every generated claim is supported.
- Keep tracing opt-in and hide inputs/outputs by default. Do not create or guess
  the user's LangSmith workspace destination or retention settings.
- Upgrade available OS packages during the runtime build and remove pip after
  installation: its vendored libraries are unnecessary in the running application.

### AI-assisted development

The developer selected the scope and architecture through discussion with Codex
before authorizing code. Codex implemented the approved increment, consulted
official documentation and local skills, and used offline doubles for verification.
Rules live in `AGENTS.md`: discuss consequential changes, preserve scope, verify
behavior, and report limitations honestly. These notes are a shared record;
the developer should review the rationale before submission.

### Deliberately deferred

- Login, persistent documents, and a durable history store; a fast NoSQL option
  is a future candidate, to be assessed against access patterns and checkpoint support.
- Vector database selection, shared indexes, background ingestion, and scaling.
- OCR, hybrid retrieval, reranking, and comprehensive prompt-injection defenses.
- CI, deployment, production auditing, monitoring, and retention guarantees.

### Live quality checks still to run

With synthetic, non-sensitive documents and an explicitly configured API key:

1. Ask a factual question and verify the cited passage and page.
2. Attach conflicting policies and ask the agent to compare specific files.
3. Ask about information absent from all documents; check that it acknowledges absence.
4. Ask a follow-up that requires conversational context.
5. Add a document containing instructions to ignore the system; verify grounding.

Offline tests do not establish Gemini's live answer quality or prompt robustness.

### Verification

- 19 offline tests pass, covering PDF/TXT extraction, the real tool loop,
  document selection, session memory/isolation, limits, and failed indexing/runs.
- Ruff lint/format and dependency consistency checks pass in Docker.
- Browser checks with model doubles pass: upload, indexing, answer, evidence,
  isolated new tab, and refresh. The screenshot shows the actual runtime's empty UI.
- The runtime starts as UID 10001 on Python 3.14.10. Secrets, tests, and development
  tools are excluded from that image.
- Trivy 0.76.2, with its database refreshed on 2026-11-19, reports no Python or
  Node.js vulnerabilities after the image corrections. Debian retains 47 high,
  103 medium, 67 low, and 13 unknown package findings; none of the high findings
  have a fix listed. These are unresolved, not accepted deployment exceptions.
  Full scan evidence and the analyzed image ID are retained outside the repository.
- No live Gemini calls, LangSmith exports, cloud deployments, or commits were made.

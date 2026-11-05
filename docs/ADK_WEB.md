# ADK Web retrieval demo

The native ADK Web chat runs one `research_demo` agent with the `search_papers`
tool. It searches the existing local corpus using BM25, vector or hybrid mode.
No Planner, report generation workflow or Critic is connected.

From PowerShell, in the repository root with the project virtual environment
active (`.venv\Scripts\Activate.ps1`):

```powershell
python run_web.py
```

The launcher checks `.env`, corpus availability and the full test
suite (80% coverage gate), then serves on http://127.0.0.1:8000.
Select **research_demo** in ADK Web and start a chat. Stop with Ctrl+C.

Configure `GOOGLE_API_KEY` and `MODEL_LIGHT` in the project `.env` as described
in the README. Chat uses Gemini; the search itself runs locally. User prompts
and retrieved abstracts are sent to Gemini to format the answer. A missing or
invalid key, unavailable model or exhausted quota prevents chat responses.
The launcher can check presence, not credential validity or quota.

Example prompts:

- `Znajdź 3 artykuły o kwantyzacji modeli językowych. Użyj bm25.`
- `Znajdź 5 artykułów o kompresji LLM, użyj vector.`
- `Search for knowledge distillation using hybrid, return 3 papers.`
- `Porównaj bm25, vector i hybrid dla zapytania "large language model quantization", po 3 wyniki.`

The response includes source links, IDs, scores and abstract-based descriptions.
Expand `search_papers` events in ADK Web to inspect actual arguments and the raw
tool response. The selected mode is passed in the chat, not through custom UI
buttons. Scores are not confidence probabilities. The corpus is a fixed local
snapshot; asking in chat does not download new papers.

The retriever and model are reused between requests; replacing the corpus file
reloads them on the next search. Search runs in a worker thread and serializes
access to the shared index. First vector use may take longer while loading the
model. ADK stores local sessions under `.adk/` (ignored by Git).

If port 8000 is occupied, stop the previous server or run the CLI on another port
after testing: `python -m google.adk.cli web --port 8001 web_agents`.

References: [ADK Web and agent setup](https://google.github.io/adk-docs/get-started/python/),
[function tools](https://google.github.io/adk-docs/tools-custom/function-tools/).

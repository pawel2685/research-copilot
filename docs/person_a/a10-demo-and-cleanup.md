# A10: Demo and cleanup

Status: done. The demo uses B's real search (it needs the corpus) and B's Planner.

Goal: a demo for the presentation and tidy documentation, so a new team member can
follow the README and run everything.

`python main.py` without a question now starts this demo, after the tests, the `.env`
check and the corpus (see [a7-integration.md](a7-integration.md), `launcher.py`).

## Files

### `demo/research_copilot/__init__.py` (new)

`from . import agent`. `adk web` imports the package and looks for `root_agent`.

### `demo/research_copilot/agent.py` (new)

Read top to bottom:

- **Module docstring.** How to run it (`adk web demo` from the repository root), and the
  one difference from the app: no revision after a rejecting Critic, because that step
  is in `agents/runner.py`, outside the ADK flow.
- **Path and `.env`.** `adk web demo` puts `demo/` on the Python path, not the
  repository root, so the file adds the root to `sys.path` before it imports the
  project modules. It then loads the root `.env` (`MODEL_LIGHT`, `MODEL_HEAVY` and the
  key).
- **`make_start_callback(cfg)`.** In `run_pipeline` the runner sets the start state. In
  `adk web` nothing does, and the skip callbacks need `deadline_at`. So the pipeline gets
  a `before_agent_callback` that reads the user's message and sets `question`,
  `sub_questions` (the question alone), a fresh `deadline_at`, and empty notes for the
  four branches. It runs at every message, so a second question in the same chat starts
  clean and does not reuse the old notes or the old deadline.
- **`build_demo_pipeline(cfg=None)`.** Builds the pipeline with `build_pipeline`: the
  search tool from the default search (B's retrieval, so the demo needs the corpus), B's
  Planner when `cfg.use_planner` is on, and C's Critic when `cfg.use_critic` is on. Adds
  the start callback. The Planner replaces the start state `sub_questions` (the question
  alone) with its sub-questions, and the search branches read them.
- **`root_agent`.** `build_demo_pipeline()` with the default `RunConfig()`. The agents
  have the retries and the cache like everywhere else, so repeating a question in the
  demo is faster (a repeat of a question with several sub-questions still asks the Writer
  and the Critic again, see [a8-cache-and-retries.md](a8-cache-and-retries.md)).

### `agents/model_switch.py` (new, added later)

The switch of the Writer's model from the chat, because `adk web` has no place for our own
buttons and `MODEL_HEAVY` can have a much lower free-tier quota than `MODEL_LIGHT` (see the
README, "Models").

- **`split_command(text)`.** A message that starts with `/lite`, `/light` or `/heavy`
  (not case sensitive, as a whole word) gives `("light" | "heavy", question)`. Any other
  message gives `(None, text)`, so `/unknown ...`, `Is /lite a command?` and `/litely` are
  plain questions.
- **`make_model_override(light, heavy)`.** A `before_model_callback` that sets
  `llm_request.model` to `light` when the session state `writer_model_choice` is
  `"light"`, otherwise to `heavy`, and records the name in `writer_model_used` (visible in
  the State tab of `adk web`). ADK calls the model named in `llm_request.model`, so this
  changes the call. It returns no response, so the call goes on.
- **`add_writer_switch(pipeline, light, heavy)`.** Puts the override in front of the model
  callbacks of the agent named `writer`, before the response cache, because the model name
  is part of the cache key. Other agents are not touched.

### `demo/research_copilot/agent.py` (changed, same change)

`make_start_callback` reads the command with `split_command`, strips it from the question
and stores the choice in `writer_model_choice`. The choice is sticky for the chat: a message
without a command keeps it, and `/heavy` goes back. `build_demo_pipeline` adds the switch
with the models of `.env` (`load_models()`), so no model name is written in the code. A
live check with the quota of `MODEL_HEAVY` used up: `/lite What is chain-of-thought
prompting?` ran the Writer on `gemini-3.5-flash-lite` and gave a report.

### `agents/verdict.py` (new, added later)

The chat of `adk web` prints the answer of every agent, and the Critic answers in a fixed
JSON format, so the chat ended with raw JSON. The module shows the verdict as text.

- **`format_critic_result(result)`.** One line: `**Verified** · 5 of 5 claims supported
  (checked against titles and abstracts only)` or `**Not verified** · ...`. Only the claims
  that are not supported are listed after it, with the reason, and then the corrections for
  the Writer. The claims that are fine are not repeated: their sources are in the report. A
  skipped Critic gives `**Not verified** · Critic skipped: <message>`.
- **`format_final_message(report, result)`.** The report, a separator and the verdict. The
  chat ends with the Critic's message, so the answer is repeated there: otherwise the last
  thing on the screen would be the verification. Without a report only the verdict is shown.
- **`readable_event(event, report)`.** Replaces the JSON text of a message of the author
  `critic` with that message. A message of another agent, a partial one, one that is not a
  valid `CriticResult`, and one without text are returned unchanged.
- **`ReadableSequentialAgent`.** A `SequentialAgent` that passes every event through
  `readable_event`, with `report_markdown` from the session state (the Writer's report is
  there when the Critic's message comes). ADK saves the result of the Critic in the state
  (`critic_result`) before the message is sent on, so the data is not changed, only what the
  chat shows.
- **What is not hidden.** The messages of the Planner, the Searchers and the Readers stay in
  the chat. The Critic's instruction has no place for the report or the notes (it is C's
  file), so it gets its evidence from the conversation, and hiding those messages would
  blind it.

### `agents/orchestrator.py` (changed, same change)

`build_pipeline` takes `pipeline_class` (default `SequentialAgent`), the class of the whole
flow. The demo passes `ReadableSequentialAgent`. The app (`answer`) and the evaluation keep
the plain `SequentialAgent`, so nothing that they read changes.

### `tests/test_verdict.py` (new, added later)

- The text for an approved, a rejected (with a reason and corrections), a skipped verdict,
  a skipped one without a message, and one without claims.
- `readable_event` changes only the valid JSON message of the Critic.
- On the real ADK runner with a fake model: the Critic's message in the chat is the text,
  the Writer's message is unchanged, and `critic_result` in the state still holds the data.
  A plain `SequentialAgent` still shows the JSON, and the demo's `root_agent` is the readable
  class.

### `tests/test_model_switch.py` (new, added later)

- `split_command`: commands, case, extra spaces, a command alone, and what is not a command.
- The override picks the model from the choice (none, heavy, light, nonsense) and records it.
- The switch goes in front of the Writer's cache callback, keeps one callback that was not a
  list, works without callbacks, and leaves a pipeline without a Writer alone.
- The whole flow on the real ADK runner with a fake model that records the model name of
  every request: no command gives the model of the environment, `/lite` the light model and
  stays, `/heavy` goes back, the command is not in the question, and the state shows the
  model used.

### `tests/test_demo.py` (new)

Nine tests. The real `.env` is not read: `load_dotenv` is replaced and dummy model names
are set in the environment.

- Importing the demo gives a `root_agent` without a network call, with the flow
  `search_branches`, `writer`, `critic`.
- The package exposes `agent` for `adk web`, the models come from the environment, the
  Critic is left out when the config switches it off, and the project root is on the
  path.
- The start callback sets the state for a question, starts a second question fresh, and
  copes with a message without text. It also reads the model command, strips it from the
  question, keeps the choice for the chat, and sets nothing without a command. The demo's
  Writer has the switch.
- The demo flow on the real ADK runner with a fake model: the start callback,
  branches, Writer and Critic run, and the session holds the report and an approving
  Critic result.

### `.gitignore` (changed)

Added `.adk/`, where `adk web` can store sessions.

### `README.md` (changed)

- The "project setup" status line is replaced by the real status, with the note that B's
  parts are still stand-ins.
- New sections "Demo in the browser" (`adk web demo`) and "Experiments"
  (`get_run_config`, `answer_with_stats`, `LLM_CACHE=off`).
- The structure lists `demo/` and the new content of `agents/` and `docs/`. The models
  table lists the Reader.

### Documentation audit

- Every stage file describes what was built. A0 and A3 got a note where later stages
  changed the picture (`run_app` in A7, `answer` in `agents/pipeline.py`).
- The status table in [README.md](README.md) is correct: all stages A0 to A10 are
  `done`.
- `docs/Research Copilot (EN).html` (550 KB, an exported document) is the leftover the
  plan names. It is tracked, so the user removes it with git after checking that nobody
  needs it.

## Checked

- `adk web demo --port 8765` started, `/list-apps` returned `["research_copilot"]`, and
  the web interface answered. The server was stopped afterwards and left no files in
  `demo/`.
- Not checked: a real question in the browser with the real key and a real model. Do
  this once before the presentation.

## Commit

```
docs: finish demo and documentation
```

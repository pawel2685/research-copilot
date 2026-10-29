# A10: Demo and cleanup

Status: done. The demo uses the stand-ins for B (see "Open dependency on B").

Goal: a demo for the presentation and tidy documentation, so a new team member can
follow the README and run everything.

**Open dependency on B.** Before the final demo and the final README, finish the
"Waiting for B" list in [README.md](README.md): real search, the Planner, and the
manual check with a real key. Otherwise the demo runs on five stub passages.

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
  search tool from the default search (the stub, `TODO(B)`), no Planner yet (`TODO(B)`),
  and C's Critic when `cfg.use_critic` is on. Adds the start callback.
- **`root_agent`.** `build_demo_pipeline()` with the default `RunConfig()`. The agents
  have the retries and the cache like everywhere else, so repeating a question in the
  demo is fast.

### `tests/test_demo.py` (new)

Nine tests. The real `.env` is not read: `load_dotenv` is replaced and dummy model names
are set in the environment.

- Importing the demo gives a `root_agent` without a network call, with the flow
  `search_branches`, `writer`, `critic`.
- The package exposes `agent` for `adk web`, the models come from the environment, the
  Critic is left out when the config switches it off, and the project root is on the
  path.
- The start callback sets the state for a question, starts a second question fresh, and
  copes with a message without text.
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
- The status table in [README.md](README.md) is correct: A0 to A6 and A8 are `done`,
  A7, A9 and A10 are `done` with B stubbed.
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

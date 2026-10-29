# A6: ADK orchestration

Status: done.

Goal: the agents run as one flow inside ADK, with parallel sub-questions, skipping of
the optional agents, and at most one Critic revision. A runner executes the flow and
returns the report.

## The flow

```
Planner (optional, B) -> [ branch_1 | branch_2 | branch_3 | branch_4 ] -> Writer -> Critic (optional, C)
                          each branch = Searcher -> Reader
```

- `ParallelAgent` needs a fixed list of sub-agents and the Planner returns up to four
  sub-questions, so there are always four branches. A branch skips itself when it has
  no sub-question.
- The revision is not an ADK loop. After the flow, plain Python checks the Critic
  result. When `approved is False` and there are revision instructions, the Writer runs
  once more with them. The Critic never runs again.
- Data moves through the session state. The Searcher's final text (the passages it got
  from the tool) is saved under `search_results_N`, the Reader's notes under
  `reading_notes_N`, the Writer's report under `report_markdown` and the Critic's
  result under `critic_result`. The Critic itself reads the conversation, so it sees
  the Writer's report and the passages that the Searchers returned.

## Files

### `agents/searcher.py`, `agents/reader.py`, `agents/writer.py` (changed)

The A5 factories got keyword-only options, because the four branches need unique names
and keys. The defaults are the A5 values, so nothing else changes.

- **`create_searcher_agent(..., name="searcher", output_key="search_results",
  question_key=None)`.** With `question_key`, the instruction ends with
  `Question to search for: {<question_key>}`, so the Searcher takes its question from
  the session state. Without it, the question comes from the user message.
- **`create_reader_agent(..., name="reader", input_key="search_results",
  output_key="reading_notes")`.** The passages placeholder is built from `input_key`.
  `READER_INSTRUCTION` no longer contains the placeholder.
- **`create_writer_agent(..., notes_keys=("reading_notes",), optional_notes=False,
  revision=False)`.** One placeholder per notes key, written `{key?}` with
  `optional_notes` so a missing key counts as empty notes (branches that were skipped).
  With `revision`, the instruction gets `REVISION_INSTRUCTION` with the placeholders
  `{draft_report}` and `{revision_instructions}`.

### `agents/skipping.py` (extended)

- **`MAX_SUB_QUESTIONS = 4`.**
- **`make_deadline_callback(min_left_s, skip_text="skipped", clock=time.time)`.** A
  `before_agent_callback` for the Planner and the Critic. It reads `deadline_at` (a
  `time.time()` value) from the state. When less than `min_left_s` is left it returns
  `Content` with `skip_text`, which makes ADK skip the agent. Otherwise it returns
  `None`. `skip_text` is a string or a function of the context. ADK saves this text
  under the `output_key` of the skipped agent and validates it against its
  `output_schema`, so it must be a valid output of that agent (see "Findings").
- **`normalize_sub_questions(value, question)`.** Accepts `None`, a list of strings, a
  dict with a `questions` list, or a JSON string of either. Returns at most four
  non-empty, stripped strings, or `[question]` when nothing usable is given.
- **`make_branch_callback(index)`.** A `before_agent_callback` for a branch. It reads
  `question` and `sub_questions` from the state, normalises them, and skips the branch
  when there is no item at `index`. Otherwise it stores the item as
  `sub_question_<index + 1>`.
- **`_skip_content(text)`.** Builds the `Content` that the callbacks return.

### `agents/orchestrator.py` (new)

- **`notes_keys()`.** The state keys `reading_notes_1` to `reading_notes_4`.
- **`_with_deadline_callback(agent, min_left_s, skip_text)`.** Returns a copy of the
  Planner or the Critic with the deadline callback put in front of the callbacks it
  already has. The agent that was passed in is not modified.
- **Skip texts.** A skipped Critic "says" the JSON of C's `critic_skipped_result(...)`,
  so its `critic_result` in the state is a valid skipped result. A skipped Planner
  "says" `["<question>"]`, a plan with the original question as the only sub-question.
- **`_build_branch(index, search_tool, light_model)`.** A `SequentialAgent` named
  `branch_N` with `searcher_N` (output `search_results_N`, question from
  `sub_question_N`) and `reader_N` (output `reading_notes_N`), and the branch callback.
- **`build_pipeline(cfg, *, search_tool, planner=None, critic=None, models=None)`.**
  Builds a `SequentialAgent` named `research_pipeline`: the Planner (only when
  `cfg.use_planner` is on and a planner is given), a `ParallelAgent` named
  `search_branches` with the four branches, the Writer (heavy model, reads all four
  notes as optional), and the Critic (only when `cfg.use_critic` is on and a critic is
  given). `models` is `(light, heavy)` and comes from `.env` when it is `None`.

### `agents/runner.py` (new)

- **`PipelineResult`.** A dataclass with `report_markdown`, `sub_questions`,
  `critic_result`, `revised` and `state` (the final session state). Its property
  `verified` is true only when the Critic approved and the report was not revised.
- **`_run_agent(agent, question, state)`.** Creates an `InMemorySessionService`, awaits
  `create_session` with the initial state, runs the agent with `Runner(app_name=...,
  agent=..., session_service=...)` and `run_async`, reads the session back with
  `get_session` and returns its state as a dict.
- **`_read_critic_result(value)`.** Turns the state value into a `CriticResult`: a dict
  or a JSON string is parsed, a missing or unreadable value becomes
  `critic_skipped_result(...)`.
- **`run_pipeline(question, cfg=None, *, search_fn=stub_search, planner=None,
  critic=None, models=None)`.** The steps:
  1. Compute `deadline_at = time.time() + cfg.time_budget_s` and build the search tool
     from `search_fn`, `cfg.hybrid` and `cfg.compress_budget_words`.
  2. Build the pipeline and run it with the initial state `deadline_at`, `question` and
     `sub_questions=[question]`. The initial `sub_questions` makes branch 1 work even
     when the Planner is skipped.
  3. Read `report_markdown` and the Critic result from the final state.
  4. When the Critic rejected the report, gave revision instructions, and time is left,
     run a revision Writer once in a second session. Its state holds the notes, the
     draft and the instructions. A non-empty result replaces the report and `revised`
     is set. An empty result keeps the first report.

### `tests/fake_llm.py` (new, test helper)

`FakeLlm`, a fake ADK model. It answers by the role in the system instruction: the
Searcher calls `search_papers` and then repeats the tool result, the Reader and the
Writer echo the part of their instruction that holds the passages or the notes, and the
Critic and the Planner answer a configured JSON. It records every instruction. With it
the real ADK `Runner` runs the whole flow without the network.

### `tests/test_skip_callbacks.py` (new)

- The deadline callback skips below the threshold and lets the agent run above it, the
  skip text can be a string or a function, and the default clock is the wall clock.
- The branch callback skips a branch without a sub-question, stores the sub-question
  as `sub_question_N`, falls back to the question, reads the Planner JSON, and skips
  when there is no question at all.
- `normalize_sub_questions` for `None`, a list, a dict, JSON strings, more than four
  items, empty strings, non-strings, garbage and other types.

### `tests/test_orchestrator.py` (new)

- The pipeline is a `SequentialAgent`, with four branches in a `ParallelAgent`, each
  branch a Searcher and a Reader with unique names and output keys.
- Models: branches use the light model, the Writer the heavy one; they come from the
  environment when not given.
- The Writer reads the four notes as optional placeholders.
- The Planner is absent when `use_planner` is `False`, the Critic when `use_critic` is
  `False`. With both, the order is Planner, branches, Writer, Critic.
- The optional agents get a skip callback, the originals are not modified, and
  callbacks they already had are kept.

### `tests/test_runner.py` (new)

With the ADK `Runner` replaced by a fake that writes a scripted state:

- The initial state has the deadline, the question and `sub_questions`.
- The report, the sub-questions and the state are returned.
- A missing, unreadable or JSON-string Critic result is handled.
- An approved report is verified and not revised.
- A rejected report with instructions is revised exactly once, the revision state has
  the notes, the draft and the instructions, and the result is not verified.
- No revision without instructions, or when the time budget is used up. An empty
  revision keeps the first report.
- Defaults: `RunConfig()` and models from the environment.

### `tests/test_pipeline_flow.py` (new)

The real ADK `Runner` with `FakeLlm`, no network:

- One sub-question runs one branch, branches 2 to 4 are skipped, and the passages
  reach the Reader and the Writer.
- The placeholders in the instructions are filled from the state.
- Planner sub-questions run in parallel branches.
- A tiny time budget skips the Planner and the Critic and still returns a report.
- An approving Critic gives a verified result. A rejecting one gives exactly one
  revision, and the result is not verified.
- The search function gets `hybrid` from the config, and the word budget is applied.

### `tests/test_agents.py` (extended)

Tests of the new factory options: own name, keys and question key for the Searcher and
the Reader, several optional notes for the Writer, and the revision Writer.

## Findings: ADK items that were not checked before

Checked in the installed google-adk 2.13.0 (source and the run with `FakeLlm`):

- **Placeholders.** `{key}` in an instruction is filled from the session state. A
  missing key raises `KeyError`, and `{key?}` is replaced by an empty string. Writing
  to `ctx.state` in a `before_agent_callback` is visible to the agents that run
  after it.
- **`get_session`.** Keyword-only `app_name`, `user_id`, `session_id`; returns
  `Optional[Session]`. `session.state` is a dict-like object.
- **Output with a schema.** An agent with `output_schema` stores a dict in the state
  (the Critic's `critic_result`).
- **Skipping.** A callback that returns `Content` skips only that agent, and the
  sequence goes on. But the returned text is saved as the agent output and validated
  against `output_schema`. A plain `skipped` text crashed the Critic, so the skip
  texts described above are used.
- **Deprecation.** ADK 2.13 warns that `SequentialAgent` and `ParallelAgent` are
  deprecated in favour of `Workflow`. They are used on purpose, because the plan and
  the project notes prescribe them, and they work.

Still to do by hand, because it needs the real API key:

- The manual run from the plan, to see a real Gemini answer end to end:

  ```python
  import asyncio
  from contracts import RunConfig
  from agents.runner import run_pipeline

  cfg = RunConfig(use_planner=False, use_critic=False)
  print(asyncio.run(run_pipeline("What is LoRA?", cfg)))
  ```

- The shape of the Planner output (`sub_questions`): a list of strings, or a dict with
  a `questions` list, or a JSON string of either. `normalize_sub_questions` accepts all
  of these, but B's Planner and the skip text above must agree. Confirm with B.
- The thresholds `PLANNER_MIN_LEFT_S` and `CRITIC_MIN_LEFT_S` are still example values.

## Commit

```
feat: add agent orchestration
```

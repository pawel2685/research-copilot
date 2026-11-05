
# Research Copilot

A multi-agent research assistant built with [Google ADK](https://google.github.io/adk-docs/).
Given a research question, it finds papers on arXiv, summarises them, checks its
own claims and writes a short report with sources. The pipeline includes
retrieval, context compression, a Planner, a Writer and a Critic. The Planner
and Critic can be skipped when the time budget runs short.

> Retrieval: arXiv corpus, BM25, vector and hybrid search are implemented.
> See [retrieval setup and usage](docs/RETRIEVAL.md). `python main.py` searches this
> corpus, so build it first (`python -m retrieval fetch ...`, then `index`).

## Requirements

- Python 3.12
- Git
- A Google account for the Gemini API key

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/pawel2685/research-copilot.git
```

```bash
cd research-copilot
```

### 2. Create a virtual environment and install dependencies

```bash
python -m venv .venv
```

Activate it. On Windows (PowerShell):

```powershell
.venv\Scripts\Activate.ps1
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

You should see `(.venv)` at the start of the prompt. Then:

```bash
pip install -r requirements.txt
```

If PowerShell refuses to run the activation script, run this once and try again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 3. Get a Gemini API key

Every team member should create their own key. Free-tier limits are counted per key,
so a shared key can run out quickly.

1. Open <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **Create API key**.
3. Choose **Default Gemini Project** (or create a new project for this repo).
4. Create the key and copy it.

Check the current billing tier and pricing conditions in Google AI Studio.
Never send confidential data to the API.

You do not need the project name or the project number. They are only used by
Vertex AI, which this project does not use.

### 4. Create your `.env` file

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

On macOS or Linux:

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder with your key. No quotes and no spaces
around `=`:

```text
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=your-api-key-here
MODEL_LIGHT=gemini-3.5-flash-lite
MODEL_HEAVY=gemini-3.5-flash
```

`.env` is in `.gitignore`. Never commit it, and never paste your key into chat,
issues or pull requests. Check with `git status`: `.env` must not appear there.

### 5. Check that everything works

```bash
python -c "from dotenv import load_dotenv; load_dotenv(); from google import genai; c = genai.Client(); print(c.models.generate_content(model='gemini-3.5-flash-lite', contents='Reply with the single word: ok').text)"
```

It should print `ok`. The client is stored in a variable (`c`) on purpose, see
Troubleshooting.

### 6. Build the paper corpus

The app searches a local corpus of arXiv papers. The corpus is not in git (`data/` is in
`.gitignore`), so every team member builds it once. Without it, `python main.py "<question>"`,
the demos and the experiments stop with `No paper corpus at ...`.

**You can skip this step if you start the web interface with `python main.py` (see
"Running the app"): it builds the same corpus and the index by itself when they are
missing.** Do it by hand when you only use the terminal, the experiments or `adk web demo`.

The five papers behind the evaluation questions (`evals/questions.py`) must be in it,
or the metrics cannot find the expected sources. This query fetches them. In Windows
PowerShell 5.1 the inner quotes must be escaped with a backslash, as in the second line:

```powershell
$q = 'ti:"Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" OR ti:"Attention Is All You Need" OR ti:"BERT: Pre-training of Deep Bidirectional Transformers" OR ti:"LoRA: Low-Rank Adaptation of Large Language Models" OR ti:"Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"'
$q = $q -replace '"', '\"'
python -m retrieval fetch --query $q --max-results 100
python -m retrieval index
```

On macOS or Linux (bash) no escaping is needed: write `q='ti:"..." OR ti:"..."'` with
the same query, skip the `-replace` line and pass it as `--query "$q"`.

`fetch` saves the titles and abstracts to `data/corpus.jsonl`. `index` builds the vector
index in `data/chroma/`, and its first run downloads the embedding model (a few hundred
MB). Check that the five ids `2005.11401`, `1706.03762`, `1810.04805`, `2106.09685` and
`2201.11903` are in the corpus:

```bash
python -m retrieval search "retrieval-augmented generation" --top-k 5
```

The query also returns other papers with similar titles. That is fine.

**Use the same `corpus.jsonl` for all experiments.** arXiv results change over time, so
fetching again can give another corpus and the results of two runs are no longer
comparable. Copy the file between team members instead. Other options of the retrieval
commands are in [docs/RETRIEVAL.md](docs/RETRIEVAL.md).

## Running the app and tests

For the retrieval chat demo, run `python run_web.py` and open
http://127.0.0.1:8000. Select `research_demo`.
See [ADK Web demo instructions](docs/ADK_WEB.md) for configuration and examples.

`main.py` is the one entry point and has two modes. Both run the whole test suite first.

**Web interface.** Run it without a question:

```bash
python main.py
```

It checks `.env` (`GOOGLE_API_KEY`, `MODEL_LIGHT`, `MODEL_HEAVY`), builds the paper
corpus and the vector index when they are missing (step 6, it needs internet and the first
index downloads the embedding model), then serves the interface. Open
<http://127.0.0.1:8000>, choose `research_copilot` in the top left and type a question.
Stop it with Ctrl+C. See "Demo in the browser" for what the interface shows.

**Terminal.** Run it with a question:

```bash
python main.py "What problem does retrieval-augmented generation address?"
```

The app prints a short Markdown report with its sources, then `Verified: yes` or
`Verified: no`. It needs `MODEL_LIGHT` and `MODEL_HEAVY` in the local `.env`, and the
corpus from step 6.

**Current implementation.** The complete research pipeline includes context
compression, the Planner and the Critic. The Planner generates focused
sub-questions, retrieval branches search for relevant papers, the Writer
produces a report, and the Critic checks its claims. The Critic can trigger
one report revision after rejecting a report.

Both the Planner and Critic can be skipped when the remaining time budget
is insufficient. Their deadline-based skipping is recorded in run statistics.

Every start runs the whole test suite first. The app starts only if all tests pass
and total coverage is at least 80% (`fail_under` in `pyproject.toml`). Otherwise it
exits with code 1. To run only the tests and see the coverage report:

```bash
pytest
```

An HTML report is written to `htmlcov/`. New code needs tests, or coverage drops
below the threshold and the app will not start.

## Demo in the browser

The same pipeline can be tried in the ADK web interface. `python main.py` starts it for
you. To start it without the test run and the corpus check, from the repository root, with
the virtual environment active, your `.env` filled in and the corpus built (step 6):

```bash
adk web demo
```

Open the address it prints (<http://127.0.0.1:8000> by default), choose
`research_copilot` in the top left and type a research question. The interface shows
the agent steps, including parallel search branches, the Writer and the Critic.
The report is the Writer's answer. Two differences from `python main.py`: the demo
does not run the tests first, and it does not do the one revision after a rejecting Critic.

**Choosing the model from the chat.** `adk web` cannot show our own buttons, so the switch
is a command at the start of a message:

| Message | What happens |
|---------|--------------|
| `/lite What is LoRA?` | The Writer uses `MODEL_LIGHT` (`gemini-3.5-flash-lite`). No daily limit of 20. |
| `/heavy What is LoRA?` | The Writer uses `MODEL_HEAVY` again. |
| `What is LoRA?` | The same model as the last command in this chat. At the start of a chat: `MODEL_HEAVY`. |

The command is not part of the question. The choice stays for the whole chat, so type it
once. A new chat starts with `MODEL_HEAVY`. Only the Writer changes, the other agents always
use `MODEL_LIGHT`. To see which model answered, open the **State** tab of the session in
`adk web`: `writer_model_choice` is your choice and `writer_model_used` is the model name of
the last Writer call. Put the command and the question in one message: a message with only
`/lite` also runs the pipeline, on an empty question.

The last message of the chat is the Critic's verdict as raw JSON (`approved`,
`assessments`, ...), because the interface shows the answer of every agent in turn. The
report is the Writer's message above it.

### Before a presentation

The free tier can answer `503` (overload) or `429` (daily limit) at any moment, so
prepare the day before:

1. Check the quota of the heavy model, see "Models": with `MODEL_HEAVY=gemini-3.5-flash`
   there are only 20 requests per day. In the web interface start the chat with `/lite`
   (see above) for a day of demos, no change of `.env` needed.
2. Ask each question you plan to show once, with the cache on (the default). Ask it
   again: the second answer should come much faster, because most calls are replayed
   from `.cache/llm/` (see "Cache and retries" for what is asked again).
3. Keep the results of the benchmark and a screenshot of one good answer as a fallback.
4. If a question fails with `503`, ask it again after a minute. Do not change anything.

## Experiments

The evaluation compares five configurations, E0 to E4, using the same five
research questions and the same local arXiv corpus.

### Main E0-E4 benchmark

The configurations are:

| Configuration | Retrieval | Compression | Planner | Critic |
|----------------|-----------|-------------|---------|--------|
| E0 | Vector search | No | No | No |
| E1 | Hybrid search | No | No | No |
| E2 | Hybrid search | Yes (3000 words) | No | No |
| E3 | Hybrid search | Yes (3000 words) | Yes | No |
| E4 | Hybrid search | Yes (3000 words) | Yes | Yes |

E0 is a separate single-call baseline, implemented in
`evals/single_call_baseline.py`. It retrieves passages using vector search
(`hybrid=False`, k=8) and generates a report with exactly one LLM agent call.
It does not use context compression, the Planner or the Critic.

E1-E4 use the main pipeline through `answer_with_stats`. Each configuration
adds a capability to the preceding one.

The benchmark is implemented in `evals/run_benchmark.py`. It runs 25 jobs
(five configurations multiplied by five questions), saves successful results
after each run and can resume without repeating completed runs.

Run the benchmark with:

```bash
LLM_CACHE=off python -m evals.run_benchmark
```

The commands in this section set the variable in front of the command, which is bash
syntax. In Windows PowerShell set it first and then run the same command without the
prefix (the setting lasts for that window):

```powershell
$env:LLM_CACHE = "off"
python -m evals.run_benchmark
```

Results are saved under `outputs/evaluation/`:

- `results.csv` contains per-question retrieval, quality, cost and latency measurements.
- `reports/` contains the generated Markdown reports.
- `failures.jsonl` contains failed runs.
- `summary.csv` and `summary.md` contain aggregated evaluation metrics once the
  full benchmark matrix is complete.

Report quality is evaluated separately after report generation. The LLM judge is
implemented in `evals/quality_judge.py`, and the scoring runner is
`evals/score_reports.py`.

Run the quality scorer with a limited number of new judge requests:

```bash
LLM_CACHE=off python -m evals.score_reports --limit 5
```

The scoring process saves its progress and can be resumed by running the command
again. The limit applies to new judge requests, not to reports already scored.

Manual review is handled separately by `evals/manual_review.py`. The scoring
workflow creates a `manual_review.csv` template for recording human assessments.
The manual review module validates these scores and generates summary outputs.

### Time-budget experiment

A separate experiment investigates the relationship between execution time
budget and report quality.

It uses the E4 configuration with three time budgets:

- 30 seconds
- 60 seconds
- 120 seconds

Each budget is tested against the same five questions, resulting in 15 runs.

The runner is implemented in `evals/time_budget_experiment.py`:

```bash
LLM_CACHE=off python -m evals.time_budget_experiment
```

The experiment records actual latency, token usage, LLM calls and whether
the Planner or Critic was skipped because of the deadline.

The time budget is a soft deadline. It controls whether additional stages
should run, but does not forcibly terminate an LLM call that is already
in progress. Actual execution time can therefore exceed the configured
budget.

Time-budget reports and measurements are saved under
`outputs/evaluation/time_budget/`.

The corresponding LLM quality scoring runner is:

```bash
LLM_CACHE=off python -m evals.score_time_budget --limit 5
```

The `--limit` option restricts the number of new judge requests. The scoring
process can be resumed by running the same command again.

The time-budget evaluation produces a summary with mean quality, latency,
token usage, and Planner/Critic skip rates for each budget.

### Evaluation metrics

The evaluation considers:

- **Retrieval quality:** Recall@5 against the expected paper IDs.
- **Report quality:** independent LLM judge scores and manual review.
- **Cost:** LLM calls and input/output token counts.
- **Latency:** actual end-to-end execution time.
- **Time-budget behaviour:** Planner and Critic skip rates under
  different time constraints.

The LLM judge and manual review are separate evaluation methods.
Quality scores should be interpreted together with retrieval and
cost measurements, rather than as a standalone measure of system quality.

## Cache and retries

The free tier has low rate limits and sometimes answers with a temporary error, so
every model call is protected:

- **Retries.** A `429` (rate limit) or a `503` (high demand) is retried up to 4 times
  with a growing pause. Other errors are raised at once. Above all a `404` (the model is
  not available for your account) is never retried, because it will not go away.
- **Response cache.** Answers of the model are stored as JSON files in `.cache/llm/`
  (ignored by git), so repeating a run does not call the API again. Set
  `LLM_CACHE_DIR` to use another directory.
- **Switch it off for measurements.** The evaluation measures latency and token use,
  and a cached answer returns at once and costs no tokens. Set `LLM_CACHE=off` for
  every measured run. Delete `.cache/` to start fresh.
- **Repeats of a whole run.** When the API stays overloaded after the retries of every
  call, `python main.py "<question>"` repeats the whole run up to twice, 20 seconds
  apart. With the cache on the calls that worked are not asked again. The measured runs
  (`answer_with_stats`) never repeat a run, because the repeat would count into the
  latency. In the web interface nothing repeats: ask the same question again.
- **What the cache does not replay.** A question that the Planner splits into several
  sub-questions runs them in parallel branches, and the Writer and the Critic see the
  events of the branches in the order they finished, which differs from run to run. Their
  two calls are therefore asked again on a repeat, while the Planner, the Searchers and
  the Readers come from the cache. A question with one sub-question is replayed in full.
  So a repeat is cheaper and shorter, but not free of the API.

## Models

Model names live in `.env`, not in the code, so changing a model is a one-line edit.

| Variable      | Model                   | Used for                          |
|---------------|-------------------------|-----------------------------------|
| `MODEL_LIGHT` | `gemini-3.5-flash-lite` | Planner, Searcher, Reader, Critic |
| `MODEL_HEAVY` | `gemini-3.5-flash`      | Writer                            |

Google retires models often. Older models such as `gemini-2.5-flash` already return
`404` for new accounts. To see which models your key can use:

```bash
python -c "from dotenv import load_dotenv; load_dotenv(); from google import genai; c = genai.Client(); print([m.name for m in c.models.list() if 'gemini-3' in m.name])"
```

Use stable names, not `*-latest` aliases or `*-preview` models, so experiments stay
reproducible. Before choosing a model, check on the Gemini API pricing page that its
free tier column says **Free of charge**.

**Daily limit of the heavy model.** On our free-tier key `gemini-3.5-flash` and
`gemini-3.6-flash` share one quota of **20 requests per day** (the API's `429` message
names the metric `GenerateRequestsPerDayPerProjectPerModel-FreeTier` and the model
`gemini-3.6-flash` even for a call to `gemini-3.5-flash`). The Writer makes one call per
question, plus one for a revision, so about 20 questions per day and key are all that
`MODEL_HEAVY=gemini-3.5-flash` allows. The 25 runs of the benchmark do not fit in a day.
`gemini-3.5-flash-lite` answered normally the whole time and showed no such limit. For a
day of experiments set `MODEL_HEAVY=gemini-3.5-flash-lite` in `.env` (the whole team the
same, or the results are not comparable). For a demo in the web interface it is enough to
start the chat with `/lite` (see "Demo in the browser"). The reports may be a bit weaker than
with the larger model. The limit resets about once a day (the message says after how
long to retry). The limits can change, so read the `429` message before you plan a day.
Note that `.env.example` sets `MODEL_HEAVY=gemini-3.6-flash`, which has this limit.

## Project structure

```text
research-copilot/
├── agents/        ADK agents, the flow, skipping, cache, retries and run stats
├── demo/          the pipeline as an agent for `adk web`
├── retrieval/     search over the paper corpus
├── data/          your local corpus and vector index, built in step 6 (not in git)
├── context/       context compression
├── evals/         test questions, metrics and results
├── stubs/         stand-ins so the team can work in parallel
├── tests/         automated tests
├── docs/          contributing rules and the stage-by-stage documentation
├── main.py        the entry point: web interface or one question in the terminal
├── launcher.py    what `main.py` needs for the web interface: `.env` check, corpus, server
├── contracts.py   shared data types and function signatures
├── CLAUDE.md      instructions for AI assistants working in this repo
├── .env.example   template for your local .env
└── requirements.txt
```

## Working in the team

Read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) before your first change. In short:

- `main` is protected. Every change goes through a pull request.
- A pull request needs at least one approval from another team member.
- Branch names use a prefix: `feat/`, `fix/`, `docs/`, `chore/`, `test/`.
- Everything (code, comments, commits, pull requests) is written in English.

## Troubleshooting

| Problem | Cause and fix |
|---------|---------------|
| `RuntimeError: Cannot send a request, as the client has been closed` | The client was not kept in a variable and got closed. Write `c = genai.Client()` and then use `c`. |
| `404 NOT_FOUND ... no longer available to new users` | The model was retired. List the models (command above) and pick a current one. |
| `503 UNAVAILABLE ... high demand` | Temporary overload on Google's side. About one call in six answered it in our test, even one at a time, and the errors come in bursts. Ask the same question again after a minute: with the cache on, the calls that worked are not asked again. |
| `429 RESOURCE_EXHAUSTED` | Free-tier limit reached. If the message says `per day` (for example `limit: 20, model: gemini-3.6-flash`), wait until it says you can retry, or use `MODEL_HEAVY=gemini-3.5-flash-lite`, see "Models". |
| `API key not valid` | Check `.env`: no quotes, no spaces around `=`, the whole key is present. |
| `(.venv)` is missing in the prompt | The environment is not activated. Run the activation command from step 2. |
| `Error: No paper corpus at ...` or `Corpus is missing` | The corpus is not built. Do step 6 (`fetch`, then `index`). |
| `unrecognized arguments: ... OR ti:...` in `python -m retrieval fetch` | Windows PowerShell 5.1 dropped the inner quotes of the query. Escape them as in step 6 (`-replace '"', '\"'`). |
| `ModuleNotFoundError: No module named 'rank_bm25'` (or `arxiv`, `chromadb`) | The dependencies are not installed after pulling. Run `pip install -r requirements.txt` in the active environment. |

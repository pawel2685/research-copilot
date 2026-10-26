# Research Copilot

A multi-agent research assistant built with [Google ADK](https://google.github.io/adk-docs/).
Given a research question, it finds papers on arXiv, summarises them, checks its
own claims and writes a short report with sources. Five agents work together, and
two of them (Planner and Critic) are skipped when the time budget runs short.

> Status: project setup. The agents are not implemented yet.

## Requirements

- Python 3.12
- Git
- A free Google account (for the Gemini API key)

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

### 3. Get a Gemini API key (free)

Every team member creates their own key. Free-tier limits are counted per key, so a
shared key would run out quickly.

1. Open <https://aistudio.google.com/apikey> and sign in with a Google account.
2. Click **Create API key**.
3. Choose **Default Gemini Project** (or create a new project for this repo). Do not
   pick an existing project that may have billing enabled.
4. Name the key `research-copilot` and create it, then copy it.
5. Check on the keys list that the **Billing Tier** column says **Free tier**.

Do not set up billing. On the free tier you cannot be charged: when a limit is
reached the API returns an error instead of a bill. On the free tier Google may use
the data you send to improve its services, so never send anything confidential.

You do not need the project name or the project number. They are only used by
Vertex AI, which this project does not use.

### 4. Create your `.env` file

```powershell
Copy-Item .env.example .env
```

Open `.env` and replace the placeholder with your key. No quotes and no spaces
around `=`:

```
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

## Running the app and tests

```bash
python main.py
```

Every start runs the whole test suite first. The app starts only if all tests pass
and total coverage is at least 80% (`fail_under` in `pyproject.toml`). Otherwise it
exits with code 1. To run only the tests and see the coverage report:

```bash
pytest
```

An HTML report is written to `htmlcov/`. New code needs tests, or coverage drops
below the threshold and the app will not start.

## Models

Model names live in `.env`, not in the code, so changing a model is a one-line edit.

| Variable      | Model                   | Used for                          |
|---------------|-------------------------|-----------------------------------|
| `MODEL_LIGHT` | `gemini-3.5-flash-lite` | Planner, Searcher, Critic         |
| `MODEL_HEAVY` | `gemini-3.5-flash`      | Writer                            |

Google retires models often. Older models such as `gemini-2.5-flash` already return
`404` for new accounts. To see which models your key can use:

```bash
python -c "from dotenv import load_dotenv; load_dotenv(); from google import genai; c = genai.Client(); print([m.name for m in c.models.list() if 'gemini-3' in m.name])"
```

Use stable names, not `*-latest` aliases or `*-preview` models, so experiments stay
reproducible. Before choosing a model, check on the Gemini API pricing page that its
free tier column says **Free of charge**.

## Project structure

```
research-copilot/
├── agents/        ADK agents and the skipping logic
├── retrieval/     search over the paper corpus
├── context/       context compression
├── evals/         test questions, metrics and results
├── stubs/         stand-ins so the team can work in parallel
├── tests/         automated tests
├── docs/          project documentation
├── contracts.py   shared data types and function signatures
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
| `503 UNAVAILABLE ... high demand` | Temporary overload on Google's side. Wait a few minutes and retry. |
| `429 RESOURCE_EXHAUSTED` | Free-tier rate limit reached. Wait a minute, or until the next day for the daily limit. |
| `API key not valid` | Check `.env`: no quotes, no spaces around `=`, the whole key is present. |
| `(.venv)` is missing in the prompt | The environment is not activated. Run the activation command from step 2. |

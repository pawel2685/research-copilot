# Contributing

These rules apply to everyone on the team. Keep them short, follow them always.

## Language

Everything is written in English: code, comments, branch names, commit
messages, pull requests, and docs.

## Branches

- `main` is protected. Nobody pushes to it directly.
- Every change goes through a pull request.
- Branch names use a prefix, then a short kebab-case description:

| Prefix  | Use for                          | Example              |
|---------|----------------------------------|----------------------|
| `feat/` | new functionality                | `feat/hybrid-search` |
| `fix/`  | bug fix                          | `fix/empty-query`    |
| `docs/` | documentation only               | `docs/contributing`  |
| `chore/`| setup, config, dependencies      | `chore/add-pytest`   |
| `test/` | tests only                       | `test/skip-logic`    |

## Commits

Start the message with the same prefix, then a short imperative summary:

```
feat: add Chunk and Report contracts
fix: handle empty search query
docs: add contributing rules
```

Keep commits small and focused. One logical change per commit.

## Pull requests

1. Create a branch from an up-to-date `main`.
2. Push the branch and open a pull request into `main`.
3. At least **one approval** from another team member is required to merge.
4. If you push new commits after an approval, it is dismissed and you need a new
   one. You cannot approve the latest push of your own pull request.
5. Keep pull requests small. Describe what changed and why.
6. Resolve all review comments before merging.

## Working on your branch

```bash
git switch main
git pull
git switch -c feat/your-change
```

After committing, publish the branch and open the pull request on GitHub.

## Secrets

Never commit API keys or tokens. Keep them in a local `.env` file, which is in
`.gitignore`.

## Shared files

`contracts.py` is shared by the whole team. Change it only in a separate pull
request that all team members approve.
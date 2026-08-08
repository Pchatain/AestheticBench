always use uv instead of python or pip.

## API Keys / Environment

`OPENROUTER_API_KEY` lives in `.env.local` (gitignored). Nothing in the code calls
`load_dotenv`, so any command that hits OpenRouter must load it via uv's `--env-file` flag:

```
uv run --env-file .env.local python main.py db grade ...
```

Without `--env-file` the command fails at `Config.from_env()`
(`packages/backend/src/moral_bench/config.py:34`) with "OPENROUTER_API_KEY not found".

## Git Commits

Never add Co-Authored-By lines to commits. Commits should be authored by the user only.

## Server Hot-Reload

The frontend (Vite) and backend (FastAPI with uvicorn --reload) have hot-reload enabled. Never suggest restarting these servers - changes are picked up automatically.

## Debugging Backend Issues

Always check the backend server logs when things aren't working. Use:
```
tmux capture-pane -t <session_name> -p -S -100
```
to see recent logs. The user will provide the tmux session name.

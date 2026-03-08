always use uv instead of python or pip.

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

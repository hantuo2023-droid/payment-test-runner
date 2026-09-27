# Payment Test Runner
- Read TASK_SPEC.md and TASK_STATE.md before continuing. Preserve passed work.
- Stack: Next.js, FastAPI, SQLite/Alembic, Playwright Chromium; no mock fallback.
- Production tasks only verify UI. Binding requires an explicitly authorized non-production target; built-in sandbox uses synthetic fixtures only.
- Never expose passwords, card numbers, CVC, cookies, or tokens in lists, logs, exports, screenshots, or traces. Encrypt secrets at rest.
- Unknown browser outcomes are ERROR/UNKNOWN_RESULT. Wait through redirects. Stop closes browser and finalizes evidence.
- Validate each phase, commit passing milestones, update TASK_STATE.md. Mark unexecuted checks NOT TESTED.
- Keep six navigation entries and Chinese field help. No workflow or selector editor.

---
name: m_save
description: Snapshot the current work into the standing handoff file `.m_last_task.md` at the project root — task, what's done, what's in progress, next step, key files, decisions, blockers, and the commands to build/test. Overwrites the previous snapshot (one standing file, not a log). Use before ending a session, switching tasks, or when context is getting long, so /m_go can resume later.
disable-model-invocation: true
---

# m_save

Write a **complete, self-contained snapshot** of the current work to `.m_last_task.md` in the project root. This is the standing "last task" file — always one file, always overwritten. Its counterpart `/m_go` reads it in a fresh session and continues.

## Inputs
- `$ARGUMENTS` (optional): extra notes to include verbatim in the snapshot (e.g. "stop after step 3", a hint for the next session).

## Rules

- **Write for a stranger.** The next session has NONE of this conversation. No "as discussed above", no shorthand invented mid-chat. Every file mentioned gets its full repo-relative path; every command is copy-pasteable.
- **One standing file.** Always `.m_last_task.md` at the project root. Overwrite what's there — do not append, do not create dated copies. (If the current file describes a *different unfinished task*, mention that in one line under "Previous task" so it isn't silently lost.)
- **No secrets.** Never write tokens, passwords, keys, or prod credentials into the file — reference the secret's *name/location* (env var, vault entry) instead.
- **Gitignore:** if `.m_last_task.md` is not covered by `.gitignore`, append it (create `.gitignore` if missing) — this file is personal working state, not repo content. Skip silently if already ignored.
- If an `.m_plan/<slug>/` run is active, don't duplicate its content — link the slug and state which step/`V-*` row you're on; `09_verification.md` stays the oracle.

## Snapshot format

```markdown
# Last task — <one-line task title>
_Saved: <YYYY-MM-DD HH:MM> · branch: <git branch> · last commit: <short-hash subject>_

## Task
<1–3 sentences: what the user asked for, in full — the original goal, not the current sub-step.>

## State
- ✅ Done: <bullet per completed chunk, with file paths>
- 🔧 In progress: <exactly what is half-finished and where it stands>
- ⏭ Next step: <the single concrete action to take first when resuming>

## Key files
- `<path>` — <why it matters / what was changed>

## Decisions & context
<Non-obvious decisions made, approaches rejected and why, constraints from the user — anything the next session couldn't rediscover from the diff.>

## Blockers / open questions
<Anything waiting on the user or an external system, or "none".>

## How to verify
<Copy-pasteable build/test/run commands and what "working" looks like.>

## Plan link (if any)
<`.m_plan/<slug>/` — current step N, open `V-*` rows — or "none".>

## Notes
<$ARGUMENTS verbatim, if provided.>
```

Fill every section; write "none" rather than deleting a heading. Get branch/commit from `git branch --show-current` and `git log -1 --oneline`; if not a git repo, write "no git".

## Procedure

1. Gather: current task and conversation state (from context), `git status`/`git log -1`/branch, any active `.m_plan/<slug>/`.
2. Write `.m_last_task.md` per the format above (overwrite).
3. Ensure it's gitignored (rule above).
4. Confirm to the user in 2–3 lines: where it was saved and what the recorded "next step" is. Do not dump the whole file back into chat.

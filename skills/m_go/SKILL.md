---
name: m_go
description: Resume the last saved work session — read the standing handoff file `.m_last_task.md` (written by /m_save) at the project root, restore context by reading the key files it names, then continue from its recorded "next step". Use at the start of a fresh session to pick up exactly where the previous one stopped.
disable-model-invocation: true
---

# m_go

Read `.m_last_task.md` from the project root (written earlier by `/m_save`), rebuild working context, and **continue the work** — not just summarize it.

## Inputs
- `$ARGUMENTS` (optional): adjustments to the resumed task ("skip the tests part", "focus on X first"). Apply them on top of the saved plan.

## Procedure

1. **Read the snapshot.** Read `.m_last_task.md` at the project root.
   - Missing → tell the user there is no saved task (`/m_save` hasn't been run here) and stop.
   - Present in a parent directory but not here → mention it and ask which project they meant; don't guess.
2. **Sanity-check freshness.** Compare the snapshot's branch/commit line with `git branch --show-current` and `git log -1 --oneline`. If the repo has moved on (different branch, new commits, dirty tree not explained by the snapshot), say so in one line and account for it — the snapshot describes intent, the repo describes reality; reality wins.
3. **Restore context.** Read every file under "Key files" (relevant parts, not blindly whole files). If the snapshot links an `.m_plan/<slug>/` run, open `05_step_plan.md` and `09_verification.md` — for a plan run, prefer resuming via `/m_plan_implement` (it owns the step-walking and `V-*` bookkeeping) and say you're doing so.
4. **Brief the user (short).** 3–5 lines: the task, what's done, and the next step you're about to take. This is a status line, not a report — then keep going without waiting, unless "Blockers / open questions" contains something only the user can answer (ask exactly that, then proceed).
5. **Continue the work** from "⏭ Next step", honoring "Decisions & context" (don't re-litigate settled decisions) and using "How to verify" to check your results.
6. **Keep the snapshot current.** When the resumed task completes, or the user switches to something else mid-run, update `.m_last_task.md` accordingly (an `/m_save`-style overwrite) so the file never describes stale work as pending.

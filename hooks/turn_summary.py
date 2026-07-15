#!/usr/bin/env python3
"""
End-of-WORK summary hook (Stop).

Fires the «Что сделал» / «Что дальше» / «Задача» text summary only when the
whole piece of work looks FINISHED — not after every intermediate agent turn.

Stop is the only hook event that ends an agent response, and it fires on every
turn: including intermediate ones where the agent merely paused while background
subagents / background Bash tasks / workflows / scheduled wakeups are still
running (their notifications re-invoke the agent later). v3.1.0 summarized on
every such stop, spamming the chat. v3.2.0 adds two gates:

  1. PENDING-WORK GATE — scan the transcript segment since the last genuine
     human prompt; if background work appears to still be in flight
     (backgrounded Agent/Bash/Workflow calls not yet matched by
     task-notifications, or a live ScheduleWakeup), stay silent. The summary
     is emitted on the LAST turn, when nothing is pending.
  2. ONCE-PER-PROMPT GATE — a state file remembers the human-prompt position
     already summarized; even if pending-detection ever misses, at most one
     summary is produced per human request.

Flow per stop:
  Stop fires (stop_hook_active=false)
    -> trivial segment (< MIN_TOOLS tools)          -> silent
    -> background work still pending                -> silent
    -> this prompt already summarized               -> silent
    -> else emit {"decision":"block"} with the summary instruction;
       the agent writes the three blocks, then stops.
  Stop fires again with stop_hook_active=true -> silent. No loop.

FAIL-OPEN: any error -> exit 0 with no output, so a bug here can never trap the
session in a block loop.
"""
import sys, json, os, tempfile, hashlib

# --- tunables (env-overridable) ---------------------------------------------
MIN_TOOLS = int(os.environ.get("CLAUDE_SUMMARY_MIN_TOOLS", "2"))
MAX_PROMPT_CHARS = 800   # how much of the user's prompt to pass as paraphrase source
REASON_CHAR_CAP = 9500   # hook output strings are capped at 10k

# background-by-default tools (desktop Agent tool, Workflow) vs tools that are
# background only when explicitly asked (CLI Task subagents, Bash)
BG_DEFAULT_TOOLS = {"Agent", "Workflow"}
BG_OPT_IN_TOOLS = {"Task", "Bash"}


# --- transcript parsing -----------------------------------------------------
def _content_blocks(obj):
    msg = obj.get("message") or {}
    content = msg.get("content", "")
    if isinstance(content, list):
        return content
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return []


def _text_of(obj):
    return " ".join(
        b.get("text", "") for b in _content_blocks(obj)
        if isinstance(b, dict) and b.get("type") == "text"
    )


def is_human_prompt(obj):
    """True only for a genuine user-typed prompt (not a tool_result carrier,
    not meta, not a slash-command expansion / sidechain / task-notification)."""
    if obj.get("type") != "user":
        return False
    if obj.get("isMeta") or obj.get("isSidechain") or obj.get("isCompactSummary"):
        return False
    for b in _content_blocks(obj):
        if isinstance(b, dict) and b.get("type") == "tool_result":
            return False  # tool result carrier, not a human turn
    t = _text_of(obj).strip()
    if not t:
        return False
    # skip slash-command expansions / injected stdout / harness notifications
    if t.startswith("<command-") or t.startswith("<local-command"):
        return False
    if "<task-notification" in t or t.startswith("<system-reminder"):
        return False
    return True


def parse_turn(transcript_path):
    """Analyze the segment last-human-prompt -> EOF."""
    if not transcript_path or not os.path.exists(transcript_path):
        return None

    lines = []
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                lines.append(json.loads(line))
            except Exception:
                continue

    # index of last genuine human prompt
    start_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if is_human_prompt(lines[i]):
            start_idx = i
            break
    if start_idx is None:
        return None

    last_prompt = _text_of(lines[start_idx])

    tools_total = 0
    bg_started = 0          # backgrounded Agent/Task/Workflow/Bash calls
    notifications = 0       # task-notifications that came back
    wakeup_pending = False  # a ScheduleWakeup without stop:true is live

    for obj in lines[start_idx:]:
        otype = obj.get("type")
        if otype == "assistant":
            for b in _content_blocks(obj):
                if not (isinstance(b, dict) and b.get("type") == "tool_use"):
                    continue
                tools_total += 1
                name = b.get("name") or ""
                inp = b.get("input") or {}
                if name in BG_DEFAULT_TOOLS:
                    if inp.get("run_in_background") is not False:
                        bg_started += 1
                elif name in BG_OPT_IN_TOOLS and inp.get("run_in_background"):
                    bg_started += 1
                elif name == "ScheduleWakeup":
                    wakeup_pending = not inp.get("stop")
        elif otype in ("user", "system"):
            txt = _text_of(obj)
            if "<task-notification" in txt or "task-notification" in str(obj.get("subtype") or ""):
                notifications += 1

    pending = wakeup_pending or (bg_started > notifications)
    return {
        "tools_total": tools_total,
        "last_prompt": last_prompt,
        "pending": pending,
        "prompt_key": "%d:%s" % (
            start_idx,
            hashlib.sha1(last_prompt.encode("utf-8", "replace")).hexdigest()[:12],
        ),
    }


# --- once-per-prompt state ---------------------------------------------------
def _state_path(session_id):
    safe = "".join(c for c in (session_id or "unknown") if c.isalnum() or c in "-_")[:64]
    return os.path.join(tempfile.gettempdir(), "claude_turn_summary_%s.state" % safe)


def already_summarized(session_id, prompt_key):
    try:
        with open(_state_path(session_id), "r", encoding="utf-8") as f:
            return f.read().strip() == prompt_key
    except Exception:
        return False


def mark_summarized(session_id, prompt_key):
    try:
        with open(_state_path(session_id), "w", encoding="utf-8") as f:
            f.write(prompt_key)
    except Exception:
        pass  # fail-open: worst case is a duplicate summary


# --- output builder ---------------------------------------------------------
def build_reason(last_prompt):
    """End-of-work summary: three plain-text blocks (NO widget, NO show_widget,
    NO ledger). Owner's personal hook text, Russian by design (see AGENTS.md
    conventions)."""
    prompt = (last_prompt or "").replace("\n", " ").strip()[:MAX_PROMPT_CHARS]
    reason = (
        "[end-of-work summary hook] Вся работа по запросу завершена. Обычным "
        "форматированным ТЕКСТОМ (НИКАКИХ виджетов, НЕ вызывай show_widget) "
        "сделай по порядку:\n\n"
        "1) Блок «Что сделал» — 1–4 коротких пункта: итог ВСЕЙ выполненной работы "
        "по этому запросу (не только последнего хода).\n\n"
        "2) Блок «Что дальше» — 1–3 коротких пункта: логичный следующий шаг.\n\n"
        "3) В САМОМ КОНЦЕ блок «Задача» — ОДНО предложение: суть того, что я просил "
        f"(НЕ дословно). Источник для перефраза (не цитируй целиком): «{prompt}»\n\n"
        "Кроме этих трёх блоков в чат больше ничего не выводи."
    )
    return reason[:REASON_CHAR_CAP]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # hook stdout is cp1252 on Windows
    except Exception:
        pass
    try:
        hook_input = json.loads(sys.stdin.read())
    except Exception:
        return  # fail-open

    # second firing after our own block: do nothing -> breaks the loop
    if hook_input.get("stop_hook_active"):
        return

    turn = parse_turn(hook_input.get("transcript_path", ""))
    if not turn:
        return  # nothing to summarize -> stay silent, fail-open

    # trivial segment (conversational, few/no tools) -> no forced summary
    if turn["tools_total"] < MIN_TOOLS:
        return

    # background work still in flight -> not the end yet, stay silent
    if turn["pending"]:
        return

    # this human prompt was already summarized -> stay silent
    session_id = hook_input.get("session_id", "")
    if already_summarized(session_id, turn["prompt_key"]):
        return

    mark_summarized(session_id, turn["prompt_key"])
    print(json.dumps({
        "decision": "block",
        "reason": build_reason(turn["last_prompt"]),
        "suppressOutput": True,
    }))  # ensure_ascii=True -> pure-ASCII output, encoding-safe for any consumer


if __name__ == "__main__":
    main()

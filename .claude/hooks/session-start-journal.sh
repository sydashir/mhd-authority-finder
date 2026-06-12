#!/bin/bash
# Claude Code has no PreCompact hook (checked 2026-06-12); SessionStart fires on
# startup/resume/clear/compact, so this re-arms the journal rule after compaction too.
latest=$(ls -1 journal/SESSION-*.md 2>/dev/null | sort | tail -n 1)
if [ -z "$latest" ]; then
  exit 0
fi
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Session journal rule is active (CLAUDE.md working rules). Read the most recent journal now as part of context rebuild: %s. Write a NEW journal BEFORE compaction (~90%% context), at session end, and before risky long-running operations; update journal/INDEX.md each time."}}\n' "$latest"

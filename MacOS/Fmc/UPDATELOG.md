# updatelog

## further task
- Consider trimming the fm transcript when it approaches the 8192-token ceiling; it currently only ever grows.
- Routing missed "ask.py 里 BASICS 这个常量写了什么" (title "ask.py 分流器" is in the list). Long questions carrying instructions seem to throw the classifier off; worth a larger test set.

## v1.1
- Split classification and small talk into two separate `fm` calls. The routing schema no longer has a `reply` field at all, so the model cannot speak while classifying, and the small-talk call no longer sees the 66-title list. Doing both in one call let the list bleed into casual answers — asked for the date it replied with the date and then "这个话题涉及容器管理，建议谨慎部署"
- Routing is now stateless; stickiness already handles follow-ups, so the classifier does not need conversation history. The conversation transcript carries only the chat persona
- Injects the current date into both instruction sets; without it the model answers from training data (observed: 2024-04-05)
- Costs one extra ~1s local call per small-talk turn

## v1.0
- Initial tool: routes each question between the on-device Apple foundation model (`fm`) and Claude Code. Small talk is answered locally, offline and free; anything touching a topic in the Claude memory index is handed off to `claude -p`
- Feeds `fm` only the 66 memory titles (~476 tokens) instead of the full index (~3088), leaving most of the 8192-token window for the conversation itself
- Three entry points: `fmc '<question>'` one-shot, `fmc` conversation mode, `cat f | fmc` treats stdin as a single question
- Conversation mode uses sticky handoff: once a topic is hit every following turn goes to Claude until `/fm` releases it. Follow-ups such as "那改成别名要怎么写" carry no topic keyword at all, so without stickiness the 3B model would classify them as small talk and answer from nothing
- Keeps Claude-side continuity with a self-generated `--session-id`, then `--resume` on that same uuid. Deliberately avoids `-c`, which attaches to the most recent session and would cross into unrelated ones
- Discards the `reply` field whenever `escalate` is true: `fm` only ever sees titles, so anything it says about their contents is fabricated
- Validates `topic` against the title list and drops it when absent. It reaches Claude as a hint only, never as fact — measured accuracy was 8/8 on the escalate decision but only 6/8 on which topic was hit
- Writes just the first line (150 chars) of each Claude answer back into the fm transcript; echoing full answers would exhaust the context window within a few turns
- Pre-authorises Claude with a read-only tool allowlist, since `claude -p` cannot obtain approval when running non-interactively — without it Claude stops and asks instead of answering. Verified: reading files works, deleting one is refused
- Does not use `--permission-mode auto`: it was measured letting a destructive operation through (asked to delete a probe file, it deleted it). A blocklist cannot cover every dangerous command, so the allowlist is the only reliable form here
- `--allowedTools` takes variadic values and will swallow the following prompt as a tool name, so it must be passed in the `--allowedTools=...` form
- Exact prefix patterns do not match the command forms Claude actually writes: `Bash(git log*)` never matches `git -C <path> log`. git is therefore left out of the allowlist entirely rather than opened up as `Bash(git *)`, which would also admit `git push`
- `Bash(ssh*)` is the widest grant in the allowlist — the remote end can run anything. Remove it to tighten

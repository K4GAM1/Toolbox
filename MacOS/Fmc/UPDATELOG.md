# updatelog

## further task
- Consider trimming the fm transcript when it approaches the 8192-token ceiling; it currently only ever grows. Hitting the ceiling means restarting the conversation.
- `topic` accuracy stays around 6/8 no matter how the prompt is worded. It is only ever passed to Claude as a hint, so this is tolerable, but a larger test set would tell whether it is worth keeping at all.
- Only the machine list in `BASICS` is hardcoded and will go stale; the topic list is read from MEMORY.md at every run and needs no maintenance.

## v1.3
- **Streams Claude's answer instead of blocking on it.** `claude -p` with the default `--output-format text` does not stream at all: a 34-second answer kept the screen empty for 33.8s and then dumped everything at once. Switched to `--output-format stream-json --verbose --include-partial-messages` and printing `text_delta` events as they arrive — first characters now appear at ~1.2s. `thinking_delta` events are deliberately not shown
- Appends a style instruction (`--append-system-prompt`) telling Claude this is a command-line conversation: three to five sentences, no headings or sections. Without it answers ran over a thousand characters, which also made them slower to generate. The napcat test case went from >1000 characters to 212
- Measured latency, for reference: `fm` is not the bottleneck — 1.69s on the very first call (model load), 0.25s afterwards, 0.73s for a classification with the 493-token instructions, 0.42s for a small-talk answer, so about 1.15s for a full small-talk turn. `claude -p` takes ~7s for a short answer and ~34s for a long one; `--model haiku` was only ~1s faster, so the model is not the lever — the output length and the streaming are

## v1.2
- Renamed from `ask` to `fmc` (directory, script, symlink and the tool's own usage text). `ask_claude()` keeps its name — it means "ask Claude", not the tool
- **Excludes the "协作偏好" group of MEMORY.md from the classifier list.** Those entries are behaviour rules for Claude, not queryable topics, and they poisoned the matching: "git 熟练度" made "git rebase 和 merge 有什么区别" escalate. Dropping that group took accuracy from 9/12 to 11/12 and the list from 68 to 56 titles (569 → 493 tokens). The one remaining miss is a follow-up with no topic keyword, which stickiness already covers
- Tested the alternative "escalate whenever fm cannot answer" design — classify by whether the question is about Max at all, no topic list. **Measured worse: 6/10 vs 7/10, and it fails in the dangerous direction**: asked about PZ void-stuck and napcat 1006514 it judged itself capable and then fabricated. The model does not know what it does not know, so self-assessment cannot carry the routing decision
- Dropped the Toolbox location from `BASICS`; hardcoded facts in the persona are easy to trip over and it was not needed
- Conversation mode now removes its temporary transcript directory on exit; it used to leave one behind in $TMPDIR per run
- Auth failures now print what to actually check instead of relaying claude's raw error. The usual cause is not an expired token but a shell started before the token was written — its environment is a snapshot from launch time

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

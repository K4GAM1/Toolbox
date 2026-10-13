#!/usr/bin/env python3
"""分流器：闲聊由本地 fm 答，涉及记忆库话题的转 claude -p。

  ask.py '问题'        单次问答
  ask.py               进入对话模式（命中话题后粘滞在 Claude，/fm 放开）
  cat f | ask.py       把 stdin 当一个问题
"""
import io, json, os, re, subprocess, sys, tempfile, uuid

MEMORY = os.path.expanduser(
    "~/.claude/projects/-Users-max-Develop-Library-Claude-code/memory/MEMORY.md")
PROJECT = "/Users/max/Develop Library/Claude_code"  # claude -p 只在此 cwd 下加载 memory

BASICS = ("Max 用中文交流，人在日本。他的机器：eeast(Mac mini)、ceast(Windows)、"
          "deast(Arch，与 ceast 同一台物理机)、n1(OpenWrt 软路由)、hakuto(实验室 Windows)。"
          "Toolbox 工具仓库在 ceast 的 D 盘，按操作系统分组。")

# claude -p 在非交互下拿不到权限批准，所以这里预授权。只给只读。
# 不用 --permission-mode auto：实测它会放行破坏性操作（让它删一个探针文件，真删了）。
# 注意 --allowedTools 是可变参数，必须写成 --allowedTools=... 的等号形式，
# 否则它会把后面的 prompt 一起吞成工具名，报"没有提供输入"。
# 精确前缀模式匹配不上实际命令形式（Bash(git log*) 匹配不到 git -C <path> log），
# 所以这里不收 git；要看仓库状态让 Claude 用 Read 读，或自己跑。
# Bash(ssh*) 是这份白名单里最大的口子——远程那头能执行任意命令。要收紧就删掉它。
CLAUDE_ALLOW = ("Read,Grep,Glob,WebSearch,"
                "Bash(ls*),Bash(cat*),Bash(head*),Bash(tail*),Bash(grep*),Bash(find*),"
                "Bash(ssh*),Bash(ping*),Bash(tailscale*),Bash(defaults read*),Bash(fm *)")

SCHEMA = {
    "title": "Route", "type": "object", "additionalProperties": False,
    "required": ["escalate"], "x-order": ["escalate", "topic", "reply"],
    "properties": {
        "escalate": {"type": "boolean", "description": "用户的话是否涉及话题清单里的内容"},
        "topic": {"type": "string", "description": "命中的话题标题，必须从清单里原样抄写"},
        "reply": {"type": "string", "description": "没命中时的直接回答，一两句话"},
    },
}


def uid():
    return str(uuid.uuid4()).upper()


def titles():
    return re.findall(r"^- \[([^\]]+)\]", io.open(MEMORY, encoding="utf-8").read(), re.M)


def instructions(tl):
    return (f"你是 Max 的助手兼分流器。{BASICS}\n"
            f"他记忆库里已有的话题清单：\n{'、'.join(tl)}\n"
            "规则：用户的话涉及清单里某个话题时，escalate=true 并把那个标题原样抄进 topic；"
            "无关的闲聊则 escalate=false 并用 reply 直接回答。topic 只能是清单里的原文。")


def entry(role, text, **extra):
    e = {"id": uid(), "role": role, "contents": [{"id": uid(), "text": text, "type": "text"}]}
    e.update(extra)
    return e


def new_transcript(path, inst):
    doc = {"modelName": "system",
           "transcript": {"transcript": {"entries": [entry("instructions", inst)]},
                          "version": "1.1", "type": "FoundationModels.Transcript"}}
    io.open(path, "w", encoding="utf-8").write(json.dumps(doc, ensure_ascii=False))


def append_turn(path, q, a):
    """把一轮问答补进 transcript，好让 fm 知道这段聊过什么。"""
    doc = json.loads(io.open(path, encoding="utf-8").read())
    es = doc["transcript"]["transcript"]["entries"]
    es.append(entry("user", q, options={}, contextOptions={}))
    es.append(entry("response", a))
    io.open(path, "w", encoding="utf-8").write(json.dumps(doc, ensure_ascii=False))


def route(q, tl, transcript=None):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(SCHEMA, f)
        schema = f.name
    cmd = ["fm", "respond", "--no-stream", "--schema", schema]
    if transcript:  # 对话模式：上下文走 transcript，instructions 已在里面
        cmd += ["--resume", transcript, "--save-transcript", transcript]
    else:
        cmd += ["-i", instructions(tl)]
    try:
        r = subprocess.run(cmd + [q], capture_output=True, text=True)
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"escalate": False,
                "reply": f"(fm 返回异常: {r.stdout.strip()[:120]}{r.stderr.strip()[:120]})"}
    finally:
        os.unlink(schema)


def ask_claude(q, sid, hit=None, new=False):
    """new=True 用这个 sid 开新会话，否则续接已有的。"""
    prompt = f"{q}\n\n（提示：记忆库里可能有「{hit}」这条相关）" if hit else q
    flag = ["--session-id", sid] if new else ["--resume", sid]
    r = subprocess.run(["claude", "-p", f"--allowedTools={CLAUDE_ALLOW}"] + flag + [prompt],
                       cwd=PROJECT, capture_output=True, text=True)
    return (r.stdout or r.stderr).strip()


def oneshot(q):
    tl = titles()
    d = route(q, tl)
    if not d.get("escalate"):
        print(d.get("reply") or "(fm 没给出回答)")
        return 0
    # escalate 时 fm 只有标题没有内容，它填的 reply 是编的，丢弃。
    hit = d.get("topic") if d.get("topic") in tl else None
    print(f"[转 Claude{'：' + hit if hit else ''}]", file=sys.stderr)
    print(ask_claude(q, str(uuid.uuid4()), hit, new=True))
    return 0


def repl():
    tl = titles()
    t = os.path.join(tempfile.mkdtemp(prefix="ask-"), "chat.json")
    new_transcript(t, instructions(tl))
    sid, sticky = None, False
    print("fm 对话中。命中记忆话题会粘滞到 Claude，/fm 放开，/q 退出。")
    while True:
        try:
            q = input("\n[claude] > " if sticky else "\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not q:
            continue
        if q in ("/q", "/quit", "/exit"):
            break
        if q == "/fm":
            sticky = False
            print("(已放开，回到 fm)")
            continue

        if sticky:
            a = ask_claude(q, sid)
            print(a)
            append_turn(t, q, a.split("\n")[0][:150])  # 只回灌一句，别吃光 8192
            continue

        d = route(q, tl, transcript=t)
        if not d.get("escalate"):
            print(d.get("reply") or "(fm 没给出回答)")
            continue
        hit = d.get("topic") if d.get("topic") in tl else None
        print(f"[转 Claude{'：' + hit if hit else ''}]", file=sys.stderr)
        sid = str(uuid.uuid4())
        a = ask_claude(q, sid, hit, new=True)
        print(a)
        append_turn(t, q, a.split("\n")[0][:150])
        sticky = True
    print("bye")
    return 0


def main():
    arg = " ".join(sys.argv[1:]).strip()
    if arg:
        return oneshot(arg)
    if not sys.stdin.isatty():
        q = sys.stdin.read().strip()
        return oneshot(q) if q else 1
    return repl()


sys.exit(main())

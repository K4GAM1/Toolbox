#!/usr/bin/env python3
"""分流器：闲聊由本地 fm 答，涉及记忆库话题的转 claude -p。

  ask '问题'        单次问答
  ask               进入对话模式（命中话题后粘滞在 Claude，/fm 放开）
  cat f | ask       把 stdin 当一个问题
"""
import datetime, io, json, os, re, subprocess, sys, tempfile, uuid

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

# 分类和闲聊拆成两次调用。这个 schema 里故意没有 reply 字段——让模型只做分类、
# 没有说话的机会。合在一次调用里时，instructions 里那 66 条标题会把闲聊带偏：
# 问"今天几号"它答完日期还续了句"这个话题涉及容器管理，建议谨慎部署"。
ROUTE_SCHEMA = {
    "title": "Route", "type": "object", "additionalProperties": False,
    "required": ["escalate"], "x-order": ["escalate", "topic"],
    "properties": {
        "escalate": {"type": "boolean", "description": "用户的话是否涉及话题清单里的内容"},
        "topic": {"type": "string", "description": "命中的话题标题，必须从清单里原样抄写"},
    },
}


def uid():
    return str(uuid.uuid4()).upper()


def today():
    # 模型不知道当前日期，不注入的话它会按训练数据自信地编（实测答成 2024 年）。
    return datetime.date.today().isoformat()


def titles():
    return re.findall(r"^- \[([^\]]+)\]", io.open(MEMORY, encoding="utf-8").read(), re.M)


def route_instructions(tl):
    return (f"你是一个分类器。今天是 {today()}。\n"
            f"下面是一份话题清单：\n{'、'.join(tl)}\n"
            "判断用户这句话是否涉及清单里的某个话题：涉及则 escalate=true，"
            "并把那个标题原样抄进 topic；不涉及则 escalate=false。"
            "topic 只能是清单里的原文。只做分类，不要回答用户的问题。")


def chat_instructions():
    # 这里故意不含话题清单，否则闲聊会被清单里的技术话题带偏。
    return (f"你是 Max 的助手。今天是 {today()}。{BASICS}\n"
            "自然、简洁地聊天，一两句话就够。问到具体事实而你不确定时说不知道，但聊喜好、感受这类就正常聊，别推说不知道。")


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


def route(q, tl):
    """只分类，无状态。粘滞模式已经管住追问，判断不需要对话历史。"""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(ROUTE_SCHEMA, f)
        schema = f.name
    try:
        r = subprocess.run(["fm", "respond", "--no-stream", "--schema", schema,
                            "-i", route_instructions(tl), q], capture_output=True, text=True)
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        print(f"(分类失败，当闲聊处理: {r.stderr.strip()[:120]})", file=sys.stderr)
        return {"escalate": False}
    finally:
        os.unlink(schema)


def chat(q, transcript=None):
    """闲聊，自然语言。给了 transcript 就带着对话历史走。"""
    cmd = ["fm", "respond", "--no-stream"]
    if transcript:
        cmd += ["--resume", transcript, "--save-transcript", transcript]
    else:
        cmd += ["-i", chat_instructions()]
    r = subprocess.run(cmd + [q], capture_output=True, text=True)
    return r.stdout.strip() or f"(fm 无输出: {r.stderr.strip()[:120]})"


def ask_claude(q, sid, hit=None, new=False):
    """new=True 用这个 sid 开新会话，否则续接已有的。"""
    prompt = f"{q}\n\n（提示：记忆库里可能有「{hit}」这条相关）" if hit else q
    flag = ["--session-id", sid] if new else ["--resume", sid]
    r = subprocess.run(["claude", "-p", f"--allowedTools={CLAUDE_ALLOW}"] + flag + [prompt],
                       cwd=PROJECT, capture_output=True, text=True)
    return (r.stdout or r.stderr).strip()


def hit_of(d, tl):
    """topic 只有 6/8 准，必须拿清单校验；它只是给 Claude 的提示，不是事实。"""
    return d.get("topic") if d.get("topic") in tl else None


def oneshot(q):
    tl = titles()
    d = route(q, tl)
    if not d.get("escalate"):
        print(chat(q))
        return 0
    hit = hit_of(d, tl)
    print(f"[转 Claude{'：' + hit if hit else ''}]", file=sys.stderr)
    print(ask_claude(q, str(uuid.uuid4()), hit, new=True))
    return 0


def repl():
    tl = titles()
    t = os.path.join(tempfile.mkdtemp(prefix="ask-"), "chat.json")
    new_transcript(t, chat_instructions())  # 对话上下文只带人设，不带清单
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

        d = route(q, tl)
        if not d.get("escalate"):
            print(chat(q, t))
            continue
        hit = hit_of(d, tl)
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

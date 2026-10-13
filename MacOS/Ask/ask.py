#!/usr/bin/env python3
"""分流器：闲聊由本地 fm 答，涉及记忆库话题的转给 claude -p。"""
import io, json, os, re, subprocess, sys, tempfile

MEMORY = os.path.expanduser(
    "~/.claude/projects/-Users-max-Develop-Library-Claude-code/memory/MEMORY.md")
PROJECT = "/Users/max/Develop Library/Claude_code"  # claude -p 只在此 cwd 下加载 memory

BASICS = ("Max 用中文交流，人在日本。他的机器：eeast(Mac mini)、ceast(Windows)、"
          "deast(Arch，与 ceast 同一台物理机)、n1(OpenWrt 软路由)、hakuto(实验室 Windows)。"
          "Toolbox 工具仓库在 ceast 的 D 盘，按操作系统分组。")

SCHEMA = {
    "title": "Route", "type": "object", "additionalProperties": False,
    "required": ["escalate"], "x-order": ["escalate", "topic", "reply"],
    "properties": {
        "escalate": {"type": "boolean", "description": "用户的话是否涉及话题清单里的内容"},
        "topic": {"type": "string", "description": "命中的话题标题，必须从清单里原样抄写"},
        "reply": {"type": "string", "description": "没命中时的直接回答，一两句话"},
    },
}


def main():
    q = " ".join(sys.argv[1:]).strip() or sys.stdin.read().strip()
    if not q:
        sys.exit("用法: ask.py '你的问题'")

    titles = re.findall(r"^- \[([^\]]+)\]", io.open(MEMORY, encoding="utf-8").read(), re.M)
    inst = (f"你是 Max 的助手兼分流器。{BASICS}\n"
            f"他记忆库里已有的话题清单：\n{'、'.join(titles)}\n"
            "规则：用户的话涉及清单里某个话题时，escalate=true 并把那个标题原样抄进 topic；"
            "无关的闲聊则 escalate=false 并用 reply 直接回答。topic 只能是清单里的原文。")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(SCHEMA, f)
        schema = f.name
    try:
        r = subprocess.run(["fm", "respond", "--no-stream", "--schema", schema, "-i", inst, q],
                           capture_output=True, text=True)
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        sys.exit(f"fm 返回异常: {r.stdout.strip()[:200]} {r.stderr.strip()[:200]}")
    finally:
        os.unlink(schema)

    if not d.get("escalate"):
        print(d.get("reply") or "(fm 没给出回答)")
        return

    # escalate 时模型只有标题、没有内容，它填的 reply 是编的，丢弃不用。
    hit = d.get("topic") if d.get("topic") in titles else None
    print(f"[转 Claude{'：' + hit if hit else ''}]", file=sys.stderr)
    prompt = f"{q}\n\n（提示：记忆库里可能有「{hit}」这条相关）" if hit else q
    sys.exit(subprocess.run(["claude", "-p", prompt], cwd=PROJECT).returncode)


main()

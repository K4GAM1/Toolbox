#!/usr/bin/env bash
#
# default-apps.sh — 批量/手动设置 macOS 文件类型的默认打开程序
#
# 引擎: 内置一个小 Swift 助手(NSWorkspace.setDefaultApplication),首次运行
#       自动编译到 ~/.cache/default-apps/lsdefault。比 duti 强:duti 用的老
#       LaunchServices C 接口在 macOS 26 上无法给"动态 UTI"(无人声明的扩展名,
#       如 .env/.toml/.svelte)设默认程序(报 error -50);本助手用新 API 可以,
#       个别系统受保护类型(shell 脚本等)再自动退回老接口兜底。
#
# 说明: 改的是 Launch Services 数据库,与 .DS_Store 无关(.DS_Store 只存
#       Finder 视图/图标布局)。每次应用改动前自动备份 secure.plist,可回滚。
#
# 依赖: Xcode 命令行工具(swiftc)。若缺: xcode-select --install
#
# 用法:
#   ./default-apps.sh                # 交互式菜单(无参数)
#   ./default-apps.sh audio          # 音频类   -> foobar2000
#   ./default-apps.sh text           # 文本/代码 -> VS Code
#   ./default-apps.sh all            # 以上两组都应用
#   ./default-apps.sh list           # 查看当前所有已配置扩展名的默认程序
#   ./default-apps.sh set <bundleId|App名> <ext1> [ext2 ...]   # 手动指定
#   ./default-apps.sh backup         # 仅备份当前 LaunchServices 配置
#
# 例:
#   ./default-apps.sh set "IINA" mkv mp4        # 用 App 名(自动查 bundle id)
#   ./default-apps.sh set com.colliderli.iina mkv
#
# 注: 变量一律带 {} 以防中文标点吞名(兼容系统自带 bash 3.2)。

# ---------------------------------------------------------------------------
# 可编辑区: 目标 App 与扩展名清单。想改归属直接改这里即可。
# ---------------------------------------------------------------------------

FOOBAR="com.foobar2000.mac"       # foobar2000
VSCODE="com.microsoft.VSCode"     # Visual Studio Code

# 音频格式 (foobar2000 Mac 能原生解码的:无损/有损/播放列表)
# 特意排除以下(foobar Mac 解不了或不合适,已单独处理):
#   .dsf .dff (DSD)、.tta、.dts、.mka —— foobar Mac 不支持,已恢复"无默认程序"
#     (系统不认作音频;要放这些得装 IINA/VLC 这类 ffmpeg 系播放器)
#   .m4b (有声书) —— 改用 Books.app;脚本复现: ./default-apps.sh set com.apple.iBooksX m4b
#   .caf —— 保持系统默认(GarageBand)
AUDIO_EXTS="mp3 flac m4a aac wav aiff aif aifc ogg oga opus wma ape wv tak mpc ac3 m3u m3u8 pls cue"

# 文本 / 配置 / 程序代码
# 注: shell 脚本 (sh/bash/zsh/fish) 特意不放进来 —— 保持用 kitty 打开(双击即运行)。
TEXT_EXTS="txt text log md markdown rst adoc tex \
json jsonc yaml yml toml ini conf cfg env properties plist xml \
css scss sass less js jsx mjs cjs ts tsx vue svelte astro \
py pyw rb go rs c h cpp cc cxx hpp hh cs java kt kts scala swift m mm php pl pm lua r jl dart groovy \
ps1 psm1 bat cmd \
csv tsv sql graphql diff patch \
gitignore gitattributes editorconfig dockerignore"

# 默认没放 html/htm(双击一般想用浏览器预览)。想让 VS Code 接管就去掉下行注释:
# TEXT_EXTS="${TEXT_EXTS} html htm"

# ---------------------------------------------------------------------------
# 内部逻辑,一般不用动
# ---------------------------------------------------------------------------

LS_PLIST="${HOME}/Library/Preferences/com.apple.LaunchServices/com.apple.launchservices.secure.plist"
CACHE_DIR="${HOME}/.cache/default-apps"
HELPER="${CACHE_DIR}/lsdefault"
HELPER_SRC="${CACHE_DIR}/lsdefault.swift"

RED=$'\033[31m'; GRN=$'\033[32m'; YLW=$'\033[33m'; CYN=$'\033[36m'; DIM=$'\033[2m'; RST=$'\033[0m'

# 写出并(按需)编译 Swift 助手
ensure_helper() {
  mkdir -p "${CACHE_DIR}"
  local tmp="${CACHE_DIR}/.src.tmp"
  cat > "${tmp}" <<'SWIFT'
import AppKit
import UniformTypeIdentifiers
import CoreServices
let a = CommandLine.arguments
guard a.count >= 3 else {
  FileHandle.standardError.write("usage: lsdefault set <bundleId> <ext...> | query <ext...>\n".data(using:.utf8)!)
  exit(2)
}
let ws = NSWorkspace.shared
switch a[1] {
case "set":
  let bid = a[2]
  guard let app = ws.urlForApplication(withBundleIdentifier: bid) else { print("ERR *: app not found: \(bid)"); exit(1) }
  for ext in a[3...] {
    guard let type = UTType(filenameExtension: ext) else { print("ERR .\(ext): no UTType"); continue }
    let sem = DispatchSemaphore(value: 0); var msg: String? = nil
    ws.setDefaultApplication(at: app, toOpen: type) { e in msg = e?.localizedDescription; sem.signal() }
    sem.wait()
    if msg == nil { print("OK  .\(ext)"); continue }
    // 新 API 失败(常见于 shell 脚本等系统受保护类型)→ 退回老 API
    let st = LSSetDefaultRoleHandlerForContentType(type.identifier as CFString, .all, bid as CFString)
    print(st == 0 ? "OK  .\(ext)" : "ERR .\(ext): \(msg!)")
  }
case "query":
  for ext in a[2...] {
    let tmp = FileManager.default.temporaryDirectory.appendingPathComponent("q_\(UUID().uuidString).\(ext)")
    FileManager.default.createFile(atPath: tmp.path, contents: Data())
    let name = ws.urlForApplication(toOpen: tmp)?.deletingPathExtension().lastPathComponent ?? "NONE"
    print(".\(ext)\t\(name)")
    try? FileManager.default.removeItem(at: tmp)
  }
default:
  FileHandle.standardError.write("unknown mode\n".data(using:.utf8)!); exit(2)
}
SWIFT
  # 源码有变化才替换 + 重新编译
  if [ ! -f "${HELPER_SRC}" ] || ! cmp -s "${tmp}" "${HELPER_SRC}"; then
    mv "${tmp}" "${HELPER_SRC}"
  else
    rm -f "${tmp}"
  fi
  if [ ! -x "${HELPER}" ] || [ "${HELPER_SRC}" -nt "${HELPER}" ]; then
    if ! command -v swiftc >/dev/null 2>&1; then
      echo "${RED}需要 Xcode 命令行工具(swiftc)。请运行: xcode-select --install${RST}" >&2
      exit 1
    fi
    if ! swiftc -O -o "${HELPER}" "${HELPER_SRC}" 2>"${CACHE_DIR}/build.log"; then
      echo "${RED}Swift 助手编译失败,见 ${CACHE_DIR}/build.log${RST}" >&2
      exit 1
    fi
  fi
}

backup_ls() {
  if [ -f "${LS_PLIST}" ]; then
    local stamp bak
    stamp="$(date +%Y%m%d-%H%M%S)"
    bak="${LS_PLIST}.bak-${stamp}"
    cp "${LS_PLIST}" "${bak}" 2>/dev/null \
      && echo "${DIM}已备份 LaunchServices -> ${bak}${RST}"
  fi
}

# App 名 -> bundle id;已是 bundle id(含点)则原样返回
resolve_bundle() {
  local input="$1"
  if printf '%s' "${input}" | grep -q '\.'; then printf '%s' "${input}"; return 0; fi
  local bid
  bid="$(osascript -e "id of app \"${input}\"" 2>/dev/null)"
  [ -n "${bid}" ] && { printf '%s' "${bid}"; return 0; }
  return 1
}

# 应用一组扩展名 -> 某 bundle id
apply_group() {
  local bundle="$1"; shift
  "${HELPER}" set "${bundle}" "$@" | while IFS= read -r line; do
    case "${line}" in
      OK*)  printf '  %s%s%s\n' "${GRN}" "${line}" "${RST}" ;;
      ERR*) printf '  %s%s%s\n' "${YLW}" "${line}" "${RST}" ;;
      *)    printf '  %s\n' "${line}" ;;
    esac
  done
}

# 查看一组扩展名当前默认程序
show_current() {
  "${HELPER}" query "$@" | while IFS=$'\t' read -r ext app; do
    [ "${app}" = "NONE" ] && app="${DIM}(无默认程序)${RST}"
    printf '  %-14s %s\n' "${ext}" "${app}"
  done
}

cmd_audio() { echo "${CYN}== 音频 -> foobar2000 ==${RST}"; apply_group "${FOOBAR}" ${AUDIO_EXTS}; }
cmd_text()  { echo "${CYN}== 文本/代码 -> VS Code ==${RST}"; apply_group "${VSCODE}" ${TEXT_EXTS}; }

cmd_list() {
  echo "${CYN}== 音频组 ==${RST}"; show_current ${AUDIO_EXTS}
  echo; echo "${CYN}== 文本/代码组 ==${RST}"; show_current ${TEXT_EXTS}
}

cmd_set() {
  local app="$1"; shift
  if [ -z "${app}" ] || [ -z "$1" ]; then
    echo "${RED}用法: $0 set <bundleId|App名> <ext1> [ext2 ...]${RST}" >&2; exit 1
  fi
  local bundle
  bundle="$(resolve_bundle "${app}")"
  if [ -z "${bundle}" ]; then
    echo "${RED}无法解析 App: ${app} (找不到已安装的同名 App)${RST}" >&2; exit 1
  fi
  echo "${CYN}== 手动: ${bundle} ==${RST}"; backup_ls; apply_group "${bundle}" "$@"
}

# 交互式选 App,结果写入全局 PICKED
pick_app() {
  PICKED=""
  {
    echo "  选择目标程序:"
    echo "    1) foobar2000"
    echo "    2) Visual Studio Code"
    echo "    3) 输入 App 名称 (如 IINA / Numbers)"
    echo "    4) 直接输入 bundle id"
    printf "  选择 [1-4]: "
  } >&2
  local c; read -r c
  case "${c}" in
    1) PICKED="${FOOBAR}" ;;
    2) PICKED="${VSCODE}" ;;
    3) printf "  App 名称: " >&2; local n; read -r n
       PICKED="$(resolve_bundle "${n}")"
       [ -z "${PICKED}" ] && { echo "  ${RED}找不到该 App${RST}" >&2; return 1; } ;;
    4) printf "  bundle id: " >&2; read -r PICKED ;;
    *) echo "  ${RED}无效选择${RST}" >&2; return 1 ;;
  esac
  return 0
}

interactive() {
  while true; do
    echo
    echo "${CYN}===== 默认程序设置 =====${RST}"
    echo "  1) 音频格式  -> foobar2000"
    echo "  2) 文本/代码 -> VS Code"
    echo "  3) 以上两组都应用"
    echo "  4) 手动: 为指定扩展名挑选程序"
    echo "  5) 查看当前配置"
    echo "  q) 退出"
    printf "选择: "
    local choice; read -r choice
    case "${choice}" in
      1) backup_ls; cmd_audio ;;
      2) backup_ls; cmd_text ;;
      3) backup_ls; cmd_audio; echo; cmd_text ;;
      4) printf "输入扩展名(空格分隔, 不带点, 如: mkv mp4 webm): "
         local exts; read -r exts
         [ -z "${exts}" ] && { echo "${YLW}没输入扩展名${RST}"; continue; }
         if pick_app && [ -n "${PICKED}" ]; then
           backup_ls; echo "${CYN}== ${PICKED} ==${RST}"; apply_group "${PICKED}" ${exts}
         fi ;;
      5) cmd_list ;;
      q|Q) break ;;
      *) echo "${YLW}无效选择${RST}" ;;
    esac
  done
}

# ---------------------------------------------------------------------------
main() {
  case "${1:-}" in
    -h|--help|help) grep '^#' "$0" | sed 's/^# \{0,1\}//' | head -40; exit 0 ;;
  esac
  ensure_helper
  case "${1:-}" in
    audio)  backup_ls; cmd_audio ;;
    text)   backup_ls; cmd_text ;;
    all)    backup_ls; cmd_audio; echo; cmd_text ;;
    list)   cmd_list ;;
    backup) backup_ls ;;
    set)    shift; cmd_set "$@" ;;
    ""|menu) interactive ;;
    *) echo "${RED}未知命令: ${1}${RST}"; echo "运行 $0 --help 查看用法"; exit 1 ;;
  esac
}

main "$@"

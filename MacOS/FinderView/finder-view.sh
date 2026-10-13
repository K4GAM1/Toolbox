#!/bin/bash
#
# 统一 Finder 视图设置（图标式 / 列表式二选一）+ 显示隐藏文件
#
# 为什么不用 `defaults write`：
#   老式 plist 字典语法 `{textSize=14;}` 会把 14 存成 <string>，而 Finder 期望
#   <real>。类型不符时 Finder 静默回落到最小值（文字变 10、间距滑块跑到最左），
#   但 `defaults read` 打印出来和正常值一模一样，问题会被藏住。
#   所以这里用 plutil -replace -xml 显式指定类型。
#
# 兼容性：Mac 自带 /bin/bash 是 3.2.57（没有 homebrew bash），不支持
# `declare -A` 关联数组（bash4+ 才有），所以 i18n 用 case 语句实现，
# 不要往这个文件里加 bash4+ 语法。
#
# 用法：
#   ./finder-view.sh                  交互式菜单（终端里裸调用时）
#   ./finder-view.sh --menu           强制打开交互式菜单
#   ./finder-view.sh --yes            跳过菜单，用当前配置直接应用
#   ./finder-view.sh --view=icon      视图样式：icon（图标式，默认）/ list（列表式）
#   ./finder-view.sh --lang=zh        界面语言：en（默认）/ zh
#   ./finder-view.sh --desktop        同时统一桌面（桌面是独立的一套）
#   ./finder-view.sh --clean-dsstore  顺带清掉家目录下的 .DS_Store 覆盖
#   ./finder-view.sh --hidden         显示隐藏文件
#   ./finder-view.sh --no-hidden      不显示隐藏文件（默认）
#
# 上面这些参数（--menu 除外）只要出现任意一个，就视为自动化调用，直接应用、
# 不进菜单；裸调用且在交互终端里才会进菜单循环。

set -euo pipefail

# ---- 默认配置 --------------------------------------------------------------
VIEW_STYLE=icon        # icon / list

# 图标视图
ICON_SIZE=48            # 16 / 32 / 48 / 64 / 128 / 256 / 512
GRID_SPACING=35         # 网格间距，Finder 滑块范围约 30-100
ICON_TEXT_SIZE=16       # 10 / 11 / 12 / 13 / 14 / 16
LABEL_ON_BOTTOM=true    # false = 标签显示在图标右侧
SHOW_ICON_PREVIEW=true
SHOW_ITEM_INFO=false
ARRANGE_BY=name         # none / name / dateModified / kind / size / label

# 列表视图
LIST_ICON_SIZE=16       # 16 / 32
LIST_TEXT_SIZE=13       # 10 / 11 / 12 / 13 / 14 / 16
LIST_SHOW_PREVIEW=true
LIST_USE_RELATIVE_DATES=true
LIST_CALC_ALL_SIZES=false
LIST_SORT_COLUMN=name    # name / dateModified / dateCreated / size / kind

# 通用
LANG_SEL=en              # en / zh
APPLY_DESKTOP=false
CLEAN_DSSTORE=false
SHOW_HIDDEN=false
FORCE_MENU=false
FORCE_APPLY=false
ARGS_GIVEN=false
# -----------------------------------------------------------------------------

PLIST="$HOME/Library/Preferences/com.apple.finder.plist"

# ---- i18n -------------------------------------------------------------------
# bash 3.2 没有关联数组，用 case 语句代替查表。
msg() {
  local key="$1"
  if [ "${LANG_SEL}" = "zh" ]; then
    case "$key" in
      logo_tag)          echo "Finder 视图设置" ;;
      menu_title)        echo "==== 主菜单 ====" ;;
      menu_view_style)   echo "视图样式" ;;
      menu_icon_opts)    echo "图标视图选项" ;;
      menu_list_opts)    echo "列表视图选项" ;;
      menu_common_opts)  echo "通用选项（隐藏文件 / 桌面）" ;;
      menu_clean_dsstore) echo "标记：应用时顺带清理 .DS_Store" ;;
      menu_language)     echo "界面语言" ;;
      menu_apply)        echo "应用设置并退出" ;;
      menu_quit)         echo "不应用，直接退出" ;;
      prompt_choice)     echo "请输入选项：" ;;
      invalid_choice)    echo "无效选项，请重新输入。" ;;
      bye)                echo "已退出，未做任何更改。" ;;
      submenu_view_prompt) echo "1) 图标式  2) 列表式（当前：${VIEW_STYLE}）" ;;
      submenu_back_hint)  echo "（直接回车 = 保持当前值不变）" ;;
      prompt_icon_size)   echo "图标大小 [当前 ${ICON_SIZE}，可选 16/32/48/64/128/256/512]：" ;;
      prompt_grid_spacing) echo "网格间距 [当前 ${GRID_SPACING}，约 30-100]：" ;;
      prompt_icon_text_size) echo "文字大小 [当前 ${ICON_TEXT_SIZE}]：" ;;
      prompt_label_pos)   echo "标签位置 [当前 ${LABEL_ON_BOTTOM}] 1) 下方 2) 右侧：" ;;
      prompt_icon_preview) echo "显示图标预览？[当前 ${SHOW_ICON_PREVIEW}] 1) 是 2) 否：" ;;
      prompt_arrange_by)  echo "排列依据 [当前 ${ARRANGE_BY}] name/dateModified/kind/size/label/none：" ;;
      prompt_list_icon_size) echo "列表图标大小 [当前 ${LIST_ICON_SIZE}，可选 16/32]：" ;;
      prompt_list_text_size) echo "文字大小 [当前 ${LIST_TEXT_SIZE}]：" ;;
      prompt_list_preview) echo "显示图标预览？[当前 ${LIST_SHOW_PREVIEW}] 1) 是 2) 否：" ;;
      prompt_relative_dates) echo "日期显示为相对时间（如“昨天”）？[当前 ${LIST_USE_RELATIVE_DATES}] 1) 是 2) 否：" ;;
      prompt_calc_all_sizes) echo "计算文件夹总大小？[当前 ${LIST_CALC_ALL_SIZES}，开启会变慢] 1) 是 2) 否：" ;;
      prompt_sort_column) echo "排序列 [当前 ${LIST_SORT_COLUMN}] name/dateModified/dateCreated/size/kind：" ;;
      prompt_show_hidden) echo "显示隐藏文件？[当前 ${SHOW_HIDDEN}] 1) 是 2) 否：" ;;
      prompt_apply_desktop) echo "桌面也一起统一？[当前 ${APPLY_DESKTOP}] 1) 是 2) 否：" ;;
      prompt_lang)         echo "选择语言 1) English 2) 中文：" ;;
      applying)            echo "==> 关闭 Finder 窗口并退出，刷新偏好缓存" ;;
      writing)             echo "==> 写入视图设置（${VIEW_STYLE}）" ;;
      hidden_on)           echo "    AppleShowAllFiles = true（Cmd+Shift+. 可随时临时切换）" ;;
      hidden_off)          echo "    AppleShowAllFiles = false" ;;
      cleaning)            echo "==> 清理 .DS_Store（Finder 仍处于退出状态）" ;;
      cleaned)             echo "    已删除 %d 个（图标手动摆位与窗口大小会一并丢失）" ;;
      starting_finder)     echo "==> 启动 Finder" ;;
      verifying)           echo "==> 校验（类型必须是 real，不能是 string）" ;;
      done_msg)            echo "完成。按 Cmd+J 复查面板数值。" ;;
      dsstore_note)        echo "注意：单个文件夹被手动调过之后会生成自己的 .DS_Store，从此不再跟随全局值，用 --clean-dsstore 重置，或在该窗口改完后点\"用作默认\"。" ;;
      unknown_arg)         echo "未知参数（-h 看用法）" ;;
      *) echo "$key" ;;
    esac
  else
    case "$key" in
      logo_tag)          echo "Finder View Settings" ;;
      menu_title)        echo "==== Main Menu ====" ;;
      menu_view_style)   echo "View style" ;;
      menu_icon_opts)    echo "Icon view options" ;;
      menu_list_opts)    echo "List view options" ;;
      menu_common_opts)  echo "Common options (hidden files / desktop)" ;;
      menu_clean_dsstore) echo "Mark: clean .DS_Store on apply" ;;
      menu_language)     echo "Interface language" ;;
      menu_apply)        echo "Apply settings and exit" ;;
      menu_quit)         echo "Quit without applying" ;;
      prompt_choice)     echo "Enter choice:" ;;
      invalid_choice)    echo "Invalid choice, try again." ;;
      bye)                echo "Exited without making changes." ;;
      submenu_view_prompt) echo "1) Icon  2) List  (current: ${VIEW_STYLE})" ;;
      submenu_back_hint)  echo "(press Enter to keep current value)" ;;
      prompt_icon_size)   echo "Icon size [current ${ICON_SIZE}, one of 16/32/48/64/128/256/512]:" ;;
      prompt_grid_spacing) echo "Grid spacing [current ${GRID_SPACING}, roughly 30-100]:" ;;
      prompt_icon_text_size) echo "Text size [current ${ICON_TEXT_SIZE}]:" ;;
      prompt_label_pos)   echo "Label position [current ${LABEL_ON_BOTTOM}] 1) bottom 2) right:" ;;
      prompt_icon_preview) echo "Show icon preview? [current ${SHOW_ICON_PREVIEW}] 1) yes 2) no:" ;;
      prompt_arrange_by)  echo "Arrange by [current ${ARRANGE_BY}] name/dateModified/kind/size/label/none:" ;;
      prompt_list_icon_size) echo "List icon size [current ${LIST_ICON_SIZE}, one of 16/32]:" ;;
      prompt_list_text_size) echo "Text size [current ${LIST_TEXT_SIZE}]:" ;;
      prompt_list_preview) echo "Show icon preview? [current ${LIST_SHOW_PREVIEW}] 1) yes 2) no:" ;;
      prompt_relative_dates) echo "Use relative dates (e.g. \"Yesterday\")? [current ${LIST_USE_RELATIVE_DATES}] 1) yes 2) no:" ;;
      prompt_calc_all_sizes) echo "Calculate all folder sizes? [current ${LIST_CALC_ALL_SIZES}, slower] 1) yes 2) no:" ;;
      prompt_sort_column) echo "Sort column [current ${LIST_SORT_COLUMN}] name/dateModified/dateCreated/size/kind:" ;;
      prompt_show_hidden) echo "Show hidden files? [current ${SHOW_HIDDEN}] 1) yes 2) no:" ;;
      prompt_apply_desktop) echo "Also apply to Desktop? [current ${APPLY_DESKTOP}] 1) yes 2) no:" ;;
      prompt_lang)         echo "Choose language 1) English 2) 中文:" ;;
      applying)            echo "==> Closing Finder windows and quitting, flushing pref cache" ;;
      writing)             echo "==> Writing view settings (${VIEW_STYLE})" ;;
      hidden_on)           echo "    AppleShowAllFiles = true (toggle anytime with Cmd+Shift+.)" ;;
      hidden_off)          echo "    AppleShowAllFiles = false" ;;
      cleaning)            echo "==> Cleaning .DS_Store (Finder still quit)" ;;
      cleaned)             echo "    Removed %d file(s) (manual icon placement / window sizes will be lost)" ;;
      starting_finder)     echo "==> Starting Finder" ;;
      verifying)           echo "==> Verifying (type must be real, not string)" ;;
      done_msg)            echo "Done. Press Cmd+J to double-check the values." ;;
      dsstore_note)        echo "Note: a folder that was manually adjusted gets its own .DS_Store and stops following the global value; reset it with --clean-dsstore, or click \"Use as Defaults\" after adjusting that window." ;;
      unknown_arg)         echo "unknown argument (-h for usage)" ;;
      *) echo "$key" ;;
    esac
  fi
}

print_logo() {
  cat <<'LOGO'
   ______           __
  / ____/  ______  / /___  _____
 / /_/ / / / / __ \/ __/ / / / _ \
/ __/ /_/ / / / / /_/ /_/ /  __/
/_/  \__,_/_/ /_/\__/\__,_/\___/
LOGO
  echo "  $(msg logo_tag)"
  echo
}

# ---- 参数解析 ----------------------------------------------------------------
usage() {
  sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
  case "$arg" in
    --view=icon)     VIEW_STYLE=icon; ARGS_GIVEN=true ;;
    --view=list)     VIEW_STYLE=list; ARGS_GIVEN=true ;;
    --lang=en)       LANG_SEL=en ;;
    --lang=zh)       LANG_SEL=zh ;;
    --menu)          FORCE_MENU=true ;;
    --yes)           FORCE_APPLY=true; ARGS_GIVEN=true ;;
    --desktop)       APPLY_DESKTOP=true; ARGS_GIVEN=true ;;
    --clean-dsstore) CLEAN_DSSTORE=true; ARGS_GIVEN=true ;;
    --hidden)        SHOW_HIDDEN=true; ARGS_GIVEN=true ;;
    --no-hidden)     SHOW_HIDDEN=false; ARGS_GIVEN=true ;;
    -h|--help)       usage; exit 0 ;;
    *) echo "$(msg unknown_arg): $arg" >&2; exit 1 ;;
  esac
done

# ---- plist 片段生成 ----------------------------------------------------------
icon_view_xml() {
  cat <<XML
<dict>
	<key>arrangeBy</key>
	<string>${ARRANGE_BY}</string>
	<key>axTextSize</key>
	<real>${ICON_TEXT_SIZE}</real>
	<key>backgroundColorBlue</key>
	<real>1</real>
	<key>backgroundColorGreen</key>
	<real>1</real>
	<key>backgroundColorRed</key>
	<real>1</real>
	<key>backgroundType</key>
	<integer>0</integer>
	<key>gridOffsetX</key>
	<real>0.0</real>
	<key>gridOffsetY</key>
	<real>0.0</real>
	<key>gridSpacing</key>
	<real>${GRID_SPACING}</real>
	<key>iconSize</key>
	<real>${ICON_SIZE}</real>
	<key>labelOnBottom</key>
	<${LABEL_ON_BOTTOM}/>
	<key>showIconPreview</key>
	<${SHOW_ICON_PREVIEW}/>
	<key>showItemInfo</key>
	<${SHOW_ITEM_INFO}/>
	<key>textSize</key>
	<real>${ICON_TEXT_SIZE}</real>
	<key>viewOptionsVersion</key>
	<integer>1</integer>
</dict>
XML
}

# 列表视图的标准列集合，跟 Finder 里手动切到列表视图时看到的一致。
# 这里整份覆盖（跟图标视图一个思路），会连带覆盖掉手动调过的列宽/列显隐。
list_view_xml() {
  cat <<XML
<dict>
	<key>calculateAllSizes</key>
	<${LIST_CALC_ALL_SIZES}/>
	<key>columns</key>
	<array>
		<dict>
			<key>ascending</key>
			<true/>
			<key>identifier</key>
			<string>name</string>
			<key>visible</key>
			<true/>
			<key>width</key>
			<real>300</real>
		</dict>
		<dict>
			<key>ascending</key>
			<false/>
			<key>identifier</key>
			<string>dateModified</string>
			<key>visible</key>
			<true/>
			<key>width</key>
			<real>181</real>
		</dict>
		<dict>
			<key>ascending</key>
			<false/>
			<key>identifier</key>
			<string>dateCreated</string>
			<key>visible</key>
			<false/>
			<key>width</key>
			<real>181</real>
		</dict>
		<dict>
			<key>ascending</key>
			<false/>
			<key>identifier</key>
			<string>size</string>
			<key>visible</key>
			<true/>
			<key>width</key>
			<real>97</real>
		</dict>
		<dict>
			<key>ascending</key>
			<true/>
			<key>identifier</key>
			<string>kind</string>
			<key>visible</key>
			<true/>
			<key>width</key>
			<real>115</real>
		</dict>
		<dict>
			<key>ascending</key>
			<true/>
			<key>identifier</key>
			<string>label</string>
			<key>visible</key>
			<false/>
			<key>width</key>
			<real>100</real>
		</dict>
		<dict>
			<key>ascending</key>
			<true/>
			<key>identifier</key>
			<string>version</string>
			<key>visible</key>
			<false/>
			<key>width</key>
			<real>75</real>
		</dict>
		<dict>
			<key>ascending</key>
			<true/>
			<key>identifier</key>
			<string>comments</string>
			<key>visible</key>
			<false/>
			<key>width</key>
			<real>300</real>
		</dict>
	</array>
	<key>iconSize</key>
	<real>${LIST_ICON_SIZE}</real>
	<key>showIconPreview</key>
	<${LIST_SHOW_PREVIEW}/>
	<key>sortColumn</key>
	<string>${LIST_SORT_COLUMN}</string>
	<key>textSize</key>
	<real>${LIST_TEXT_SIZE}</real>
	<key>useRelativeDates</key>
	<${LIST_USE_RELATIVE_DATES}/>
	<key>viewOptionsVersion</key>
	<integer>1</integer>
</dict>
XML
}

# 普通文件夹只是其中一套。"电脑"、网络、废纸篓、最近搜索等特殊位置各有独立的
# *ViewSettings 键，改普通窗口碰不到它们。这里自动发现所有以 ViewSettings 结尾
# 的顶层字典键，以后系统新增位置也能自动覆盖，不用回来改脚本。
#   StandardViewSettings    = 普通窗口
#   FK_StandardViewSettings = 后备设置，图形界面完全碰不到，不写会和上面不一致
#   ComputerViewSettings 等 = 特殊位置
discover_targets() {
  python3 - "$PLIST" <<'PY'
import plistlib, sys
with open(sys.argv[1], 'rb') as f:
    d = plistlib.load(f)
for k, v in d.items():
    if isinstance(v, dict) and k.endswith('ViewSettings'):
        print(k)
PY
}

apply_settings() {
  local SETTINGS_SUBKEY FX_STYLE XML_DICT
  if [ "${VIEW_STYLE}" = "list" ]; then
    SETTINGS_SUBKEY=ListViewSettings
    FX_STYLE=Nlsv
    XML_DICT="$(list_view_xml)"
  else
    SETTINGS_SUBKEY=IconViewSettings
    FX_STYLE=icnv
    XML_DICT="$(icon_view_xml)"
  fi

  local TARGETS=()
  while IFS= read -r k; do
    # 桌面单独一套，默认不动（桌面图标通常想大一点），--desktop / 菜单里选是 才纳入
    [ "$k" = "DesktopViewSettings" ] && ! ${APPLY_DESKTOP} && continue
    TARGETS+=("$k")
  done < <(discover_targets)

  # 这两个是根本，即使 plist 里还没有也要写（全新系统上可能尚未生成）
  local must
  for must in StandardViewSettings FK_StandardViewSettings; do
    case " ${TARGETS[*]:-} " in *" $must "*) ;; *) TARGETS+=("$must") ;; esac
  done

  echo "$(msg applying)"
  # 先关窗口，再退出。Finder 重启时会恢复退出前打开的窗口，并把那些窗口的旧视图
  # 状态写回各自的 .DS_Store——只退出不关窗口的话，刚清掉的覆盖会立刻被重建。
  osascript -e 'tell application "Finder" to close every window' 2>/dev/null || true
  sleep 1
  # 退出还有一层原因：Finder 运行时会在退出瞬间把内存里的旧设置写回 plist，
  # 直接改文件的话改动会被盖掉。cfprefsd 同理，它有独立的内存缓存。
  osascript -e 'tell application "Finder" to quit' 2>/dev/null || true
  sleep 2
  killall cfprefsd 2>/dev/null || true
  sleep 1

  echo "$(msg writing)"
  local key
  for key in "${TARGETS[@]}"; do
    plutil -replace "${key}.${SETTINGS_SUBKEY}" -xml "$XML_DICT" "$PLIST"
    echo "    $key"
  done

  plutil -replace FXPreferredViewStyle -xml "<string>${FX_STYLE}</string>" "$PLIST"
  echo "    FXPreferredViewStyle = ${FX_STYLE}"

  if ${SHOW_HIDDEN}; then
    plutil -replace AppleShowAllFiles -xml "<true/>" "$PLIST"
    echo "$(msg hidden_on)"
  else
    plutil -replace AppleShowAllFiles -xml "<false/>" "$PLIST"
    echo "$(msg hidden_off)"
  fi

  killall cfprefsd 2>/dev/null || true
  sleep 1

  # .DS_Store 存的是单个文件夹的视图覆盖，存在时会盖过上面的全局值。
  # 必须趁 Finder 还没启动时删：Finder 退出时会把内存里的窗口状态写回 .DS_Store，
  # 所以"启动后再删再重启"等于白删——删完必须直接启动，中间不能再让它退出一次。
  if ${CLEAN_DSSTORE}; then
    echo "$(msg cleaning)"
    # find 碰到无权限的子目录会返回非零，配合 pipefail 会误判为失败，故兜底
    local count
    count=$( { find "$HOME" -name .DS_Store -type f 2>/dev/null || true; } | wc -l | tr -d ' ')
    find "$HOME" -name .DS_Store -type f -delete 2>/dev/null || true
    rm -f /Applications/.DS_Store 2>/dev/null || true
    printf "$(msg cleaned)\n" "$count"
  fi

  echo "$(msg starting_finder)"
  open -a Finder
  sleep 3

  echo
  echo "$(msg verifying)"
  for key in "${TARGETS[@]}"; do
    echo "--- $key ---"
    if [ "${VIEW_STYLE}" = "list" ]; then
      plutil -extract "${key}.${SETTINGS_SUBKEY}" xml1 -o - "$PLIST" \
        | grep -A1 -E '<key>(iconSize|textSize)</key>' | grep -v '^--'
    else
      plutil -extract "${key}.${SETTINGS_SUBKEY}" xml1 -o - "$PLIST" \
        | grep -A1 -E '<key>(iconSize|gridSpacing|textSize)</key>' | grep -v '^--'
    fi
  done

  echo
  echo "$(msg done_msg)"
  echo "$(msg dsstore_note)"
}

# ---- 交互菜单 ----------------------------------------------------------------
# 每次换一级菜单（主菜单<->子菜单）都清屏，不留上一级的回显。
# `clear` 在没有终端(非tty)时会报错，兜底成 ANSI 转义码，两边都失败就干脆不清。
clear_screen() {
  clear 2>/dev/null || printf '\033[H\033[2J' 2>/dev/null || true
}

bool_from_choice() { # $1=1/2 -> echo true/false
  case "$1" in
    1) echo true ;;
    2) echo false ;;
    *) echo "" ;;
  esac
}

submenu_view_style() {
  clear_screen
  echo "$(msg submenu_view_prompt)"
  read -r c
  case "$c" in
    1) VIEW_STYLE=icon ;;
    2) VIEW_STYLE=list ;;
    "") ;; # 保持不变
    *) echo "$(msg invalid_choice)" ;;
  esac
}

submenu_icon_opts() {
  clear_screen
  echo "$(msg submenu_back_hint)"
  local v
  read -rp "$(msg prompt_icon_size) " v; [ -n "$v" ] && ICON_SIZE="$v"
  read -rp "$(msg prompt_grid_spacing) " v; [ -n "$v" ] && GRID_SPACING="$v"
  read -rp "$(msg prompt_icon_text_size) " v; [ -n "$v" ] && ICON_TEXT_SIZE="$v"
  read -rp "$(msg prompt_label_pos) " v
  case "$v" in 1) LABEL_ON_BOTTOM=true ;; 2) LABEL_ON_BOTTOM=false ;; esac
  read -rp "$(msg prompt_icon_preview) " v
  case "$v" in 1) SHOW_ICON_PREVIEW=true ;; 2) SHOW_ICON_PREVIEW=false ;; esac
  read -rp "$(msg prompt_arrange_by) " v; [ -n "$v" ] && ARRANGE_BY="$v"
}

submenu_list_opts() {
  clear_screen
  echo "$(msg submenu_back_hint)"
  local v
  read -rp "$(msg prompt_list_icon_size) " v; [ -n "$v" ] && LIST_ICON_SIZE="$v"
  read -rp "$(msg prompt_list_text_size) " v; [ -n "$v" ] && LIST_TEXT_SIZE="$v"
  read -rp "$(msg prompt_list_preview) " v
  case "$v" in 1) LIST_SHOW_PREVIEW=true ;; 2) LIST_SHOW_PREVIEW=false ;; esac
  read -rp "$(msg prompt_relative_dates) " v
  case "$v" in 1) LIST_USE_RELATIVE_DATES=true ;; 2) LIST_USE_RELATIVE_DATES=false ;; esac
  read -rp "$(msg prompt_calc_all_sizes) " v
  case "$v" in 1) LIST_CALC_ALL_SIZES=true ;; 2) LIST_CALC_ALL_SIZES=false ;; esac
  read -rp "$(msg prompt_sort_column) " v; [ -n "$v" ] && LIST_SORT_COLUMN="$v"
}

submenu_common_opts() {
  clear_screen
  echo "$(msg submenu_back_hint)"
  local v
  read -rp "$(msg prompt_show_hidden) " v
  case "$v" in 1) SHOW_HIDDEN=true ;; 2) SHOW_HIDDEN=false ;; esac
  read -rp "$(msg prompt_apply_desktop) " v
  case "$v" in 1) APPLY_DESKTOP=true ;; 2) APPLY_DESKTOP=false ;; esac
}

submenu_language() {
  clear_screen
  read -rp "$(msg prompt_lang) " v
  case "$v" in 1) LANG_SEL=en ;; 2) LANG_SEL=zh ;; esac
}

main_menu() {
  while true; do
    clear_screen
    print_logo
    echo "$(msg menu_title)"
    echo "1) $(msg menu_view_style) [${VIEW_STYLE}]"
    echo "2) $(msg menu_icon_opts)"
    echo "3) $(msg menu_list_opts)"
    echo "4) $(msg menu_common_opts)"
    echo "5) $(msg menu_clean_dsstore) [${CLEAN_DSSTORE}]"
    echo "6) $(msg menu_language) [${LANG_SEL}]"
    echo "A) $(msg menu_apply)"
    echo "Q) $(msg menu_quit)"
    read -rp "$(msg prompt_choice) " choice
    case "$choice" in
      1) submenu_view_style ;;
      2) submenu_icon_opts ;;
      3) submenu_list_opts ;;
      4) submenu_common_opts ;;
      5) if ${CLEAN_DSSTORE}; then CLEAN_DSSTORE=false; else CLEAN_DSSTORE=true; fi ;;
      6) submenu_language ;;
      A|a) apply_settings; return 0 ;;
      Q|q) clear_screen; echo "$(msg bye)"; exit 0 ;;
      *) echo "$(msg invalid_choice)" ;;
    esac
  done
}

# ---- 入口 --------------------------------------------------------------------
main() {
  if ${FORCE_MENU}; then
    main_menu
  elif ${FORCE_APPLY} || ${ARGS_GIVEN} || [ ! -t 0 ]; then
    apply_settings
  else
    main_menu
  fi
}

main

#!/usr/bin/env python3
"""GC formation setup driver (dev v1, supervised checkpoints).

按 lineup-spec-s45.json 在黄金竞技场阵形编辑器里重建阵容：
清空 -> 按 spec 顺序逐个（搜索->点候选->面板校验点->点格位）放置 -> 校验 -> 保存/恢复。

实测力学（2026-10-09 晚，全分辨率定点；设备坐标 1920x1080）：
- 平面视角格中心：列 x=[762,862,965,1062]，行 y=[362,455,543,640,732]（以禁格红 X 中心实测）
- 放置顺序 = 行动顺序（append）；单件卸下重放会掉到队尾 -> 必须全清后按序重建，禁止单件修补
- 名单（更换）内已部署服装不显示；搜索：放大镜 -> 输入框 -> 主机剪贴板 + keyevent 279 粘贴，结果实时过滤
- 点候选卡 -> 信息面板（角色名/站位/技能范围图）= 身份校验门 -> 点高亮格位落位
- 卸除：名单模式点「卸除」-> 移除子模式点棋盘上单位 -> 「取消」退出子模式
- 编辑器脏状态才出现 保存(1085,974)/恢复(838,974)；恢复 = 丢弃回上次保存态
- 庇佑页：设置(1763,227) 进入；先攻(372,139)/后攻(537,139) 页签；已选列表 X 列 x=592；
  墙卡列 x=[762,992,1222,1452,1682]、行 y=[290,615]+滚动；恢复(1412,1006)/确认(1652,1006)

运行（在 ~/workspace/mfabd2-install/ 下，复用 emu_step.py / run_ps.py 通道）：
  python3 gc_setup.py --lineup L2 --mode rehearse   # 演练：全流程后按「恢复」，不落盘
  python3 gc_setup.py --lineup L2 --mode commit     # 正式：保存并重进校验
每个校验门会存截图到 ./gc_setup_shots/ 并等待监督者在终端确认（v1 监督模式）。
TODO（独立化）：面板角色名/范围图校验改 Maa OCR/模板节点；庇佑墙卡定位表补齐后启用 --blessings。
"""
import argparse, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(HERE, "gc_setup_shots")
os.makedirs(SHOTS, exist_ok=True)

COLS_X = [762, 862, 965, 1062]
ROWS_Y = [362, 455, 543, 640, 732]

def cell_xy(cell):
    c, r = cell
    return COLS_X[c - 1], ROWS_Y[r - 1]

def step(actions, tag):
    """执行 emu_step 动作列并把截图另存为校验点。"""
    r = subprocess.run([sys.executable, os.path.join(HERE, "emu_step.py"), json.dumps(actions)],
                       capture_output=True, text=True)
    src = os.path.join(HERE, "emu_shot.jpg")
    if os.path.exists(src):
        dst = os.path.join(SHOTS, f"{tag}.jpg")
        subprocess.run(["cp", src, dst])
        return dst
    return None

def tap(x, y, tag, wait=3):
    return step([["tap", x, y], ["sleep", wait]], tag)

def gate(tag, desc):
    shot = step([["sleep", 1]], f"gate_{tag}")
    print(f"[GATE {tag}] {desc}\n  截图: {shot}")
    ans = input("  确认无误回车继续；输入 q 中止（中止后请手动按恢复）: ").strip()
    if ans.lower() == "q":
        print("监督者中止。当前编辑器可能处于脏状态，请手动处理（恢复/保存）。")
        sys.exit(2)

def set_clipboard(text):
    ps1 = os.path.join(HERE, "setclip_kw.ps1")
    with open(ps1, "w", encoding="utf-8") as f:
        f.write(f"Set-Clipboard -Value '{text}'\n'clip set'\n")
    subprocess.run([sys.executable, os.path.join(HERE, "run_ps.py"), "setclip_kw.ps1", "30000"],
                   capture_output=True, text=True)

def paste():
    subprocess.run([sys.executable, os.path.join(HERE, "run_ps.py"), "key279.ps1", "30000"],
                   capture_output=True, text=True)

def enter_editor():
    # 前置：竞技场主页（阵形设置在左下 (250,830)）
    tap(250, 830, "enter_editor", wait=6)
    # 切平面视角（若已在平面则此点会切回斜视角 -> 监督门确认）
    tap(1388, 966, "flat_view", wait=3)

def open_roster():
    tap(148, 964, "roster", wait=4)

def clear_all(members_cells):
    """卸除全部已部署单位。members_cells: 当前棋盘上单位的格位列表（col,row）。"""
    tap(958, 966, "remove_mode", wait=3)          # 卸除 -> 移除子模式
    for cell in members_cells:
        x, y = cell_xy(cell)
        tap(x, y, f"remove_{cell[0]}_{cell[1]}", wait=2)
    tap(958, 966, "remove_mode_exit", wait=3)     # 取消 -> 退出子模式

def place_one(costume, cell, first_card_xy=(185, 270)):
    kw = costume["search_keyword"]
    tap(1053, 88, f"search_open_{kw}", wait=3)    # 放大镜
    tap(585, 70, f"search_focus_{kw}", wait=1)    # 输入框
    set_clipboard(kw)
    paste()
    time.sleep(2)
    step([["sleep", 1]], f"search_result_{kw}")
    gate(f"search_{kw}", f"搜索「{kw}」应只剩目标候选（{costume['costume_name']}·{costume['character']}）；多于一张时先人工指认坐标再继续")
    tap(*first_card_xy, f"card_{kw}", wait=3)     # 点候选卡 -> 面板
    gate(f"panel_{kw}", f"面板校验：角色名={costume['character']}、属性={costume['element']}、伤害={costume['damage_type']}，且技能范围图与本地库一致")
    x, y = cell_xy(cell)
    tap(x, y, f"placed_{kw}", wait=3)             # 点目标格位落位
    # 清搜索（X 在搜索栏右端 (1074,76)）
    tap(1074, 76, f"search_clear_{kw}", wait=2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=os.path.join(HERE, "lineup-spec-s45.json"))
    ap.add_argument("--lineup", default="L2")
    ap.add_argument("--mode", choices=["rehearse", "commit"], default="rehearse")
    ap.add_argument("--current-cells", default="1,2;1,4;4,4;3,1;2,5;4,2",
                    help="当前棋盘已部署单位格位（清空用），分号分隔 col,row")
    args = ap.parse_args()

    spec = json.load(open(args.spec, encoding="utf-8"))
    lineup = next(l for l in spec["lineups"] if l["id"] == args.lineup)
    cur_cells = [tuple(int(v) for v in p.split(",")) for p in args.current_cells.split(";") if p]

    print(f"== GC setup {args.lineup} ({lineup['band']}) mode={args.mode} ==")
    gate("start", "前置：游戏停在黄金竞技场主页（能看到阵形设置按钮）")
    enter_editor()
    gate("editor", "已进阵形编辑器且为平面视角（棋盘为正视网格、禁格红 X 可见）")
    open_roster()
    clear_all(cur_cells)
    gate("cleared", "棋盘应已清空（6 人全卸下）")
    for m in lineup["members_in_placement_order"]:
        c = spec["costumes"][m["costume"]]
        # 同名陷阱（海滨度假有伊柯/墨菲亚两件）靠「首张候选 + 面板校验门」兜底：
        # 实测搜索会忽略属性筛选、且结果按 costume_id 升序，目标件恰为首张（2026-10-09 晚实证）
        place_one(c, m["cell_col_row"])
    # 退出名单模式回编辑器主视图（保存/恢复按钮只在主视图；v1 首跑曾在此误点卸除，已修）
    tap(162, 984, "roster_exit", wait=3)
    gate("placed", "6 人应全部落位：棋盘格位与 spec 一致，左侧槽位顺序 = spec 放置顺序、战力列对得上")
    if args.mode == "commit":
        tap(1085, 974, "save", wait=3)
        print("已保存。请退出重进编辑器做读回校验（脚本外人工/后续版本自动）。")
    else:
        tap(838, 974, "restore", wait=3)
        print("演练模式：已按「恢复」丢弃本次编辑，保存态未变。")

if __name__ == "__main__":
    main()

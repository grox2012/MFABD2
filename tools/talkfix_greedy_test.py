# -*- coding: utf-8 -*-
"""谈心贪心扫描修复（fix/daily-intimacy-greedy-20261103）离线测试。

用法：
  python3 talkfix_greedy_test.py <Daily.json> <基线 Daily.json(ac80f385 版)>

分两部分（均为离线，不碰游戏、不改文件）：
  S: 结构校验 —— 节点接线、闸值、出口、未动节点同一性。
  C: 逻辑模拟 —— 按 CatalogCard next 列表求值顺序 + 标签语义，
     对名册/剩余次数/按钮生死建模，跑“旧（无翻页）vs 新”对照。
     注意：模拟是逻辑层模型，不是 MAA 运行时；MAA 侧的 on_error 触发语义
     （识别失败/超时是否走 on_error）须由实战首验确认，见 TEST-RESULTS。
"""
import json
import sys

NEW_NODES = [
    "Daily_Intimacy_Scroll_Inc",
    "Daily_Intimacy_Scroll_Ck",
    "Daily_Intimacy_Swip_Page",
    "Daily_Intimacy_Scroll_Reset",
    "Daily_Intimacy_FastTalk",
    "Daily_Intimacy_FastTalk_Ck",
    "Daily_Intimacy_FastTalk_Done",
]
TOUCHED = {"Daily_Intimacy_CatalogCard", "Daily_Intimacy_Switch_Turn",
           "Daily_Intimacy_Up_MSG"}

FAILURES = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else " :: " + detail))
    if not cond:
        FAILURES.append(name)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- S: 结构
def structural(d, b):
    check("S1 节点总数 = 基线 + 7", len(d) == len(b) + 7,
          f"{len(d)} vs {len(b)}")
    for name in NEW_NODES:
        check(f"S1 新节点在位 {name}", name in d)
    diff = [k for k in b if k not in TOUCHED and d.get(k) != b[k]]
    check("S2 除 3 个改动节点外其余节点与基线逐项一致", not diff, str(diff[:5]))
    cc = d["Daily_Intimacy_CatalogCard"]["next"]
    check("S3 目录 next 顺序：Up < 翻页闸 < Switch_Turn < AllCapped",
          cc.index("[JumpBack]Daily_Intimacy_Up") < cc.index("Daily_Intimacy_Scroll_Ck")
          < cc.index("[JumpBack]Daily_Intimacy_Switch_Turn")
          < cc.index("Daily_Intimacy_AllCapped_CkSet"),
          str(cc))
    check("S3 Exhausted 排在 Up 之前",
          cc.index("Daily_Intimacy_Exhausted") < cc.index("[JumpBack]Daily_Intimacy_Up"))
    st = d["Daily_Intimacy_Switch_Turn"]
    check("S4 Switch_Turn.next 改走翻页计数", st["next"] == ["Daily_Intimacy_Scroll_Inc"])
    si = d["Daily_Intimacy_Scroll_Inc"]
    check("S4 翻页计数节点：Scroll 步数 +1 后走下一位",
          si["custom_action_param"] == {"tag": "Intimacy_Scroll_Step", "value": 1}
          and si["next"] == ["Daily_Intimacy_Turn_NextPerson"])
    ck = d["Daily_Intimacy_Scroll_Ck"]
    check("S5 翻页闸：Scroll 步数达 6（inverse）才触发",
          ck["custom_recognition_param"] == {"tag": "Intimacy_Scroll_Step", "max": 6}
          and ck.get("inverse") is True and ck["next"] == ["Daily_Intimacy_Swip_Page"])
    sw, pg = d["Daily_Intimacy_Swip"], d["Daily_Intimacy_Swip_Page"]
    same = all(pg.get(k) == sw.get(k) for k in
               ["max_hit", "recognition", "roi", "expected", "action",
                "custom_action", "custom_action_param"])
    check("S6 翻页滑屏参数与原 Swip 逐项一致", same)
    check("S6 翻页滑屏出口：复位节点 + fail-closed（非回主界面空转）",
          pg["next"] == ["Daily_Intimacy_Scroll_Reset"]
          and pg["on_error"] == ["Daily_Intimacy_AllCapped_Unfinished"])
    rs = d["Daily_Intimacy_Scroll_Reset"]
    check("S7 翻页复位：只复位 Set 与 Scroll 步数，不复位 Turn",
          rs["custom_action_param"]["tags"] == ["Intimacy_Switch_Set", "Intimacy_Scroll_Step"]
          and rs["next"] == ["Daily_Intimacy_CatalogCard"])
    um = d["Daily_Intimacy_Up_MSG"]
    check("S8 Up_MSG：正常 next 未动 + 超时 15000 + 快速谈兜底",
          um["next"] == ["Daily_Intimacy_Talk_Enter", "Daily_Intimacy_Up_MSG"]
          and um.get("timeout") == 15000
          and um.get("on_error") == ["Daily_Intimacy_FastTalk"])
    ft = d["Daily_Intimacy_FastTalk"]
    check("S9 快速谈心钮：ROI 落在快速钮（720p 由 11-01 实测设备框 /1.5 换算）",
          ft["roi"] == [1047, 631, 119, 36] and ft["expected"] == "快速谈心"
          and ft["next"] == ["Daily_Intimacy_FastTalk_Ck"]
          and ft["on_error"] == ["Daily_Intimacy_Switch_Turn"])
    fc = d["Daily_Intimacy_FastTalk_Ck"]
    check("S10 快速确认窗：与 Up_MSG 同 ROI/文案 + 超时 + 死钮前进",
          fc["roi"] == um["roi"] and fc["expected"] == "确认"
          and fc.get("timeout") == 15000
          and fc["next"] == ["Daily_Intimacy_FastTalk_Done"]
          and fc["on_error"] == ["Daily_Intimacy_Switch_Turn"])
    fd = d["Daily_Intimacy_FastTalk_Done"]
    check("S11 快速结算等待：目录头复现后经翻页计数前进，超时亦前进",
          fd["roi"] == d["Daily_Intimacy_CatalogCard"]["roi"]
          and fd["expected"] == "亲密度增益" and fd.get("only_rec") is True
          and fd["next"] == ["Daily_Intimacy_Scroll_Inc"]
          and fd["on_error"] == ["Daily_Intimacy_Switch_Turn"])
    for name in NEW_NODES:
        s = json.dumps(d[name], ensure_ascii=False)
        check(f"S12 新节点无 MarkComplete：{name}", "MarkComplete" not in s)
    check("S12 Unfinished 出口无 MarkComplete",
          "MarkComplete" not in json.dumps(d["Daily_Intimacy_AllCapped_Unfinished"]))
    check("S12 正常出口 End 仍打标",
          d["Daily_Intimacy_End"]["custom_action"] == "MarkComplete")
    for name in ["Daily_Intimacy_Exhausted", "Daily_Intimacy_End",
                 "Daily_Intimacy_Up", "Sub_Intimacy_Number", "Sub_Intimacy_LV"]:
        check(f"S12 未动节点：{name}", d[name] == b[name])


# ---------------------------------------------------------------- C: 逻辑模拟
class Char:
    def __init__(self, normal, fast, level=10, maxed=False):
        self.normal = normal  # live | dead
        self.fast = fast      # live | dead
        self.level = level
        self.maxed = maxed

    def up_matches(self):
        # Up = Sub_Intimacy_Number（静态 1/1 徽，谈后仍显示）+ Sub_Intimacy_LV（1-19）
        return (not self.maxed) and 1 <= self.level <= 19


def simulate(pages, remaining, scroll_enabled, max_cycles=10000):
    """返回 (outcome, stats)。outcome: complete | unfinished | HANG。

    模型要点（与实测行为对齐）：
    - Up 判据 = 静态 1/1 徽 + LV 1-19：已耗尽对象仍命中 Up，点普通谈心后
      靠 Up_MSG 超时 → 快速谈兜底 → 仍死则前进下一位来区分。
    - 锚点越过当页末行后，点按落空、选区失效（sel=None）。佐证：11-02/11-03
      夜 AllCapped 能触发——若选区恒在死钮对象上，Up 将恒命中、
      AllCapped 永无触发机会。
    """
    tags = {"Set": 0, "Turn": 0, "Scroll": 0}
    page, anchor, sel = 0, 0, None
    stats = {"turns": 0, "swipes": 0, "talks": 0, "fast_talks": 0,
             "skipped_dead": 0, "cycles": 0, "mark_complete": False}

    def advance():
        nonlocal anchor, sel
        anchor += 1
        if anchor < len(pages[page]):
            sel = pages[page][anchor]
        else:
            sel = None  # 越过末行：点按落空，选区失效

    for cycle in range(max_cycles):
        stats["cycles"] = cycle + 1
        stats["turns"] = tags["Turn"]
        # 1) Set 闸（首轮）：锚首位
        if tags["Set"] < 1:
            tags["Set"] = 1
            anchor = 0
            sel = pages[page][0] if pages[page] else None
        # 2) Exhausted：剩余归零 → End 打标
        if remaining == 0:
            stats["mark_complete"] = True
            return "complete", stats
        # 3) Up：选中对象可谈判据命中 → 点普通谈心
        if sel is not None and sel.up_matches():
            if sel.normal == "live":
                remaining -= 1
                sel.normal = sel.fast = "dead"
                stats["talks"] += 1
                sel = None  # 正常谈后回列表页（10-31 实测：谈后走下一位）
                continue
            # 普通钮静默 → Up_MSG 超时 → 快速谈心兜底
            if sel.fast == "live":
                remaining -= 1
                sel.normal = sel.fast = "dead"
                stats["talks"] += 1
                stats["fast_talks"] += 1
                # FastTalk_Done → Scroll_Inc 前进
                tags["Turn"] += 1
                tags["Scroll"] += 1
                advance()
                continue
            # 快速钮亦静默 → 前进下一位
            stats["skipped_dead"] += 1
            tags["Turn"] += 1
            tags["Scroll"] += 1
            advance()
            continue
        # 4) 翻页闸（新）：步数达 6
        if scroll_enabled and tags["Scroll"] >= 6:
            if page >= len(pages) - 1:
                stats["turns"] = tags["Turn"]
                return "unfinished", stats  # 滑不动 → fail-closed
            stats["swipes"] += 1
            page += 1
            tags["Set"] = 0
            tags["Scroll"] = 0  # Turn 不复位
            continue
        # 5) Switch_Turn：Turn 未满 → 下一位
        if tags["Turn"] < 100:
            tags["Turn"] += 1
            tags["Scroll"] += 1
            advance()
            continue
        # 6) AllCapped：Set 已置且 Turn 满 → fail-closed
        stats["turns"] = tags["Turn"]
        return "unfinished", stats
    return "HANG", stats


def dead():
    return Char("dead", "dead")


def cases():
    # C1：可谈对象在第二页（首屏全是耗尽/死钮对象）——旧 vs 新
    p1 = [dead() for _ in range(6)]
    p2 = [Char("live", "live"), Char("live", "live")] + [dead() for _ in range(4)]
    out_old, st_old = simulate([p1, p2], 2, scroll_enabled=False)
    check("C1 旧逻辑：首屏外可谈对象不可达，100 转触顶未完成",
          out_old == "unfinished" and st_old["talks"] == 0, f"{out_old} {st_old}")
    out_new, st_new = simulate([p1, p2], 2, scroll_enabled=True)
    check("C1 新逻辑：翻页后谈成 2 次、正常完成、Turn 未满",
          out_new == "complete" and st_new["talks"] == 2
          and st_new["mark_complete"] and st_new["swipes"] >= 1
          and st_new["turns"] < 100, f"{out_new} {st_new}")
    # C2：全员耗尽 + 剩余 >0 → fail-closed，不打标，不挂死
    out, st = simulate([[dead() for _ in range(6)]], 2, scroll_enabled=True)
    check("C2 全员耗尽：fail-closed 未完成、无打标、有界终止",
          out == "unfinished" and not st["mark_complete"] and st["turns"] <= 100,
          f"{out} {st}")
    # C3：剩余 0 入场 → 立即正常完成
    out, st = simulate([[dead() for _ in range(6)]], 0, scroll_enabled=True)
    check("C3 剩余 0：立即正常完成、零 Turn", out == "complete" and st["turns"] == 0)
    # C4：普通死钮 + 快速可用（11-02 尤里/马莫尼勒型）→ 快速谈清零
    p = [Char("dead", "live"), Char("dead", "live")] + [dead() for _ in range(4)]
    out, st = simulate([p], 2, scroll_enabled=True)
    check("C4 普通死钮快速可用：经快速谈完成、至少 1 次快速谈",
          out == "complete" and st["fast_talks"] >= 1, f"{out} {st}")
    # C5：双钮皆死（11-03 白雷尤里型）→ 跳过不挂死，最终 fail-closed
    p = [Char("dead", "dead")] + [dead() for _ in range(5)]
    out, st = simulate([p], 1, scroll_enabled=True)
    check("C5 双钮皆死：跳过该对象、不挂死、最终 fail-closed",
          out == "unfinished" and st["skipped_dead"] >= 1 and not st["mark_complete"],
          f"{out} {st}")
    # C6：Lv.20 Max 对象永不触发 Up（LV 围栏）
    p = [Char("live", "live", level=20, maxed=True)] + [dead() for _ in range(5)]
    out, st = simulate([p], 1, scroll_enabled=True)
    check("C6 Max 对象：Up 不命中、零谈成",
          st["talks"] == 0, f"{out} {st}")
    # C7：87 人名册全覆盖——可谈对象在第 80、86 位时 Turn 仍 <100
    roster = [dead() for _ in range(87)]
    roster[80] = Char("live", "live")
    roster[86] = Char("live", "live")
    pages = [roster[i:i + 6] for i in range(0, 87, 6)]
    out, st = simulate(pages, 2, scroll_enabled=True)
    check("C7 87 人全覆盖：第 80/86 位可谈对象在 Turn 100 内谈成",
          out == "complete" and st["talks"] == 2 and st["turns"] < 100,
          f"{out} {st}")


def main():
    d, b = load(sys.argv[1]), load(sys.argv[2])
    structural(d, b)
    cases()
    print(f"\n{'ALL GREEN' if not FAILURES else 'FAILURES: ' + str(FAILURES)}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    sys.exit(main())

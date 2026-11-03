#!/usr/bin/env python3
"""黄金竞技场阵容 spec 校验器：形状检查 + 与本地 bd2-db 对账（costumes / blessings 表）。

用法: python3 validate_spec.py <spec.json> [--db <bd2.sqlite 路径>]
全绿 exit 0；有 ERROR exit 1（WARNING 不拦）。驱动 gc_setup.py 只应吃校验通过的 spec。
"""
import argparse, json, os, sqlite3, sys

ELEMENTS = {"Fire", "Water", "Wind", "Light", "Darkness"}
DTYPES = {"Physical", "Magical"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--db", default=os.path.expanduser("~/workspace/bd2-db/bd2.sqlite"))
    a = ap.parse_args()
    errors, warns = [], []
    E = errors.append; W = warns.append
    spec = json.load(open(a.spec, encoding="utf-8"))
    con = sqlite3.connect(a.db)
    db_costumes = {r[0]: r for r in con.execute(
        "SELECT c.costume_id, ch.name_cn, c.name_cn, ch.element, ch.damage_type "
        "FROM costumes c JOIN characters ch ON ch.id = c.character_id")}
    db_costume_by_name = {}
    for r in db_costumes.values():
        db_costume_by_name.setdefault((r[1], r[2]), r)
    db_bless = {r[0]: r for r in con.execute("SELECT name, cost, category, banned_s45 FROM blessings")}
    con.close()

    if spec.get("schema_version") != "1.0":
        E(f"schema_version 应为 '1.0'，实为 {spec.get('schema_version')!r}")
    if not spec.get("season"):
        E("缺 season")
    src = spec.get("source") or {}
    if not src.get("guide_url"):
        W("source.guide_url 为空（出处应可追溯）")
    rules = spec.get("season_rules")
    if rules is None:  # 兼容旧键
        rules = next((v for k, v in spec.items() if k.startswith("season_rules")), None)
        if rules is not None:
            W("使用了旧键名 season_rules_*，请改名 season_rules")
    if not rules:
        E("缺 season_rules")
        rules = {}
    cols = rules.get("board_cols") or 0
    rows_n = rules.get("board_rows") or 0
    units = rules.get("units")
    banned_cells = {tuple(c) for c in (rules.get("banned_cells_col_row") or [])}
    banned_bless = set(rules.get("banned_blessings") or [])
    banned_costumes = set(rules.get("banned_costumes") or [])
    budget = {"first_attack": rules.get("first_attack_blessing_budget"),
              "second_attack": rules.get("second_attack_blessing_budget")}

    costumes = spec.get("costumes") or {}
    if not costumes:
        E("costumes 为空")
    for slug, c in costumes.items():
        r = db_costume_by_name.get((c.get("character"), c.get("costume_name")))
        if r is None:
            E(f"costumes.{slug}: 目录中找不到「{c.get('character')}·{c.get('costume_name')}」")
            continue
        if c.get("costume_id") != r[0]:
            E(f"costumes.{slug}: costume_id 应为 {r[0]}（实为 {c.get('costume_id')}）")
        if c.get("element") != r[3]:
            E(f"costumes.{slug}: element 应为 {r[3]}（实为 {c.get('element')}）")
        if c.get("damage_type") != r[4]:
            E(f"costumes.{slug}: damage_type 应为 {r[4]}（实为 {c.get('damage_type')}）")
        kw = c.get("search_keyword") or ""
        if not kw or kw not in (c.get("costume_name") or ""):
            E(f"costumes.{slug}: search_keyword「{kw}」必须是服装名的子串")
        if c.get("costume_name") in banned_costumes:
            E(f"costumes.{slug}: 该服装本季被禁用")

    lineups = spec.get("lineups") or []
    if not lineups:
        E("lineups 为空")
    for lu in lineups:
        lid = lu.get("id", "?")
        members = lu.get("members_in_placement_order") or []
        if units and len(members) != units:
            E(f"{lid}: 成员数 {len(members)} != 规则 units {units}")
        cells, slugs = set(), set()
        for m in members:
            slug = m.get("costume")
            if slug not in costumes:
                E(f"{lid}: 成员引用了未定义的 costume slug「{slug}」")
            if slug in slugs:
                E(f"{lid}: slug「{slug}」重复出现")
            slugs.add(slug)
            cell = m.get("cell_col_row")
            if cell is None:
                E(f"{lid}: {slug} 格位为 null（未解决，不得喂驱动）")
                continue
            cc, rr = cell
            if not (1 <= cc <= cols and 1 <= rr <= rows_n):
                E(f"{lid}: {slug} 格位 {cell} 超出棋盘 {cols}x{rows_n}")
            if tuple(cell) in banned_cells:
                E(f"{lid}: {slug} 落在禁格 {cell}")
            if tuple(cell) in cells:
                E(f"{lid}: 格位 {cell} 被重复占用")
            cells.add(tuple(cell))
            bm = m.get("burst_min")
            if bm is not None and not (0 <= bm <= 3):
                E(f"{lid}: {slug} burst_min {bm} 越界（0-3）")
        bl = lu.get("blessings") or {}
        for side in ("first_attack", "second_attack"):
            items = bl.get(side)
            if items is None:
                E(f"{lid}: 缺 blessings.{side}")
                continue
            total = 0
            for b in items:
                br = db_bless.get(b.get("name"))
                if br is None:
                    E(f"{lid}.{side}: 庇佑「{b.get('name')}」不在 blessings 表（全名含罗马数字须逐字一致）")
                    continue
                if b.get("cost") != br[1]:
                    E(f"{lid}.{side}: 「{b['name']}」费用应为 {br[1]}（实为 {b.get('cost')}）")
                total += br[1]
                if b["name"] in banned_bless:
                    E(f"{lid}.{side}: 「{b['name']}」本季被禁用")
            if budget[side] is not None and total != budget[side]:
                E(f"{lid}.{side}: 费用合计 {total} != 预算 {budget[side]}")
    unresolved = spec.get("unresolved") or []
    if unresolved:
        W(f"spec 带 unresolved 缺口 {len(unresolved)} 项（pull 未完整，喂驱动前须人工清零）")

    for w in warns:
        print("WARNING:", w)
    for e in errors:
        print("ERROR:", e)
    print(f"== {a.spec}: {len(errors)} errors, {len(warns)} warnings ==")
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()

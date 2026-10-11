#!/usr/bin/env python3
"""MFABD2 本地补丁重打工具（sideload 模式）。

补丁的事实源是本目录的 manifest.json；部署目录里的资源文件只是被打补丁的
目标，版本更新把整个目录换掉也不会伤到补丁本身。更新后跑一遍本工具即可
把全部补丁重新应用到新版资源树。

用法：
  python3 apply_patches.py --check  --resource-dir <资源 pipeline 目录>
  python3 apply_patches.py --apply  --resource-dir <资源 pipeline 目录>

--resource-dir 指向包含 Pass.json/Battle.json/... 的 pipeline 目录，例如：
  已安装发布包： C:/Users/<user>/Apps/MFABD2-vX.Y.Z/resource/base/pipeline
  仓库源码树：   <repo>/assets/resource/base/pipeline

判定是逐条 edit 进行的（一个补丁可含多条 edit）：
  edit 已应用：replacement 出现次数 >= 预期 count
  edit 待应用：anchor 出现次数 == 预期 count
  edit 冲突：  两者都不成立（上游漂移）——拒绝猜测，按
               PATCH_MAINTENANCE.md 的冲突 playbook 处理后更新 manifest
补丁三态：
  APPLIED    全部 edits 已应用且 applied_markers 全部命中——不需要动作
  PENDING    无冲突、至少一条 edit 待应用（其余已应用）——--apply 只补待应用的
  CONFLICT   任一 edit 冲突，或 edits 全应用但 marker 未命中（manifest 不一致）
  RETIRED    manifest 标记 retired——跳过（上游已原生修复）

--apply 的安全纪律：
  * 逐补丁原子性：一个补丁只要有一条 edit 冲突，整条补丁不写
  * 写前逐文件备份 <文件>.bak-<yyyymmdd>-<patch-id>（已存在则不覆盖）
  * 写后立刻 json.loads 校验 + marker 复核，失败报错
  * 幂等：对已 APPLIED 的补丁不做任何写入
"""
import argparse, json, shutil, sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_manifest():
    return json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))


def read_tree(resource_dir, manifest):
    """读入资源目录里 manifest 涉及的全部文件，返回 {文件名: (原文, eol)}。"""
    files = {}
    names = set()
    for p in manifest["patches"]:
        names.update(p["files"])
    for name in names:
        path = resource_dir / name
        if not path.exists():
            files[name] = (None, "\n")
            continue
        raw = path.read_bytes()
        eol = "\r\n" if b"\r\n" in raw else "\n"
        files[name] = (raw.decode("utf-8").replace("\r\n", "\n"), eol)
    return files


def node_block(text, node):
    """提取 "Node": { ... } 的完整块（跳过字符串内容的括号匹配）。"""
    key = f'"{node}": {{'
    i = text.find(key)
    if i < 0:
        return None
    j = text.find("{", i)
    depth, k, in_str, esc = 0, j, False, False
    while k < len(text):
        c = text[k]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[i:k + 1]
        k += 1
    return None


def markers_ok(patch, files):
    for m in patch["applied_markers"]:
        text = files[m["file"]][0]
        if text is None:
            return False
        if "node" in m:
            block = node_block(text, m["node"])
            if block is None or m["contains"] not in block:
                return False
        elif m["contains"] not in text:
            return False
    return True


def edit_state(edit, files):
    """返回 (state, reason)：state ∈ applied|pending|conflict。"""
    text = files[edit["file"]][0]
    if text is None:
        return "conflict", f"{edit['file']} 不存在"
    if edit["type"] == "replace":
        scope, where = text, edit["file"]
        # 插入新节点的 edit：replacement 以另一个节点的定义开头。
        # 若该节点定义已存在于文件中（位置可能与本工具的插入点不同，
        # 如手工部署或上游部分采纳），视为已应用，禁止重复插入。
        stripped = edit["replacement"].lstrip()
        if stripped.startswith('"') and '": {' in stripped[:80]:
            new_key = stripped.split('"')[1]
            anchor_key = edit["anchor"].strip().lstrip('"').split('"')[0]
            if new_key != anchor_key and f'"{new_key}": {{' in text:
                return "applied", ""
    elif edit["type"] == "node_replace":
        scope = node_block(text, edit["node"])
        if scope is None:
            return "conflict", f"{edit['file']} 找不到节点 {edit['node']}"
        where = f"{edit['file']} 节点 {edit['node']} 内"
    else:
        return "conflict", f"未知 edit type: {edit['type']}"
    if scope.count(edit["replacement"]) >= edit["count"]:
        return "applied", ""
    if scope.count(edit["anchor"]) == edit["count"]:
        return "pending", ""
    return "conflict", (f"{where} 锚点命中 {scope.count(edit['anchor'])} 次、"
                        f"replacement 命中 {scope.count(edit['replacement'])} 次，"
                        f"预期 {edit['count']} 次：{edit['anchor'][:60]}...")


def apply_edit(edit, files):
    """把一条 pending edit 应用到内存副本（调用前已确认 state=pending）。"""
    fname = edit["file"]
    text = files[fname][0]
    if edit["type"] == "replace":
        files[fname][0] = text.replace(edit["anchor"], edit["replacement"])
    else:  # node_replace
        block = node_block(text, edit["node"])
        files[fname][0] = text.replace(
            block, block.replace(edit["anchor"], edit["replacement"]), 1)


def patch_state(patch, files):
    """返回 (state, detail)。markers 是「已应用」的语义定义，先于 edit 级判定：
    补丁可能被手工部署或上游部分采纳，edit 锚点对不上位置不等于没应用。"""
    if markers_ok(patch, files):
        return "applied", ""
    states = []
    for e in patch["edits"]:
        st, reason = edit_state(e, files)
        if st == "conflict":
            return "conflict", reason
        states.append(st)
    if all(s == "applied" for s in states):
        if markers_ok(patch, files):
            return "applied", ""
        return "conflict", "edits 全部已应用但 applied_markers 未命中（manifest 不一致，请人工核对）"
    return "pending", f"{states.count('pending')}/{len(states)} 条 edit 待应用"


def main():
    ap = argparse.ArgumentParser(description="MFABD2 本地补丁重打工具")
    ap.add_argument("--check", action="store_true", help="只报告三态，不写文件")
    ap.add_argument("--apply", action="store_true", help="把 PENDING 的 edits 写入资源树")
    ap.add_argument("--resource-dir", required=True, help="pipeline 目录（含 Pass.json 等）")
    args = ap.parse_args()
    if args.check == args.apply:
        ap.error("--check 与 --apply 必须二选一")

    resource_dir = Path(args.resource_dir)
    if not resource_dir.is_dir():
        print(f"资源目录不存在：{resource_dir}")
        return 2
    manifest = load_manifest()
    files = read_tree(resource_dir, manifest)
    exit_code = 0
    stamp = date.today().strftime("%Y%m%d")

    for patch in manifest["patches"]:
        pid = patch["id"]
        if patch.get("status") == "retired":
            print(f"RETIRED   {pid}（上游已原生修复，跳过）")
            continue
        state, detail = patch_state(patch, files)
        if state == "applied":
            print(f"APPLIED   {pid}")
            continue
        if state == "conflict":
            print(f"CONFLICT  {pid}：{detail}")
            print("          → 按 patches/PATCH_MAINTENANCE.md 冲突 playbook 处理，禁止硬打。")
            exit_code = 2
            continue
        # pending
        if args.check:
            print(f"PENDING   {pid}（{detail}，可 --apply 重打）")
            continue
        work = {k: [v[0], v[1]] for k, v in files.items()}
        touched = set()
        for e in patch["edits"]:
            st, _ = edit_state(e, work)
            if st == "pending":
                apply_edit(e, work)
                touched.add(e["file"])
        # JSON 合法性校验（全部 edits 后）
        bad = None
        for fname in touched:
            try:
                json.loads(work[fname][0])
            except Exception as ex:
                bad = f"{fname} 应用后 JSON 校验失败：{ex}"
        if bad:
            print(f"CONFLICT  {pid}：{bad}")
            exit_code = 2
            continue
        for fname in sorted(touched):
            old_text, eol = files[fname]
            new_text = work[fname][0]
            if new_text == old_text:
                continue
            target = resource_dir / fname
            backup = target.with_name(f"{fname}.bak-{stamp}-{pid}")
            if not backup.exists():
                shutil.copy2(target, backup)
            target.write_bytes(new_text.replace("\n", eol).encode("utf-8"))
            print(f"APPLIED   {pid} → {fname}（备份 {backup.name}）")
        files = {k: (v[0], v[1]) for k, v in work.items()}
        state2, detail2 = patch_state(patch, files)
        if state2 != "applied":
            print(f"ERROR     {pid}：写入后复核未通过（{state2}：{detail2}）")
            exit_code = 2

    if args.check:
        print("（--check 模式，未写入任何文件）")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

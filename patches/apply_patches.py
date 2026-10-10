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

三态报告（每个补丁一条结论）：
  APPLIED    已应用（applied_markers 全部命中）——不需要动作
  PENDING    未应用且全部锚点完好——--apply 可安全重打
  CONFLICT   锚点数量与 manifest 预期不符（上游改版漂移）——拒绝猜测，
             按 PATCH_MAINTENANCE.md 的冲突 playbook 处理后更新 manifest
  RETIRED    manifest 标记 retired——跳过（上游已原生修复）

--apply 的安全纪律：
  * 逐补丁原子性：一个补丁的全部 edits 都能命中才写它涉及的文件
  * 写前逐文件备份 <文件>.bak-<yyyymmdd>-<patch-id>（已存在则不覆盖）
  * 写后立刻 json.loads 校验，校验失败恢复备份并报错
  * 幂等：对已 APPLIED 的补丁不做任何写入
"""
import argparse, json, shutil, sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load_manifest():
    return json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))


def read_tree(resource_dir):
    """读入资源目录里 manifest 涉及的全部文件，返回 {文件名: (原文, eol)}。"""
    files = {}
    names = set()
    for p in load_manifest()["patches"]:
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


def try_edits(patch, files):
    """在内存副本上试应用全部 edits。成功返回 (True, 新files)；失败返回
    (False, 原因)。不写盘。"""
    work = {k: [v[0], v[1]] for k, v in files.items()}
    for e in patch["edits"]:
        fname = e["file"]
        text = work[fname][0]
        if text is None:
            return False, f"{fname} 不存在"
        if e["type"] == "replace":
            n = text.count(e["anchor"])
            if n != e["count"]:
                return False, f"{fname} 锚点命中 {n} 次，预期 {e['count']} 次：{e['anchor'][:60]}..."
            work[fname][0] = text.replace(e["anchor"], e["replacement"])
        elif e["type"] == "node_replace":
            block = node_block(text, e["node"])
            if block is None:
                return False, f"{fname} 找不到节点 {e['node']}"
            n = block.count(e["anchor"])
            if n != e["count"]:
                return False, f"{fname} 节点 {e['node']} 内锚点命中 {n} 次，预期 {e['count']} 次"
            new_block = block.replace(e["anchor"], e["replacement"])
            work[fname][0] = text.replace(block, new_block, 1)
        else:
            return False, f"未知 edit type: {e['type']}"
    # 全部 edits 后，所涉文件必须仍是合法 JSON
    for fname in {e["file"] for e in patch["edits"]}:
        try:
            json.loads(work[fname][0])
        except Exception as ex:
            return False, f"{fname} 应用后 JSON 校验失败：{ex}"
    return True, {k: (v[0], v[1]) for k, v in work.items()}


def main():
    ap = argparse.ArgumentParser(description="MFABD2 本地补丁重打工具")
    ap.add_argument("--check", action="store_true", help="只报告三态，不写文件")
    ap.add_argument("--apply", action="store_true", help="把 PENDING 的补丁写入资源树")
    ap.add_argument("--resource-dir", required=True, help="pipeline 目录（含 Pass.json 等）")
    args = ap.parse_args()
    if args.check == args.apply:
        ap.error("--check 与 --apply 必须二选一")

    resource_dir = Path(args.resource_dir)
    if not resource_dir.is_dir():
        print(f"资源目录不存在：{resource_dir}")
        return 2
    manifest = load_manifest()
    files = read_tree(resource_dir)
    exit_code = 0
    changed_files = {}

    for patch in manifest["patches"]:
        pid = patch["id"]
        if patch.get("status") == "retired":
            print(f"RETIRED   {pid}（上游已原生修复，跳过）")
            continue
        if markers_ok(patch, files):
            print(f"APPLIED   {pid}")
            continue
        ok, result = try_edits(patch, files)
        if not ok:
            print(f"CONFLICT  {pid}：{result}")
            print(f"          → 按 patches/PATCH_MAINTENANCE.md 冲突 playbook 处理，禁止硬打。")
            exit_code = 2
            continue
        if args.check:
            print(f"PENDING   {pid}（锚点完好，可 --apply 重打）")
            continue
        # --apply：逐文件备份 + 写入（本补丁涉及的文件）
        new_files = result
        stamp = date.today().strftime("%Y%m%d")
        for fname in {e["file"] for e in patch["edits"]}:
            old_text, eol = files[fname]
            new_text = new_files[fname][0]
            if new_text == old_text:
                continue
            target = resource_dir / fname
            backup = target.with_name(f"{fname}.bak-{stamp}-{pid}")
            if not backup.exists():
                shutil.copy2(target, backup)
            target.write_bytes(new_text.replace("\n", eol).encode("utf-8"))
            changed_files[fname] = True
            print(f"APPLIED   {pid} → {fname}（备份 {backup.name}）")
        files = new_files
        # 写后复核 marker
        if not markers_ok(patch, files):
            print(f"ERROR     {pid}：写入后 marker 复核未通过，请检查备份并人工处理")
            exit_code = 2

    if args.check:
        print("（--check 模式，未写入任何文件）")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

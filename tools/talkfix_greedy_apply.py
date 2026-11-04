# -*- coding: utf-8 -*-
"""谈心贪心扫描修复：对 Daily.json 做手术式文本编辑（保持其余字节不变）.

用法：python3 apply_fix.py <Daily.json 路径>
断言：每处锚点恰好出现一次；改后 JSON 可解析；除 3 个改动节点 + 7 个新增节点外，
其余节点与输入完全一致（调用方另行与 ac80f385 版比对）。
"""
import json
import re
import sys


def replace_once(txt, old, new, label):
    n = txt.count(old)
    assert n == 1, f"{label}: anchor count = {n}, expected 1"
    return txt.replace(old, new)


def main(path):
    txt = open(path, encoding="utf-8").read()

    # R1: CatalogCard.next 中 Up 之后、Switch_Turn 之前插入翻页闸。
    txt = replace_once(
        txt,
        '            "[JumpBack]Daily_Intimacy_Up",\n'
        '            "[JumpBack]Daily_Intimacy_Switch_Turn",',
        '            "[JumpBack]Daily_Intimacy_Up",\n'
        '            "Daily_Intimacy_Scroll_Ck",\n'
        '            "[JumpBack]Daily_Intimacy_Switch_Turn",',
        "R1 CatalogCard.next",
    )

    # R2: Switch_Turn.next 改走翻页计数节点。
    txt = replace_once(
        txt,
        '"next": ["Daily_Intimacy_Turn_NextPerson"]',
        '"next": ["Daily_Intimacy_Scroll_Inc"]',
        "R2 Switch_Turn.next",
    )

    # R3: Up_MSG 加超时 + 普通钮静默时走快速谈心兜底。
    txt = replace_once(
        txt,
        '        "expected": "确认",\n'
        '        "action": "Click",\n'
        '        "post_delay": 1000,\n'
        '        "next": [\n'
        '            "Daily_Intimacy_Talk_Enter",',
        '        "expected": "确认",\n'
        '        "action": "Click",\n'
        '        "post_delay": 1000,\n'
        '        "timeout": 15000,\n'
        '        "on_error": ["Daily_Intimacy_FastTalk"],\n'
        '        "next": [\n'
        '            "Daily_Intimacy_Talk_Enter",',
        "R3 Up_MSG",
    )

    # R4: 在 Swich_Reset 块之后插入 7 个新节点。Swip_Page 由原 Swip 块原文变换得到
    # （正则等字节保持原样，只换名/desc/next/on_error）。
    m = re.search(
        r'    "Daily_Intimacy_Swip": \{(.*?)\n    \},\n',
        txt,
        re.S,
    )
    assert m, "Swip block not found"
    swip_body = m.group(1)
    assert '"next": ["Daily_Intimacy_Swich_Reset"]' in swip_body
    assert (
        '        "on_error": [\n'
        '            "Global_ToHomePage",\n'
        '            "Global_Null"\n'
        '        ]'
    ) in swip_body
    page_body = swip_body.replace(
        '"next": ["Daily_Intimacy_Swich_Reset"]',
        '"next": ["Daily_Intimacy_Scroll_Reset"]',
    ).replace(
        '        "on_error": [\n'
        '            "Global_ToHomePage",\n'
        '            "Global_Null"\n'
        '        ]',
        '        "on_error": ["Daily_Intimacy_AllCapped_Unfinished"]',
    )
    # 原 Swip 块无 desc 字段；给 Page 版补 desc（插在 max_hit 之前）。
    page_body = page_body.replace(
        '        "max_hit": 3,',
        '        "desc": "[本地补丁] 谈心翻页：上滑一屏切到下一页名册；滑不动（已到底）时走 fail-closed 未完成出口，不打标完成。见 patches/manifest.json#daily-intimacy-greedy-20261103",\n'
        '        "max_hit": 3,',
        1,
    )
    swip_page = '    "Daily_Intimacy_Swip_Page": {' + page_body + '\n    }'

    new_nodes = r'''    "Daily_Intimacy_Scroll_Inc": {
        "desc": "[本地补丁] 谈心翻页计数：每次“下一位”后翻页步数 +1，满 6 步触发翻页。见 patches/manifest.json#daily-intimacy-greedy-20261103",
        "action": "Custom",
        "custom_action": "UpdateTag",
        "custom_action_param": {
            "tag": "Intimacy_Scroll_Step",
            "value": 1
        },
        "next": ["Daily_Intimacy_Turn_NextPerson"]
    },
    "Daily_Intimacy_Scroll_Ck": {
        "desc": "[本地补丁] 谈心翻页闸：翻页步数达 6（当前页约一屏已走完）且未谈成时触发翻页，不再烧满 100 转空点。见 patches/manifest.json#daily-intimacy-greedy-20261103",
        "recognition": "Custom",
        "custom_recognition": "CheckTag",
        "custom_recognition_param": {
            "tag": "Intimacy_Scroll_Step",
            "max": 6
        },
        "inverse": true,
        "next": ["Daily_Intimacy_Swip_Page"]
    },
    "Daily_Intimacy_Scroll_Reset": {
        "desc": "[本地补丁] 谈心翻页复位：只复位 Set 闸与翻页步数（不复位 Turn 总预算），下一轮重锚首位继续走。见 patches/manifest.json#daily-intimacy-greedy-20261103",
        "action": "Custom",
        "custom_action": "ResetTag",
        "custom_action_param": {
            "tags": [
                "Intimacy_Switch_Set",
                "Intimacy_Scroll_Step"
            ]
        },
        "next": ["Daily_Intimacy_CatalogCard"]
    },
    "Daily_Intimacy_FastTalk": {
        "desc": "[本地补丁] 快速谈心兜底：普通谈心确认窗超时未出（普通钮静默）时改点快速谈心钮；快速谈只给基础经验、不进剧情记录。见 patches/manifest.json#daily-intimacy-greedy-20261103",
        "recognition": "OCR",
        "roi": [
            1047,
            631,
            119,
            36
        ],
        "expected": "快速谈心",
        "action": "Click",
        "post_delay": 1000,
        "next": ["Daily_Intimacy_FastTalk_Ck"],
        "on_error": ["Daily_Intimacy_Switch_Turn"]
    },
    "Daily_Intimacy_FastTalk_Ck": {
        "desc": "[本地补丁] 快速谈心确认窗：点确认进入快速谈结算；超时未出（快速钮亦静默）时视为该对象不可谈，前进下一位。见 patches/manifest.json#daily-intimacy-greedy-20261103",
        "recognition": "OCR",
        "roi": [
            662,
            405,
            118,
            118
        ],
        "expected": "确认",
        "action": "Click",
        "post_delay": 1000,
        "timeout": 15000,
        "next": ["Daily_Intimacy_FastTalk_Done"],
        "on_error": ["Daily_Intimacy_Switch_Turn"]
    },
    "Daily_Intimacy_FastTalk_Done": {
        "desc": "[本地补丁] 快速谈结算等待：等目录头复现（结算完成）后经翻页计数前进下一位；超时未复现亦前进（不挂死）。目录重估时 Exhausted 照常检查归零。见 patches/manifest.json#daily-intimacy-greedy-20261103",
        "recognition": "OCR",
        "roi": [
            218,
            62,
            95,
            27
        ],
        "expected": "亲密度增益",
        "only_rec": true,
        "pre_delay": 5000,
        "timeout": 30000,
        "next": ["Daily_Intimacy_Scroll_Inc"],
        "on_error": ["Daily_Intimacy_Switch_Turn"]
    }'''

    # Swich_Reset 是文件最后一个节点（块尾无逗号，文件以 "    }\n}" 收尾）。
    swich_reset = (
        '    "Daily_Intimacy_Swich_Reset": {\n'
        '        "action": "Custom",\n'
        '        "custom_action": "ResetTag",\n'
        '        "custom_action_param": {\n'
        '            "tags": [\n'
        '                "Intimacy_Switch_Set",\n'
        '                "Intimacy_Switch_Turn"\n'
        '            ]\n'
        '        },\n'
        '        "next": ["Daily_Intimacy_CatalogCard"]\n'
        '    }\n'
        '}'
    )
    assert txt.count(swich_reset) == 1, "Swich_Reset anchor count != 1"
    txt = txt.replace(
        swich_reset,
        swich_reset[:-1] + ",\n" + new_nodes + ",\n" + swip_page + "\n}\n",
        1,
    )

    # 校验：可解析；新节点齐全。
    d = json.loads(txt)
    for name in [
        "Daily_Intimacy_Scroll_Inc",
        "Daily_Intimacy_Scroll_Ck",
        "Daily_Intimacy_Swip_Page",
        "Daily_Intimacy_Scroll_Reset",
        "Daily_Intimacy_FastTalk",
        "Daily_Intimacy_FastTalk_Ck",
        "Daily_Intimacy_FastTalk_Done",
    ]:
        assert name in d, f"missing node {name}"
    open(path, "w", encoding="utf-8").write(txt)
    print("OK: edited", path)


if __name__ == "__main__":
    main(sys.argv[1])

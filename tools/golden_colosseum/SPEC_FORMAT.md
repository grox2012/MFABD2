# 黄金竞技场阵容 spec —— 输入格式契约（schema_version 1.0）

`gc_setup.py` 的唯一输入。攻略 pull（LLM 按 `PULL_PROMPT.md` 从攻略网页提取）产出本格式，
`validate_spec.py` 校验通过后才允许喂给驱动。金样例：`fixtures/lineup-spec-s45.json`（S45 两套阵容，实战验证过）。

## 顶层字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `schema_version` | ✓ | 固定 `"1.0"` |
| `game` | ✓ | `"Brown Dust 2 - Golden Colosseum"` |
| `season` | ✓ | 赛季号，如 `"S45"`；**每季新建一个 spec 文件**（`lineup-spec-s46.json` …），不覆盖旧季 |
| `source` | ✓ | `{guide_url, guide_title, extract_file?, positions_provenance}`：出处与格位来源说明（攻略文字/站位图反演），不得留空 |
| `season_rules` | ✓ | 本季规则（**每季现读游戏内规则页或攻略确认**，字段见下） |
| `costumes` | ✓ | 本 spec 用到的服装字典：key = 小写下划线 slug（自选，全 spec 内唯一） |
| `lineups` | ✓ | 阵容数组（攻略按分数段给几套就几套；无分段给一套） |

## `season_rules`

```json
{
  "board_cols": 4, "board_rows": 5,
  "units": 6,
  "first_attack_blessing_budget": 7,
  "second_attack_blessing_budget": 9,
  "banned_cells_col_row": [[4,1],[3,2],[1,3],[4,3],[2,4],[3,5]],
  "banned_blessings": ["永恒祝福","先锋斗志","极限诅咒II","按兵不动"],
  "banned_costumes": [],
  "note": "规则来源与读取日期"
}
```
格位坐标一律 `[列, 行]`，左上 = `[1,1]`，列 1..board_cols、行 1..board_rows。

## `costumes.<slug>`

```json
{
  "character": "莎赫拉查德",
  "costume_id": "000303",
  "costume_name": "魔法学校教授",
  "element": "Water",              // Fire/Water/Wind/Light/Darkness，与本地库一致
  "damage_type": "Magical",        // Physical/Magical
  "search_keyword": "教授",         // 名单放大镜搜索词：服装名中 1–2 个确定字，必须是 costume_name 的子串
  "note": "可选：同名碰撞/攻略误记等陷阱说明"
}
```
身份字段（id/属性/类型）**以本地库 bd2-db 为准**，不以攻略文本为准；攻略与库冲突时用库并在 `note` 记明。

## `lineups[]`

```json
{
  "id": "L2",                       // L1/L2… 按分数段升序
  "band": "1500+",                  // 适用分数段（攻略原文）
  "members_in_placement_order": [   // 数组顺序 = 游戏内放置顺序 = 行动顺序，驱动全清后按此重建
    {"costume": "<slug>", "cell_col_row": [1,2], "burst_min": 0, "range_potential_required": false}
  ],
  "blessings": {
    "first_attack":  [{"name": "突袭准备", "cost": 1}],   // 数组顺序 = 游戏内添加顺序
    "second_attack": [{"name": "守护屏障I", "cost": 1}]
  }
}
```
- `burst_min`：攻略要求的爆发解锁段数下限（0–3）；`range_potential_required`：攻略是否要求范围潜能。
  驱动/setup **只校验不自动升级**：账号不达门槛即停机汇报（用户裁决 Q3）。
- 庇佑 `name` 必须与本地库 `blessings` 表全名逐字一致（含罗马数字），`cost` 必须与库一致；
  两侧费用合计必须 **等于** 对应预算（攻略给的就是打满的配置；不等即提取有误）。
- 同一角色的不同服装可同队（如莎赫拉查德两件）；同 slug 不得重复出现；成员格位不得重复、不得落在禁格。
- 被本季禁用的服装/庇佑不得出现在任何阵容里。

## 校验

`python3 validate_spec.py <spec.json>`：形状检查 + 与 bd2-db（costumes/blessings 表）逐项对账 +
预算/禁格/重复检查。全绿才可交给 `gc_setup.py --spec <spec.json> --lineup L<n> --mode rehearse|commit [--blessings]`。

# 攻略阵容 pull 提示词（每周/每季复用）

用法：`pull_prepare.py` 会把本模板与①攻略网页正文（含站位图说明）②本地库目录
（costumes 全表、blessings 全表）拼成一份完整 prompt 交给大模型；模型**只输出 spec JSON**，
随后必须过 `validate_spec.py`。占位符 `{{...}}` 由 prepare 脚本填充。

---

你是一个数据提取器。任务：从《棕色尘埃2》黄金竞技场攻略网页中，提取**当前最新赛季**的推荐阵容，
输出为驱动脚本规定的 spec JSON 格式（schema_version 1.0，格式契约见文末）。

## 输入材料
1. 攻略网页正文：{{GUIDE_TEXT}}
2. 本地服装目录（权威身份源，字段：character / costume_name / costume_id / element / damage_type）：{{COSTUME_CATALOG}}
3. 本地庇佑目录（权威源，字段：name / cost / category）：{{BLESSING_CATALOG}}
4. 本季游戏内规则（若附有规则页文本/截图转录则以它为准；否则用攻略写的规则）：{{SEASON_RULES_TEXT}}

## 提取规则（硬性）
1. **只提取攻略明确给出的阵容**：有几套（按分数段）提几套；成员、格位、庇佑、爆发/潜能门槛逐项照抄攻略，不许凭经验补全、不许替补、不许优化。
2. **服装身份以服装目录为准**：按「角色名+服装名」在目录中定位，复制其 costume_id / element / damage_type。
   - 攻略用词与目录不一致时（如攻略误记的别名），以目录名为准，并在该服装的 `note` 写明攻略原文写法。
   - **同名服装有多个主人时**（目录里同 costume_name 不同 character），必须用攻略上下文（角色名/属性）消歧，并在 `note` 标注同名陷阱。
   - 目录里找不到的服装：不要编造，把它放进顶层 `unresolved` 数组（写明攻略原文），该阵容其余部分照常输出。
3. **search_keyword**：取服装名的 1–2 个确定汉字（必须是 costume_name 的子串，优先取辨识度最高的字，如「教授」「钢铁」）。
4. **格位**：攻略若给站位图，按图读格位（坐标 [列,行]，左上 [1,1]）；先用图中的禁格（红 X）位置校准行列方向再读其余格子。
   读不准的格子不要猜——把该成员的 `cell_col_row` 置为 `null` 并在 `unresolved` 说明。攻略只有文字站位描述时按文字转换。
   在 `source.positions_provenance` 写明格位来源（站位图/文字）与读取方式。
5. **庇佑**：名字必须与庇佑目录逐字一致（含 I/II/III 罗马数字后缀，如「桎梏之链II」≠「桎梏之链I」），`cost` 复制目录值；
   按攻略给出的顺序输出（驱动按此顺序添加）。目录里找不到的庇佑进 `unresolved`，不要替换成近名卡
   （特别注意形近名：「守护圣域」≠「圣域之恩」、「生命结界」≠「均衡结界」）。
6. **门槛**：`burst_min` = 攻略要求该服装的爆发解锁段数（没写 = 0）；攻略要求范围潜能时 `range_potential_required: true`（没写 = false）。
7. **赛季规则**：`season_rules` 的棋盘/人数/预算/禁格/禁庇佑/禁服装以规则输入为准；
   攻略与规则输入都没有的数值不要猜，对应字段填 `null` 并在 `unresolved` 标明「须人工现读规则页」。
8. **预算自检**：每套阵容两侧庇佑费用合计应等于对应预算；不等时不要自行增删，在 `unresolved` 注明差额。

## 输出
只输出一个 JSON 对象（不要解释文字、不要 markdown 围栏），结构严格按格式契约：
`schema_version / game / season / source{guide_url, guide_title, positions_provenance} / season_rules /
costumes{slug: {...}} / lineups[{id, band, members_in_placement_order, blessings{first_attack, second_attack}}] / unresolved[]`。
slug 用「角色拼音或英文名_服装关键词」的英文小写下划线形式（如 `sara_professor`）。
`unresolved` 为空数组时表示提取完整无缺口。

## 格式契约（SPEC_FORMAT.md 全文）
{{SPEC_FORMAT}}

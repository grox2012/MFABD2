# 谈心贪心扫描修复离线测试结果（fix/daily-intimacy-greedy-20261103）

- 分支：fix/daily-intimacy-greedy-20261103（自 fix/daily-intimacy-failclosed-20261031 @ ac80f385 拉出）
- 基线对照：ac80f385 版 Daily.json（md5 bb3eac3528d9806e4c63ad51fe9fa628）
- 测试脚本：tools/talkfix_greedy_test.py（结构 S + 逻辑模拟 C，纯离线，不碰游戏）
- 运行命令：python3 tools/talkfix_greedy_test.py assets/resource/base/pipeline/Daily.json /tmp/daily_failclosed.json
- 结论：ALL GREEN（结构 35 项 + 逻辑 8 项 = 43 项全过）

## 覆盖清单

- S1-S2：节点总数 = 基线 +7；7 个新节点在位；除 3 个改动节点外其余节点与基线逐项一致。
- S3：目录 next 顺序 Exhausted < Up < Scroll_Ck < Switch_Turn < AllCapped_CkSet。
- S4-S7：Switch_Turn 改走翻页计数；翻页闸 Scroll 步数达 6（inverse）；滑屏参数与原 Swip 逐项一致；滑屏出口 = 复位节点 + fail-closed；复位只复位 Set 与 Scroll 步数、不复位 Turn。
- S8-S11：Up_MSG 正常 next 未动 + 超时 15000 + 快速谈兜底；快速谈心钮 ROI [1047,631,119,36]；快速确认窗与 Up_MSG 同 ROI/文案 + 超时 + 死钮前进；快速结算等待目录头复现后经翻页计数前进、超时亦前进。
- S12：7 个新节点与 Unfinished 出口均无 MarkComplete；正常出口 End 仍打标；Exhausted/End/Up/Sub_Number/Sub_LV 未动。
- C1：可谈对象在第二页时，旧逻辑 100 转触顶未完成、新逻辑翻页后谈成 2 次正常完成。
- C2：全员耗尽 + 剩余>0 → fail-closed 未完成、无打标、有界终止。
- C3：剩余=0 入场 → 立即正常完成、零 Turn。
- C4：普通死钮 + 快速可用（11-02 尤里/马莫尼勒型）→ 经快速谈完成。
- C5：双钮皆死（11-03 白雷尤里型）→ 跳过不挂死、最终 fail-closed。
- C6：Lv.20 Max 对象 Up 不命中、零谈成。
- C7：87 人名册全覆盖，可谈对象在第 80/86 位时 Turn <100 谈成。

## 模型修正记录（测试过程中的真实发现）

- 首版逻辑模拟在 C1/C2/C5/C7 全部 HANG：原因是模型把“锚点越过当页末行后选区仍停在末位死钮对象”写死了，导致 Up 恒命中、Turn 永不触顶。
- 修正：锚点越页后选区失效（sel=None）。佐证：11-02/11-03 夜 AllCapped 确实触发——若选区恒在死钮对象上，Up 将恒命中、AllCapped 永无触发机会。
- 该修正同时是实战待验点：若实机上越页后选区仍停在末位对象且 Up 恒命中，则 Turn 触顶时 AllCapped 可能被 Up 抢占而出现超时空转，须在实战首验中观察 Turn=100 附近的行为。

## 未验证项（离线无法证实，须实战首验）

1. MAA on_error 触发语义：本修复假定识别失败/超时也走 on_error（Up_MSG 超时→FastTalk、FastTalk_Ck 超时→前进、Swip_Page 滑不动→Unfinished）；若 MAA 仅在动作失败时触发 on_error，快速兜底分支永不触发（正常路径不受影响）。
2. 快速钮 ROI [1047,631,119,36] 与确认窗框由 11-01 设备框 /1.5 换算，未经逐帧重算。
3. 每页 6 行、滑距沿用原 Swip（约 5 行）为推断；若实机行距/滑距不同，覆盖仍有界（Turn 100 + 到底 fail-closed），但可能多空点或多翻页。
4. 约 20 秒/转的周期耗时来源未定案（默认 20 秒等待或双 OCR 耗时二选一），本次未优化。
5. 实战首验必须覆盖：有剩余次数的日常段；首屏下可谈者翻页命中；普通死钮 + 快速可用兜底；到底 fail-closed；正常完成路径不受影响。未过实战验不算修好（验收两段制）。

## 原始输出

PASS S1 节点总数 = 基线 + 7
PASS S1 新节点在位 Daily_Intimacy_Scroll_Inc
PASS S1 新节点在位 Daily_Intimacy_Scroll_Ck
PASS S1 新节点在位 Daily_Intimacy_Swip_Page
PASS S1 新节点在位 Daily_Intimacy_Scroll_Reset
PASS S1 新节点在位 Daily_Intimacy_FastTalk
PASS S1 新节点在位 Daily_Intimacy_FastTalk_Ck
PASS S1 新节点在位 Daily_Intimacy_FastTalk_Done
PASS S2 除 3 个改动节点外其余节点与基线逐项一致
PASS S3 目录 next 顺序：Up < 翻页闸 < Switch_Turn < AllCapped
PASS S3 Exhausted 排在 Up 之前
PASS S4 Switch_Turn.next 改走翻页计数
PASS S4 翻页计数节点：Scroll 步数 +1 后走下一位
PASS S5 翻页闸：Scroll 步数达 6（inverse）才触发
PASS S6 翻页滑屏参数与原 Swip 逐项一致
PASS S6 翻页滑屏出口：复位节点 + fail-closed（非回主界面空转）
PASS S7 翻页复位：只复位 Set 与 Scroll 步数，不复位 Turn
PASS S8 Up_MSG：正常 next 未动 + 超时 15000 + 快速谈兜底
PASS S9 快速谈心钮：ROI 落在快速钮（720p 由 11-01 实测设备框 /1.5 换算）
PASS S10 快速确认窗：与 Up_MSG 同 ROI/文案 + 超时 + 死钮前进
PASS S11 快速结算等待：目录头复现后经翻页计数前进，超时亦前进
PASS S12 新节点无 MarkComplete：Daily_Intimacy_Scroll_Inc
PASS S12 新节点无 MarkComplete：Daily_Intimacy_Scroll_Ck
PASS S12 新节点无 MarkComplete：Daily_Intimacy_Swip_Page
PASS S12 新节点无 MarkComplete：Daily_Intimacy_Scroll_Reset
PASS S12 新节点无 MarkComplete：Daily_Intimacy_FastTalk
PASS S12 新节点无 MarkComplete：Daily_Intimacy_FastTalk_Ck
PASS S12 新节点无 MarkComplete：Daily_Intimacy_FastTalk_Done
PASS S12 Unfinished 出口无 MarkComplete
PASS S12 正常出口 End 仍打标
PASS S12 未动节点：Daily_Intimacy_Exhausted
PASS S12 未动节点：Daily_Intimacy_End
PASS S12 未动节点：Daily_Intimacy_Up
PASS S12 未动节点：Sub_Intimacy_Number
PASS S12 未动节点：Sub_Intimacy_LV
PASS C1 旧逻辑：首屏外可谈对象不可达，100 转触顶未完成
PASS C1 新逻辑：翻页后谈成 2 次、正常完成、Turn 未满
PASS C2 全员耗尽：fail-closed 未完成、无打标、有界终止
PASS C3 剩余 0：立即正常完成、零 Turn
PASS C4 普通死钮快速可用：经快速谈完成、至少 1 次快速谈
PASS C5 双钮皆死：跳过该对象、不挂死、最终 fail-closed
PASS C6 Max 对象：Up 不命中、零谈成
PASS C7 87 人全覆盖：第 80/86 位可谈对象在 Turn 100 内谈成

ALL GREEN

# 补丁 C 立项诊断稿：赛季任务魔兽子段（EM.EM.等级下调活锁）摘除/改道

- 诊断日期：2026-10-16（PDT）
- 性质：**只读诊断**。未改任何代码/配置，未碰运行中的 MFAAvalonia 与游戏实例，未启停任何进程。fork 仓仅 `git log` 只读。
- 对象：「[执行]赛季活动快速战斗」任务内魔兽子段，连续两晚活锁：
  - 2026-10-15 两轮：19:02:17、19:17:01 两次进入（第二轮为自修复补跑复卡），当日 app 日志 `EM.EM.等级下调` 共 **94 条**；
  - 2026-10-16 一轮：18:08:07 进入，共 **34 条**（18:15 人工停队列止）。
  - 活锁周期 ≈ **6.15 秒/轮**（[Record] 时间戳实测）。
- 证据源：实装日志 `C:\Users\wanya\Apps\MFABD2-v4.4.4\logs\log-20261015.log` / `log-20261016.log`、框架日志 `debug\maafw.log`（reco 原始输出）、卡点帧 `stuck-2026-10-16/emu_stuck_season_fiend_1810.jpg`、fork 与实装 pipeline/interface/instance 配置原文。

---

## 1. 赛季任务 pipeline 全图

### 1.1 文件与入口

| 层 | fork（补丁载体） | 实装（运行态） |
|---|---|---|
| pipeline | `~/MFABD2-fork/assets/resource/base/pipeline/EventBattle.json`（124 节点） | `C:\Users\wanya\Apps\MFABD2-v4.4.4\resource\base\pipeline\EventBattle.json` |
| interface | `~/MFABD2-fork/assets/interface.json` | `C:\Users\wanya\Apps\MFABD2-v4.4.4\interface.json` |
| 实例配置 | — | `config\instances\1a979e84.json`（日常-尽快完成） |
| 公共节点 | `assets/resource/base/pipeline/Global.json`（Global_ToHomePage / Global_BackPageHub_Once / Global_WaitingForLoading 等定义） | 同名文件 |
| 历史备份 | — | `EventBattle.json.bak-20261006-ismenu`（2026-10-06 IsMenu 修复前备份，仍在位） |

任务定义（两侧一致）：`[执行]赛季活动快速战斗`，entry = `Event_HomePage`，无 pipeline_override；挂三个 option：

- `赛季-强制只跑指定子项`（switch，默认 No）——Yes 时以 pipeline_override 把五个 Hub 全部 `enabled:false`，再由 `赛季-指定子项`（checkbox：剧情15战/魔兽讨伐/战场探索/回归魔兽）逐个 `enabled:true` 放行；
- `赛季活动快速战斗难度`（select，默认 自动）——以 override 改写 `SeasonEvent_Battle_Start.next`；
- `魔兽初始等级`（input，默认 "1"）——以 override 把 `Even_MamonoFollow_lvCustom_Ck.expected` 改写为 `[lL][Vv][^a-zA-Z0-9]?{等级}$`。

**实例现行值**（1a979e84.json 实读）：强制只跑 index 0（=No）、难度 index 0（=自动）、魔兽初始等级 "1"——即两晚均为全扇出默认配置。

**fork ↔ 实装一致性**：EventBattle.json 功能字段（剔除 desc/doc）逐节点比对，**仅一处差异**——`Event_Battle_IsMenu.roi`：fork 为旧值 `[626,235,189,54]`，实装为 2026-10-06 修复值 `[620,230,490,200]`（该修复只落了实装、未回 fork，是既有漂移，与本补丁无关但建议顺手对齐）。魔兽子段全部节点两侧**功能逐字相同**；fork 侧多出的只是 desc 注释（jb1 架构说明，见下）。

### 1.2 任务骨架（扇出层）

```
Event_HomePage（DirectHit，只分发）
└─ next: Event_Event_Main, [JB]Global_WaitingForLoading, [JB]Event_GoinEvent, [JB]Global_ToHomePage
Event_GoinEvent（And: 主页活动入口 OCR+色核 → Click (1118,387)，focus=EM.从主页面进入活动）
Event_Event_Main（Or: 赛季活动页标题 OCR×2，timeout 1000，focus=EM.赛季活动进入确认.）——兼任务选择器
└─ next（按序，均为 [JumpBack]，各 Hub 带 max_hit 1）:
   ① Event_Battle_Hub（剧情 15 战） ② Event_Mamono_Hub（魔兽讨伐） ③ Event_MiniGame_Run_Hub（跑酷）
   ④ SeasonEvent_MiniGame_Quiz_HUB（问答） ⑤ SeasonEvent_ReMamono_Hub（回归魔兽）
   ⑥ Global_ToHomePage_Enter ⑦ Global_ToHomePage（终局回主页）
SeasonEvent_Main_Return（Or: Event_Event_Main，只识别，focus 同上）——各子段的"已回赛季页"收尾确认
```

Hub 通式（以魔兽为例）：`Event_Mamono_Hub {enabled:true, max_hit:1, next:[SeasonEvent_Mamono_Start, [JB]Event_GoinEvent, [JB]Global_BackPageHub_Once]}`。`enabled` 是 interface option 的抓手（fork desc 原文自述），`max_hit:1` 保证每轮任务每个子段至多进一次——**但该上限只约束 Hub 层，不约束子段内部循环（见 §2）**。

### 1.3 剧情 15 战段（简图，两晚均正常跑完，非本补丁对象）

`SeasonEvent_Battle_Start`（And: Event_Event_Main；next 由难度 option 改写，自动=`Event_EnterBattle_Auto`）→ `Event_EnterBattle_Auto` → `[JB]SeasonEvent_Battle_Int_Anchor` + `[Anchor]Auto_Battle`（外文件）；或 `SeasonEvent_EnterlBattle_Normal/Challenge`（OCR Click，进关；on_error→`Event_Battle_IsMenu`）→ `SeasonEvent_EnterlBattle_Confirm` → AP 判定 `SeasonEvent_Battle_Recon_AP_Full`（→IsMenu）/ `_AP_Empty`（→Main_Return）；`Event_Battle_IsMenu`（OCR「在战斗中获胜」roi 即 10-06 修复点）→ `Event_FastNormalBattle`/`SeasonEvent_NormlBattle` → 页签切换 `SeasonEvent_TabTo_Challenge/Nomarl`（回 Battle_Start）/ `Event_Battle_BattleStatus_Enable`（Click→`SeasonEvent_FastBattle_SubMenu`→`SeasonEvent_FreeAP_Verdict` 色核分流：Ispass→`Event_NormalBattleMAX`→`Event_TouchNormalBattle`→`Event_NormalBattleIsOver`→Main_Return；NOpass→Main_Return）/ `..._Unable` → `Event_Battle_TabAutoBattle*` 链 → `AutoBattle_Entry`（外文件）；`Event_NoHaveAP` → IsOver/Main_Return。两晚日志实序：难度:自动→难度:挑战→战斗关卡页面→快速战斗→免费AP已选中→快速战斗MAX→战斗结算(无对象)→返回→赛季活动进入确认，约 60 秒完成。

### 1.4 魔兽子段完整节点链（本补丁对象）

入口两条，汇合于 `MamonoEnter`：

**主入口（两晚实走路径，maafw 事件中父节点名 `SeasonEvent_Mamono_Start` 为证）：**

| # | 节点 | 识别 | 动作 | next / on_error |
|---|---|---|---|---|
| 1 | `SeasonEvent_Mamono_Start` | And(Event_Event_Main)，只分发 | — | [InMamono, Mamono_Bypass] |
| 2 | `SeasonEvent_Mamono_Bypass` | OCR roi[174,425,923,172]「可练习战斗」 | 无（无 next，终点） | — （准备期旁路：命中即本段无事结束） |
| 3 | `Even_MamonoFollowUp_InMamono` | OCR roi[99,433,1126,293]「魔兽追踪者」 | Click 命中框，post_wait_freezes 3000 / post_delay 1000 | [MamonoEnter, InMamono, [JB]Global_WaitingForLoading] |
| 4 | **`Even_MamonoFollowUp_MamonoEnter`** | OCR roi[219,25,68,32]「魔兽」，only_rec，focus=**EM.魔兽界面确认打开** | 无 | [**Practice**, **QuickBattle_Enable**, **lv1_Ck**, **InMamono**, **[JB]lvdown**]（按序试） |

**MamonoEnter 的五条出路：**

| 出路 | 节点 | 识别/动作 | 去向 |
|---|---|---|---|
| a 准备期出口 | `SeasonEvent_MamonoFollow_Practice` | Or(Ocr_01: roi[933,27,141,30]「距离开始还」only_rec；Ocr_02: roi[826,215,211,72]「狩猎期间开始解除」) | [Main_Return, [JB]Global_BackPageHub_Once] |
| b 快速战斗 | `SeasonEvent_MamonoFollow_QuickBattle_Enable` | And(OCR roi[842,625,109,49]「快速战斗」 + `Sub_Ocr_Enable_Clr` 色核)，Click，post_delay 2000 | [QuickBattle_ck, 本节点]；on_error [Event_LeaveEvent, Global_Null_Exception, Global_Null_Panic] |
| c 等级链 | `Even_MamonoFollow_lv1_Ck` | OCR roi[858,82,142,67] 正则 `[lL][Vv][^a-zA-Z0-9]?1$`，post_delay 1000，focus=E.复位到Lv1 | [lvCustom_Ck, [JB]MmnHpUp] |
| d 回枢纽 | `Even_MamonoFollowUp_InMamono` | 同 #3 | 回 #4 |
| e 兜底（**活锁源**） | `Even_MamonoFollowUp_lvdown` | And(MamonoEnter)，**Click target (851,113)，repeat 15，repeat_delay 300**，focus=**EM.EM.等级下调**；**无 next / 无 max_hit / 无 timeout** | JumpBack：执行完回 #4 的 next 列表重扫 |

**等级链与战斗链（c 命中后）：**

| 节点 | 识别/动作 | next |
|---|---|---|
| `Even_MamonoFollow_lvCustom_Ck` | OCR 同 roi，正则 `Lv?{魔兽初始等级}$`（option 注入，当前 =1），post_wait_freezes/post_delay 3000 | [HP_Hunting, [JB]HP_Hunted, [JB]HP_NoMeetHunt] |
| `SeasonEvent_MamonoFollow_HP_Hunting` | Or(`Rec_Mamono_HP_Hunting_Ocr`：roi[714,136,276,29] 血量「非空非全满」正则) | [QuickBattle_Enable, QuickBattle_Unable] |
| `SeasonEvent_MamonoFollow_HP_Hunted` | Or(血量「为空」正则)，max_hit 50 | [MmnHpUp]（升一级后回等级链逐级跟随） |
| `SeasonEvent_MamonoFollow_HP_NoMeetHunt` | Or(血量「全满」正则 / `SeasonEvent_Mamono_HP_Right_Red` 色核)，max_hit 10 | [NormalBattle] |
| `Even_MamonoFollowUp_MmnHpUp` | DirectHit，Click (974,114)，post_delay 1000，focus=EM.EM.等级上调 | 无（JumpBack 回调用方列表） |
| `SeasonEvent_MamonoFollow_QuickBattle_Enable/Unable` | 同上 b / And(OCR「快速战斗」+`Sub_Ocr_Unable_Clr`)，timeout 10000 | Unable→[BackedToSubMain, [JB]WaitingForLoading, [JB]BackPageHub_Once]；on_error [Global_ToHomePage, …] |
| `Even_MamonoFollowUp_QuickBattle_ck` | OCR roi[691,547,83,33]「确认」，Click，post_delay 2000 | [[JB]QuickBattle_Cleared, PostVerify, 本节点] |
| `Even_MamonoFollowUp_QuickBattle_Cleared` | And(`Rec_Reward_Ocr` 奖励识别)，Click (1,1)，post_delay 1500 | 无（领奖终点） |
| `Even_MamonoFollowUp_QuickBattle_PostVerify` | And(onSubMain) | [HP_Hunting, [JB]HP_Hunted, [JB]HP_NoMeetHunt] |
| `SeasonEvent_MamonoFollow_NormalBattle` | OCR roi[1044,631,74,35]「去战斗」，only_rec | [NormalBattle_Enable, NormalBattle_Unable] |
| `..._NormalBattle_Enable` | And(`Anc_Ocr_Enable_Clr`)，Click，timeout 40000 | [AutoBattle_Entry(外文件), [JB]AutoBattle 退出链, [JB]WaitingForLoading] |
| `..._NormalBattle_Unable` | And(`Anc_Ocr_Unable_Clr`) | [Team_Troubleshoot] |
| `SeasonEvent_MamonoFollow_Team_Troubleshoot` | OCR roi[608,240,100,43]「?」，only_rec | [Team_Edit] |
| `..._Team_Edit` | OCR roi[644,617,141,68]「编辑队伍」，Click | [Team_UsePreset, 本节点] |
| `..._Team_UsePreset` | OCR roi[734,651,100,37]「推荐部署」，Click | [Team_FindPreset, 本节点] |
| `..._Team_FindPreset` | OCR roi[972,155,118,430]「使用」，Click，focus=使用推荐部署覆盖本地部署 | [Team_End, 本节点, [JB]BackPageHub_Once] |
| `..._Team_End` | And(NormalBattle)，只识别 | 无（终点） |
| `Even_MamonoFollowUp_lv1NoMet` | ColorMatch roi[987,134,10,32] 红 (151,21,21)-(154,23,23) count 10 | [onSubMain] |
| `Even_MamonoFollowUp_onSubMain` | OCR roi[702,158,151,41]「阶段最高」 | [Main_Return, [JB]BackPageHub_Once] |
| `SeasonEvent_BackedToSubMain` | And(Event_Event_Main)，只识别 | 无（终点） |

**回归入口（赛季外回归魔兽，与主链共用 MamonoEnter 以下全部节点）：**
`SeasonEvent_ReMamono_Hub`（enabled, max_hit 1）→ `SeasonEvent_ReMamono_Start`（And: Event_GoinEvent，timeout 2000）→ `SeasonEvent_ReMamono_Enter`（OCR roi[833,132,269,235]「回归赛季」，Click，timeout 5000；next [MamonoEnter, [JB]WaitingForLoading, 本节点]，on_error [Global_ToHomePage]）。

**小游戏段（简图）**：跑酷 `Event_MiniGame_Run_Hub`→`Event_MiniGame_Run_Switch`（Custom 每日存档判据）→`SeasonEvent_MiniGame_Run_Start`→`Event_MiniGame_Run_Entry`→`..._QuickComplete`→`..._CLR_Enable/Unable`→`..._Confirm`→`..._RewardBack`→`..._Back`→`Event_MiniGame_Run_End`→Global_ToHomePage；问答 `SeasonEvent_MiniGame_Quiz_HUB`→`..._CheckDaily`（Custom）→`..._PreEntry`→`..._Entry`→`..._GoAction`→`..._SubMenu`→`..._Enter/Swipe`→`..._SandBox`→`..._Reward`。

### 1.5 两晚实走轨迹（日志 [Record] 全序，两晚逐字相同）

```
…复位到主菜单-已确认 → EM.从主页面进入活动 → EM.赛季活动进入确认. → 赛季活动-15战模块
→ EM.活动.难度:自动 → EM.活动.难度:挑战 →（载入）→ EM.活动.战斗关卡页面 → EM.活动.快速战斗
→ EM.免费AP已选中 → EM.活动.快速战斗MAX → EM.活动.战斗结算(无对象) → GO.点击返回按钮
→ EM.赛季活动进入确认. →（InMamono 点底部页签「魔兽追踪者」，约 10 s）→ EM.魔兽界面确认打开
→ EM.EM.等级下调 ×N（6.15 s/轮，直至人工停队列）
```

---

## 2. 「等级下调」为何在 CHALLENGE 备战页不生效——证据级归因

**结论先行：定到「页面状态不符」层（根因层），并在识别层、落点层各有逐条原始证据钉死。** 不是识别参数调优问题，而是整条等级链所假设的页面形态在狩猎期正式页上不存在。

### 2.1 单轮循环的逐条 reco 实录（2026-10-16 18:08:07–18:08:14，debug\maafw.log）

MamonoEnter 命中后（OCR「魔兽」box [219,25,68,32] score 0.9992，即正式页左上标题），框架按 next 顺序逐个试识别：

| 候选 | 当晚 OCR 原始输出 | 结果 |
|---|---|---|
| a Practice/Ocr_01（expected「距离开始还」，roi[933,27,141,30]） | 读到 **「距离结束还剩4天」** score 0.99997，filtered=[] | ✗ 文案是狩猎期「结束」倒计时，节点写的是准备期「开始」倒计时 |
| a Practice/Ocr_02（expected「狩猎期间开始解除」，roi[826,215,211,72]） | 读到 "CEN" score 0.70（CHALLENGE 药丸字残片），filtered=[] | ✗ |
| b QuickBattle_Enable 的 OCR 子项（expected「快速战斗」，roi[842,625,109,49]） | 仅读到「红」score 0.158，filtered=[]（And 短路，色核子项未及评估） | ✗ 该 roi 在正式页落在队伍头像行，无快速战斗按钮 |
| c lv1_Ck（expected 正则 `Lv?1$`，roi[858,82,142,67]） | 仅读到 **「(水)」**（box [858,84,59,36]，boss 名「深渊魔姬卡（水）」的元素后缀），filtered=[]，best=null | ✗ **roi 里根本没有 Lv 文本** |
| d InMamono（expected「魔兽追踪者」，roi[99,433,1126,293]） | 无命中记录；因列表顺序在 lvdown 之前，若命中必先于 lvdown 执行，实际命中 lvdown ⇒ 其必未命中（正式页无底部页签栏） | ✗ |
| e **lvdown**（And: MamonoEnter 复检） | 18:08:07.998 `reco hit [result.name=Even_MamonoFollowUp_lvdown]` | ✓ 唯一可命中者 |

lvdown 动作实录：18:08:08.0→18:08:13.4 执行完毕（5.4 s ≈ repeat 15 × 300 ms + 动作开销），action_details 实测 `point=[851,113]` 与配置逐字一致；随后 JumpBack 回 MamonoEnter 列表，18:08:13.55 起第二轮逐字重演（Practice 仍读到「距离结束还剩4天」、lv1_Ck 仍读到「(水)」），周期 6.15 s，与 Monitor [Record] 刷屏周期吻合。10-15 两轮轨迹同型（进入时刻 19:02:17 / 19:17:01，其后同签名刷屏）。

### 2.2 落点层

卡点帧（18:10:37）为狩猎期正式 CHALLENGE 页：boss「深渊魔姬卡（水）」、CHALLENGE 药丸、9,000,000,013,200 血条、队伍 1 战力 60906 / 队伍 2 战力 63287、战术配置开关、编辑队伍/去战斗按钮。lvdown 的点击点 **(851,113)** 在该帧（÷2 换算 (425,56)）落在 boss 头像圆环左侧的**空白背景**上——无任何控件；该页唯一的难度相关控件是 CHALLENGE 药丸的 ‹ › 切换（约 (1034,204)/(1176,202)），功能是切 boss 页签而非数字等级，且纵坐标（y≈190–215）也落在 lv1_Ck 的 roi（y 82–149）之外。即：点 15 下、点 1500 下，页面状态都不会发生任何改变，循环没有任何自发收敛的可能。

### 2.3 结构层（为何是活锁而非超时退出）

1. lvdown 被放在 MamonoEnter 的 next **末位作 JumpBack 兜底**：设计意图应为「等级高于目标时先连点下调、回列表再判 lv1_Ck」，但它自身**无 max_hit、无 timeout、无 next**，MamonoEnter 亦无 timeout——四个真出口全灭时，它成为唯一出口且可无限重入；
2. Hub 层 `max_hit:1` 只防子段被二次进入，防不住子段内部循环；
3. 每次 lvdown 都以 And(MamonoEnter) 复检成功收尾（标题「魔兽」在正式页恒命中），框架从不报错、不走 on_error（lvdown 与 MamonoEnter 均未配 on_error），Monitor 层只剩 [Record] 刷屏。

### 2.4 与 2026-10-06 IsMenu 案的对照

同文件前科：`Event_Battle_IsMenu` 的 OCR roi 没覆盖挑战关页面布局（识别框层问题），扩 roi 至 [620,230,490,200] 修复，备份 `.bak-20261006-ismenu` 至今在位。两案同属「节点假设的页面形态 ≠ 实际页面」，但层级不同：IsMenu 案是**同一页面上 roi 框偏**（调参可解）；本案是**整套等级 UI 在该页面缺席**（roi 内只有 boss 名后缀「(水)」、落点是空白背景），调参无解——这正是立项「摘除/改道」而非再扩 roi 的依据。

### 2.5 证据缺口（不猜测，明示）

- **等级链的设计目标页面形态无当晚帧可证**：链内 roi/落点（Lv 文本约在 x 858–1000、y 82–149，‹ › 在 (851,113)/(974,114)）指向一种带数字等级选择器的魔兽页（与练习侧难度选择布局相容，但本诊断未取练习页帧逐点比对，不下「链是照练习页写的」结论）。能定的是：**该形态 ≠ 狩猎期正式 CHALLENGE 页**（卡点帧 + OCR 原始输出双证）。
- 狩猎期首日（10-15）前该链在准备期的实走轨迹未单独取证：准备期有 Practice 出口（a），按图应在 InMamono 后经 a 收尾，与「准备期两晚无事故」的运行史相容，但属推断、非实录。
- QuickBattle_Enable 的色核子项 `Sub_Ocr_Enable_Clr` 当晚未被评估（And 短路于 OCR 子项），其在正式页上是否本可命中无证据——不影响结论（OCR 子项已先行失败）。

**归因定级：根因 = 页面状态不符（等级链假设的页面形态在狩猎期正式页缺席）；识别层、落点层均为其下游表现且各自有原始证据；结构层（无上限 JumpBack 兜底）为活锁放大器。三层俱全，无需再向「识别调参」方向投入。**

---

## 3. 依赖分析：摘除魔兽子段后赛季任务能否正常收尾

### 3.1 任务完成判定

MaaFramework pipeline 无显性「完成节点」：任务自 entry 沿图行走，图穷尽（终局节点执行完/列表无可命中项）即任务完成。本任务的实际收尾路径 = Event_Event_Main 的 next 列表逐个 JumpBack 子段走完后，落到尾项 `Global_ToHomePage_Enter` / `Global_ToHomePage` 回主页。**没有任何节点读取魔兽子段的"产出"**——pipeline 是无状态画面流，子段间唯一的耦合是画面位置，而每个 Hub 都自带 `[JB]Event_GoinEvent` / `[JB]Global_BackPageHub_Once` 复位兜底，Event_Event_Main 本身又是「在赛季页」的识别锚。魔兽子段在扇出序中居第 2 位，其后是跑酷、问答、回归魔兽与回主页——**这正是两晚被活锁饿死的部分**（任务永不完成 ⇒ 实例队列后续任务 [执行]周常、[领取]×5 全部阻塞，10-15 须人工停队列后补跑剩余队列 19:43 才走完，10-16 亦人工停队列处置）。

### 3.2 通行证 / 活动计数依赖

- 本 pipeline 内**无**任何通行证、活动计数、奖励领取的读取或写回节点依赖魔兽子段；领奖类动作在独立 interface 任务（[领取]活动页奖励 `Activities_Start`、[领取]通行证奖励 `Pass_HomePage`）里，与本任务仅同队列前后关系。
- 魔兽子段自身的游戏内产出只有一项：interface 描述原文「**魔兽补刀：每日快速战斗一次领取参与奖**」——即逐级快速战斗（QuickBattle_Enable→ck→Cleared 领奖点击）与未解锁时的常规战斗自动刷取（NormalBattle 链）。参与奖/击杀奖励是游戏服务器侧发放，脚本侧只是"去打并点掉领奖弹窗"。

### 3.3 摘除后逐项得失

| 项 | 影响 |
|---|---|
| 剧情 15 战段 | 无影响（扇出独立、两晚实证先于魔兽段跑完） |
| 跑酷 / 问答小游戏 | **由"被饿死"变"照常跑"**（含各自每日完成存档判据） |
| 任务收尾 | 恢复正常：扇出走完 → Global_ToHomePage 回主页 → 任务完成、队列后续任务不再被堵 |
| 魔兽快速战斗「参与奖」及逐级击杀领奖 | **脚本侧不再领取**——按督导既定口径转由日常阶段四 ⑮ 正式魔兽段（战术配置法）承担；本诊断只登记此差异，不重复裁决等价性 |
| 魔兽常规战斗刷取（快速战斗不可用时的后备路径） | 一并摘除（同链下游）；⑮ 为正式段全场战斗，覆盖关系同上 |
| 准备期行为 | 原 Practice 出口（进页确认→退出）消失，改为 Hub 层直接跳过——准备期该段本就无产出，**无损失**，且少一次无谓进页 |
| 回归魔兽（ReMamono 链） | 与主链共用 MamonoEnter 以下节点：若只摘主 Hub，回归链仍可达同一活锁（其 Enter 需「回归赛季」UI 命中，赛季内不触发、两晚未涉）；是否一并摘除见 §4 决策点 |
| option「赛季-指定子项」 | 摘除后「魔兽讨伐」case 的 enabled:true override 会把 Hub 重新放行——补丁须对此有交代（§4 保险丝） |

**结论：摘除魔兽子段后，赛季任务可正常收尾，通行证与活动计数零依赖、零损失；唯一让渡的是魔兽补刀的脚本侧参与奖领取，已有 ⑮ 承接口径。**

---

## 4. 候选补丁（≥2 案）

改动载体统一为 fork（`~/MFABD2-fork`），部署另循 fork 纪律（issue→branch→PR→审→部署窗口→.bak+apply+重启 MFAAvalonia→solo 验证），本节只给方案。

### 案 A（推荐）：Hub 层摘除 + lvdown 保险丝

- 改 `assets/resource/base/pipeline/EventBattle.json` 两处 Hub 的一个字段：
  - `Event_Mamono_Hub`：`"enabled": true` → `false`（1 行）；
  - `SeasonEvent_ReMamono_Hub`：同上（1 行）——回归链与主链共用活锁源，一并摘除才符合「赛季段不再进魔兽页」的立項目标（**决策点：若督导要保留赛季外回归魔兽自动化，则此行不改，改为接受其活锁风险靠保险丝兜底**）。
- 保险丝一行：`Even_MamonoFollowUp_lvdown` 加 `"max_hit": 3`（1 行）。理由：interface option 的 pipeline_override 可把 Hub 的 enabled 重新置 true（「赛季-指定子项/魔兽讨伐」case），base 摘除并非不可逆绕过；有了 max_hit，任何路径（option 放行、回归链、未来上游改版）再进 MamonoEnter，lvdown 至多空转 3 轮（约 18 秒）即耗尽，列表穷尽后子段退栈、任务继续——活锁在结构上被根除，而非仅在本配置下消失。
- diff 规模：**3 行**（同一文件）。节点链本体、interface、实例配置全不动。
- 风险：
  - 上游更新覆盖：EventBattle.json 若被官方更新，fork 合并时需重打此 3 行（fork 既有政策内，changelog 可见）；
  - 识别误伤：无（不改任何识别参数；Hub 的 enabled 语义与 interface option 的 override 完全同构，是作者自备的抓手，非生造机制）；
  - 收尾判定：Hub 跳过后 Event_Event_Main 列表照常走完其余项至 Global_ToHomePage（§3.1），max_hit 语义为框架原生字段（Hub 与 HP_Hunted 等节点已在用）；
  - 残余：若未来赛季的魔兽页恢复等级 UI 且业务上想恢复脚本补刀，需手动回滚此 3 行——属可逆小改动，成本低。

### 案 B：MamonoEnter 改道（保留 Hub，拆等级链）

- 改 `EventBattle.json` 中 `Even_MamonoFollowUp_MamonoEnter.next`（约 3 行）：删 `Even_MamonoFollow_lv1_Ck` 与 `[JumpBack]Even_MamonoFollowUp_lvdown` 两项，尾加 `[JumpBack]Global_BackPageHub_Once` 与 `SeasonEvent_Main_Return`——进页后只保留 Practice 出口与快速战斗尝试，两者不中则退回赛季页收尾；并同样给 lvdown 加 max_hit 保险丝（防 PostVerify→HP 链等残余路径回灌）。
- diff 规模：约 **4–6 行**（同一文件、同一节点为主）。
- 风险：
  - 残余面大：QuickBattle_Enable 若在某种页面形态下命中，其下游 ck/PostVerify/HP 链仍通向 MmnHpUp 与 lv1_Ck 的 JumpBack 列表（lv1_Ck 本体还在图里），存在第二条回灌路径，论证与验证成本都高于案 A；
  - 改道后的退栈路径（BackPageHub→Main_Return）需实机验证不会与 Event_Event_Main 的扇出计数（Hub max_hit）相互干扰；
  - 保留了「进魔兽页看一眼」的行为，与立項目标「赛季段不再进魔兽页」字面不符。
- 定位：仅当督导希望保留脚本侧魔兽快速战斗参与奖（不走 ⑮ 承接）时才值得选；与现行口径（⑮ 承担）相悖，**不推荐**。

### 案 C（配置层零 diff，仅登记、不推荐为正案）

- 实例 option 改 `赛季-强制只跑指定子项=Yes` + `赛季-指定子项` 只勾剧情15战/战场探索。机制与案 A 的 Hub 摘除同构、零代码。
- 不推荐理由：① 立项要求补丁进 fork 本体，实例配置在重建/换机/新实例时即失效；② 「强制只跑」改变全任务语义，未来新增子段默认不跑，易漏；③ 与每晚「见签名跳赛季」的人工处置叠加后，配置状态来源变多、排障面变大。可作为部署窗口到来前的临时止血（与现行人工跳赛季口径并行不悖），但不算补丁 C 的交付。

**推荐：案 A（两 Hub 摘除 + lvdown max_hit 保险丝，共 3 行）。** 它用作者自备的 enabled 抓手完成摘除、 diff 最小、无识别面改动，且保险丝把「活锁」这一故障类在结构上关闭，不依赖配置不被改动。

---

## 5. solo 验证方案（部署后）

前置（部署窗口内、避开日常时段）：实装 `EventBattle.json` 先留 `.bak-patchC-<日期>`；apply fork 改动；**重启 MFAAvalonia**（Agent 缓存 pipeline，不重启不生效——既有坑）；`instcfg.ps1` 复核实例绑定三元组（serial 16416 / extras index 1 / 横屏）。

### 5.1 主验证（案 A 生效判定）

- 配置：用既有 solo 实例（config/instances/solo*.json 惯例）或日常实例临时只勾 `[执行]赛季活动快速战斗` 一项；option 保持生产值（强制只跑 No、难度 自动、魔兽初始等级 1）——必须在**默认全扇出**下验证，不许靠 option 关魔兽冒充补丁生效。
- 跑法：游戏停主界面 → 开始任务 → 全程旁观日志（Monitor [Record] + maafw.log）。
- 通过判据（全须满足）：
  1. 任务**自行完成**（出现任务结束/队列收尾记录，中途零人工干预、零停任务动作）；
  2. 日志中 `EM.魔兽界面确认打开` **0 条**、`EM.EM.等级下调` **0 条**（grep 计数为证）——魔兽页根本未进入；
  3. 15 战段轨迹与基线同序（难度:自动→挑战→战斗关卡页面→快速战斗MAX→战斗结算→返回）；
  4. 跑酷/问答段按当日存档状态正常走或正常跳过，最终帧停在主界面（Global_ToHomePage 已执行）；
  5. 任务总时长 ≤ 约 10 分钟（基线：15 战段约 1 分钟 + 小游戏段按当日状态浮动；超限即查）。
- 活锁判据（任一命中即验证失败）：同一 [Record] 以约 6 秒周期重复 ≥3 次；任务运行 >15 分钟未自结；出现新的同签名刷屏。
- 效果核查（跑后直读，沿阶段四口径）：赛季页挑战/AP 状态与跑前对比——剧情段消耗符合预期、魔兽段次数未动（本就应由 ⑮ 承担）；通行证/活动页计数无异常变化。

### 5.2 保险丝附加验证（可选、只在 solo 实例做）

- 在 solo 实例临时以 option 放行魔兽讨伐（强制只跑 Yes + 只勾魔兽讨伐），单跑该任务：预期进入魔兽页后 lvdown 至多 3 轮（日志计数 ≤3）即退栈、任务自行结束（或经其余出口收尾），**不出现第 4 条 `EM.EM.等级下调`**。此项验证「活锁类故障已被结构关闭」，与 5.1 互不替代。验完 solo 实例配置还原。

### 5.3 回滚

- 恢复 `.bak-patchC-<日期>` 覆盖实装 EventBattle.json → 重启 MFAAvalonia → 随手单跑赛季任务确认回到补丁前行为（能进魔兽页、轨迹与基线一致即回滚成功；回滚后每晚口径回到「见活锁签名即跳赛季 + 阶段四手动补 + ⑮ 照打」）。
- fork 侧：补丁走独立 branch/PR，未 merge 前回滚 = 不 merge；已 merge 则 revert 提交，保留 issue 记录。

---

## 附：关键坐标/参数速查（供审 diff 时对图）

- lvdown：And(MamonoEnter) / Click (851,113) / repeat 15 / repeat_delay 300 / 无 next·max_hit·timeout。
- MmnHpUp：Click (974,114) / post_delay 1000。
- lv1_Ck / lvCustom_Ck roi：[858,82,142,67]；正式页该框实读文本仅「(水)」。
- MamonoEnter roi：[219,25,68,32]「魔兽」；InMamono roi：[99,433,1126,293]「魔兽追踪者」（实走为赛季页底部页签，box [672,641,83,21]）。
- QuickBattle_Enable OCR roi：[842,625,109,49]「快速战斗」；HP 三态 OCR roi：[714,136,276,29]。
- 两晚进入时刻：10-15 19:02:17 / 19:17:01；10-16 18:08:07。等级下调条数：10-15 共 94；10-16 共 34（人工停队列截断）。

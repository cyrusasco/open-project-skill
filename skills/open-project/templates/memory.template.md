# <PROJECT> — Memory event log

> **append-only**：舊 entries／rows／狀態／原文都不修改或刪除。更正、取代、撤回只 append 新 event。
> 當前狀態係事件鏈計算結果：current／superseded／revoked；唔回頭改舊 row 成 superseded，唔用刪線覆寫舊內容。
> 每 entry／event 有唯一 ID、time、source-version ref；新事件引用舊 ID。未知不進已驗證事實。

## §0 FROZEN 關係

適用不變量見 `FROZEN_*.md` 及**外部 manifest**。舊 frozen bytes 唔改，supersedes 映射／hash／授權放外部。此處只 append 為何凍結或更換版本嘅證據事件。

## §A 已驗證事實 entries

| entry ID | time | 事實 | evidence ID／version／scope |
|---|---|---|---|
| A1 | <ISO time+offset> | <verified fact> | <ref/hash/command output> |

不要在原 row 寫可變「current」狀態。狀態由 §K events 推導，未被有效 supersedes／revokes 嘅最新鏈端先 current。

## §B 坑與解法 entries

| entry ID | time | 症狀 | 有證據根因 | 解法／observed result | source refs |
|---|---|---|---|---|---|
| B1 | <time> | <symptom> | <evidence-backed cause> | <solution/result> | <refs> |

無證據歸因去 §D；唔將臨時 workaround 自動升格需求。

## §C 誤判紀錄

| entry ID | time | 當時判斷 | 核實後事實 | 教訓／來源 |
|---|---|---|---|---|
| C1 | <time> | <old claim> | <verified correction> | <ref> |

寫新 entry，再 append correction event 指向舊 claim，唔回頭改舊字句。

## §D 待驗證 entries（UNVERIFIED）

| entry ID | time | 說法／缺失 | 原因 | 驗證方法／所需授權 | source ref |
|---|---|---|---|---|---|
| D1 | <time> | <unknown> | <reason> | <next check> | <ref> |

驗證後新增 §A／§B entry，再以 supersedes event 指向舊未知；原未知保留。

## §E 用戶明確指示

| entry ID | time | 原文／具體範圍 | decision/source ref |
|---|---|---|---|
| E1 | <time> | <explicit request/authorization> | <session ref + source version> |

撤回以新 revokes event 指向 E1，唔刪 E1。已有相同範圍明確授權持續有效；不由模糊舊偏好推導破壞性操作授權。

## §F 事件時間線

| entry ID | time | 事件／里程碑 | evidence refs |
|---|---|---|---|
| F1 | <time> | <milestone> | <refs> |

capture time、source 修改時間分開；mtime 不證明作者。

## §G 歷史問題 entries

| entry ID | time | 問題 | 根因／解法或繞道 | 當時 observed 狀態 | source refs |
|---|---|---|---|---|---|
| G1 | <time> | <issue> | <evidence-backed explanation> | <resolved/open/unknown> | <refs> |

後續結果寫新 entry＋event，不編輯當時狀態。序號持續追加，宣稱總數由實際 entry counts 計。

## §H 重複模式

| entry ID | time | 模式／次數／範圍 | 證據 | 工具化評估連結 |
|---|---|---|---|---|
| H1 | <time> | <pattern/count/scope> | <command/query + refs> | <PLAN §6 ID or N/A> |

重複不代表必須自建工具，N/A 可合法。

## §I 歷史未解項

| entry ID | time | 問題／當時缺口 | 下一步 acceptance | ref |
|---|---|---|---|---|
| I1 | <time> | <open item> | <criterion> | <ref> |

即時目前清單放 project_status，呢度保留事件歷史。

## §J 記錄規則

1. 每條有 unique ID、time、來源與範圍，數字連可重跑方法。
2. 同時有新說法與舊說法時，append correction／supersedes event，不改舊 row。
3. current 只由有效事件鏈推導；revoked 不當現行指示，superseded 只當歷史。
4. 新 session 收尾 append 新坑／新證據／新決定；當前狀態放 status。
5. 不記 secret 值；只記存在／位置。不要將整庫私人內容貼入 memory。
6. 設計 acceptance 放 specification；觀察、修復史、fine-tuning 過程留本文件／status／review。

## §K Append-only 狀態／更正事件

| event ID | time | type | target entry/event ID | replacement entry ID | reason／decision evidence |
|---|---|---|---|---|---|
| EVT1 | <time> | <supersedes/revokes/correction> | <old ID> | <new ID or N/A> | <source ref> |

supersedes＝新 entry 取代舊 entry；revokes＝撤回該 entry 效力；correction＝明確指出舊說法錯誤並連新 evidence。原文原行原狀保留；若更正事件本身有誤，再 append event 指向該 event。不要 rewrite 舊狀態為 current／superseded／revoked。

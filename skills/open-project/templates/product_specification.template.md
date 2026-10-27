# <PROJECT> — Product specification

> Contract revision：<ID>　capture time：<ISO8601_WITH_OFFSET>
> 本文件只定義產品應做嘅功能、來源及可判定驗收。observed status、修復史、fine-tuning 輪次、驗證過程寫 status／memory／review（AP-18）。
> 新案來源＝明確用戶要求／訪談。reorg 分開實讀現況同 desired behavior；現存 bug／workaround 唔自動變需求。

## §1 定位與邊界

- 一句話：<邊個喺咩場景解決咩問題／得到咩結果>。
- 使用者／情境：<roles and journeys>。
- In scope：<adopted scope>。
- Out of scope：<explicit exclusions>。
- 約束：<platform/time/budget/compatibility>。

## §2 成功準則

| ID | desired success | 量度方法／固定門檻 | requirement IDs |
|---|---|---|---|
| S1 | <desired outcome> | <measurable threshold + method> | <REQ IDs> |

本節不放「已達／未達」；實際結果放 project_status／review 並引用相同 ID。

## §3 功能矩陣

每項有穩定 requirement ID、來源 ID＋版本、desired behavior 及可客觀判定 acceptance。描述 input／trigger→處理→output／failure behavior，唔以「正常工作」代替準則。

| ID | 來源／版本 | 功能／desired behavior | acceptance（pass/fail） | priority／required |
|---|---|---|---|---|
| REQ1 | <explicit request/interview/source ID> | <trigger, processing, output, errors> | <given/when/then; measurable expected result> | <P0–P3; true/false> |

### §3.1 <功能域>

| ID | 角色／前置條件 | desired flow | 錯誤／邊界行為 | acceptance |
|---|---|---|---|---|
| <REQ ID> | <user/state> | <expected steps> | <failure/retry/permission> | <fixed criterion> |

## §4 User journey

1. <角色／觸發→處理→可見結果；引用 requirement ID>。
2. <拒絕／空值／錯誤路徑及回復行為>。
3. <完成後可觀察輸出／後續操作>。

## §5 非功能要求

| ID | 類別 | desired requirement | acceptance／量度方法 | source ID |
|---|---|---|---|---|
| NFR1 | 性能 | <target> | <fixed test and threshold> | <source> |
| NFR2 | 穩定性 | <desired reliability> | <baseline and measurable result> | <source> |
| NFR3 | 安全／私隱 | <secret/access/data boundary> | <observable criterion> | <source> |
| NFR4 | 可觀測性 | <logs/health/evidence> | <verification method> | <source> |

N/A 要有需求層理由。無 baseline 唔宣稱穩定（AP-12），未確認門檻列未知，唔杜撰。

## §6 外部依賴與產品限制

| ID | 依賴／限制 | desired contract | 失效時行為 | 來源 |
|---|---|---|---|---|
| L1 | <service/platform> | <required behavior> | <fallback/error> | <ref> |

## §7 名詞與追溯

| 名詞／ID | 定義／來源 |
|---|---|
| <term> | <definition> |

requirements→planned drafts→驗收證據 ID 需可追溯。需求變更更新本契約 revision，重建 packet／hash／對應批准；觀察結果不反向改 acceptance 去迎合現況。

# FROZEN_<METHOD>.md — <METHOD> 不可變契約

> 狀態：FROZEN　版本：<ID>　凍結時間：<ISO8601_WITH_OFFSET>
> 範圍：<frozen method/invariants>　授權／證據：<decision/source IDs>
> **本版本凍結後原始 bytes 不得修改**，包括 banner、狀態、連結、換行及更正。新版本及 supersedes 關係放外部 manifest，唔回頭改本檔。

## §1 宣言與邊界

<已驗證且採用嘅方法、適用條件、唔包範圍。未驗證內容唔稱凍結事實。>

## §2 凍結流程

1. <輸入／前置條件→操作→預期輸出>。
2. <後續步驟及明確 failure behavior>。
3. <重試／fail-closed／回復規則>。

## §3 不變量

| ID | 不變量 | acceptance／assertion | evidence ID／revision |
|---|---|---|---|
| INV1 | <observable invariant> | <testable pass/fail> | <ref> |
| INV2 | <invariant> | <assertion> | <ref> |

宣稱數量必須與實際 rows 對帳；唔以永遠 exit 0 當驗證。

## §4 證據清單

| evidence ID | 位置／locator | source version／SHA-256 | capture time／scope |
|---|---|---|---|
| E1 | <test/log/path> | <hash> | <time; coverage> |

## §5 凍結快照

| 項目 | 已觀察值／ref |
|---|---|
| repo／branch／HEAD | <actual snapshot or N/A> |
| 原始文件／檔案 bytes | <external SHA-256 manifest path> |
| 生效來源 | <approval/decision ref> |
| 適用依賴版本 | <pins and refs> |

不要在本檔寫自己嘅最終 hash 形成循環；自身 hash 放外部 manifest。

## §6 可重跑驗證

| invariant ID | 獨立命令／方法 | effects／授權 | expected result |
|---|---|---|---|
| INV1 | <actual safe verifier> | <effects; authorization> | <pass/fail criterion> |

有實際 CLI 先使用 verify；無 CLI＝NOT_APPLICABLE 並採用選定嘅直接檢查，唔為模板生成 CLI。未跑＝NOT_RUN／UNVERIFIED，唔當 PASS。

## §7 已知邊界

<凍結範圍以外、未驗證 host 行為、依賴限制；與不變量分開。>

## §8 版本變更程序（舊版本不改）

1. 取得對具體變更嘅授權及驗收條件；已有同範圍授權沿用。
2. 寫新 `FROZEN_<METHOD>-v<N>.md`，完整內容及 evidence；舊 bytes 保留原位／按已批搬移。
3. 只更新**外部 manifest**：old/new ID、path、SHA-256、supersedes、授權、驗收證據；superseded banner 唔寫入舊檔。
4. 新版本重新驗證；memory append 版本事件及來源，不修改舊 row。
5. 明確目前有效版本由外部 manifest 推導；歷史 hash 不覆寫。

## §9 風險與復原

| 風險 | 觸發 | 緩解／驗證 |
|---|---|---|
| <risk> | <trigger> | <action> |

promotion 復原只保證已驗證嘅 target file bytes；備份、journal、新建空 parent directories 可保留，失敗如實記 FAILED_UNRECOVERED。

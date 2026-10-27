# <PROJECT> — Independent review report

> reviewer：<independent role/session ref>；未參與本輪改動，唯讀、不 commit。
> capture time：<ISO8601_WITH_OFFSET>　review snapshot：<source revision/hash>
> packet：<plan_id; revision; packet SHA-256>　approval：<ref/digest>
> 結論：**<ACCEPTED/CHANGES REQUIRED/PARTIAL>**
> required coverage：<complete/partial/unknown>；P0：<N>；required P1：<N unresolved>；書面範圍變更：<refs or N/A>。

## §1 方法與判定規則

逐項 PASS／FAIL／UNVERIFIED／N/A＋證據。只重跑相關、安全且已授權核對；未跑標 NOT_RUN＋原因，對應結論 UNVERIFIED。不憑作者／subagent 宣稱當證據；自行抽樣核對命令、hash、路徑及資料源。N/A 必須具體理由，不降低已承諾 required acceptance。

**零 P0 只係必要條件**：
- P0 未解→CHANGES REQUIRED。
- required P1 未修→CHANGES REQUIRED；書面豁免唔能將未解 required P1 偽裝通過。
- required coverage／來源／acceptance 未驗證→PARTIAL，唔可 ACCEPTED。
- required checks 完成、無 P0、無未解 required P1，先可 ACCEPTED。授權人明確修改驗收範圍須新 packet／revision／對應批准；限制保留，唔沿用舊 required check 假裝 PASS。
- advisory exit 0、PACKAGED、LOCAL COMPLETE／NOT_PUSHED 各自唔代表 review ACCEPTED。

## §2 P0

| ID | 問題／影響 | path／requirement | 可重跑證據 | 修復／覆核 acceptance |
|---|---|---|---|---|
| <0 items or P0-ID> | <issue> | <locator> | <command/hash/ref> | <criterion> |

越過已批准 draft／target／transform／effects 改內容，或偽造證據，按 P0 處理。

## §3 P1 與書面處理

| ID | 問題 | required | evidence | 修復或具體 waiver ref／風險 | 覆核結果 |
|---|---|---|---|---|---|
| <ID> | <issue> | <true/false> | <ref> | <decision> | <state> |

## §4 P2／roadmap

| ID | 建議／限制 | evidence／位置 | owner／後續 acceptance |
|---|---|---|---|
| <ID> | <suggestion> | <ref> | <action> |

## §5 十二項檢查

| # | 檢查 | required／適用理由 | PASS/FAIL/UNVERIFIED/N/A | evidence ID／命令／exit／範圍 |
|---|---|---|---|---|
| 1 | FROZEN invariants／數量／hash；舊 bytes 不改，外部 supersedes manifest | <scope> | <state> | <ref> |
| 2 | PLAN／JSON／HTML 數字及 packet digest 同源一致 | true | | |
| 3 | 11 節 PLAN、全部 manifest 草稿、必交 spec、來源及 requirements 齊 | true | | |
| 4 | 引用路徑／draft／target／dependencies 可定位且安全 | true | | |
| 5 | Secret SCANNED／NOT_SCANNED 逐檔原因／findings；不輸出值 | <publish scope> | | |
| 6 | 適用 verifier／doctor／verify 實跑；無 CLI 可有理由 N/A | <adopted tools> | | |
| 7 | Git branch／HEAD／dirty；有 push 授權且已 push 才驗遠端 tip | <scope> | | |
| 8 | Native agent line1 frontmatter、host kind／角色與現有模型政策 | <agents or N/A> | | |
| 9 | agent SOP／skill／CLI 一致；命令無假 pipeline／強迫 push | true | | |
| 10 | 抽查過時宣稱；source versions、capture times、未知未假綠 | true | | |
| 11 | rendered PLAN／HTML 完整草稿、離線、escape、安全連結、顯示保真 | true | | |
| 12 | separate approval 綁定 plan／digest／draft／target／baseline／expected／transforms／effects；正式 MD 對帳 | <promote scope> | | |

ZCode AP-17 保留：專屬 agent 有有效用戶確認 provider/model，不空／inherit；模型問題已 RESOLVED，不開 runtime mapping 工程。實際 loaded definition 未可見＝UNKNOWN。fresh session／host enforcement 不由 synthetic tests 推論。

## §6 Coverage 與結果限制

| 範圍 | 已驗證內容 | 未驗證／跳過及原因 | 影響結論 |
|---|---|---|---|
| global discovery | <metadata/content/query/closure/snapshot coverage> | <missing/delta/errors> | <impact> |
| deep-read | <per-source tags/ranges> | <partial/summary-only/unread> | <impact> |
| deterministic tests | <source revision; command; exit> | <scope limits> | <impact> |
| host／fresh session | <loaded role/evidence> | <UNKNOWN if untested> | <impact> |
| browser／offline HTML | <actual inspected behavior> | <unverified parts> | <impact> |
| live／network integration | <actual evidence> | <NOT_RUN reasons> | <impact> |

## §7 Promotion／恢復與最終快照

<逐檔 promoted/no-op/STOPPED_DRIFTED/BLOCKED/FAILED_RECOVERED/FAILED_UNRECOVERED；journal ref。恢復 scope 只係 target_file_bytes，備份／journal／新空 directories 可留存。合作鎖非全域 CAS。>

最終 review 對應 packet／source hash：<IDs>。修復後更新相應 packet／views／approval，再對受影響範圍覆核，唔沿用已變內容嘅舊 PASS。

## §8 證據附件及尾部建議

```text
<實際命令、exit、輸出摘要／hash／refs；secret 值遮蔽；NOT_RUN 有原因>
```

<可選 suggestions、N/A 理由、known limits、下一步；不覆蓋 required failure/unknown。>

# {{PROJECT}} — Independent review report

Status: {{NOT_RUN/PENDING/ACCEPTED/CHANGES_REQUIRED/PARTIAL}}
Reviewer ID: {{ACTUAL_REVIEWER_ID_OR_NOT_RUN}}
Snapshot SHA-256: {{CURRENT_WORKFLOW_SNAPSHOT_OR_NOT_RUN}}

{{Phase4填真實NOT_RUN；完成review後在未批准candidate定稿實際結果。最終accepted須plain Status: ACCEPTED及真實reviewer／snapshot，不能同時留current NOT_RUN/PENDING。}}

> reviewer：{{independent role/session ref}}；未參與本輪改動，唯讀、不 commit。
> capture time：{{ISO8601_WITH_OFFSET}}　review snapshot：{{source revision/hash}}
> packet：{{plan_id; revision; packet SHA-256}}　approval：{{ref/digest}}
> 結論由上方唯一 Status 行表示；observed結果與workflow.review相符。
> required coverage：{{complete/partial/unknown}}；P0：{{N}}；required P1：{{N unresolved}}；書面範圍變更：{{refs or N/A}}。

## §0 Reviewer 身份與獨立性

| 欄位 | 實際值／證據 |
|---|---|
| reviewer_id／author_id | {{不同身份及工作分工；未指派用 NOT_RUN，唔填假身份}} |
| scope／revision | {{plan及當前受審 outputs/evidence snapshot}} |
| snapshot_sha256 | {{workflow snapshot digest；排除 report自身及 terminal envelope 自循環}} |
| changed_ids／affected_areas | {{本輪內容、roots、package等變更；area IDs及原因}} |
| 沿用未受影響結果 | {{舊 review ref、area、source匹配及理由；無則寫無}} |

作者 addendum 只係作者自查；變更後獨立覆核要有實際 reviewer。Phase4可交完整 review 計劃及 NOT_RUN，唔預填未來 ACCEPTED。

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
| {{0 items or P0-ID}} | {{issue}} | {{locator}} | {{command/hash/ref}} | {{criterion}} |

越過已批准 draft／target／transform／effects 改內容，或偽造證據，按 P0 處理。

## §3 P1 與書面處理

| ID | 問題 | required | evidence | 修復或具體 waiver ref／風險 | 覆核結果 |
|---|---|---|---|---|---|
| {{ID}} | {{issue}} | {{true/false}} | {{ref}} | {{decision}} | {{state}} |

## §4 P2／roadmap

| ID | 建議／限制 | evidence／位置 | owner／後續 acceptance |
|---|---|---|---|
| {{ID}} | {{suggestion}} | {{ref}} | {{action}} |

## §5 驗收檢查

| # | 檢查 | required／適用理由 | PASS/FAIL/UNVERIFIED/N/A | evidence ID／命令／exit／範圍 |
|---|---|---|---|---|
| 1 | FROZEN invariants／數量／hash；舊 bytes 不改，外部 supersedes manifest | {{scope}} | {{state}} | {{ref}} |
| 2 | PLAN／JSON／HTML 數字及 packet digest 同源一致 | true | {{CHECK_2_RESULT}} | {{CHECK_2_EVIDENCE}} |
| 3 | 11 節 PLAN、五核心角色、全部草稿、sources／features／settings／requirements及階段義務齊 | true | {{CHECK_3_RESULT}} | {{CHECK_3_EVIDENCE}} |
| 4 | docs/source root分開、creation/action receipts、跨根引用／draft／target／dependencies安全且無斷鏈 | true | {{CHECK_4_RESULT}} | {{CHECK_4_EVIDENCE}} |
| 5 | Secret SCANNED／NOT_SCANNED 逐檔原因／findings；不輸出值 | {{publish scope}} | {{CHECK_5_RESULT}} | {{CHECK_5_EVIDENCE}} |
| 6 | 適用 verifier／doctor／verify 實跑；無 CLI 可有理由 N/A | {{adopted tools}} | {{CHECK_6_RESULT}} | {{CHECK_6_EVIDENCE}} |
| 7 | Git branch／HEAD／tracked及untracked如實；porcelain非空不稱clean；已push核遠端tip | {{scope}} | {{CHECK_7_RESULT}} | {{CHECK_7_EVIDENCE}} |
| 8 | Codex native agent TOML、host kind／角色與用戶／host模型繼承政策 | {{agents or N/A}} | {{CHECK_8_RESULT}} | {{CHECK_8_EVIDENCE}} |
| 9 | agent SOP／skill／CLI 一致；命令無假 pipeline／強迫 push | true | {{CHECK_9_RESULT}} | {{CHECK_9_EVIDENCE}} |
| 10 | 抽查過時宣稱；source versions、capture times、未知未假綠 | true | {{CHECK_10_RESULT}} | {{CHECK_10_EVIDENCE}} |
| 11 | rendered PLAN／HTML 完整草稿、離線、escape、安全連結、顯示保真 | true | {{CHECK_11_RESULT}} | {{CHECK_11_EVIDENCE}} |
| 12 | separate approval 綁定 plan／digest／draft／target／baseline／expected／transforms／effects；正式 MD 對帳 | {{promote scope}} | {{CHECK_12_RESULT}} | {{CHECK_12_EVIDENCE}} |
| 13 | GitNexus onboarding tools row完整；每個採用／建立Skill及Plugin有artifact、owner／source identity、適用graph／catalog驗收及freshness證據 | true；無產物有理由N/A | {{CHECK_13_RESULT}} | {{CHECK_13_EVIDENCE}} |

Codex model／reasoning由用戶及host管理；native agent可省略相關欄位繼承parent，不引入其他harness模型限制。實際loaded definition未可見＝UNKNOWN。fresh session／host enforcement不由synthetic tests推論。

GitNexus PLAN齊件／G6通過不代表onboarding完成。PLANNED／BLOCKED／staged結果不能當VERIFIED；fixture oracle PASS不能推論真實專案。每個artifact對照既有graph／catalog owner、scope／source版本、receipts及可查結果；graph N/A要有該artifact理由，catalog仍需評估。required onboarding缺證據＝PARTIAL，保留缺口，唔為過關擴大現有fixture adapter權限。

## §6 Coverage 與結果限制

| 範圍 | 已驗證內容 | 未驗證／跳過及原因 | 影響結論 |
|---|---|---|---|
| global discovery | {{metadata/content/query/closure/snapshot coverage}} | {{missing/delta/errors}} | {{impact}} |
| deep-read | {{per-source tags/ranges}} | {{partial/summary-only/unread}} | {{impact}} |
| deterministic tests | {{source revision; command; exit}} | {{scope limits}} | {{impact}} |
| host／fresh session | {{loaded role/evidence}} | {{UNKNOWN if untested}} | {{impact}} |
| browser／offline HTML | {{actual inspected behavior}} | {{unverified parts}} | {{impact}} |
| live／network integration | {{actual evidence}} | {{NOT_RUN reasons}} | {{impact}} |
| GitNexus graph／catalog | {{per-artifact IDs; source/pin; receipt; structural query/catalog lookup; freshness; capture time}} | {{PLANNED/BLOCKED; missing real-project/catalog adapter; graph N/A reason}} | {{required incomplete→PARTIAL}} |

## §7 Promotion／恢復與最終快照

{{逐檔 promoted/no-op/STOPPED_DRIFTED/BLOCKED/FAILED_RECOVERED/FAILED_UNRECOVERED；journal ref。恢復 scope 只係 target_file_bytes，備份／journal／新空 directories 可留存。合作鎖非全域 CAS。}}

最終 review 對應 packet／source hash：{{IDs}}。修復後更新相應 packet／views／approval，再對受影響範圍覆核，唔沿用已變內容嘅舊 PASS。

## §8 證據附件及尾部建議

```text
{{實際命令、exit、輸出摘要／hash／refs；secret 值遮蔽；NOT_RUN 有原因}}
```

{{可選 suggestions、N/A 理由、known limits、下一步；不覆蓋 required failure/unknown。}}

### 機械 area IDs 與版本影響

共同12項順序對應 frozen、parity、structure、paths、secrets、verification、git、native_agents、logic、claims、plan_views、promotion。workflow.review.areas 每項有 id/status/evidence/reason；rev3 PASS不能自動覆蓋後加rev5／搬root。受影響area補獨立覆核，未受影響結果有明證先沿用；snapshot/revision/hash不匹配保留 PARTIAL／PENDING。

## §9 結果與 completion

{{NOT_RUN/PENDING/ACCEPTED/CHANGES REQUIRED/PARTIAL；逐required缺口、尚未驗證範圍、當前snapshot及影響。}}

完成核對：五核心文件及內容、Phase義務、來源覆蓋、唯一決定現況、實際package清單、封存映射、最終gate／completion_receipt。PACKAGED／PROMOTED／exit0不代替整體完成。未解P0／requiredP1／requiredunknown不稱ACCEPTED。review不將自身hash反寫受審packet形成循環；terminal append只按預先明確授權。

逐finding與workflow.issues對賬：id/severity/required/phase/status/reference/reason；P0及requiredP1未解不通過，唔以報告PASS掩蓋結構化OPEN項。

### Final report 發布身份

保留原已批revision，先開未批准candidate revision再review；凍定其material／status-memoryprefix，snapshot排除report自身hash。實際report全文及對應結果只在該未批candidate定稿，render／gate後取得匹配最終packet／selectedfiles嘅實際批准，再promote及completion。其他material改動另開candidate／重審，唔用同revision偷偷換稿；NOT_RUN草稿不當最終已完成report。

# 關聯篩選與停止前檢查

## 搜尋範圍與閱讀範圍

全系統發現係喺已授權、實際可讀來源搵本 project 嘅相關歷史；只深讀已確認相關內容。
先列來源／分頁，按 project 名、repo、路徑、別名、特色功能及已證 session 引用搜尋。
可用搜尋索引先搜；無搜尋接口才按需要讀少量可見上下文確認。唔為判定無關而先拉全篇。
title／directory／parent 係候選提示；單憑另一目錄或無關標題不能排除。同 parent 或提及名字亦不能直接算相關。

逐來源保留 query／覆蓋範圍／snapshot／實際可讀性；native 與 JSONL 以明確 ID／來源身份對照。
清單數量差異本身不能當漏讀數目；其他 host／無法映射身份標 UNKNOWN，唔推論不存在。

| 關聯 | 做法 | 深讀義務 |
|---|---|---|
| RELATED | 有需求／決定／實作／follow-up 等直接關聯；記證據及需要嘅內容範圍 | 只讀相關範圍及理解佢所需嘅上下文，追查相關延續／child |
| UNRELATED | 有已記錄嘅範圍搜尋、有限上下文或用戶範圍決定支持 | 跳過，唔因未全文讀而阻擋完成 |
| UNDETERMINED | metadata 不足、內容未搜尋、工具／權限限制 | 優先最低限度核對；未證關聯前唔做全面深讀 |

搜尋命中唔等於相關或已讀；零命中只支持該次 query／來源範圍，唔宣稱永遠無關。
唔將 copied governance、同名別項目、單純提及當直接需求；對比使用者／assistant及時間順序。
FULL 指已聲明所需相關範圍讀完，唔係整個帳戶、session附件或未暴露後端全部讀完。
相關附件先做已授權路徑存在性及身份核對，再按交付需要讀內容；視覺驗收不適用時可有理由不讀像素。
未試、路徑不存在、無權限、工具截斷分開記。無關附件不探查、不下載。

## PARTIAL 前要分清可做與受阻

停止前逐項列剩餘已授權工作：READY立即繼續；BLOCKED有實際依賴證據及owner；
DEFERRED有用戶延期／改scope來源；DONE有結果。單寫「PARTIAL」、Jev route缺失或另一個步驟受阻唔係停止理由。
將相關未讀、未確認關聯及相關附件檢查分成具體task。工具限制只阻相依步驟；唔自行擴權或修改shared tool。
用戶明確停止／延期依當次指示處理，保留checkpoint，唔為通過檢查重新執行已撤回範圍。

完成canonical packet後，每次準備以PARTIAL交接前建立 `md-drafts/followup-checkpoint.json`，
用 `schemas/followup.schema.json`，綁當前 `plan_id/revision/packet_sha256`。保留舊checkpoint，改packet後重建。
`inventory_evidence`及各列evidence用`source:<ID>`，指packet中已捕獲、hash相符嘅檔案來源；
inventory係已盤點嘅來源／session ID，screening須一一對應。可重用有hash綁定嘅篩選表證據，唔複製聊天全文。
不同來源同一session要保留來源身份，並在證據列對照／去重；不同revision唔冒認同一正文。
scope無歷史亦可inventory/screening空array，但inventory_evidence仍要有來源及N/A依據。

```text
python <SKILL_ROOT>/scripts/gate-check.py <PROJECT_ROOT> --stage checkpoint --strict --json
```

- `CONTINUE_REQUIRED`／exit1：有READY工作，繼續相應task。
- `CHECKPOINT_INCOMPLETE`／exit1：補列缺失篩選、來源、狀態或修正漂移；唔等於必須深讀全部session。
- `CHECKPOINT_JUSTIFIED`／exit0：已列工作無READY，可交代受阻／延期項；**complete永遠false**。

呢個係新增獨立stage，不改舊packet2.0、promote批准或既有completion判定。
舊checkpoint不存在時明確報缺件；普通plan/completion仍可診斷舊packet，唔暗加來源／改批准。
packet未建立時先記同等最少清單，完成可獨立盤點；唔為湊JSON先偽造完整plan。

## 獨立review核對

機械檢查只核宣告、身份對賬、來源bytes及是否尚有READY，唔能證明內容判斷正確或全系統列齊。
Reviewer須將inventory對照實際list/search receipts，抽查排除理由及跨目錄相關命中，確認無以title／path一刀切。
缺已確認相關內容才列reading缺口；未篩選列screening缺口，未知可讀性列UNKNOWN；唔把三者統稱漏讀。
覆核BLOCKED有實際嘗試／限制證據、DEFERRED有用戶決定、附件有需要程度與存在性記錄。
其餘正式文件、獨立驗收及completion gate照舊；checkpoint唔授權promote、push或部署。

## 大型Git觀察

維持完整原始porcelain輸出及SHA-256。checker以64KiB chunks串流讀至EOF，同時計數及hash，
核對前後檔案identity，記憶體唔隨整檔增長。單筆上限1MiB、整份profile上限256MiB；
超限／格式錯／漂移／hash不符一律ERROR，不截短、不取部分計數冒認完成。
ignored輸出非空仍不得稱clean。呢個檢查只讀capture，不執行Git、不讀ignored檔案內容。

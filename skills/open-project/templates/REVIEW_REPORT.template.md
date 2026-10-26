# REVIEW_REPORT.md — <PROJECT> 獨立驗收報告

> Reviewer：<獨立 subagent／session ref>（唯讀；無參與本輪改動）
> 日期：<YYYY-MM-DD>　Review 對象：<commit sha／快照>
> 結論：**<PASS（0 P0）／FAIL（P0 xN）>**
> 方法約束：重跑受 skill 全域執行安全規則約束——**只重跑安全且相關嘅唯讀核對命令**；有副作用嘅重跑標 NOT_RUN＋結果 UNVERIFIED。

---

## §1 方法

- 指令：唯讀（「唔好改任何檔案、唔好 commit」）。
- 檢查範圍：open-project skill Phase 8 十二項（見 §5）；結論一律 PASS／FAIL／UNVERIFIED＋證據。
- 證據原則：唔信文件宣稱——verify／doctor 自己重跑（安全項）；路徑自己 ls；數字自己數。

## §2 P0（必修；0 P0 先可交付）

| # | 問題 | 位置 | 證據 | 修復建議 |
|---|---|---|---|---|
| （無＝寫「0 項」） |  |  |  |  |

## §3 P1（必修，可交付前）

| # | 問題 | 位置 | 證據 | 修復建議 |
|---|---|---|---|---|

## §4 P2（記錄入 roadmap）

| # | 建議 | 位置 |
|---|---|---|

## §5 十二項檢查（逐項 PASS／FAIL／UNVERIFIED＋證據）

| # | 檢查 | 結論 | 證據 |
|---|---|---|---|
| 1 | FROZEN 對賬（宣稱 N 條 vs 實際 N 條） | PASS／FAIL／UNVERIFIED | <命令＋輸出摘要> |
| 2 | 數字一致（PLAN↔plan-data.json↔HTML 三方） |  |  |
| 3 | 結構完整（核心 MD 章節對模板） |  |  |
| 4 | 路徑存在（文件引用路徑逐一驗） |  |  |
| 5 | Secret 重跑（R3 狀態制：SCANNED／NOT_SCANNED／findings；要發布檔有 NOT_SCANNED→整體只能 PARTIAL） |  |  |
| 6 | 適用嘅 doctor／verify 重跑（冇 CLI＝NOT_APPLICABLE 記錄） |  |  |
| 7 | Git 一致（branch/dirty 同文件講法） |  |  |
| 8 | Agent frontmatter（line 1 開始，未被覆蓋） |  |  |
| 9 | 邏輯一致（agent SOP／skill 流程／CLI 子命令互相對應） |  |  |
| 10 | 過時內容（抽 3 個「最新狀態」宣稱對實況） |  |  |
| 11 | PLAN·HTML 對賬（抽 §1 三個安全數字重跑一致；HTML 離線開到、數字同 json 一致） |  |  |
| 12 | 草稿對賬（最終 MD vs 已批草稿 diff 經 metadata 白名單過濾；**越權改動＝P0**） |  |  |

## §6 殘留風險

- <已知但唔阻塞交付嘅嘢＋跟進位置（roadmap Pn）>

## §7 證據附錄

```
<關鍵命令＋輸出節錄（secret 值必須遮蔽；NOT_RUN 項記原因）>
```

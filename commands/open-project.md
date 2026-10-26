---
description: 開新 project／重整舊 project（open-project：review → PLAN＋草稿 → 批 → promote → 實作 → review）
argument-hint: "[new|reorg] <project folder or goal>"
skills: open-project
---

用 `open-project` skill 處理呢個請求，按 Phase 0–9 執行。全程受 skill「全域執行安全規則」約束（執行前審副作用＋授權；未批→NOT_RUN 唔阻塞）。

流程重點：
1. Phase 0：定路線＋規模（new 行兩輪訪談；reorg 快速意圖登記）——唔出計劃。
2. Phase 1–3：事實／舊 session（範圍制＋深度 tag）／舊檔＋代碼 review。
3. Phase 4（核心）：staging `md-drafts/` 三件套——PLAN.DRAFT.md（§1–§11，含工具化評估＋批准請求表）＋逐檔完整 MD 草稿（禁一句交差）＋plan-data.json＋離線 HTML 證據視圖。**停喺待批位，老闆批 §11＋過目草稿先繼續。**
4. Phase 5：逐檔漂移核對（§8 baseline）→位元組備份→逐字 promote（白名單轉換）。
5. Phase 6–9：照評估實作（N/A 合法）→plugin（PACKAGED/INSTALLED 狀態制）→獨立 review 12 項→handover（LOCAL COMPLETE/NOT_PUSHED 合法收尾）。

$ARGUMENTS

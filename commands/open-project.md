---
description: 明確調用 open-project：開案／重整嘅完整 PLAN、MD 草稿、審批、受控 promote、驗收及交接
argument-hint: "[new|reorg] <project folder or goal>"
skills: open-project
---

用 `open-project` skill 處理以下明確請求。只涵蓋本次任務生命週期；普通新 project／一般 coding 唔自動啟動。ZCode 原生 manual-only enforcement 未核實＝UNKNOWN；本入口及 checker 係 advisory，唔聲稱 OS／host 強制。

先確認 PLUGIN_ROOT／SKILL_ROOT 同用戶指定 PROJECT_ROOT，使用原始 authoring 文件；第一次 raw-byte 讀取先記 baseline，先起草。唔自動更新 installed cache、global rules、host config 或安裝／啟用。

Phase 0–9：
1. 意圖／訪談、new/reorg、S/M/L；已有答案沿用。
2. 事實＋首讀 baseline；reorg 全系統 metadata／可見 content discovery 先於 directory/title，parent closure、opaque IDs、WAL 短 read-only、來源版本與 coverage／深讀 tags。
3. 檔案／代碼／git／secret review，desired requirements 與 observed 歷史分開。
4. 完整 packet：11 節 PLAN、必交 product specification、每份 planned MD 完整草稿、schema 1.0 JSON、同源離線 HTML、gate 報告及尾部 suggestions；S 不減交付。
5. 獨立批准 JSON 綁 plan／digest／draft／target／baseline／expected／transforms／effects；promote 預設 dry-run，已授權先 apply／resume，原始 bytes 備份及 drift 檢查。
6. 按 §6 評估實作；CLI／agent／MCP／Plugin 可 N/A。保留 AP-17 已確認模型／provider 政策，唔再開模型修復工程。Agent／subagent_type、RSC、.zcode-plugin 按 host reference。
7. 打包與 installed／loaded 分開，PACKAGED 合法交貨。
8. 唯讀獨立 12 項 review；required P1 未解／required coverage UNKNOWN 都唔可 ACCEPTED，即使零 P0。
9. status、append-only memory events、immutable FROZEN＋外部 manifest、follow-up；LOCAL COMPLETE／NOT_PUSHED 合法。已有明確授權持續有效，唔重複請批。

所有命令按實際副作用與既有授權執行；未跑記 NOT_RUN／UNVERIFIED，不假綠。使用本 skill 嘅 scripts/render-plan.py、gate-check.py、promote.py、discover-sessions.py，明傳 PROJECT_ROOT，唔依賴 cwd。

$ARGUMENTS

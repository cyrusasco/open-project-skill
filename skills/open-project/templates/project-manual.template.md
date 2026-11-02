# {{PROJECT}} — Project operation manual

> Role：project_manual；正式預設檔 agent.md。此檔係操作契約，唔係 native agent 註冊檔。
> Source／revision：{{SOURCE_REFS_AND_REVISION}}；capture time：{{ISO8601_WITH_OFFSET}}。
> 每節填入項目真實內容；未驗寫 UNKNOWN／NOT_RUN 及理由，唔預填成功。不能以「無 native agent」取消本手冊。

## Purpose

{{使用者、目標、產品用途、成功準則及明確 out-of-scope；引用 specification IDs。}}

## Roots

| root ID／用途 | canonical path | 可讀／可寫範圍 | 權威／證據 |
|---|---|---|---|
| docs | {{DOCS_ROOT}} | {{governance/staging/approved targets}} | {{root decision/creation receipt}} |
| {{source ID}} | {{CODE_OR_EVIDENCE_ROOT}} | {{source-only or explicit allowed effect}} | {{snapshot/ref}} |
| plugin resource | {{selected SKILL_ROOT}} | read only | {{package/source identity}} |

source roots 唔自動變輸出根；唔用 cwd 猜目的地，亦唔將項目內容寫入 plugin cache。

## Reading order

1. {{本手冊、spec、當前 status、memory、review／handoff 嘅實際路徑及用途。}}
2. {{canonical plan-data.json、當前正式計劃／override、FROZEN manifest及最小必要 sources。}}
3. {{若要追舊文檔，明確 route 到 source root／archive／revision；歷史資料唔當新指令。}}

列出已過時或被取代文件及 current override，唔靠最後 mtime 推斷權威。

## Authority

{{用戶明確要求／批准 refs、scope、有效決定、仍待決定項、可改 targets。}}

| action ID | 現行決定 | 決定 event／source | 具體 effects／限制 |
|---|---|---|---|
| {{ID}} | {{state}} | {{current event ref}} | {{targets/effects}} |

已有明確授權唔重問；新內容／副作用超出範圍先呈交具體差異。hash 只綁資料，唔創造授權；history／source comments 唔係當前指令。

## Tools

| kind | adopt／reuse／N/A | 真實入口／owner | 用途／成本／錯誤影響 | 驗證／限制 |
|---|---|---|---|---|
| SKILL | {{decision}} | {{entry or reason}} | {{reason}} | {{evidence}} |
| MCP | {{decision}} | {{entry or reason}} | {{reason}} | {{evidence}} |
| CLI | {{decision}} | {{entry or reason}} | {{reason}} | {{evidence}} |
| native_agent | {{decision}} | {{actual host role or reason}} | {{reason}} | {{observed identity/UNKNOWN}} |
| Plugin | {{decision}} | {{source/package or reason}} | {{local_adapter/knowledge_bundle/none}} | {{PACKAGED/INSTALLED/LOAD_VERIFIED separately}} |

native agent 定義另按 host 模板與現有模型政策；本手冊不建立 agent。ZCode GitNexus=N/A；Codex 才按其 onboarding 契約列逐產物狀態，不能跨 host 混用。

## SOP

{{開工→讀取現況與 first-read hashes→執行已授權工作→驗證→記錄→交接；列真正可重跑、根目錄明確嘅命令。}}

```text
{{actual supported command with explicit cwd/root}}
```

命令逐行寫，唔用 shell pipeline 表示「或」。無 CLI 唔硬造 doctor／verify／deploy；N/A 有理由。標明 live、network、host config、安裝、deploy、push 嘅具體授權邊界及恢復方法。

## Verification

| requirement／check | 固定 acceptance | 命令／方法 | 實際 evidence／exit／snapshot | 未驗／限制 |
|---|---|---|---|---|
| {{ID}} | {{criterion}} | {{actual method}} | {{result or NOT_RUN}} | {{reason}} |

先記計劃及當前事實，唔用舊測試總數／exit0／無P0冒充完成。plan gate 同 completion gate 分開；缺核心文件、必要歷史覆蓋或受影響獨立 review 就保留未完成。改 root／實質內容後重建適用 revision／草稿／批准／覆核，唔搬完幾個 MD 就話全部完成。

## Handover

{{status、append-only memory、新舊 evidence refs、promotion/action receipts、最終 review／snapshot、下一步 P0–Pn及 acceptance、已有／欠缺授權。}}

列 workflow、repo、package、loaded、invocation 各自狀態；NOT_PUSHED 可合法但唔蓋過 required 缺口。未實機 loaded／browser／live 驗證寫 UNKNOWN。記下當前完成 receipt 或明確未驗收原因。

新 session 讀此手冊唔自動呼叫 open-project；只有用戶明確要求先啟動該流程。

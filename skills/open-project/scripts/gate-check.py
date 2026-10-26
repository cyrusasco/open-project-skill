# -*- coding: utf-8 -*-
"""
gate-check.py — open-project 機械閘（v2.2.4）
用法：python gate-check.py <PROJECT_DIR> [--strict] [--out <file>]
預設 advisory：出報告＋建議，exit 0（保留彈性，老闆裁量）。
--strict：有任何 FAIL 先 exit 1（要硬閘嗰陣用）。
檢查項：
  G1 §8 manifest 逐檔存在（AP-16 草稿齊件）
  G2 PLAN 新過 plan-data.json/HTML → 要重生成（AP-15）
  G3 agent 草稿 frontmatter model 必須有效字串（AP-17：留空/inherit/placeholder 都會靜默跌錯 provider）
  G4 PLAN 時間戳 vs 檔案 mtime（人手作假時間戳）
  G5 草稿引用嘅 .md 檔存在性（陳舊引用）
"""
import os, re, sys, datetime, io

def perr(s): print(s)
def main():
    args = [a for a in sys.argv[1:]]
    strict = "--strict" in args
    out = None
    if "--out" in args: out = args[args.index("--out") + 1]
    proj = args[0] if args and not args[0].startswith("--") else "."
    md = os.path.join(proj, "md-drafts")
    lines = []
    def emit(s=""): lines.append(s)

    emit("=" * 62)
    emit("open-project gate-check — " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    emit("project: " + os.path.abspath(proj) + ("   [STRICT]" if strict else "   [advisory－預設]"))
    emit("=" * 62)
    fails, warns = [], []

    def finding(level, gate, msg, suggest):
        (fails if level == "FAIL" else warns).append(gate)
        emit("[" + level + "] " + gate + "｜" + msg)
        emit("        建議：" + suggest)

    if not os.path.isdir(md):
        emit("[FAIL] 環境｜搵唔到 md-drafts/ staging 目錄"); emit("        建議：確認行緊 open-project Phase 4/5，或者檢查 project 路徑")
        report = "\n".join(lines) + flexibility_note(len(fails))
        print(report)
        if out: io.open(out, "w", encoding="utf-8", newline="\n").write(report)
        sys.exit(1 if strict else 0)

    # ---- G1 §8 manifest 逐檔 ----
    plan_path = os.path.join(md, "PLAN.DRAFT.md")
    if not os.path.exists(plan_path): plan_path = os.path.join(proj, "PLAN.md")
    plan_txt = io.open(plan_path, encoding="utf-8").read() if os.path.exists(plan_path) else ""
    sec8 = re.search(r"##\s*§8.*?(?=\n##\s*§9|\Z)", plan_txt, re.S)
    manifest = []
    if sec8:
        for row in sec8.group(0).splitlines():
            m = re.match(r"\|\s*(md-drafts/[\w.\- ]+?\.DRAFT\.md)\s*\|", row)
            if m: manifest.append(m.group(1))
    if not manifest:
        finding("WARN", "G1", "PLAN §8 manifest 解析唔到（或冇草稿行）", "檢查 §8 表格格式：每行第一格係 md-drafts/<name>.DRAFT.md")
    for f in manifest:
        if not os.path.exists(os.path.join(proj, f.replace("/", os.sep))):
            finding("FAIL", "G1", "§8 列咗但檔案唔存在：" + f, "補返草稿，或者喺 §8 移除嗰行（寫明理由）——呈交缺件＝AP-16")
    listed = set(manifest)
    for f in sorted(os.listdir(md)):
        if f.endswith(".DRAFT.md") and ("md-drafts/" + f) not in listed:
            finding("WARN", "G1", "草稿存在但未列入 §8 manifest：md-drafts/" + f, "加入 §8（有 DoD＋baseline），或者唔屬於交付物就移出去 staging")

    # ---- G2 AP-15 三方新鮮度 ----
    plan_mtime = os.path.getmtime(plan_path) if os.path.exists(plan_path) else 0
    for dep in ["plan-data.json", "PLAN-REPORT.DRAFT.html"]:
        p = os.path.join(md, dep)
        if os.path.exists(p) and os.path.getmtime(p) < plan_mtime - 5:
            lag = int(plan_mtime - os.path.getmtime(p))
            finding("FAIL", "G2", dep + " 舊過 PLAN " + str(lag) + " 秒——數據視圖脫鉤（AP-15）",
                    "改完 PLAN 必須重新生成（跑返你個 gen-report / 生成流程）")

    # ---- G3 AP-17 agent model ----
    for f in sorted(os.listdir(md)):
        if not f.endswith(".DRAFT.md"): continue
        t = io.open(os.path.join(md, f), encoding="utf-8").read()
        m = re.match(r"^---\n(.*?)\n---", t, re.S)
        if not m or "tools:" not in m.group(1): continue
        mm = re.search(r"^model:\s*(.+)$", m.group(1), re.M)
        if not mm:
            finding("FAIL", "G3", f + " frontmatter 冇 model: 行——會靜默跌落 provider 清單第一個", "加 model: <provider/model>（問用戶攞後台揀嘅有效字串）")
        else:
            v = mm.group(1).strip()
            if v.startswith("<") or "執行時填" in v or v == "inherit":
                finding("FAIL", "G3", f + " model 係 placeholder／inherit（" + v[:40] + "）——唔會跟後台 default", "Phase 4 問老闆攞字串後填實（AP-17；例 <provider>/<model-id>）")

    # ---- G4 時間戳 vs mtime ----
    if plan_txt:
        head = "\n".join(plan_txt.splitlines()[:12])
        ts = re.search(r"(20\d{2}-\d{2}-\d{2})[ T]*(\d{1,2}:\d{2})?", head)
        if ts:
            try:
                claimed = datetime.datetime.strptime(ts.group(1) + " " + (ts.group(2) or "12:00"), "%Y-%m-%d %H:%M")
                actual = datetime.datetime.fromtimestamp(plan_mtime)
                if abs((claimed - actual).total_seconds()) > 3 * 3600:
                    finding("WARN", "G4", "PLAN 頭時間戳(" + ts.group(0) + ")同檔案實際 mtime(" + actual.strftime("%m-%d %H:%M") + ")差好遠", "時間戳由腳本／實際執行時間注入，唔好手寫（今次差 " + str(int(abs((claimed-actual).total_seconds())/3600)) + " 小時）")
            except ValueError: pass

    # ---- G5 陳舊 .md 引用 ----
    proj_files = set()
    for root, dirs, files in os.walk(proj):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        proj_files.update(files)
    # 白名單：§8 正式目標欄嘅檔名＋各草稿 promote 後檔名＋標準交付檔（未出街係預期，唔算陳舊引用）
    allow = {"PLAN.md", "README.md", "REVIEW_REPORT.md", "AGENTS.md", "PROJECT.md", "SKILL.md", "handoff.md"}
    if sec8:
        for row in sec8.group(0).splitlines():
            m = re.match(r"\|[^|]+\|[^|]+\|[^|]*\|[^|]*\|\s*([^|]+?)\s*\|", row)
            if m: allow.add(os.path.basename(m.group(1).strip()))
    for f in os.listdir(md):
        if f.endswith(".DRAFT.md"): allow.add(f[:-len(".DRAFT.md")] + ".md")
    for f in sorted(os.listdir(md)):
        if not f.endswith(".DRAFT.md"): continue
        t = io.open(os.path.join(md, f), encoding="utf-8").read()
        t = re.sub(r"<[^>\n]*>", "", t)  # 去掉 placeholder
        for ref in set(re.findall(r"(?<![\w/.\\-])[A-Za-z][A-Za-z0-9_\-]*\.md(?![\w])", t)):
            if ref in proj_files or ref in allow: continue
            finding("WARN", "G5", f + " 引用咗 " + ref + " 但 project 入面搵唔到（又唔係 §8 將出街嘅檔）", "確認係咪已撤銷/改名嘅檔——改指而家嘅檔或者移除引用；如果喺另一個 repo，寫明 repo 路徑")

    # ---- 總結 ----
    emit()
    emit("-" * 62)
    emit("統計：FAIL " + str(len(fails)) + " 項｜WARN " + str(len(warns)) + " 項（advisory 模式：全部只係報告，唔阻你）")
    report = "\n".join(lines) + flexibility_note(len(fails))
    print(report)
    if out: io.open(out, "w", encoding="utf-8", newline="\n").write(report)
    sys.exit(1 if (strict and fails) else 0)

def flexibility_note(n_fail):
    return ("\n" + "-" * 62 +
            "\n【彈性說明——保留俾老闆裁量】\n"
            "· 本報告預設 advisory：列咗問題＋建議，唔强制；老闆可以逐項决定「修／接受並記入 PLAN §11」。\n"
            "· 唯一建議無彈性嘅位：G3（agent model placeholder）——promote 前必須填實，因為佢會靜靜跌錯 provider，事後睇唔出。\n"
            "· 想要硬閘（任何 FAIL 即擋）：加 --strict。\n" +
            ("· 而家有 " + str(n_fail) + " 個 FAIL 建議喺呈交／promote 前清咗佢。\n" if n_fail else ""))

if __name__ == "__main__": main()

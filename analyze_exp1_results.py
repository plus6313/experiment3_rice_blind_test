"""
分析 EXP1 人工盲測驗證結果（/exp1-agri/ + /exp1-lab/ 兩份表單）。

使用方式：
1. 將 Google Drive 下載的 exp1_agri_*.json / exp1_lab_*.json 放到
   collected_responses_exp1/
2. 執行 python analyze_exp1_results.py

輸出（results_exp1/）：
- summary.json：機器可讀摘要
- summary_zh.md：中文總覽報告（含 Cohen's κ）
- lab_dimension_summary_zh.csv：實驗室版四維度＋整體判斷統計
- lab_responses_zh.csv：實驗室版逐筆作答明細（含A/B對應真實模型）
- agri_responses_zh.csv：農業專家版逐筆作答明細
- kappa_detail_zh.csv：整體判斷 vs Claude Opus verdict 逐筆對照
"""

import collections
import csv
import json
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
PRIVATE_DIR = BASE_DIR / "private"
MAPPING_FILE = PRIVATE_DIR / "exp1_private_mapping.json"
OPUS_VERDICTS_FILE = PRIVATE_DIR / "exp1_opus_verdicts.json"

COLLECTED_DIR = BASE_DIR / "collected_responses_exp1"
RESULTS_DIR = BASE_DIR / "results_exp1"

LAB_SCORE_FIELDS = [
    ("criterion_1_accuracy", "正確性"),
    ("criterion_2_reasoning", "推理一致性"),
    ("criterion_3_actionability", "可操作性"),
    ("criterion_4_completeness", "完整性"),
]

MATCHUP_LABELS = {
    "ft_qwen_vs_base_qwen": "ft_qwen vs base_qwen",
    "ft_qwen_vs_gemini": "ft_qwen vs gemini",
    "ft_qwen_vs_gemma": "ft_qwen vs gemma",
}

VERDICT_LABELS = {"A_better": "A較好", "B_better": "B較好", "tie": "平手", None: "未作答", "": "未作答"}


def load_json(path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_mapping():
    rows = load_json(MAPPING_FILE) or []
    return {r["comparison_id"]: r for r in rows}


def load_opus_verdicts():
    rows = load_json(OPUS_VERDICTS_FILE) or []
    return {r["comparison_id"]: r for r in rows}


def load_collected(prefix):
    submissions = []
    if not COLLECTED_DIR.exists():
        return submissions
    for path in sorted(COLLECTED_DIR.glob(f"{prefix}_*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["_source_file"] = path.name
        submissions.append(data)
    return submissions


def percent(numerator, denominator):
    if not denominator:
        return ""
    return f"{numerator / denominator:.1%}"


def verdict_to_side(model_at_a, model_at_b, verdict, target_model="ft_qwen"):
    """把 A_better/B_better/tie 轉成「ft_qwen 贏/輸/平手」"""
    if verdict == "tie":
        return "tie"
    if verdict == "A_better":
        return "win" if model_at_a == target_model else "loss"
    if verdict == "B_better":
        return "win" if model_at_b == target_model else "loss"
    return None


def verdict_letter(verdict):
    """把本站的 A_better/B_better/tie 轉成跟 Opus judged.jsonl 一致的 A/B/tie 字母"""
    return {"A_better": "A", "B_better": "B", "tie": "tie"}.get(verdict)


def opus_score_winner(scores_a, scores_b, dim_key):
    if not scores_a or not scores_b:
        return None
    a = scores_a.get(dim_key)
    b = scores_b.get(dim_key)
    if a is None or b is None:
        return None
    if a > b:
        return "A"
    if b > a:
        return "B"
    return "tie"


def cohens_kappa(pairs):
    """pairs: list of (rater1_label, rater2_label)，皆為 'A'/'B'/'tie' 字串"""
    pairs = [p for p in pairs if p[0] is not None and p[1] is not None]
    n = len(pairs)
    if n == 0:
        return None, 0
    labels = sorted(set(x for pair in pairs for x in pair))
    idx = {l: i for i, l in enumerate(labels)}
    k = len(labels)
    matrix = [[0] * k for _ in range(k)]
    for r1, r2 in pairs:
        matrix[idx[r1]][idx[r2]] += 1

    po = sum(matrix[i][i] for i in range(k)) / n

    row_sums = [sum(matrix[i]) for i in range(k)]
    col_sums = [sum(matrix[i][j] for i in range(k)) for j in range(k)]
    pe = sum((row_sums[i] / n) * (col_sums[i] / n) for i in range(k))

    if pe == 1:
        return 1.0, n
    kappa = (po - pe) / (1 - pe)
    return kappa, n


def write_csv(path, rows, fieldnames):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def analyze_lab(mapping, opus_verdicts):
    submissions = load_collected("exp1_lab")
    if not submissions:
        print("[提醒] collected_responses_exp1/ 沒有 exp1_lab_*.json，略過實驗室版分析。")
        return None

    response_rows = []
    dim_counter_by_matchup = {
        m: {key: collections.Counter() for key, _ in LAB_SCORE_FIELDS}
        for m in MATCHUP_LABELS
    }
    overall_counter_by_matchup = {m: collections.Counter() for m in MATCHUP_LABELS}
    kappa_pairs = []
    kappa_detail_rows = []
    evaluators = set()

    for sub in submissions:
        evaluator = sub.get("evaluator_name", "unknown")
        evaluators.add(evaluator)
        for resp in sub.get("responses", []):
            cid = resp.get("comparison_id")
            map_row = mapping.get(cid)
            if map_row is None:
                continue
            model_a = map_row["model_at_A"]
            model_b = map_row["model_at_B"]
            matchup = map_row["matchup"]
            opp_model = model_a if model_b == "ft_qwen" else model_b

            overall = resp.get("overall_verdict")
            side = verdict_to_side(model_a, model_b, overall)
            if side:
                overall_counter_by_matchup[matchup][side] += 1

            row = {
                "評審": evaluator,
                "comparison_id": cid,
                "image_id": map_row["image_id"],
                "question_id": map_row["question_id"],
                "對戰組合": MATCHUP_LABELS.get(matchup, matchup),
                "A實際模型": model_a,
                "B實際模型": model_b,
                "整體判斷_選擇": VERDICT_LABELS.get(overall, "未作答"),
                "整體判斷_ft結果": {"win": "ft勝", "loss": f"{opp_model}勝", "tie": "平手"}.get(side, ""),
            }

            for key, label in LAB_SCORE_FIELDS:
                a_val = resp.get(f"{key}_a")
                b_val = resp.get(f"{key}_b")
                row[f"{label}_A分數"] = a_val
                row[f"{label}_B分數"] = b_val
                if a_val is not None and b_val is not None:
                    try:
                        av, bv = int(a_val), int(b_val)
                        if av > bv:
                            dim_side = "win" if model_a == "ft_qwen" else "loss"
                        elif bv > av:
                            dim_side = "win" if model_b == "ft_qwen" else "loss"
                        else:
                            dim_side = "tie"
                        dim_counter_by_matchup[matchup][key][dim_side] += 1
                    except (TypeError, ValueError):
                        pass

            response_rows.append(row)

            # Cohen's kappa：本站整體判斷 vs Claude Opus 的 verdict
            human_letter = verdict_letter(overall)
            opus_row = opus_verdicts.get(cid)
            opus_letter = opus_row.get("verdict") if opus_row else None
            if human_letter is not None and opus_letter is not None:
                kappa_pairs.append((human_letter, opus_letter))
                kappa_detail_rows.append({
                    "評審": evaluator,
                    "comparison_id": cid,
                    "人類選擇": human_letter,
                    "OpusJudge選擇": opus_letter,
                    "是否一致": "一致" if human_letter == opus_letter else "不一致",
                })

    kappa, n_kappa = cohens_kappa(kappa_pairs)
    n_agree = sum(1 for h, o in kappa_pairs if h == o)

    write_csv(
        RESULTS_DIR / "lab_responses_zh.csv",
        response_rows,
        list(response_rows[0].keys()) if response_rows else [],
    )
    if kappa_detail_rows:
        write_csv(
            RESULTS_DIR / "kappa_detail_zh.csv",
            kappa_detail_rows,
            ["評審", "comparison_id", "人類選擇", "OpusJudge選擇", "是否一致"],
        )

    # 維度統計 CSV（依對戰組合分開列，並附合併總表）
    dim_summary_rows = []
    for matchup in MATCHUP_LABELS:
        oc = overall_counter_by_matchup[matchup]
        win, loss, tie = oc.get("win", 0), oc.get("loss", 0), oc.get("tie", 0)
        total = win + loss + tie
        dim_summary_rows.append({
            "對戰組合": MATCHUP_LABELS[matchup],
            "指標": "整體判斷",
            "ft勝": win, "對手勝": loss, "平手": tie,
            "ft勝率_含平手": percent(win, total),
            "ft勝率_排除平手": percent(win, win + loss),
        })
        for key, label in LAB_SCORE_FIELDS:
            c = dim_counter_by_matchup[matchup][key]
            w, l, t = c.get("win", 0), c.get("loss", 0), c.get("tie", 0)
            tt = w + l + t
            dim_summary_rows.append({
                "對戰組合": MATCHUP_LABELS[matchup],
                "指標": label,
                "ft勝": w, "對手勝": l, "平手": t,
                "ft勝率_含平手": percent(w, tt),
                "ft勝率_排除平手": percent(w, w + l),
            })
    write_csv(
        RESULTS_DIR / "lab_dimension_summary_zh.csv",
        dim_summary_rows,
        ["對戰組合", "指標", "ft勝", "對手勝", "平手", "ft勝率_含平手", "ft勝率_排除平手"],
    )

    # 合併三個對戰組合的總體 kappa 已算好；額外算合併後的整體勝率（不分對戰組合）
    pooled = collections.Counter()
    for matchup in MATCHUP_LABELS:
        for k, v in overall_counter_by_matchup[matchup].items():
            pooled[k] += v

    return {
        "n_evaluators": len(evaluators),
        "evaluators": sorted(evaluators),
        "n_responses": len(response_rows),
        "overall_by_matchup": {
            matchup: dict(overall_counter_by_matchup[matchup]) for matchup in MATCHUP_LABELS
        },
        "pooled_overall": dict(pooled),
        "cohens_kappa": {
            "kappa": kappa,
            "n_pairs": n_kappa,
            "n_agree": n_agree,
            "agreement_rate": percent(n_agree, n_kappa),
        },
    }


def analyze_agri(mapping, opus_verdicts):
    submissions = load_collected("exp1_agri")
    if not submissions:
        print("[提醒] collected_responses_exp1/ 沒有 exp1_agri_*.json，略過農業專家版分析。")
        return None

    response_rows = []
    counter_by_matchup = {m: collections.Counter() for m in MATCHUP_LABELS}
    depth_vs_opus_pairs = []
    evaluators = set()

    for sub in submissions:
        evaluator = sub.get("evaluator_name", "unknown")
        evaluators.add(evaluator)
        for resp in sub.get("responses", []):
            cid = resp.get("comparison_id")
            map_row = mapping.get(cid)
            if map_row is None:
                continue
            model_a = map_row["model_at_A"]
            model_b = map_row["model_at_B"]
            matchup = map_row["matchup"]
            opp_model = model_a if model_b == "ft_qwen" else model_b

            verdict = resp.get("depth_verdict")
            side = verdict_to_side(model_a, model_b, verdict)
            if side:
                counter_by_matchup[matchup][side] += 1

            response_rows.append({
                "評審": evaluator,
                "comparison_id": cid,
                "image_id": map_row["image_id"],
                "question_id": map_row["question_id"],
                "對戰組合": MATCHUP_LABELS.get(matchup, matchup),
                "A實際模型": model_a,
                "B實際模型": model_b,
                "農業深度_選擇": VERDICT_LABELS.get(verdict, "未作答"),
                "農業深度_ft結果": {"win": "ft勝", "loss": f"{opp_model}勝", "tie": "平手"}.get(side, ""),
            })

            human_letter = verdict_letter(verdict)
            opus_row = opus_verdicts.get(cid)
            if human_letter is not None and opus_row:
                opus_depth_letter = opus_score_winner(
                    opus_row.get("scores_a"), opus_row.get("scores_b"), "depth"
                )
                if opus_depth_letter is not None:
                    depth_vs_opus_pairs.append((human_letter, opus_depth_letter))

    write_csv(
        RESULTS_DIR / "agri_responses_zh.csv",
        response_rows,
        list(response_rows[0].keys()) if response_rows else [],
    )

    kappa, n_kappa = cohens_kappa(depth_vs_opus_pairs)
    n_agree = sum(1 for h, o in depth_vs_opus_pairs if h == o)

    pooled = collections.Counter()
    for matchup in MATCHUP_LABELS:
        for k, v in counter_by_matchup[matchup].items():
            pooled[k] += v

    return {
        "n_evaluators": len(evaluators),
        "evaluators": sorted(evaluators),
        "n_responses": len(response_rows),
        "depth_by_matchup": {m: dict(counter_by_matchup[m]) for m in MATCHUP_LABELS},
        "pooled_depth": dict(pooled),
        "depth_vs_opus_kappa": {
            "kappa": kappa,
            "n_pairs": n_kappa,
            "n_agree": n_agree,
            "agreement_rate": percent(n_agree, n_kappa),
        },
    }


def write_report(lab_summary, agri_summary):
    lines = [
        "# EXP1 人工盲測驗證結果摘要",
        "",
        f"產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]

    if lab_summary:
        lines += [
            "## 實驗室版（/exp1-lab/）",
            "",
            f"- 評審人數：{lab_summary['n_evaluators']}（{', '.join(lab_summary['evaluators'])}）",
            f"- 收到作答筆數：{lab_summary['n_responses']}",
            "",
            "### 合併三個對戰組合的整體勝率",
            "",
        ]
        p = lab_summary["pooled_overall"]
        win, loss, tie = p.get("win", 0), p.get("loss", 0), p.get("tie", 0)
        total = win + loss + tie
        lines += [
            f"- ft_qwen 勝：{win}（{percent(win, total)}）",
            f"- 對手勝：{loss}（{percent(loss, total)}）",
            f"- 平手：{tie}（{percent(tie, total)}）",
            "",
            "### 各對戰組合的整體勝率",
            "",
            "| 對戰組合 | ft勝 | 對手勝 | 平手 | ft勝率(排除平手) |",
            "|---|---:|---:|---:|---:|",
        ]
        for matchup, label in MATCHUP_LABELS.items():
            c = lab_summary["overall_by_matchup"][matchup]
            w, l, t = c.get("win", 0), c.get("loss", 0), c.get("tie", 0)
            lines.append(f"| {label} | {w} | {l} | {t} | {percent(w, w+l)} |")

        k = lab_summary["cohens_kappa"]
        lines += [
            "",
            "### 人類整體判斷 vs Claude Opus(EXP1裁判) 一致性",
            "",
            f"- 有效對照筆數：{k['n_pairs']}",
            f"- 簡單一致率：{k['agreement_rate']}",
            f"- Cohen's κ：{k['kappa']:.3f}" if k['kappa'] is not None else "- Cohen's κ：無資料",
            "",
            "κ 解讀（Landis & Koch, 1977）：≤0 不比隨機猜好；0.01–0.20 極輕微；0.21–0.40 普通；"
            "0.41–0.60 中等；0.61–0.80 高度一致；0.81–1.00 近乎完全一致。",
            "",
        ]

    if agri_summary:
        lines += [
            "## 農業專家版（/exp1-agri/）",
            "",
            f"- 評審人數：{agri_summary['n_evaluators']}（{', '.join(agri_summary['evaluators'])}）",
            f"- 收到作答筆數：{agri_summary['n_responses']}",
            "",
            "### 合併三個對戰組合的農業深度勝率",
            "",
        ]
        p = agri_summary["pooled_depth"]
        win, loss, tie = p.get("win", 0), p.get("loss", 0), p.get("tie", 0)
        total = win + loss + tie
        lines += [
            f"- ft_qwen 勝：{win}（{percent(win, total)}）",
            f"- 對手勝：{loss}（{percent(loss, total)}）",
            f"- 平手：{tie}（{percent(tie, total)}）",
            "",
            "### 各對戰組合的農業深度勝率",
            "",
            "| 對戰組合 | ft勝 | 對手勝 | 平手 | ft勝率(排除平手) |",
            "|---|---:|---:|---:|---:|",
        ]
        for matchup, label in MATCHUP_LABELS.items():
            c = agri_summary["depth_by_matchup"][matchup]
            w, l, t = c.get("win", 0), c.get("loss", 0), c.get("tie", 0)
            lines.append(f"| {label} | {w} | {l} | {t} | {percent(w, w+l)} |")

        k = agri_summary["depth_vs_opus_kappa"]
        lines += [
            "",
            "### 農業專家「農業深度」判斷 vs Claude Opus 自己算出的depth分數贏家 一致性",
            "",
            f"- 有效對照筆數：{k['n_pairs']}",
            f"- 簡單一致率：{k['agreement_rate']}",
            f"- Cohen's κ：{k['kappa']:.3f}" if k['kappa'] is not None else "- Cohen's κ：無資料",
            "",
        ]

    with open(RESULTS_DIR / "summary_zh.md", "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines) + "\n")


def main():
    mapping = load_mapping()
    opus_verdicts = load_opus_verdicts()

    if not mapping:
        print(f"[錯誤] 找不到 {MAPPING_FILE}，請確認 private/exp1_private_mapping.json 存在。")
        return
    if not opus_verdicts:
        print(f"[警告] 找不到 {OPUS_VERDICTS_FILE}，將無法計算 Cohen's κ。")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    lab_summary = analyze_lab(mapping, opus_verdicts)
    agri_summary = analyze_agri(mapping, opus_verdicts)

    if not lab_summary and not agri_summary:
        print(f"[提醒] {COLLECTED_DIR} 沒有任何回覆檔案，請先把 Google Drive 下載的結果放進來。")
        return

    with open(RESULTS_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump({"lab": lab_summary, "agri": agri_summary}, f, ensure_ascii=False, indent=2)

    write_report(lab_summary, agri_summary)

    print(f"已完成分析，輸出位置：{RESULTS_DIR}")
    print(f"中文摘要：{RESULTS_DIR / 'summary_zh.md'}")


if __name__ == "__main__":
    main()

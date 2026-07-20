"""
分析 experiment 3 的人工評測結果。

使用方式：
1. 將 Google Drive 下載的 exp3_*.json 放到 collected_responses/
2. 執行 python analyze_results.py

輸出：
- results/summary.json：機器可讀摘要
- results/summary_zh.md：中文總覽報告
- results/criteria_summary_zh.csv：各指標中文統計表
- results/responses_zh.csv：每一筆作答明細，含 A/B 對應模型
- results/results_ft_qwen.jsonl、results_base_qwen.jsonl：保留原本逐模型 JSONL
"""

import collections
import csv
import json
from datetime import datetime

import config


CRITERIA = [
    ("criterion_1_stage_match", "生育期判斷是否正確"),
    ("criterion_2_gt_citation", "是否引用題目給定資訊"),
    ("criterion_3_no_errors", "是否沒有明顯錯誤"),
    ("criterion_4_no_fluff", "是否精簡不空泛"),
    ("criterion_5_no_hallucination", "是否沒有幻覺"),
]

MODEL_LABELS = {
    "ft_qwen": "微調模型",
    "base_qwen": "基礎模型",
}

CHOICE_LABELS = {
    "A": "選 A",
    "B": "選 B",
    "tie": "平手",
    None: "未作答",
    "": "未作答",
}

FT_RESULT_LABELS = {
    "win": "微調模型勝",
    "loss": "基礎模型勝",
    "tie": "平手",
    None: "無效",
}

OVERALL_LABEL = "總體判定：整體來說，哪個回答比較好？"


def load_mapping():
    mapping = {}
    with open(config.MAPPING_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            mapping[row["comparison_id"]] = row
    return mapping


def load_questions():
    if not config.SITE_DATA_FILE.exists():
        return {}
    with open(config.SITE_DATA_FILE, encoding="utf-8") as f:
        return {row["comparison_id"]: row for row in json.load(f)}


def load_collected():
    submissions = []
    if not config.COLLECTED_DIR.exists():
        return submissions

    for path in sorted(config.COLLECTED_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["_source_file"] = path.name
        submissions.append(data)
    return submissions


def model_zh(model_code):
    return MODEL_LABELS.get(model_code, model_code or "")


def percent(numerator, denominator):
    if not denominator:
        return ""
    return f"{numerator / denominator:.1%}"


def _win_side(model_code, model_a, model_b, verdict):
    if verdict == "tie":
        return "tie"
    if verdict == "A" and model_a == model_code:
        return "win"
    if verdict == "B" and model_b == model_code:
        return "win"
    if verdict in ("A", "B"):
        return "loss"
    return None


def verdict_to_model(model_a, model_b, verdict):
    if verdict == "A":
        return model_a
    if verdict == "B":
        return model_b
    if verdict == "tie":
        return "tie"
    return None


def verdict_zh(model_a, model_b, verdict):
    winner = verdict_to_model(model_a, model_b, verdict)
    if winner == "tie":
        return "平手"
    if winner:
        return model_zh(winner)
    return "未作答"


def criterion_value(row, key):
    value = row.get(key)
    return value if value in ("A", "B", "tie") else None


def write_csv(path, rows, fieldnames):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown_report(path, summary, criteria_rows, position_check):
    overall = summary["overall"]
    agreement = summary["agreement"]

    lines = [
        "# Experiment 3 人工評測結果摘要",
        "",
        f"- 產生時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 評審人數：{summary['n_evaluators']}",
        f"- 評審名單：{', '.join(summary['evaluators']) if summary['evaluators'] else '無'}",
        f"- 題庫題數：{summary['n_items_in_pool']}",
        f"- 收到作答列數：{summary['n_response_rows']}",
        f"- 有效整體判斷數：{summary['n_valid_overall']}",
        f"- 未完成或無效整體判斷數：{summary['n_invalid_overall']}",
        "",
        "## 整體勝負",
        "",
        "| 結果 | 票數 | 比例 |",
        "|---|---:|---:|",
        f"| 微調模型勝 | {overall['ft_qwen_win']} | {percent(overall['ft_qwen_win'], overall['total'])} |",
        f"| 基礎模型勝 | {overall['base_qwen_win']} | {percent(overall['base_qwen_win'], overall['total'])} |",
        f"| 平手 | {overall['tie']} | {percent(overall['tie'], overall['total'])} |",
        "",
        f"微調模型勝率（含平手作為分母）：{percent(overall['ft_qwen_win'], overall['total']) or '無資料'}",
        f"微調模型勝率（排除平手）：{percent(overall['ft_qwen_win'], overall['non_tie_total']) or '無資料'}",
        "",
        "## 各評分指標",
        "",
        "| 指標 | 微調勝 | 基礎勝 | 平手 | 微調勝率 |",
        "|---|---:|---:|---:|---:|",
    ]

    for row in criteria_rows:
        lines.append(
            f"| {row['指標']} | {row['微調模型勝']} | {row['基礎模型勝']} | "
            f"{row['平手']} | {row['微調勝率_含平手']} |"
        )

    lines.extend([
        "",
        "## A/B 對應檢查",
        "",
        "| 檢查項目 | 數值 |",
        "|---|---:|",
        f"| 網站題目數 | {position_check['n_questions']} |",
        f"| mapping 筆數 | {position_check['n_mapping']} |",
        f"| 題目缺少 mapping | {position_check['questions_missing_mapping']} |",
        f"| mapping 缺少題目 | {position_check['mapping_missing_questions']} |",
        f"| A 位置為微調模型 | {position_check['model_at_A'].get('ft_qwen', 0)} |",
        f"| A 位置為基礎模型 | {position_check['model_at_A'].get('base_qwen', 0)} |",
        f"| B 位置為微調模型 | {position_check['model_at_B'].get('ft_qwen', 0)} |",
        f"| B 位置為基礎模型 | {position_check['model_at_B'].get('base_qwen', 0)} |",
        "",
        "結論：統計時會用 comparison_id 查 private/mapping.jsonl，先把 A/B 還原成實際模型，再計算微調模型與基礎模型的勝負。",
        "",
        "## 評審一致性",
        "",
        f"- 多人評分的題目數：{agreement['n_items_multi_rated']}",
        f"- 完全一致題目數：{agreement['n_items_full_agreement']}",
        f"- 完全一致率：{percent(agreement['n_items_full_agreement'], agreement['n_items_multi_rated']) or '無資料'}",
        "",
        "## 輸出檔案",
        "",
        "- criteria_summary_zh.csv：各指標統計，適合用 Excel 檢視。",
        "- responses_zh.csv：每一筆作答明細，包含 A/B 對應模型與實際勝方。",
        "- summary.json：保留機器可讀摘要。",
    ])

    with open(path, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines) + "\n")


def main():
    mapping = load_mapping()
    questions = load_questions()
    submissions = load_collected()

    if not submissions:
        print(f"[提醒] {config.COLLECTED_DIR} 沒有任何 JSON 檔。請先把 Google Drive 下載的結果放進來。")
        return

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    question_ids = set(questions)
    mapping_ids = set(mapping)
    position_check = {
        "n_questions": len(questions),
        "n_mapping": len(mapping),
        "questions_missing_mapping": len(question_ids - mapping_ids),
        "mapping_missing_questions": len(mapping_ids - question_ids) if questions else 0,
        "model_at_A": dict(collections.Counter(row["model_at_A"] for row in mapping.values())),
        "model_at_B": dict(collections.Counter(row["model_at_B"] for row in mapping.values())),
    }

    per_model_lines = collections.defaultdict(list)
    response_rows = []
    criteria_rows = []

    overall_counter = collections.Counter()
    by_criterion_counter = {key: collections.Counter() for key, _label in CRITERIA}
    per_evaluator = collections.defaultdict(collections.Counter)
    per_item_overall_verdicts = collections.defaultdict(list)

    evaluators = []
    n_response_rows = 0
    n_valid_overall = 0
    n_invalid_overall = 0
    n_missing_mapping = 0

    for sub in submissions:
        evaluator = sub.get("evaluator_name", "unknown")
        evaluators.append(evaluator)
        source_file = sub.get("_source_file", "")
        submitted_at = sub.get("submitted_at", "")

        for response in sub.get("responses", []):
            n_response_rows += 1
            cid = response.get("comparison_id")
            map_row = mapping.get(cid)
            question = questions.get(cid, {})

            if map_row is None:
                n_missing_mapping += 1
                n_invalid_overall += 1
                continue

            model_a = map_row["model_at_A"]
            model_b = map_row["model_at_B"]
            overall = response.get("overall_verdict")
            ft_overall_side = _win_side("ft_qwen", model_a, model_b, overall)
            is_valid_overall = ft_overall_side in ("win", "loss", "tie")

            if is_valid_overall:
                n_valid_overall += 1
                overall_counter[ft_overall_side] += 1
                per_evaluator[evaluator][ft_overall_side] += 1
                per_item_overall_verdicts[cid].append(overall)
            else:
                n_invalid_overall += 1

            row = {
                "來源檔案": source_file,
                "評審": evaluator,
                "送出時間": submitted_at,
                "comparison_id": cid,
                "image_id": map_row.get("image_id", ""),
                "田區": question.get("field_id", ""),
                "日期": question.get("date", ""),
                "品種": question.get("variety", ""),
                "標準生育期": question.get("gt_stage", ""),
                "A實際模型": model_zh(model_a),
                "B實際模型": model_zh(model_b),
                f"{OVERALL_LABEL}_選擇": CHOICE_LABELS.get(overall, overall or "未作答"),
                f"{OVERALL_LABEL}_實際勝方": verdict_zh(model_a, model_b, overall),
                f"{OVERALL_LABEL}_換算結果": FT_RESULT_LABELS.get(ft_overall_side, "無效"),
                "備註": response.get("comment", ""),
            }

            for key, label in CRITERIA:
                value = criterion_value(response, key)
                side = _win_side("ft_qwen", model_a, model_b, value)
                if side:
                    by_criterion_counter[key][side] += 1
                row[f"{label}_選擇"] = CHOICE_LABELS.get(value, "未作答")
                row[f"{label}_實際勝方"] = verdict_zh(model_a, model_b, value)

            response_rows.append(row)

            if not is_valid_overall:
                continue

            for side_model, opp_model, position in (
                (model_a, model_b, "A"),
                (model_b, model_a, "B"),
            ):
                if overall == "tie":
                    result = "tie"
                elif overall == position:
                    result = "win"
                else:
                    result = "loss"

                per_model_lines[side_model].append({
                    "comparison_id": cid,
                    "image_id": map_row["image_id"],
                    "evaluator": evaluator,
                    "position": position,
                    "opponent": opp_model,
                    **{key: response.get(key) for key, _label in CRITERIA},
                    "overall_result": result,
                    "comment": response.get("comment", ""),
                })

    for model_code, rows in per_model_lines.items():
        path = config.RESULTS_DIR / f"results_{model_code}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    n_win = overall_counter.get("win", 0)
    n_tie = overall_counter.get("tie", 0)
    n_loss = overall_counter.get("loss", 0)
    n_total = n_win + n_tie + n_loss
    n_non_tie = n_win + n_loss

    multi_rated = {cid: verdicts for cid, verdicts in per_item_overall_verdicts.items() if len(verdicts) > 1}
    n_agree = sum(1 for verdicts in multi_rated.values() if len(set(verdicts)) == 1)

    for key, label in CRITERIA:
        counter = by_criterion_counter[key]
        c_win = counter.get("win", 0)
        c_tie = counter.get("tie", 0)
        c_loss = counter.get("loss", 0)
        c_total = c_win + c_tie + c_loss
        criteria_rows.append({
            "指標": label,
            "微調模型勝": c_win,
            "基礎模型勝": c_loss,
            "平手": c_tie,
            "有效票數": c_total,
            "微調勝率_含平手": percent(c_win, c_total),
            "微調勝率_排除平手": percent(c_win, c_win + c_loss),
        })

    overall_row = {
        "指標": OVERALL_LABEL,
        "微調模型勝": n_win,
        "基礎模型勝": n_loss,
        "平手": n_tie,
        "有效票數": n_total,
        "微調勝率_含平手": percent(n_win, n_total),
        "微調勝率_排除平手": percent(n_win, n_non_tie),
    }
    criteria_rows = [overall_row] + criteria_rows

    summary = {
        "n_evaluators": len(set(evaluators)),
        "evaluators": sorted(set(evaluators)),
        "n_items_in_pool": len(mapping),
        "n_responses": n_valid_overall,
        "n_response_rows": n_response_rows,
        "n_valid_overall": n_valid_overall,
        "n_invalid_overall": n_invalid_overall,
        "n_missing_mapping": n_missing_mapping,
        "position_check": position_check,
        "overall": {
            "ft_qwen_win": n_win,
            "base_qwen_win": n_loss,
            "ft_qwen_loss": n_loss,
            "tie": n_tie,
            "total": n_total,
            "non_tie_total": n_non_tie,
            "ft_qwen_win_rate": (n_win / n_total) if n_total else None,
            "ft_qwen_win_rate_without_ties": (n_win / n_non_tie) if n_non_tie else None,
        },
        "by_criterion": {
            key: {
                "label_zh": label,
                "ft_qwen_win": by_criterion_counter[key].get("win", 0),
                "base_qwen_win": by_criterion_counter[key].get("loss", 0),
                "ft_qwen_loss": by_criterion_counter[key].get("loss", 0),
                "tie": by_criterion_counter[key].get("tie", 0),
            }
            for key, label in CRITERIA
        },
        "per_evaluator": {
            evaluator: {
                "n_answered": sum(counter.values()),
                "ft_qwen_win": counter.get("win", 0),
                "base_qwen_win": counter.get("loss", 0),
                "ft_qwen_loss": counter.get("loss", 0),
                "tie": counter.get("tie", 0),
            }
            for evaluator, counter in sorted(per_evaluator.items())
        },
        "agreement": {
            "n_items_multi_rated": len(multi_rated),
            "n_items_full_agreement": n_agree,
            "agreement_rate": (n_agree / len(multi_rated)) if multi_rated else None,
        },
    }

    response_fieldnames = [
        "來源檔案",
        "評審",
        "送出時間",
        "comparison_id",
        "image_id",
        "田區",
        "日期",
        "品種",
        "標準生育期",
        "A實際模型",
        "B實際模型",
        f"{OVERALL_LABEL}_選擇",
        f"{OVERALL_LABEL}_實際勝方",
        f"{OVERALL_LABEL}_換算結果",
    ]
    for _key, label in CRITERIA:
        response_fieldnames.extend([f"{label}_選擇", f"{label}_實際勝方"])
    response_fieldnames.append("備註")

    with open(config.RESULTS_DIR / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    write_csv(
        config.RESULTS_DIR / "criteria_summary_zh.csv",
        criteria_rows,
        ["指標", "微調模型勝", "基礎模型勝", "平手", "有效票數", "微調勝率_含平手", "微調勝率_排除平手"],
    )
    write_csv(config.RESULTS_DIR / "responses_zh.csv", response_rows, response_fieldnames)
    write_markdown_report(config.RESULTS_DIR / "summary_zh.md", summary, criteria_rows, position_check)

    print(f"已完成分析，輸出位置：{config.RESULTS_DIR}")
    print(f"中文摘要：{config.RESULTS_DIR / 'summary_zh.md'}")
    print(f"作答明細：{config.RESULTS_DIR / 'responses_zh.csv'}")


if __name__ == "__main__":
    main()

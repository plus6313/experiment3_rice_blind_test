"""
彙總人工評測結果。

使用方式：
  1. 到 Google Drive 的評測資料夾，把所有 exp3_*.json 下載到 collected_responses/ 資料夾
  2. python analyze_results.py

輸出（在 results/ 資料夾）：
  - results_ft_qwen.jsonl / results_base_qwen.jsonl：每位評審者對每一題的判定（已解盲）
  - summary.json：整體勝率、各評分依據的勝率、逐位評審者統計、多人評同一題的一致率
"""

import json
import collections

import config


CRITERIA = [
    "criterion_1_stage_match",
    "criterion_2_gt_citation",
    "criterion_3_no_errors",
    "criterion_4_no_fluff",
    "criterion_5_no_hallucination",
]


def load_mapping():
    mapping = {}
    with open(config.MAPPING_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            mapping[d["comparison_id"]] = d
    return mapping


def load_collected():
    """回傳評審回覆清單，每筆為 (evaluator_name, submitted_at, responses[])。"""
    out = []
    if not config.COLLECTED_DIR.exists():
        return out
    for path in sorted(config.COLLECTED_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        out.append(data)
    return out


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


def main():
    mapping = load_mapping()
    submissions = load_collected()

    if not submissions:
        print(f"[提醒] {config.COLLECTED_DIR} 底下沒有任何 exp3_*.json，"
              f"請先從 Google Drive 資料夾下載評審回覆到這裡再重跑。")
        return

    per_model_lines = collections.defaultdict(list)

    overall_counter = collections.Counter()
    by_criterion_counter = {c: collections.Counter() for c in CRITERIA}
    per_evaluator = collections.defaultdict(lambda: collections.Counter())

    # 用來檢查多人評同一題的一致率
    per_item_overall_verdicts = collections.defaultdict(list)

    n_responses = 0
    evaluators = []

    for sub in submissions:
        evaluator = sub.get("evaluator_name", "unknown")
        evaluators.append(evaluator)

        for r in sub.get("responses", []):
            cid = r.get("comparison_id")
            m = mapping.get(cid)
            if m is None:
                continue  # 對不到 mapping，跳過（理論上不該發生）

            overall = r.get("overall_verdict")
            if overall not in ("A", "B", "tie"):
                continue  # 該題評審沒作答，跳過

            n_responses += 1
            model_a, model_b = m["model_at_A"], m["model_at_B"]

            per_item_overall_verdicts[cid].append(overall)

            side = _win_side("ft_qwen", model_a, model_b, overall)
            overall_counter[side] += 1
            per_evaluator[evaluator][side] += 1

            for c in CRITERIA:
                v = r.get(c)
                if v not in ("A", "B", "tie"):
                    continue
                side_c = _win_side("ft_qwen", model_a, model_b, v)
                by_criterion_counter[c][side_c] += 1

            for side_model, opp_model, position in (
                (model_a, model_b, "A"),
                (model_b, model_a, "B"),
            ):
                if overall == "tie":
                    result = "tie"
                elif (overall == "A" and position == "A") or (overall == "B" and position == "B"):
                    result = "win"
                else:
                    result = "loss"
                per_model_lines[side_model].append({
                    "comparison_id": cid,
                    "image_id": m["image_id"],
                    "evaluator": evaluator,
                    "position": position,
                    "opponent": opp_model,
                    "criterion_1_stage_match": r.get("criterion_1_stage_match"),
                    "criterion_2_gt_citation": r.get("criterion_2_gt_citation"),
                    "criterion_3_no_errors": r.get("criterion_3_no_errors"),
                    "criterion_4_no_fluff": r.get("criterion_4_no_fluff"),
                    "criterion_5_no_hallucination": r.get("criterion_5_no_hallucination"),
                    "overall_result": result,
                    "comment": r.get("comment", ""),
                })

    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    for model_code, rows in per_model_lines.items():
        path = config.RESULTS_DIR / f"results_{model_code}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    n_win = overall_counter.get("win", 0)
    n_tie = overall_counter.get("tie", 0)
    n_loss = overall_counter.get("loss", 0)
    n_total = n_win + n_tie + n_loss

    # 多人評同一題的一致率：該題所有評審的總體判定是否完全一致
    multi_rated = {cid: vs for cid, vs in per_item_overall_verdicts.items() if len(vs) > 1}
    n_agree = sum(1 for vs in multi_rated.values() if len(set(vs)) == 1)

    summary = {
        "n_evaluators": len(set(evaluators)),
        "evaluators": sorted(set(evaluators)),
        "n_items_in_pool": len(mapping),
        "n_responses": n_responses,
        "overall": {
            "ft_qwen_win": n_win,
            "tie": n_tie,
            "ft_qwen_loss": n_loss,
            "ft_qwen_win_rate": (n_win / n_total) if n_total else None,
        },
        "by_criterion": {
            c: {
                "ft_qwen_win": by_criterion_counter[c].get("win", 0),
                "tie": by_criterion_counter[c].get("tie", 0),
                "ft_qwen_loss": by_criterion_counter[c].get("loss", 0),
            }
            for c in CRITERIA
        },
        "per_evaluator": {
            ev: {
                "n_answered": sum(cnt.values()),
                "ft_qwen_win": cnt.get("win", 0),
                "tie": cnt.get("tie", 0),
                "ft_qwen_loss": cnt.get("loss", 0),
            }
            for ev, cnt in per_evaluator.items()
        },
        "agreement": {
            "n_items_multi_rated": len(multi_rated),
            "n_items_full_agreement": n_agree,
            "agreement_rate": (n_agree / len(multi_rated)) if multi_rated else None,
        },
    }

    summary_path = config.RESULTS_DIR / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n輸出目錄: {config.RESULTS_DIR}")


if __name__ == "__main__":
    main()

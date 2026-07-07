"""
實驗 3：人工盲測資料準備。

1. 讀取 ft_qwen / base_qwen 的 Q4 答案（Q4 有明確 gt_stage，較能客觀判斷；
   Q5 需要深厚農藝知識評斷農事建議，容易卡關，故不用於人工評測）
2. 依 gt_stage 生育階段做「分層比例抽樣」50 筆：用最大餘數法(Largest Remainder
   Method) 依各生育階段筆數比例分配抽樣名額，確保各階段依比例出現，
   而不是單純均勻隨機（避免抽到的樣本集中在少數幾個階段）
3. 每一筆用固定 seed 決定「回答A / 回答B」位置，並做身分 sanitization
4. 輸出：
   - private/mapping.jsonl      身分對照表，絕不可上傳 GitHub，本地留存供
                                  analyze_results.py 事後解盲用
   - site/data/questions.json   給靜態網頁用的公開題目檔（不含模型身分）
   - site/images/*.jpg          壓縮後的照片（INCLUDE_IMAGES=True 時）
"""

import json
import random
import collections

import config
from sanitizer import sanitize_answer


def load_q4(path):
    fm = config.FIELD_MAP
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            if d[fm["question_type"]] != config.QUESTION_TYPE:
                continue
            out[d[fm["image_id"]]] = d
    return out


def stratified_sample(ft_data, sample_size, seed):
    """
    依 gt_stage 分層、依各階層比例抽樣（最大餘數法分配名額），
    回傳 (抽到的 image_id 清單, 各階段分配到的抽樣數)。
    """
    fm = config.FIELD_MAP
    by_stage = collections.defaultdict(list)
    for image_id, rec in ft_data.items():
        by_stage[rec[fm["gt_stage"]]].append(image_id)

    total = len(ft_data)
    stages = sorted(by_stage.keys())  # 固定順序，確保可重現

    raw_alloc = {s: len(by_stage[s]) / total * sample_size for s in stages}
    base_alloc = {s: int(raw_alloc[s]) for s in stages}
    remainder = sample_size - sum(base_alloc.values())

    # 依小數餘數大小分配剩餘名額；同分時依階段名稱排序，確保可重現
    order = sorted(stages, key=lambda s: (-(raw_alloc[s] - base_alloc[s]), s))
    for s in order[:remainder]:
        base_alloc[s] += 1

    rng = random.Random(seed)
    sampled = []
    for s in stages:
        pool = sorted(by_stage[s])
        n = min(base_alloc[s], len(pool))
        sampled.extend(rng.sample(pool, n))

    return sorted(sampled), base_alloc


def build_items(sampled_ids, ft_data, base_data, seed):
    fm = config.FIELD_MAP
    rng = random.Random(seed)
    items_public = []
    mapping_rows = []

    for image_id in sampled_ids:
        rec_ft = ft_data[image_id]
        rec_base = base_data[image_id]

        question_text = rec_ft[fm["question"]]
        gt_stage = rec_ft[fm["gt_stage"]]

        flip = rng.random() < 0.5
        if flip:
            model_a, model_b = "base_qwen", "ft_qwen"
            raw_a, raw_b = rec_base[fm["answer"]], rec_ft[fm["answer"]]
        else:
            model_a, model_b = "ft_qwen", "base_qwen"
            raw_a, raw_b = rec_ft[fm["answer"]], rec_base[fm["answer"]]

        clean_a, flag_a, hits_a = sanitize_answer(raw_a, config.IDENTITY_KEYWORDS)
        clean_b, flag_b, hits_b = sanitize_answer(raw_b, config.IDENTITY_KEYWORDS)

        comparison_id = f"{image_id}_Q4"

        items_public.append({
            "comparison_id": comparison_id,
            "image_id": image_id,
            "field_id": rec_ft[fm["field_id"]],
            "date": rec_ft[fm["date"]],
            "variety": rec_ft[fm["variety"]],
            "gt_stage": gt_stage,
            "question_text": question_text,
            "answer_a": clean_a,
            "answer_b": clean_b,
            "image": f"images/{image_id}.jpg" if config.INCLUDE_IMAGES else None,
        })

        mapping_rows.append({
            "comparison_id": comparison_id,
            "image_id": image_id,
            "model_at_A": model_a,
            "model_at_B": model_b,
            "seed": seed,
            "answer_len_A": len(clean_a),
            "answer_len_B": len(clean_b),
            "sanitization_flag": bool(flag_a or flag_b),
        })

    return items_public, mapping_rows


def mask_timestamp(img):
    """
    模糊遮蔽左上角燒錄的時間戳記，保留其後的地點文字。
    只處理 config.TIMESTAMP_MASK_BY_WIDTH 裡登記過的解析度；其餘解析度
    （目前資料集中的 6240x4160）沒有燒錄時間戳，直接原樣回傳。

    邊界不是硬切一刀，而是在 mask_x 之後用 TIMESTAMP_MASK_FEATHER 像素的
    寬度做線性羽化（從全模糊漸變回清晰）。這樣就算不同照片裡時間戳最後一兩個
    數字的實際寬度有些微差異，也不會在畫面上留下清晰可辨識的殘留數字，
    也不會出現一條生硬的遮蔽邊界。
    """
    import numpy as np
    from PIL import ImageFilter

    w, h = img.size
    mask_x = config.TIMESTAMP_MASK_BY_WIDTH.get(w)
    if mask_x is None:
        return img

    mask_h = int(h * config.TIMESTAMP_MASK_HEIGHT_FRAC)
    feather = config.TIMESTAMP_MASK_FEATHER_BY_WIDTH.get(w, 20)
    full_w = min(w, mask_x + feather)

    margin = max(20, int(w * 0.03))
    ext_w = min(w, full_w + margin)
    ext_h = min(h, mask_h + margin)

    # 裁一塊比實際要合成的範圍略大的區域再模糊，避免邊緣因為缺乏鄰近像素
    # 資訊而出現不自然的接縫。
    region = img.crop((0, 0, ext_w, ext_h))
    radius = max(10, w // 45)
    blurred_region = region.filter(ImageFilter.GaussianBlur(radius=radius))

    sharp = img.crop((0, 0, full_w, mask_h))
    blurred = blurred_region.crop((0, 0, full_w, mask_h))

    alpha = np.zeros((mask_h, full_w), dtype=np.uint8)
    alpha[:, :mask_x] = 255
    if feather > 0 and full_w > mask_x:
        ramp = np.linspace(255, 0, full_w - mask_x).astype(np.uint8)
        alpha[:, mask_x:full_w] = ramp[np.newaxis, :]

    from PIL import Image as _Image
    alpha_img = _Image.fromarray(alpha, mode="L")
    composite = _Image.composite(blurred, sharp, alpha_img)
    img.paste(composite, (0, 0, full_w, mask_h))
    return img


def prepare_images(sampled_ids):
    if not config.INCLUDE_IMAGES:
        return
    from PIL import Image

    config.SITE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    n_ok = 0
    n_masked = 0
    for image_id in sampled_ids:
        src = None
        for ext in (".jpg", ".JPG", ".jpeg", ".JPEG"):
            candidate = config.IMAGES_SRC_DIR / f"{image_id}{ext}"
            if candidate.exists():
                src = candidate
                break
        if src is None:
            print(f"  [WARN] 找不到照片: {image_id}")
            continue

        img = Image.open(src).convert("RGB")
        w, h = img.size
        if w in config.TIMESTAMP_MASK_BY_WIDTH:
            img = mask_timestamp(img)
            n_masked += 1
        edge = max(w, h)
        if edge > config.IMAGE_MAX_EDGE:
            scale = config.IMAGE_MAX_EDGE / edge
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))

        dst = config.SITE_IMAGES_DIR / f"{image_id}.jpg"
        img.save(dst, "JPEG", quality=config.IMAGE_JPEG_QUALITY)
        n_ok += 1

    print(f"  照片處理完成：{n_ok}/{len(sampled_ids)}（其中 {n_masked} 張已模糊遮蔽時間戳）")


def main():
    print("讀取答案檔（僅 Q4）...")
    ft_data = load_q4(config.FT_FILE)
    base_data = load_q4(config.BASE_FILE)

    common_ids = sorted(set(ft_data) & set(base_data))
    print(f"  ft_qwen: {len(ft_data)}  base_qwen: {len(base_data)}  共同: {len(common_ids)}")
    ft_data = {k: v for k, v in ft_data.items() if k in common_ids}
    base_data = {k: v for k, v in base_data.items() if k in common_ids}

    print(f"依 gt_stage 分層比例抽樣 {config.SAMPLE_SIZE} 筆（seed={config.SEED}）...")
    sampled_ids, alloc = stratified_sample(ft_data, config.SAMPLE_SIZE, config.SEED)
    print("  各生育階段抽樣數（階段: 抽樣數/該階段總數）：")
    fm = config.FIELD_MAP
    stage_totals = collections.Counter(rec[fm["gt_stage"]] for rec in ft_data.values())
    for s in sorted(alloc):
        print(f"    {s}: {alloc[s]}/{stage_totals[s]}")
    print(f"  共抽出 {len(sampled_ids)} 筆")

    print("建立比較項目（A/B 隨機配置 + sanitization）...")
    items_public, mapping_rows = build_items(sampled_ids, ft_data, base_data, config.SEED)

    print("處理照片...")
    prepare_images(sampled_ids)

    config.PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(config.MAPPING_FILE, "w", encoding="utf-8") as f:
        for row in mapping_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"  身分對照表已寫入（不可上傳！）: {config.MAPPING_FILE}")

    (config.SITE_DIR / "data").mkdir(parents=True, exist_ok=True)
    with open(config.SITE_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(items_public, f, ensure_ascii=False, indent=2)
    print(f"  公開題目檔已寫入: {config.SITE_DATA_FILE}")


if __name__ == "__main__":
    main()

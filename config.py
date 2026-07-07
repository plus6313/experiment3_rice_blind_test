"""實驗 3（人工盲測）設定檔。"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ANS_DIR = BASE_DIR.parent / "ans"
IMAGES_SRC_DIR = BASE_DIR.parent / "test_images"

FT_FILE = str(ANS_DIR / "answers_finetuned_qwen.jsonl")
BASE_FILE = str(ANS_DIR / "answers_base_qwen.jsonl")

FIELD_MAP = {
    "image_id": "image_id",
    "field_id": "field_id",
    "date": "date",
    "variety": "variety",
    "gt_stage": "gt_stage",
    "question_type": "question_type",
    "question": "question",
    "model": "model",
    "answer": "answer",
}

QUESTION_TYPE = "Q4"  # 只用 Q4：有明確 GT，較能客觀判斷
SAMPLE_SIZE = 50
SEED = 42  # 固定 seed：分層抽樣 + A/B 隨機配置皆可重現

INCLUDE_IMAGES = True
IMAGE_MAX_EDGE = 1024
IMAGE_JPEG_QUALITY = 80

# 照片左上角燒錄的時間戳記需要模糊遮蔽（避免評審從時間戳猜測身分/其他線索），
# 但地點文字（如「楊梅智慧田示範區」）要保留。
# 不同解析度的攝影系統，時間戳文字結束的 x 座標不同（同解析度內固定字型/位置，
# 已用多張樣本比對確認），下面是各解析度對應的遮蔽右邊界（像素，遮 [0, x] 這塊）。
# 6240x4160 這組照片沒有燒錄時間戳（另一套相機系統），不在表中的解析度一律略過不遮。
TIMESTAMP_MASK_BY_WIDTH = {
    1920: 380,  # 時間戳約在 x<355 結束，地點文字約在 x>420 開始
    1280: 247,  # 時間戳約在 x<240-244 結束（各檔案略有±幾px差異），地點文字約在 x>246-259 開始
}
TIMESTAMP_MASK_HEIGHT_FRAC = 0.08
# 遮蔽邊界之後再羽化這麼多像素（由完全模糊線性過渡回清晰），用來吸收上面
# 邊界值的估計誤差：就算實際邊界差了幾像素，也只是讓地點文字第一個字最左邊
# 一兩筆筆畫被柔化，而不是留下清晰可辨識的時間戳數字或出現生硬的方框接縫。
# 1280 這組時間戳跟地點文字間距非常小，羽化寬度不能太大，否則會吃掉整個字；
# 1920 這組間距較寬鬆，可以用大一點的羽化讓過渡更自然。
TIMESTAMP_MASK_FEATHER_BY_WIDTH = {
    1920: 30,
    1280: 14,
}

# 與 experiment2 相同精神：人工評測一樣要盲測，答案中若含身分字串一樣要清洗
IDENTITY_KEYWORDS = [
    "阿里巴巴", "阿里雲", "alibaba", "aliyun",
    "google", "谷歌", "deepmind",
    "anthropic",
    "qwen", "gemini", "gemma", "claude",
    "as an ai language model", "as an ai model", "as a language model",
    "i'm claude", "i am claude", "as claude",
    "i'm gemini", "i am gemini", "as gemini",
    "i'm qwen", "i am qwen", "as qwen",
    "i'm gemma", "i am gemma", "as gemma",
    "作為qwen", "作為 qwen", "作為gemini", "作為 gemini",
    "作為gemma", "作為 gemma", "作為claude", "作為 claude",
    "我是qwen", "我是 qwen", "我是gemini", "我是 gemini",
    "我是gemma", "我是 gemma", "我是claude", "我是 claude",
    "我是一個大型語言模型", "我是一個ai", "我是一個 ai",
    "本模型由", "由阿里巴巴", "由google", "由 google",
]

# ---- 本地私有輸出（絕不可上傳 GitHub）----
PRIVATE_DIR = BASE_DIR / "private"
MAPPING_FILE = PRIVATE_DIR / "mapping.jsonl"

# ---- 靜態網站輸出（此資料夾內容會上傳到 GitHub Pages）----
SITE_DIR = BASE_DIR / "site"
SITE_DATA_FILE = SITE_DIR / "data" / "questions.json"
SITE_IMAGES_DIR = SITE_DIR / "images"

# ---- 收集回來的人工評測回覆（analyze_results.py 用）----
COLLECTED_DIR = BASE_DIR / "collected_responses"
RESULTS_DIR = BASE_DIR / "results"

GOOGLE_DRIVE_FOLDER_ID = "1lLXDS8qw93Ol6zW4mbHFRMIfPMcorHdp"

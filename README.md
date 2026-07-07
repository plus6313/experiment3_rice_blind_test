# 實驗 3：人工盲測（Fine-tuned vs Base Qwen，僅 Q4）

## 已完成的資料準備

`prepare_data.py` 已經跑過一次，目前狀態：

- 依 `gt_stage`（10 個生育階段）用最大餘數法分層比例抽樣出 50 筆（seed=42，可重跑重現）
- 每筆的「回答 A / 回答 B」位置已用同一組 seed 隨機決定
- 兩邊答案已做身分 sanitization
- `site/data/questions.json`：50 題公開資料（**不含**模型身分），可直接上傳 GitHub
- `site/images/*.jpg`：50 張壓縮後照片（長邊 ≤1024px，品質80，共約 11MB）
- `private/mapping.jsonl`：A/B 對應到 ft_qwen/base_qwen 的身分對照表 —
  **絕對不可上傳 GitHub**，`.gitignore` 已排除，事後用 `analyze_results.py` 解盲用

若要重新抽樣或調整參數，改 `config.py` 後重跑 `python prepare_data.py` 即可（會覆寫上述三個輸出）。

## 部署步驟

### 1. 部署 Google Apps Script（接收評測結果寫入你的 Drive）

1. 前往 https://script.google.com/ → 新增專案
2. 把 `apps_script/Code.gs` 的內容整個貼進去（`FOLDER_ID` 已預填你提供的資料夾
   `1lLXDS8qw93Ol6zW4mbHFRMIfPMcorHdp`）
3. 右上角「部署」→「新增部署作業」：
   - 類型：**網頁應用程式**
   - 執行身分：**我**（你自己的帳號 —— 這樣指令碼才能寫入你的 Drive，評審者不需要登入 Google）
   - 具有存取權的使用者：**任何人**
4. 第一次部署會跳出授權畫面（因為指令碼要寫入你的 Drive）。這是 Google 對「你自己寫的、
   存取你自己資料」的指令碼的標準一次性同意流程 —— 只有你自己要按過一次「允許」，
   不需要另外提供任何金鑰、密碼給我或任何人。若畫面顯示「未經驗證的應用程式」，
   點「進階」→「前往...（不安全）」即可，這只是因為指令碼還沒送 Google 審核，
   但只有你自己使用，沒有風險。
5. 複製部署完成後出現的「網頁應用程式網址」
6. 打開 `site/app.js`，把最上面的：
   ```js
   const APPS_SCRIPT_URL = "PUT_YOUR_DEPLOYED_WEB_APP_URL_HERE";
   ```
   換成剛剛複製的網址
7. 可以直接在瀏覽器打開這個網址測試：看到 `{"status":"ok","message":"exp3 endpoint is alive"}`
   就代表部署成功

之後如果修改了 `Code.gs`，要記得「管理部署作業」→ 編輯 → 部署「新版本」，網址才會套用新程式碼。

### 2. 推上 GitHub Pages

只有 `site/` 資料夾底下的內容需要上傳（`private/`、`collected_responses/`、`results/`
已經在 `.gitignore` 排除，即使不小心 `git add .` 也不會被加入）。

```bash
cd "正式微調後/experiment3"
git init
git add .
git commit -m "experiment3 human evaluation site"
git branch -M main
git remote add origin https://github.com/<你的帳號>/<repo名稱>.git
git push -u origin main
```

推上去之後到 repo 的 Settings → Pages：
- Source: Deploy from a branch
- Branch: `main`，資料夾選 `/site`

存好之後，網址通常是 `https://<你的帳號>.github.io/<repo名稱>/`（GitHub 需要幾分鐘才會生效）。

把這個網址分享給農業專家即可開始評測。

## 3. 收集完評測後：解盲與彙總

1. 到 Google Drive 資料夾，把所有 `exp3_*.json` 下載到 `experiment3/collected_responses/`
2. 執行：
   ```bash
   cd "正式微調後/experiment3"
   python analyze_results.py
   ```
3. 產出在 `experiment3/results/`：
   - `results_ft_qwen.jsonl` / `results_base_qwen.jsonl`：每位評審者對每一題的判定（已解盲）
   - `summary.json`：整體勝率、三個評分依據各自的勝率、逐位評審者統計、
     多人評同一題的一致率（agreement_rate）

## 檔案結構

```
experiment3/
  config.py              抽樣/路徑等設定
  sanitizer.py            身分字串清洗（與 experiment2 相同邏輯）
  prepare_data.py          產生 site/data/questions.json + site/images/ + private/mapping.jsonl
  analyze_results.py       解盲 + 彙總評測結果
  apps_script/Code.gs      Google Apps Script 後端（部署後把網址填進 site/app.js）
  private/mapping.jsonl    身分對照表（.gitignore 排除，不可上傳）
  site/                    要上傳 GitHub Pages 的靜態網站
    index.html / style.css / app.js
    data/questions.json
    images/*.jpg
  collected_responses/     手動從 Drive 下載回來的評審回覆（.gitignore 排除）
  results/                 analyze_results.py 的輸出（.gitignore 排除）
```

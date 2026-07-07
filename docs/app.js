// ============================================================================
// 設定：部署 Apps Script 後，把下面網址換成你的「網頁應用程式」網址
// （site/../apps_script/Code.gs 部署完成後 Google 會給你這個網址）
// ============================================================================
const APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzt70DJOdVboTrWvO662T_zAROI47dTyZgCCVdO3U44X869vIDpcIziyf3m0mRbOZEn/exec";

const STORAGE_KEY = "exp3_progress_v2";
const CRITERIA_NAMES = [
  "criterion_1_stage_match",
  "criterion_2_gt_citation",
  "criterion_3_no_errors",
  "criterion_4_no_fluff",
  "criterion_5_no_hallucination",
  "overall_verdict",
];

let ITEMS = [];
let responses = {}; // comparison_id -> {criterion_1_stage_match, criterion_2_gt_citation, criterion_3_no_errors, overall_verdict, comment}
let currentIndex = 0;
let evaluatorName = "";

const screens = {
  intro: document.getElementById("screen-intro"),
  question: document.getElementById("screen-question"),
  done: document.getElementById("screen-done"),
};

function showScreen(name) {
  Object.values(screens).forEach((s) => (s.style.display = "none"));
  screens[name].style.display = "block";
}

function loadProgress() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}

function saveProgress() {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ evaluatorName, responses, currentIndex })
  );
}

function isComplete(v) {
  return !!(
    v &&
    v.criterion_1_stage_match &&
    v.criterion_2_gt_citation &&
    v.criterion_3_no_errors &&
    v.criterion_4_no_fluff &&
    v.criterion_5_no_hallucination &&
    v.overall_verdict
  );
}

function currentFormValues() {
  const form = document.getElementById("criteria-form");
  const fd = new FormData(form);
  return {
    criterion_1_stage_match: fd.get("criterion_1_stage_match") || null,
    criterion_2_gt_citation: fd.get("criterion_2_gt_citation") || null,
    criterion_3_no_errors: fd.get("criterion_3_no_errors") || null,
    criterion_4_no_fluff: fd.get("criterion_4_no_fluff") || null,
    criterion_5_no_hallucination: fd.get("criterion_5_no_hallucination") || null,
    overall_verdict: fd.get("overall_verdict") || null,
    comment: document.getElementById("comment").value || "",
  };
}

function onFormChange() {
  const item = ITEMS[currentIndex];
  responses[item.comparison_id] = currentFormValues();
  saveProgress();
  updateAnsweredHint();
}

function renderItem(index) {
  const item = ITEMS[index];

  document.getElementById("progress-label").textContent = `第 ${index + 1} / ${ITEMS.length} 題`;
  document.getElementById("progress-fill").style.width = `${(index / ITEMS.length) * 100}%`;

  document.getElementById("ctx-field").textContent = `田區 ${item.field_id}`;
  document.getElementById("ctx-date").textContent = item.date;
  document.getElementById("ctx-variety").textContent = item.variety;

  const imgEl = document.getElementById("item-image");
  if (item.image) {
    imgEl.src = item.image;
    imgEl.style.display = "block";
  } else {
    imgEl.style.display = "none";
  }

  document.getElementById("question-text").textContent = item.question_text;
  document.getElementById("gt-stage").textContent = item.gt_stage;
  document.getElementById("answer-a").textContent = item.answer_a;
  document.getElementById("answer-b").textContent = item.answer_b;

  const form = document.getElementById("criteria-form");
  form.reset();
  document.getElementById("comment").value = "";

  const saved = responses[item.comparison_id];
  if (saved) {
    for (const name of CRITERIA_NAMES) {
      if (saved[name]) {
        const el = form.querySelector(`input[name="${name}"][value="${saved[name]}"]`);
        if (el) el.checked = true;
      }
    }
    document.getElementById("comment").value = saved.comment || "";
  }

  document.getElementById("btn-prev").disabled = index === 0;
  document.getElementById("btn-next").textContent =
    index === ITEMS.length - 1 ? "完成 →" : "下一題 →";

  updateAnsweredHint();
  window.scrollTo(0, 0);
}

function updateAnsweredHint() {
  const n = Object.values(responses).filter(isComplete).length;
  document.getElementById("answered-hint").textContent = `已完成 ${n} / ${ITEMS.length} 題`;
}

function goTo(index) {
  const item = ITEMS[currentIndex];
  responses[item.comparison_id] = currentFormValues();
  saveProgress();

  if (index >= ITEMS.length) {
    renderDoneScreen();
    return;
  }
  if (index < 0) return;

  currentIndex = index;
  saveProgress();
  renderItem(currentIndex);
}

function renderDoneScreen() {
  showScreen("done");
  const nComplete = Object.values(responses).filter(isComplete).length;
  const summary = document.getElementById("done-summary");
  if (nComplete < ITEMS.length) {
    summary.textContent = `您目前已完成 ${nComplete} / ${ITEMS.length} 題，建議先補齊所有題目再送出（點下方題號可直接跳回該題）。`;
  } else {
    summary.textContent = `您已完成全部 ${ITEMS.length} 題，感謝您的協助！請點擊下方按鈕送出結果。`;
  }

  const jumpList = document.getElementById("jump-list");
  jumpList.innerHTML = "";
  ITEMS.forEach((item, i) => {
    const btn = document.createElement("button");
    const done = isComplete(responses[item.comparison_id]);
    btn.textContent = `${i + 1}`;
    btn.className = "jump-btn " + (done ? "done" : "todo");
    btn.addEventListener("click", () => {
      currentIndex = i;
      showScreen("question");
      renderItem(i);
    });
    jumpList.appendChild(btn);
  });
}

function buildPayload() {
  return {
    evaluator_name: evaluatorName,
    submitted_at: new Date().toISOString(),
    app_version: "exp3-v1",
    n_items: ITEMS.length,
    responses: ITEMS.map((item) => ({
      comparison_id: item.comparison_id,
      ...(responses[item.comparison_id] || {
        criterion_1_stage_match: null,
        criterion_2_gt_citation: null,
        criterion_3_no_errors: null,
        criterion_4_no_fluff: null,
        criterion_5_no_hallucination: null,
        overall_verdict: null,
        comment: "",
      }),
    })),
  };
}

function downloadBackup() {
  const payload = buildPayload();
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  const safeName = (evaluatorName || "unknown").replace(/[^\w一-鿿-]/g, "_");
  a.href = url;
  a.download = `exp3_${safeName}_backup.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

async function onSubmit() {
  const statusEl = document.getElementById("submit-status");

  if (!APPS_SCRIPT_URL || APPS_SCRIPT_URL.indexOf("PUT_YOUR_") === 0) {
    statusEl.textContent =
      "⚠️ 尚未設定送出網址，請聯絡研究人員。已為您產生本地備份，請改用「下載備份」按鈕保存後回傳。";
    downloadBackup();
    return;
  }

  const payload = buildPayload();
  const safeName = (evaluatorName || "unknown").replace(/[^\w一-鿿-]/g, "_");
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  // Apps Script 端的 doPost 預期 {fileName, content} 這個包裝格式
  const wrapped = { fileName: `exp3_${safeName}_${ts}.json`, content: payload };

  statusEl.textContent = "送出中...";
  try {
    // Apps Script 網頁應用程式走 no-cors，瀏覽器無法讀回應內容，
    // 但只要 fetch 沒有丟出例外，代表請求已經送出去了。
    await fetch(APPS_SCRIPT_URL, {
      method: "POST",
      mode: "no-cors",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify(wrapped),
    });
    statusEl.textContent = "✅ 已送出，感謝您的協助！（若不放心，可再按一次下載備份自行保存）";
    localStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    statusEl.textContent =
      "❌ 送出失敗（可能是網路問題），請按「下載備份」把檔案存下來，再回傳給研究人員。";
    console.error(err);
  }
}

function onStart() {
  const nameInput = document.getElementById("evaluator-name");
  const name = nameInput.value.trim();
  if (!name) {
    alert("請先輸入您的姓名再開始評測");
    return;
  }

  const saved = loadProgress();
  if (saved && saved.evaluatorName === name) {
    responses = saved.responses || {};
    currentIndex = saved.currentIndex || 0;
  } else {
    responses = {};
    currentIndex = 0;
  }
  evaluatorName = name;
  saveProgress();
  showScreen("question");
  renderItem(currentIndex);
}

async function init() {
  const res = await fetch("data/questions.json");
  ITEMS = await res.json();

  const saved = loadProgress();
  if (saved && saved.evaluatorName) {
    document.getElementById("evaluator-name").value = saved.evaluatorName;
    const nAnswered = Object.values(saved.responses || {}).filter(isComplete).length;
    const hint = document.getElementById("resume-hint");
    hint.style.display = "block";
    hint.textContent = `偵測到上次未完成的紀錄（${saved.evaluatorName}，已完成 ${nAnswered}/${ITEMS.length} 題），輸入同樣的姓名並按「開始評測」即可繼續。`;
  }

  document.getElementById("btn-start").addEventListener("click", onStart);
  document.getElementById("btn-prev").addEventListener("click", () => goTo(currentIndex - 1));
  document.getElementById("btn-next").addEventListener("click", () => goTo(currentIndex + 1));
  document.getElementById("btn-early-submit").addEventListener("click", () => goTo(ITEMS.length));
  document.getElementById("btn-submit").addEventListener("click", onSubmit);
  document.getElementById("btn-download").addEventListener("click", downloadBackup);
  document.getElementById("criteria-form").addEventListener("change", onFormChange);

  showScreen("intro");
}

init();

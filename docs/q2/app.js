// ============================================================================
// Q2 盲測評測 — 視覺判讀版 (exp3-q2)
// 與 Q4 版本差異：
//   1. STORAGE_KEY / app_version / fileName 前綴均換為 q2 識別字
//   2. CRITERIA_NAMES 對應五大指標（accuracy / reasoning / depth /
//      actionability / completeness）+ overall_verdict
//   3. renderItem() 不顯示 gt_stage（評測者只看圖片，不看 GT）
//   4. cleanText() 去除 Markdown 排版（去粗體、標題、emoji、條列符號）
//      讓兩個回答視覺上長度更接近，不透露排版風格
//   5. 其餘 Google Apps Script 傳送邏輯與 Q4 完全相同（同一 endpoint）
// ============================================================================
const APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyjOWJkuD6u1xlq7iy4vdgLOEB6NV3KHemNoTKmDwEDzHtV4-PhDGJxUz0KPJzaFk91/exec";

const STORAGE_KEY = "exp3_q2_progress_v1";
const CRITERIA_NAMES = [
  "criterion_1_accuracy",
  "criterion_2_reasoning",
  "criterion_3_depth",
  "criterion_4_actionability",
  "criterion_5_completeness",
  "overall_verdict",
];

let ITEMS = [];
let responses = {};
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

// 去除 Markdown 排版，讓兩個回答在排版上無法區分
function cleanText(text) {
  if (!text) return "";
  return text
    .replace(/\*\*(.+?)\*\*/g, "$1")           // **粗體**
    .replace(/\*(.+?)\*/g, "$1")               // *斜體*
    .replace(/#{1,6}\s*/g, "")                 // ## 標題
    .replace(/^[-*+]\s+/gm, "")               // 條列 bullet
    .replace(/^\d+\.\s+/gm, "")              // 數字條列
    .replace(/[✅⚠️📌💡📸🌾]/gu, "")          // 常見 emoji
    .replace(/^---+\s*$/gm, "")              // 水平線
    .replace(/\n{3,}/g, "\n\n")              // 連續空行壓縮
    .trim();
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
    v.criterion_1_accuracy &&
    v.criterion_2_reasoning &&
    v.criterion_3_depth &&
    v.criterion_4_actionability &&
    v.criterion_5_completeness &&
    v.overall_verdict
  );
}

function currentFormValues() {
  const form = document.getElementById("criteria-form");
  const fd = new FormData(form);
  return {
    criterion_1_accuracy:      fd.get("criterion_1_accuracy")      || null,
    criterion_2_reasoning:     fd.get("criterion_2_reasoning")     || null,
    criterion_3_depth:         fd.get("criterion_3_depth")         || null,
    criterion_4_actionability: fd.get("criterion_4_actionability") || null,
    criterion_5_completeness:  fd.get("criterion_5_completeness")  || null,
    overall_verdict:           fd.get("overall_verdict")           || null,
    comment:                   document.getElementById("comment").value || "",
  };
}

function isTruncated(text) {
  if (!text) return false;
  const last = text.trimEnd().slice(-1);
  return !'。！？」…"、)）.!?'.includes(last);
}

function setAnswerText(elId, text) {
  const el = document.getElementById(elId);
  el.textContent = cleanText(text);
  if (isTruncated(text)) {
    const note = document.createElement("span");
    note.textContent = "⚠ 此回答達到字數上限，內容可能不完整";
    note.style.cssText = "display:block;margin-top:8px;font-size:0.82rem;color:#b45309;font-style:italic;";
    el.appendChild(note);
  }
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
  document.getElementById("ctx-hour").textContent = item.capture_hour != null ? item.capture_hour : "—";
  document.getElementById("ctx-variety").textContent = item.variety;

  // GT 參考資訊（讓評測者能驗證 Accuracy / Reasoning）
  document.getElementById("gt-stage").textContent = item.gt_stage || "—";
  document.getElementById("gt-days").textContent = item.gt_days != null ? item.gt_days : "—";
  document.getElementById("gt-transplant").textContent = item.gt_transplant_date || "—";
  const heightAvg = item.gt_plant_height && item.gt_plant_height["平均"] != null
    ? item.gt_plant_height["平均"].toFixed(1) : "—";
  document.getElementById("gt-height").textContent = heightAvg;
  const leafAvg = item.gt_leaf_color && item.gt_leaf_color["平均"] != null
    ? item.gt_leaf_color["平均"].toFixed(1) : "—";
  document.getElementById("gt-leaf").textContent = leafAvg;

  const imgEl = document.getElementById("item-image");
  if (item.image) {
    imgEl.src = item.image;
    imgEl.style.display = "block";
  } else {
    imgEl.style.display = "none";
  }

  document.getElementById("question-text").textContent = item.question_text;
  setAnswerText("answer-a", item.answer_a);
  setAnswerText("answer-b", item.answer_b);

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
    app_version: "exp3-q2-v1",
    n_items: ITEMS.length,
    responses: ITEMS.map((item) => ({
      comparison_id: item.comparison_id,
      ...(responses[item.comparison_id] || {
        criterion_1_accuracy:      null,
        criterion_2_reasoning:     null,
        criterion_3_depth:         null,
        criterion_4_actionability: null,
        criterion_5_completeness:  null,
        overall_verdict:           null,
        comment:                   "",
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
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  a.href = url;
  a.download = `exp3_q2_${safeName}_backup_${ts}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---- Google Apps Script 傳送（與 Q4 相同邏輯）----

function appsScriptJsonpRequest(params = {}, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const callbackName = `exp3q2EndpointPing_${Date.now()}_${Math.random()
      .toString(36)
      .slice(2)}`;
    const script = document.createElement("script");
    const separator = APPS_SCRIPT_URL.includes("?") ? "&" : "?";
    const searchParams = new URLSearchParams({
      ...params,
      callback: callbackName,
      t: Date.now().toString(),
    });
    const timeout = window.setTimeout(() => {
      cleanup();
      reject(new Error("Apps Script endpoint check timed out."));
    }, timeoutMs);

    function cleanup() {
      window.clearTimeout(timeout);
      script.remove();
      delete window[callbackName];
    }

    window[callbackName] = (result) => {
      cleanup();
      if (
        result &&
        (result.status === "ok" || result.status === "success" || result.status === "pending")
      ) {
        resolve(result);
      } else {
        reject(new Error((result && result.message) || "Apps Script endpoint returned an error."));
      }
    };

    script.onerror = () => {
      cleanup();
      reject(new Error("Apps Script endpoint is not publicly reachable."));
    };

    script.src = `${APPS_SCRIPT_URL}${separator}${searchParams.toString()}`;
    document.body.appendChild(script);
  });
}

function appsScriptJsonpPing(timeoutMs = 10000) {
  return appsScriptJsonpRequest({}, timeoutMs);
}

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

async function waitForSubmissionReceipt(submissionId) {
  for (let i = 0; i < 10; i += 1) {
    const result = await appsScriptJsonpRequest({ submissionId }, 10000);
    if (result.status === "success") return result;
    if (result.status !== "pending") {
      throw new Error(result.message || "Apps Script submission failed.");
    }
    await sleep(1000);
  }
  throw new Error("Timed out waiting for Google Drive confirmation.");
}

async function postToAppsScript(wrapped) {
  await appsScriptJsonpPing();
  await fetch(APPS_SCRIPT_URL, {
    method: "POST",
    mode: "no-cors",
    headers: { "Content-Type": "text/plain;charset=utf-8" },
    body: JSON.stringify(wrapped),
  });
  const result = await waitForSubmissionReceipt(wrapped.submissionId);
  return { confirmed: true, result };
}

async function onSubmit() {
  const statusEl = document.getElementById("submit-status");
  const submitBtn = document.getElementById("btn-submit");

  if (!APPS_SCRIPT_URL || APPS_SCRIPT_URL.indexOf("PUT_YOUR_") === 0) {
    statusEl.textContent =
      "⚠️ 尚未設定送出網址，請聯絡研究人員。已為您產生本地備份，請改用「下載備份」按鈕保存後回傳。";
    downloadBackup();
    return;
  }

  const payload = buildPayload();
  const safeName = (evaluatorName || "unknown").replace(/[^\w一-鿿-]/g, "_");
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  const submissionId = `exp3_q2_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  // Apps Script 端的 doPost 預期 {fileName, content, submissionId} 格式（與 Q4 相同）
  const wrapped = {
    submissionId,
    fileName: `exp3_q2_${safeName}_${ts}.json`,
    content: payload,
  };

  statusEl.textContent = "送出中...";
  submitBtn.disabled = true;
  try {
    const submitResult = await postToAppsScript(wrapped);
    statusEl.textContent = `✅ 已送出並確認存到 Google Drive：${submitResult.result.fileName}`;
    localStorage.removeItem(STORAGE_KEY);
  } catch (err) {
    statusEl.textContent =
      "❌ 送出失敗：Google Apps Script 端點目前無法公開存取。請按「下載我的作答備份」保存，並通知研究人員重新部署。";
    console.error(err);
  } finally {
    submitBtn.disabled = false;
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

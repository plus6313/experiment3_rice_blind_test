// ============================================================================
// Q2 盲測評測 — SOP 評分版 v2 (exp3-q2-sop-v2)
// 與 /q2-sop/ 版本差異：
//   1. 版面改為桌面寬螢幕懸浮版：頂部固定列（進度/情境/GT）+ 左右固定
//      選項 A/B（各自可獨立捲動）+ 中間可捲動的題目與評分表單。
//      手機窄螢幕維持原本上下堆疊瀏覽，不啟用懸浮版面。
//   2. 新增「生育階段對照表」懸浮按鈕，評測全程可隨時點開查閱完整
//      官方階段＋同義詞說法，不需要離開當前題目。
//   3. STORAGE_KEY / app_version / fileName 前綴均換為 q2sopv2 識別字
//   4. 其餘（BARS 0~3 分評分機制、cleanText、GT 顯示、截斷警示、
//      Apps Script 傳送）與 /q2-sop/ 完全相同
// ============================================================================
const APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbyjOWJkuD6u1xlq7iy4vdgLOEB6NV3KHemNoTKmDwEDzHtV4-PhDGJxUz0KPJzaFk91/exec";

const STORAGE_KEY = "exp3_q2sopv2_progress_v1";

// 生育階段對照表資料（依插秧後平均生育天數排序）
const STAGE_TABLE = [
  { stage: "成活期", days: "~15天", syn: ["同義：返青期、返青末期"] },
  { stage: "分蘗初期", days: "~19天", syn: ["同義：分蘗期初期、分蘗期（泛稱）"] },
  { stage: "分蘗盛期", days: "~34天", syn: ["同義：分蘖盛期、最高分蘗期、有效分蘗盛期、分蘗旺盛期、盛蘗期"] },
  { stage: "停滯期", days: "~49天", syn: ["同義：分蘗末期、有效分蘗末期、無效分蘗期、分蘗終止期、封行期"] },
  { stage: "幼穗形成期", days: "~56天", syn: ["同義：幼穗分化期、幼穗分化初期、拔節期、拔節初期／後期／末期（拔節常與此期同時發生）"] },
  { stage: "孕穗期", days: "~64天", syn: ["同義：孕穗早期、孕穗末期、孕穗前期"] },
  { stage: "抽穗期", days: "~76天", syn: ["同義：抽穗初／中／末／前／後期、揚花期、揚花初期／盛期、開花期、開花初期、開花結實期"] },
  {
    stage: "糊熟期",
    days: "~94天",
    syn: [
      "同義：糊熟",
      "範圍涵蓋GT：灌漿期（統稱，未指明子階段時，視為給出範圍且GT落在其中 → 2分）",
      "<span class=\"early\">比糊熟期早（2分）</span>：乳熟期（及初／中／末期）── 穀粒還像牛奶一樣軟、還沒定型",
      "<span class=\"late\">比糊熟期晚（2分）</span>：蠟熟期／蜡熟期（及初／末期）── 穀粒已變硬像蠟，但含水量仍高",
    ],
  },
  { stage: "黃熟期", days: "~103天", syn: ["同義：黃熟初期、黃熟末期"] },
  { stage: "完熟期", days: "~112天", syn: ["同義：完熟初期、成熟期、成熟前／後／初期"] },
];

const STAGE_TABLE_NOTE =
  "額外提醒：若答案用「或」連接兩個鄰近階段（例如「抽穗期或揚花初期」），視為表達不確定性／給出範圍，只要 GT 落在其中即可算 2分（除非兩者剛好都等於 GT，則算 3分）。" +
  "若答案提到「即將進入 XX 期」，代表模型認為現在還不是 XX 期，這個 XX 期不算模型的當下判斷，評分時應忽略，只看模型明確宣稱的「當下」階段。";

function buildStageTableHTML() {
  const rows = STAGE_TABLE.map((row, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><strong>${row.stage}</strong></td>
      <td>${row.days}</td>
      <td>${row.syn.join("<br>")}</td>
    </tr>
  `).join("");
  return `
    <thead>
      <tr>
        <th>#</th>
        <th>官方階段（GT用詞）</th>
        <th>平均插秧後天數</th>
        <th>相近／易混淆說法</th>
      </tr>
    </thead>
    <tbody>${rows}</tbody>
  `;
}

function renderStageTable() {
  const html = buildStageTableHTML();
  const introTable = document.getElementById("intro-stage-table");
  const modalTable = document.getElementById("modal-stage-table");
  if (introTable) introTable.innerHTML = html;
  if (modalTable) modalTable.innerHTML = html;
  const introNote = document.getElementById("intro-stage-table-note");
  const modalNote = document.getElementById("modal-stage-table-note");
  if (introNote) introNote.textContent = STAGE_TABLE_NOTE;
  if (modalNote) modalNote.textContent = STAGE_TABLE_NOTE;
}

function updateStickyOffset() {
  const topbar = document.querySelector(".sticky-topbar");
  if (topbar && topbar.offsetParent !== null) {
    document.documentElement.style.setProperty("--topbar-height", topbar.offsetHeight + "px");
  }
}

// 五個維度 × (A, B) 的分數欄位
const SCORE_FIELDS = [
  "criterion_1_accuracy_a", "criterion_1_accuracy_b",
  "criterion_2_reasoning_a", "criterion_2_reasoning_b",
  "criterion_3_depth_a", "criterion_3_depth_b",
  "criterion_4_actionability_a", "criterion_4_actionability_b",
  "criterion_5_completeness_a", "criterion_5_completeness_b",
];
const ALL_FIELDS = [...SCORE_FIELDS, "overall_verdict"];

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
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/#{1,6}\s*/g, "")
    .replace(/^[-*+]\s+/gm, "")
    .replace(/^\d+\.\s+/gm, "")
    .replace(/[✅⚠️📌💡📸🌾]/gu, "")
    .replace(/^---+\s*$/gm, "")
    .replace(/\n{3,}/g, "\n\n")
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

// 分數 "0" 也算已作答，只有 null/undefined 才算未作答
function isComplete(v) {
  if (!v) return false;
  return ALL_FIELDS.every((f) => v[f] !== null && v[f] !== undefined && v[f] !== "");
}

function currentFormValues() {
  const form = document.getElementById("criteria-form");
  const fd = new FormData(form);
  const result = {};
  for (const f of SCORE_FIELDS) {
    const val = fd.get(f);
    result[f] = val === null ? null : val;
  }
  result.overall_verdict = fd.get("overall_verdict") || null;
  result.comment = document.getElementById("comment").value || "";
  return result;
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
    for (const f of ALL_FIELDS) {
      const val = saved[f];
      if (val !== null && val !== undefined && val !== "") {
        const el = form.querySelector(`input[name="${f}"][value="${val}"]`);
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
  requestAnimationFrame(updateStickyOffset);
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

function emptyResponse() {
  const r = {};
  for (const f of SCORE_FIELDS) r[f] = null;
  r.overall_verdict = null;
  r.comment = "";
  return r;
}

function buildPayload() {
  return {
    evaluator_name: evaluatorName,
    submitted_at: new Date().toISOString(),
    app_version: "exp3-q2-sop-v2",
    n_items: ITEMS.length,
    responses: ITEMS.map((item) => ({
      comparison_id: item.comparison_id,
      ...(responses[item.comparison_id] || emptyResponse()),
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
  a.download = `exp3_q2sopv2_${safeName}_backup_${ts}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ---- Google Apps Script 傳送（與 Q4 / Q2 相同邏輯）----

function appsScriptJsonpRequest(params = {}, timeoutMs = 10000) {
  return new Promise((resolve, reject) => {
    const callbackName = `exp3q2sopEndpointPing_${Date.now()}_${Math.random()
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
  const submissionId = `exp3_q2sopv2_${Date.now()}_${Math.random().toString(36).slice(2)}`;
  const wrapped = {
    submissionId,
    fileName: `exp3_q2sopv2_${safeName}_${ts}.json`,
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

  renderStageTable();

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

  // 生育階段對照表懸浮按鈕
  const stageBtn = document.getElementById("btn-stage-table");
  const stageOverlay = document.getElementById("stage-table-overlay");
  const stageClose = document.getElementById("btn-close-stage-table");
  if (stageBtn && stageOverlay && stageClose) {
    stageBtn.addEventListener("click", () => stageOverlay.classList.add("open"));
    stageClose.addEventListener("click", () => stageOverlay.classList.remove("open"));
    stageOverlay.addEventListener("click", (e) => {
      if (e.target === stageOverlay) stageOverlay.classList.remove("open");
    });
  }

  // 照片點擊放大 Lightbox
  const itemImage = document.getElementById("item-image");
  const lightbox = document.getElementById("image-lightbox");
  const lightboxImg = document.getElementById("lightbox-img");
  if (itemImage && lightbox && lightboxImg) {
    itemImage.addEventListener("click", () => {
      lightboxImg.src = itemImage.src;
      lightbox.classList.add("open");
    });
    lightbox.addEventListener("click", () => lightbox.classList.remove("open"));
  }

  // 頂部固定列高度會隨內容（GT文字長度）變動，監聽視窗大小改變時重新量測
  window.addEventListener("resize", updateStickyOffset);

  showScreen("intro");
}

init();

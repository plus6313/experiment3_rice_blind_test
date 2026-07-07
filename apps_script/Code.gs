/**
 * 實驗3 人工盲測 — 接收 GitHub Pages 送出的評測結果，寫入指定的 Google Drive 資料夾。
 *
 * 前端（site/app.js）送出的格式是：
 *   { "fileName": "exp3_姓名_時間戳.json", "content": { ...實際評測資料... } }
 * 這裡就是把 content 原封不動寫成一個 JSON 檔，檔名用 fileName。
 *
 * 部署方式：
 * 1. 前往 https://script.google.com/ 建立新專案，把這個檔案內容整個貼進去（取代預設內容）。
 * 2. 確認下面 FOLDER_ID 是你要存放結果的 Google Drive 資料夾 ID（已預填你提供的資料夾）。
 * 3. 右上角「部署」>「新增部署作業」：
 *      類型：網頁應用程式
 *      執行身分：我（你自己的 Google 帳號）
 *      具有存取權的使用者：任何人
 * 4. 第一次部署時 Google 會跳出授權畫面（因為指令碼要用你的帳號寫入 Drive）。
 *    這是 Google 對「你自己寫的、要存取你自己 Drive」的指令碼的標準一次性授權流程，
 *    只有你（帳號擁有者）需要按過一次，不需要額外提供任何金鑰或密碼給任何人。
 *    畫面若顯示「未經驗證的應用程式」，點「進階」→「前往 (專案名稱)（不安全）」即可，
 *    這是因為指令碼還沒送去 Google 審核，但只有你自己在使用，安全無虞。
 * 5. 部署完成後複製「網頁應用程式網址」，貼到 site/app.js 最上方的 APPS_SCRIPT_URL。
 * 6. 之後若修改這份程式碼，要記得「管理部署作業」→ 編輯 → 部署新版本，網址才會套用新程式碼
 *    （只存檔 Ctrl+S 不會讓已部署的 /exec 網址套用新程式碼）。
 */

var FOLDER_ID = '1lLXDS8qw93Ol6zW4mbHFRMIfPMcorHdp';

function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);

    var rawName = (data.fileName || ('rice_annotation_' + new Date().getTime() + '.json')).toString();
    var fileName = rawName.replace(/[\\\/:*?"<>|]/g, '_');

    var folder = DriveApp.getFolderById(FOLDER_ID);
    var contentString = JSON.stringify(data.content, null, 2);
    var blob = Utilities.newBlob(contentString, 'application/json', fileName);
    folder.createFile(blob);

    return ContentService
      .createTextOutput(JSON.stringify({ status: 'success', fileName: fileName }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (error) {
    return ContentService
      .createTextOutput(JSON.stringify({ status: 'error', message: error.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

/** 部署後可直接在瀏覽器打開網頁應用程式網址，看到這個回應就代表部署成功。 */
function doGet(e) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: 'ok', message: 'exp3 endpoint is alive' }))
    .setMimeType(ContentService.MimeType.JSON);
}

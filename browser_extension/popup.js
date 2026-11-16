const baseInput = document.getElementById("baseUrl");
const codeInput = document.getElementById("pairingCode");
const status = document.getElementById("status");

function show(text, kind) {
  status.textContent = text;
  status.className = "status" + (kind ? " " + kind : "");
}

function settings() {
  return new Promise((resolve) => chrome.storage.local.get({ baseUrl: "http://127.0.0.1:5015", pairingCode: "" }, resolve));
}

async function localRequest(path, options = {}) {
  const values = await settings();
  const headers = Object.assign({}, options.headers || {}, { "X-Jarvis-Extension": values.pairingCode });
  if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const response = await fetch(values.baseUrl.replace(/\/$/, "") + path, Object.assign({}, options, { headers }));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Bridge returned ${response.status}.`);
  return data;
}

async function registerSavedConnection(showErrors = true) {
  const values = await settings();
  baseInput.value = values.baseUrl;
  codeInput.value = values.pairingCode;
  if (!values.pairingCode) {
    show("Not connected — paste the Browser pairing code once.", "bad");
    return false;
  }
  try {
    await localRequest("/extension/register", { method: "POST", body: JSON.stringify({ name: "JARVIS Local Browser Link" }) });
    chrome.runtime.sendMessage({ type: "jarvis-poll-now" }, () => {
      if (chrome.runtime.lastError) return;
      setTimeout(refreshWorkerStatus, 180);
    });
    show("Pairing accepted — waking the background research worker…", "ok");
    return true;
  } catch (error) {
    if (showErrors) show(error.message || "Saved pairing could not reach JARVIS.", "bad");
    return false;
  }
}

function refreshWorkerStatus() {
  chrome.runtime.sendMessage({ type: "jarvis-worker-status" }, (result) => {
    if (chrome.runtime.lastError || !result) return;
    if (result.connected) show("Connected — background research worker is online.", "ok");
    else if (result.paired) show("Pairing saved; background worker is reconnecting. Keep JARVIS running.", "bad");
  });
}

registerSavedConnection(true).then(() => setTimeout(refreshWorkerStatus, 350));

document.getElementById("connect").addEventListener("click", async () => {
  const baseUrl = baseInput.value.trim().replace(/\/$/, "");
  const pairingCode = codeInput.value.trim();
  if (!/^http:\/\/(?:127\.0\.0\.1|localhost):\d+$/i.test(baseUrl)) {
    show("Use the local JARVIS address, for example http://127.0.0.1:5015.", "bad");
    return;
  }
  if (pairingCode.length < 12) {
    show("Paste the browser pairing code from JARVIS Settings → Server Sharing.", "bad");
    return;
  }
  await chrome.storage.local.set({ baseUrl, pairingCode });
  await registerSavedConnection(true);
});

document.getElementById("readPage").addEventListener("click", () => {
  chrome.tabs.query({ active: true, lastFocusedWindow: true }, (tabs) => {
    if (!tabs || !tabs[0] || !tabs[0].id) { show("No active browser tab.", "bad"); return; }
    const pageUrl = String(tabs[0].url || "");
    if (/^(?:edge|chrome|about|devtools|view-source):/i.test(pageUrl) || /^https?:\/\/(?:chromewebstore\.google\.com|microsoftedge\.microsoft\.com\/addons)/i.test(pageUrl)) {
      show("JARVIS is paired. This browser-owned page blocks extensions; open a normal website to use Read this page.", "ok");
      return;
    }
    chrome.tabs.sendMessage(tabs[0].id, { type: "jarvis-command", command: { operation: "read_page" } }, (result) => {
      if (chrome.runtime.lastError) { show("JARVIS is still paired, but this page does not allow the reader. Try a normal http/https page.", "ok"); return; }
      if (!result || !result.ok) { show((result && result.message) || "Could not read this page.", "bad"); return; }
      show((result.data && result.data.title) ? `Ready: ${result.data.title}` : "Page read.", "ok");
    });
  });
});

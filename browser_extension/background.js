const DEFAULTS = {
  baseUrl: "http://127.0.0.1:5015",
  pairingCode: "",
  lastConnectedAt: 0,
  lastConnectionMessage: "Not connected."
};

let polling = false;
let pollTimer = null;
let lastRegistrationAt = 0;
const POLL_INTERVAL_MS = 1800;
const jarvisResearchTabs = new Set();

function ensurePollAlarm() {
  // MV3 workers are allowed to sleep, so setInterval alone is not a reliable
  // heartbeat. A 30-second alarm keeps the local JARVIS connection alive even
  // after the extension popup closes.
  chrome.alarms.create("jarvis-poll-backup", { periodInMinutes: 0.5 });
}

function getSettings() {
  return new Promise((resolve) => {
    chrome.storage.local.get(DEFAULTS, (settings) => resolve(settings));
  });
}

async function bridgeFetch(path, options = {}) {
  const settings = await getSettings();
  if (!settings.pairingCode) throw new Error("Paste the pairing code first.");
  const headers = Object.assign({}, options.headers || {}, {
    "X-Jarvis-Extension": settings.pairingCode
  });
  if (options.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const response = await fetch(settings.baseUrl.replace(/\/$/, "") + path, Object.assign({}, options, { headers }));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Bridge returned ${response.status}.`);
  return data;
}

async function refreshRegistration(force = false) {
  const now = Date.now();
  if (!force && now - lastRegistrationAt < 20000) return;
  await bridgeFetch("/extension/register", {
    method: "POST",
    body: JSON.stringify({ name: "JARVIS Local Browser Link" })
  });
  lastRegistrationAt = now;
  await chrome.storage.local.set({ lastConnectedAt: now, lastConnectionMessage: "Background research worker connected." });
}

function activeTab() {
  return new Promise((resolve, reject) => {
    chrome.tabs.query({ active: true, lastFocusedWindow: true }, (tabs) => {
      if (chrome.runtime.lastError || !tabs || !tabs[0] || !tabs[0].id) {
        reject(new Error("No active browser tab is available."));
        return;
      }
      resolve(tabs[0]);
    });
  });
}

function sendToTab(tabId, message) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(tabId, message, (result) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      resolve(result || { ok: false, message: "The page did not respond." });
    });
  });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function waitForTabComplete(tabId, timeoutMs = 14000) {
  return new Promise((resolve) => {
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      chrome.tabs.onUpdated.removeListener(onUpdated);
      clearTimeout(timer);
      resolve();
    };
    const onUpdated = (updatedId, changeInfo) => {
      if (updatedId === tabId && changeInfo.status === "complete") finish();
    };
    chrome.tabs.onUpdated.addListener(onUpdated);
    const timer = setTimeout(finish, timeoutMs);
    chrome.tabs.get(tabId, (current) => {
      if (!chrome.runtime.lastError && current && current.status === "complete") finish();
    });
  });
}

async function executeCommand(command) {
  if (command.operation === "close_research_tabs") {
    const ids = Array.from(jarvisResearchTabs);
    jarvisResearchTabs.clear();
    if (ids.length) {
      await new Promise((resolve) => chrome.tabs.remove(ids, () => resolve()));
    }
    return { ok: true, message: `Closed ${ids.length} JARVIS research tab${ids.length === 1 ? "" : "s"}.`, data: { closed: ids.length } };
  }
  if (command.operation === "research_model") {
    const url = "https://makerworld.com/en/search/models?keyword=" + encodeURIComponent(command.query || "3d model");
    const researchTab = await chrome.tabs.create({ url, active: !command.brain_learn || command.brain_batch_index === 0 });
    jarvisResearchTabs.add(researchTab.id);
    await waitForTabComplete(researchTab.id);
    await delay(1800);
    let result = await sendToTab(researchTab.id, { type: "jarvis-command", command: { operation: "click_best_model", query: command.query || "3d model" } });
    if (!result || !result.ok) {
      await delay(1800);
      result = await sendToTab(researchTab.id, { type: "jarvis-command", command: { operation: "click_best_model", query: command.query || "3d model" } });
    }
    return result;
  }
  if (command.operation === "research_web") {
    const url = "https://www.bing.com/search?q=" + encodeURIComponent(command.query || "");
    const researchTab = await chrome.tabs.create({ url, active: !command.brain_learn || command.brain_batch_index === 0 });
    jarvisResearchTabs.add(researchTab.id);
    await waitForTabComplete(researchTab.id);
    await delay(700);
    let result = await sendToTab(researchTab.id, { type: "jarvis-command", command: { operation: "click_best_search_result", query: command.query || "" } });
    if (!result || !result.ok) {
      await delay(900);
      result = await sendToTab(researchTab.id, { type: "jarvis-command", command: { operation: "click_best_search_result", query: command.query || "" } });
    }
    if (!result || !result.ok) return result;
    await waitForTabComplete(researchTab.id);
    await delay(650);
    const page = await sendToTab(researchTab.id, { type: "jarvis-command", command: { operation: "read_page" } });
    if (page && page.ok) {
      page.message = "Followed a search result and read the resulting page for Brain Learn Mode.";
      page.data = Object.assign({}, page.data || {}, { researchTabId: researchTab.id });
      return page;
    }
    return result;
  }
  const tab = await activeTab();
  if (command.operation === "open_url") {
    await chrome.tabs.update(tab.id, { url: command.url });
    return { ok: true, message: "Opened the requested page.", data: { url: command.url } };
  }
  return sendToTab(tab.id, { type: "jarvis-command", command });
}

async function reportResult(command, result) {
  try {
    await bridgeFetch("/extension/result", {
      method: "POST",
      body: JSON.stringify({
        command_id: command.command_id,
        ok: !!(result && result.ok),
        message: (result && result.message) || "Browser command finished.",
        data: (result && result.data) || {}
      })
    });
  } catch (error) {
    // The next poll reconnects after the local app is started again.
  }
}

async function pollOnce() {
  if (polling) return;
  polling = true;
  try {
    // The popup is only a setup/status UI.  The MV3 background worker owns
    // the actual pairing and refreshes it whenever Chrome/Edge wakes it.
    await refreshRegistration(false);
    const packet = await bridgeFetch("/extension/next", { method: "GET" });
    if (packet.command) {
      const commands = [packet.command];
      // Learn Mode intentionally opens several research tabs. Pull that batch
      // immediately and run the independent tab jobs concurrently; otherwise
      // later jobs could expire while the first page was loading.
      if (packet.command.brain_learn && packet.command.operation !== "close_research_tabs") {
        for (let i = 1; i < 10; i += 1) {
          const more = await bridgeFetch("/extension/next", { method: "GET" });
          if (!more.command) break;
          commands.push(more.command);
          if (!more.command.brain_learn || more.command.operation === "close_research_tabs") break;
        }
      }
      commands.forEach((command, index) => {
        if (command.brain_learn) command.brain_batch_index = index;
      });
      await Promise.all(commands.map(async (command) => {
        let result;
        try {
          result = await executeCommand(command);
        } catch (error) {
          result = { ok: false, message: error.message || "Browser command failed." };
        }
        await reportResult(command, result);
      }));
    }
  } catch (error) {
    await chrome.storage.local.set({ lastConnectionMessage: error && error.message ? error.message : "Background worker could not reach JARVIS." });
  } finally {
    polling = false;
  }
}

async function startPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
  ensurePollAlarm();
  const settings = await getSettings();
  if (!settings.pairingCode) return;
  lastRegistrationAt = 0;
  pollOnce();
  pollTimer = setInterval(pollOnce, POLL_INTERVAL_MS);
}

chrome.runtime.onInstalled.addListener(() => {
  ensurePollAlarm();
  startPolling();
});
chrome.runtime.onStartup.addListener(startPolling);
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "jarvis-poll-backup") {
    pollOnce();
    startPolling();
  }
});
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && (changes.baseUrl || changes.pairingCode)) startPolling();
});
chrome.tabs.onRemoved.addListener((tabId) => jarvisResearchTabs.delete(tabId));
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message && message.type === "jarvis-poll-now") {
    pollOnce().finally(() => sendResponse({ ok: true }));
    return true;
  }
  if (message && message.type === "jarvis-worker-status") {
    getSettings().then((settings) => sendResponse({
      ok: true,
      paired: !!settings.pairingCode,
      connected: !!settings.lastConnectedAt && Date.now() - Number(settings.lastConnectedAt) < 95000,
      lastConnectedAt: Number(settings.lastConnectedAt) || 0,
      message: settings.lastConnectionMessage || "Not connected."
    }));
    return true;
  }
  return false;
});

ensurePollAlarm();
startPolling();

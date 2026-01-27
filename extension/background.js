// AI Video Quiz Assistant - Background Service Worker (Manifest V3)
// Responsibilities:
// - Auth (login, refresh, logout) with token storage
// - API client with automatic token refresh
// - WebSocket connection per task_id for realtime updates
// - Message routing between content script and side panel
// - Minimal in-memory state cache (current video/task, segments, answers)

console.log("========================================");
console.log("BACKGROUND.JS LOADED");
console.log("========================================");

const DEFAULT_BACKEND_URL = "http://16.170.208.132:2135";

const state = {
  backendUrl: DEFAULT_BACKEND_URL,
  accessToken: null,
  refreshToken: null,
  user: null,
  language: "en",
  enabled: true,
  currentTaskId: null,
  currentVideoUrl: null,
  segmentsByTask: new Map(), // task_id -> segments array
  answersByQuiz: new Map(), // quiz_id -> {selected_index, is_correct, answered_at}
  ws: null,
  wsTaskId: null,
  wsReconnectTimer: null,
  wsPingTimer: null,
};

console.log("Initializing background script, state:", state);
const ready = loadStoredState();

// ---------- Storage Helpers ----------
async function loadStoredState() {
  console.log("Loading stored state from chrome.storage...");
  const stored =
    (await chrome.storage.local.get([
      "access_token",
      "refresh_token",
      "user",
      "backend_url",
      "language",
      "enabled",
      "current_task_id",
      "current_video_url",
      "segments_by_task",
    ])) || {};
  state.accessToken = stored.access_token || null;
  state.refreshToken = stored.refresh_token || null;
  state.user = stored.user || null;
  const storedBackend = stored.backend_url;
  if (storedBackend && storedBackend.includes("localhost")) {
    state.backendUrl = "http://16.170.208.132:2135";
    await chrome.storage.local.set({
      backend_url: "http://16.170.208.132:2135",
    });
  } else {
    state.backendUrl = storedBackend || DEFAULT_BACKEND_URL;
  }
  state.language = stored.language || "en";
  state.enabled = stored.enabled ?? true;
  state.currentTaskId = stored.current_task_id || null;
  state.currentVideoUrl = stored.current_video_url || null;
  const segmentsByTask = stored.segments_by_task;
  if (segmentsByTask && typeof segmentsByTask === "object") {
    Object.entries(segmentsByTask).forEach(([taskId, segs]) => {
      state.segmentsByTask.set(taskId, Array.isArray(segs) ? segs : []);
    });
  }
  console.log("Stored state loaded:", {
    user: state.user?.email,
    currentTaskId: state.currentTaskId,
    segmentsCount: state.segmentsByTask.size,
  });
}

async function persistSessionState() {
  const segmentsObject = {};
  for (const [taskId, segs] of state.segmentsByTask.entries()) {
    segmentsObject[taskId] = segs;
  }
  await chrome.storage.local.set({
    current_task_id: state.currentTaskId,
    current_video_url: state.currentVideoUrl,
    segments_by_task: segmentsObject,
  });
}

async function persistTokens(access, refresh) {
  state.accessToken = access;
  state.refreshToken = refresh;
  await chrome.storage.local.set({
    access_token: access,
    refresh_token: refresh,
  });
}

async function clearTokens() {
  state.accessToken = null;
  state.refreshToken = null;
  state.user = null;
  await chrome.storage.local.remove(["access_token", "refresh_token", "user"]);
}

// ---------- API Client ----------
async function apiFetch(path, options = {}, attemptRefresh = true) {
  const url = `${state.backendUrl}${path}`;
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");
  if (state.accessToken) {
    headers.set("Authorization", `Bearer ${state.accessToken}`);
  }
  console.info("apiFetch", { url, path, method: options.method || "GET" });
  let resp;
  try {
    resp = await fetch(url, {
      ...options,
      headers,
    });
  } catch (e) {
    console.error(
      "apiFetch network error",
      { url, path, method: options.method || "GET" },
      e,
    );
    throw e;
  }

  if (resp.status === 401 && attemptRefresh && state.refreshToken) {
    const refreshed = await refreshTokens();
    if (refreshed) {
      return apiFetch(path, options, false);
    }
  }

  if (!resp.ok) {
    const text = await safeJson(resp);
    console.error("apiFetch http error", {
      url,
      path,
      status: resp.status,
      body: text,
    });
    throw new Error(text?.detail || `HTTP ${resp.status}`);
  }

  return safeJson(resp);
}

async function safeJson(resp) {
  try {
    return await resp.json();
  } catch (_e) {
    return null;
  }
}

// ---------- Auth ----------
async function login(email, password) {
  const data = await apiFetch("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  await persistTokens(data.access_token, data.refresh_token);
  state.user = data.user || { email };
  await chrome.storage.local.set({ user: state.user });
  return data;
}

async function register(email, password) {
  const data = await apiFetch("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return data;
}

async function refreshTokens() {
  if (!state.refreshToken) return false;
  try {
    const data = await fetch(`${state.backendUrl}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: state.refreshToken }),
    });
    if (!data.ok) throw new Error("refresh failed");
    const json = await data.json();
    await persistTokens(
      json.access_token,
      json.refresh_token || state.refreshToken,
    );
    return true;
  } catch (e) {
    console.warn("Refresh failed", e);
    await clearTokens();
    return false;
  }
}

async function logout() {
  await clearTokens();
  closeWebSocket();
}

async function fetchUserProfile() {
  return apiFetch("/api/user/profile", { method: "GET" });
}

async function fetchUserStats() {
  return apiFetch("/api/user/stats", { method: "GET" });
}

// ---------- Video & Quiz API ----------
async function checkVideo(url, language) {
  return apiFetch("/api/video/check", {
    method: "POST",
    body: JSON.stringify({ url, language }),
  });
}

async function uploadVideo(url, language) {
  return apiFetch("/api/video/upload/url", {
    method: "POST",
    body: JSON.stringify({ url, language }),
  });
}

async function getSegments(taskId) {
  const res = await apiFetch(`/api/video/${taskId}/segments`);
  state.segmentsByTask.set(taskId, res.segments || []);
  await persistSessionState();
  return res;
}

async function submitAnswer(quizId, selectedIndex) {
  const res = await apiFetch(`/api/quiz/${quizId}/answer`, {
    method: "POST",
    body: JSON.stringify({ selected_index: selectedIndex }),
  });
  // cache answer
  state.answersByQuiz.set(quizId, {
    selected_index: selectedIndex,
    is_correct: res.is_correct,
    answered_at: new Date().toISOString(),
  });
  return res;
}

async function segmentStatus(segmentId) {
  return apiFetch(`/api/quiz/segment/${segmentId}/status`, { method: "GET" });
}

async function segmentReview(segmentId) {
  return apiFetch(`/api/quiz/segment/${segmentId}/review`, { method: "GET" });
}

async function segmentRetake(segmentId) {
  return apiFetch(`/api/quiz/segment/${segmentId}/retake`, {
    method: "POST",
  });
}

// ---------- WebSocket ----------
function buildWsUrl(taskId) {
  const url = new URL(
    `${state.backendUrl.replace("http", "ws")}/api/video/ws/${taskId}`,
  );
  if (state.accessToken) {
    url.searchParams.set("token", state.accessToken);
  }
  return url.toString();
}

function openWebSocket(taskId) {
  console.log("========================================");
  console.log("OPENING WEBSOCKET FOR TASK:", taskId);
  console.log("========================================");

  if (state.ws && state.wsTaskId === taskId) {
    console.log("WebSocket already connected to this task, skipping");
    return;
  }
  closeWebSocket();

  const wsUrl = buildWsUrl(taskId);
  console.log("WebSocket URL:", wsUrl);
  const ws = new WebSocket(wsUrl);
  state.ws = ws;
  state.wsTaskId = taskId;

  ws.onopen = () => {
    console.log("========================================");
    console.log("WEBSOCKET OPENED:", taskId);
    console.log("========================================");
    sendBroadcast({ channel: "ws", type: "connected", taskId });
    startWebSocketPing();
  };

  ws.onmessage = (event) => {
    console.log("========================================");
    console.log("WEBSOCKET MESSAGE RECEIVED:", taskId);
    console.log("Raw data:", event.data);
    console.log("========================================");
    let data = null;
    try {
      data = JSON.parse(event.data);
      console.log("Parsed message:", data);
    } catch (e) {
      console.error("WS parse failed", taskId, e, event.data);
      return;
    }
    try {
      handleWsEvent(taskId, data);
      console.log("WS message handled successfully");
    } catch (e) {
      console.error("WS handleWsEvent failed", taskId, e);
    }
  };

  ws.onclose = (event) => {
    console.log("========================================");
    console.log("WEBSOCKET CLOSED:", taskId);
    console.log("Code:", event.code);
    console.log("Reason:", event.reason);
    console.log("Clean:", event.wasClean);
    console.log("========================================");
    sendBroadcast({ channel: "ws", type: "disconnected", taskId });
    stopWebSocketPing();
    if (state.wsTaskId === taskId) {
      scheduleReconnect(taskId);
    }
  };

  ws.onerror = (err) => {
    console.log("========================================");
    console.error("WEBSOCKET ERROR:", taskId);
    console.error("Error:", err);
    console.error("ReadyState:", ws.readyState);
    console.log("========================================");
    // Don't close here - let onclose handle it
  };

  console.log("WebSocket handlers attached, waiting for connection...");
}

function startWebSocketPing() {
  stopWebSocketPing();
  // Send ping every 15 seconds to keep connection alive
  state.wsPingTimer = setInterval(() => {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      try {
        state.ws.send(JSON.stringify({ type: "ping" }));
        console.debug("WS ping sent");
      } catch (e) {
        console.warn("WS ping failed", e);
      }
    }
  }, 15000);
}

function stopWebSocketPing() {
  if (state.wsPingTimer) {
    clearInterval(state.wsPingTimer);
    state.wsPingTimer = null;
  }
}

function handleWsEvent(taskId, payload) {
  const { event } = payload || {};
  console.log("========================================");
  console.log("HANDLING WS EVENT:", event, "for task:", taskId);
  console.log("Payload:", payload);
  console.log("========================================");
  switch (event) {
    case "segment_ready":
      if (payload.segment) {
        const list = state.segmentsByTask.get(taskId) || [];
        list.push(payload.segment);
        state.segmentsByTask.set(taskId, list);
        persistSessionState();
      }
      break;
    case "completed":
      console.info(
        "Background: task completed, keeping WebSocket alive for final messages",
      );
      // Keep WebSocket open briefly to ensure all messages are received
      setTimeout(() => {
        if (state.wsTaskId === taskId) {
          console.info(
            "Background: closing WebSocket after completion",
            taskId,
          );
          closeWebSocket();
        }
      }, 5000); // Keep alive for 5 seconds after completion
      break;
    case "progress":
      console.log("BACKGROUND: Processing 'progress' event");
      console.log("Progress details:", {
        progress: payload.progress,
        current_stage: payload.current_stage,
        status: payload.status,
        message: payload.message,
      });
      break;
    case "error":
      console.error("BACKGROUND: Processing 'error' event");
      console.error("Error details:", payload);
      break;
    default:
      console.log("BACKGROUND: Unknown event type:", event);
      break;
  }

  console.log("BACKGROUND: About to sendBroadcast for event:", event);
  sendBroadcast({ channel: "ws", taskId, payload });
  console.log("BACKGROUND: sendBroadcast call completed for event:", event);
}

async function scheduleReconnect(taskId) {
  if (state.wsReconnectTimer) return;
  state.wsReconnectTimer = setTimeout(async () => {
    state.wsReconnectTimer = null;

    // Check if task is still processing before reconnecting
    try {
      const statusRes = await apiFetch(`/api/video/${taskId}/status`, {
        method: "GET",
      });
      const status = statusRes?.status || statusRes?.task_status;

      if (status === "processing" || status === "pending") {
        console.info("Reconnecting WebSocket for task:", taskId);
        openWebSocket(taskId);
      } else {
        console.info(
          "Task no longer processing, skipping reconnection:",
          taskId,
          "status:",
          status,
        );
      }
    } catch (e) {
      console.error("Failed to check task status before reconnect:", e);
      // Reconnect anyway in case of error
      openWebSocket(taskId);
    }
  }, 2000);
}

function closeWebSocket() {
  if (state.ws) {
    state.ws.close();
  }
  state.ws = null;
  state.wsTaskId = null;
  stopWebSocketPing();
  if (state.wsReconnectTimer) {
    clearTimeout(state.wsReconnectTimer);
    state.wsReconnectTimer = null;
  }
}

// ---------- Messaging ----------
function sendBroadcast(message) {
  console.log("========================================");
  console.log("BACKGROUND sendBroadcast called");
  console.log("Message to broadcast:", message);
  console.log("Message channel:", message?.channel);
  console.log("Message type:", message?.type);
  console.log("Message payload:", message?.payload);
  console.log("========================================");

  try {
    chrome.runtime.sendMessage(message, (response) => {
      // Ignore missing listeners or closed ports
      const err = chrome.runtime.lastError;
      if (err) {
        console.warn(
          "BACKGROUND sendBroadcast: chrome.runtime.lastError:",
          err.message,
        );
        return;
      }
      console.log("BACKGROUND sendBroadcast: message delivered successfully");
      if (response) {
        console.log("BACKGROUND sendBroadcast: response:", response);
      }
    });
  } catch (e) {
    console.error("BACKGROUND sendBroadcast: exception thrown:", e.message);
    console.error("BACKGROUND sendBroadcast: stack:", e.stack);
  }
}

function sendToYoutubeTabs(message) {
  try {
    chrome.tabs.query(
      { url: ["*://*.youtube.com/*", "*://youtube.com/*"] },
      (tabs) => {
        const err = chrome.runtime.lastError;
        if (err) {
          return;
        }
        (tabs || []).forEach((tab) => {
          if (!tab || typeof tab.id !== "number") return;
          chrome.tabs.sendMessage(tab.id, message, () => {
            const sendErr = chrome.runtime.lastError;
            if (sendErr) {
              return;
            }
          });
        });
      },
    );
  } catch (_e) {
    // Ignore: tab messaging may fail if permissions/tabs are unavailable
  }
}

chrome.runtime.onMessage.addListener((request, _sender, sendResponse) => {
  console.log("========================================");
  console.log("MESSAGE RECEIVED:", request?.type);
  console.log("Payload:", request?.payload);
  console.log("========================================");
  const handlerMap = {
    "config:get": async () => ({
      backendUrl: state.backendUrl,
      language: state.language,
      enabled: state.enabled,
      user: state.user,
      accessToken: state.accessToken ? true : false,
      currentTaskId: state.currentTaskId,
      currentVideoUrl: state.currentVideoUrl,
      segments:
        state.currentTaskId && state.segmentsByTask.has(state.currentTaskId)
          ? state.segmentsByTask.get(state.currentTaskId)
          : [],
    }),
    "config:set": async (payload) => {
      if (payload.backendUrl) {
        state.backendUrl = payload.backendUrl;
        await chrome.storage.local.set({
          backend_url: payload.backendUrl,
        });
      }
      if (payload.language) {
        state.language = payload.language;
        await chrome.storage.local.set({ language: payload.language });
      }
      if (typeof payload.enabled === "boolean") {
        state.enabled = payload.enabled;
        await chrome.storage.local.set({ enabled: payload.enabled });
      }
      return { ok: true };
    },
    "auth:login": async ({ email, password }) => login(email, password),
    "auth:register": async ({ email, password }) => register(email, password),
    "auth:logout": async () => {
      await logout();
      return { ok: true };
    },
    "video:check": async ({ url, language }) => {
      const res = await checkVideo(url, language || state.language);
      if (res?.task_id) {
        state.currentTaskId = res.task_id;
        state.currentVideoUrl = url;
        await persistSessionState();

        // Only open WebSocket if not already connected or if it's a different task
        if (
          !state.ws ||
          state.wsTaskId !== res.task_id ||
          state.ws.readyState !== WebSocket.OPEN
        ) {
          console.info("Opening WebSocket for checked video:", res.task_id);
          openWebSocket(res.task_id);
        } else {
          console.info("WebSocket already connected to task:", res.task_id);
        }

        sendBroadcast({
          channel: "video",
          type: "current",
          taskId: res.task_id,
          url,
        });
      }
      return res;
    },
    "video:upload": async ({ url, language }) => {
      const res = await uploadVideo(url, language || state.language);
      if (res.task_id) {
        state.currentTaskId = res.task_id;
        state.currentVideoUrl = url;
        await persistSessionState();

        // Only open WebSocket if not already connected or if it's a different task
        if (
          !state.ws ||
          state.wsTaskId !== res.task_id ||
          state.ws.readyState !== WebSocket.OPEN
        ) {
          console.info("Opening WebSocket for uploaded video:", res.task_id);
          openWebSocket(res.task_id);
        } else {
          console.info("WebSocket already connected to task:", res.task_id);
        }

        sendBroadcast({
          channel: "video",
          type: "current",
          taskId: res.task_id,
          url,
        });
      }
      return res;
    },
    "video:segments": async ({ taskId }) => getSegments(taskId),
    "video:status": async ({ taskId }) => {
      return apiFetch(`/api/video/${taskId}/status`, { method: "GET" });
    },
    "quiz:answer": async ({ quizId, selectedIndex }) =>
      submitAnswer(quizId, selectedIndex),
    "quiz:status": async ({ segmentId }) => segmentStatus(segmentId),
    "quiz:review": async ({ segmentId }) => segmentReview(segmentId),
    "quiz:retake": async ({ segmentId }) => segmentRetake(segmentId),
    "user:profile": async () => fetchUserProfile(),
    "user:stats": async () => fetchUserStats(),
    "ws:connect": async ({ taskId }) => {
      console.info("ws:connect handler called for taskId:", taskId);
      // Check if already connected to this task
      if (
        state.ws &&
        state.wsTaskId === taskId &&
        state.ws.readyState === WebSocket.OPEN
      ) {
        console.info("WebSocket already connected to task:", taskId);
        return { ok: true, already_connected: true };
      }
      openWebSocket(taskId);
      return { ok: true };
    },
    "ws:disconnect": async () => {
      closeWebSocket();
      return { ok: true };
    },
    "video:seek": async ({ start_time }) => {
      const message = { type: "video:seek", payload: { start_time } };
      sendBroadcast(message);
      sendToYoutubeTabs(message);
      return { ok: true };
    },
  };

  const run = async () => {
    await ready;
    if (!handlerMap[request?.type]) {
      sendResponse({ error: "Unknown request type" });
      return;
    }
    const result = await handlerMap[request.type](request.payload || {});
    sendResponse({ ok: true, data: result });
  };

  run().catch((err) => {
    console.error("Handler error", request?.type, err);
    sendResponse({ ok: false, error: err?.message || "Unknown error" });
  });

  return true; // keep channel open for async response
});

// ---------- Startup ----------
chrome.runtime.onInstalled.addListener(async () => {
  await chrome.storage.local.set({
    backend_url: state.backendUrl,
    language: state.language,
    enabled: state.enabled,
  });
});

// Auto-reconnect WebSocket on startup if there's an active processing task
async function autoReconnectOnStartup() {
  await ready;

  if (!state.currentTaskId) {
    console.info("No active task on startup");
    return;
  }

  console.info("Checking task status on startup:", state.currentTaskId);

  try {
    // Check if task is still processing
    const statusRes = await apiFetch(
      `/api/video/${state.currentTaskId}/status`,
      { method: "GET" },
    );

    if (!statusRes) {
      console.warn("Failed to fetch task status on startup");
      return;
    }

    const status = statusRes.status || statusRes.task_status;
    console.info("Task status on startup:", status);

    if (status === "processing" || status === "pending") {
      console.info(
        "Reconnecting WebSocket for active task:",
        state.currentTaskId,
      );
      openWebSocket(state.currentTaskId);
    } else {
      console.info("Task is not processing, no reconnection needed");
    }
  } catch (e) {
    console.error("Failed to check task status on startup:", e);
  }
}

console.log("========================================");
console.log("STARTING BACKGROUND SCRIPT INITIALIZATION");
console.log("========================================");
loadStoredState().then(() => {
  console.log("State loaded, checking for auto-reconnect...");
  autoReconnectOnStartup();
});
console.log("========================================");
console.log("BACKGROUND SCRIPT READY");
console.log("========================================");

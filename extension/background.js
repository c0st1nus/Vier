// AI Video Quiz Assistant - Background Service Worker (Manifest V3)
// Responsibilities:
// - Auth (login, refresh, logout) with token storage
// - API client with automatic token refresh
// - WebSocket connection per task_id for realtime updates
// - Message routing between content script and side panel
// - Minimal in-memory state cache (current video/task, segments, answers)

const DEFAULT_BACKEND_URL = "http://localhost:8000";

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
};

const ready = loadStoredState();

// ---------- Storage Helpers ----------
async function loadStoredState() {
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
    state.backendUrl = "http://localhost:8000";
    await chrome.storage.local.set({ backend_url: "http://localhost:8000" });
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
  return apiFetch(`/api/quiz/segment/${segmentId}/retake`, { method: "POST" });
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
  if (state.ws && state.wsTaskId === taskId) return;
  closeWebSocket();

  const wsUrl = buildWsUrl(taskId);
  const ws = new WebSocket(wsUrl);
  state.ws = ws;
  state.wsTaskId = taskId;

  ws.onopen = () => {
    console.info("WS connected", taskId);
    sendBroadcast({ channel: "ws", type: "connected", taskId });
  };

  ws.onmessage = (event) => {
    let data = null;
    try {
      data = JSON.parse(event.data);
    } catch (e) {
      console.warn("WS parse failed", e);
      return;
    }
    handleWsEvent(taskId, data);
  };

  ws.onclose = () => {
    console.info("WS closed", taskId);
    sendBroadcast({ channel: "ws", type: "disconnected", taskId });
    if (state.wsTaskId === taskId) {
      scheduleReconnect(taskId);
    }
  };

  ws.onerror = (err) => {
    console.error("WS error", err);
    ws.close();
  };
}

function handleWsEvent(taskId, payload) {
  const { event } = payload || {};
  switch (event) {
    case "segment_ready":
      if (payload.segment) {
        const list = state.segmentsByTask.get(taskId) || [];
        list.push(payload.segment);
        state.segmentsByTask.set(taskId, list);
        persistSessionState();
      }
      break;
    case "progress":
    case "completed":
    case "error":
    default:
      break;
  }
  sendBroadcast({ channel: "ws", taskId, payload });
}

function scheduleReconnect(taskId) {
  if (state.wsReconnectTimer) return;
  state.wsReconnectTimer = setTimeout(() => {
    state.wsReconnectTimer = null;
    openWebSocket(taskId);
  }, 2000);
}

function closeWebSocket() {
  if (state.ws) {
    state.ws.close();
  }
  state.ws = null;
  state.wsTaskId = null;
  if (state.wsReconnectTimer) {
    clearTimeout(state.wsReconnectTimer);
    state.wsReconnectTimer = null;
  }
}

// ---------- Messaging ----------
function sendBroadcast(message) {
  try {
    chrome.runtime.sendMessage(message, () => {
      // Ignore missing listeners or closed ports
      const err = chrome.runtime.lastError;
      if (err) {
        return;
      }
    });
  } catch (_e) {
    // Ignore: sendMessage can throw in MV2 if no listeners
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
  console.info("runtime.onMessage", request?.type, request?.payload);
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
        await chrome.storage.local.set({ backend_url: payload.backendUrl });
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
        openWebSocket(res.task_id);
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
        openWebSocket(res.task_id);
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
    "quiz:answer": async ({ quizId, selectedIndex }) =>
      submitAnswer(quizId, selectedIndex),
    "quiz:status": async ({ segmentId }) => segmentStatus(segmentId),
    "quiz:review": async ({ segmentId }) => segmentReview(segmentId),
    "quiz:retake": async ({ segmentId }) => segmentRetake(segmentId),
    "user:profile": async () => fetchUserProfile(),
    "user:stats": async () => fetchUserStats(),
    "ws:connect": async ({ taskId }) => {
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

loadStoredState();

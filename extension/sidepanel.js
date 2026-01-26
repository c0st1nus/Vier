/* AI Video Quiz Assistant - Side Panel Script
 * Wires UI to background service worker: auth, settings, status, segments list.
 */

(() => {
  const qs = (id) => document.getElementById(id);
  const authSection = qs("auth-section");
  const userSection = qs("user-section");
  const settingsSection = qs("settings-section");
  const debugSection = qs("debug-section");
  const segmentsSection = qs("segments-section");
  const activitySection = qs("activity-section");
  const emailInput = qs("auth-email");
  const passwordInput = qs("auth-password");
  const loginBtn = qs("btn-login");
  const registerBtn = qs("btn-register");
  const logoutBtn = qs("btn-logout");
  const authStatus = qs("auth-status");

  const languageSelect = qs("language-select");
  const toggleEnabled = qs("toggle-enabled");
  const backendInput = qs("backend-url");
  const saveSettingsBtn = qs("btn-save-settings");

  const videoTitleEl = qs("video-title");
  const progressBar = qs("progress-bar");
  const statusBadge = qs("status-badge");
  const stageLabel = qs("stage-label");
  const debugStatusEl = qs("debug-status");
  const debugStageEl = qs("debug-stage");

  const segmentList = qs("segment-list");
  const activityList = qs("activity-list");

  const statVideos = qs("stat-videos");
  const statAnswered = qs("stat-answered");
  const statCorrect = qs("stat-correct");
  const statAccuracy = qs("stat-accuracy");

  let state = {
    backendUrl: "http://localhost:8000",
    language: "en",
    enabled: true,
    user: null,
    currentTaskId: null,
    segments: [],
  };

  // ---------- Messaging helpers ----------
  function sendMessage(type, payload = {}) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type, payload }, (response) => {
        const err = chrome.runtime.lastError;
        if (err) {
          console.error("sidepanel sendMessage error", type, err);
          resolve(null);
          return;
        }
        resolve(response);
      });
    });
  }

  // ---------- UI helpers ----------
  function setText(el, text) {
    if (el) el.textContent = text;
  }

  function setProgress(value) {
    if (progressBar) {
      const clamped = Math.max(0, Math.min(100, value || 0));
      progressBar.style.width = `${clamped}%`;
    }
  }

  function showAuth(loggedIn) {
    if (authSection) authSection.hidden = !!loggedIn;
    if (userSection) userSection.hidden = !loggedIn;

    const hidden = !loggedIn;
    if (settingsSection) settingsSection.hidden = hidden;
    if (debugSection) debugSection.hidden = hidden;
    if (segmentsSection) segmentsSection.hidden = hidden;
    if (activitySection) activitySection.hidden = hidden;
  }

  function renderSegments() {
    if (!segmentList) return;
    segmentList.innerHTML = "";

    if (!state.user) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "Please sign in to process the video and view segments.";
      segmentList.appendChild(li);
      return;
    }

    if (!state.segments.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent =
        "No segments yet. They will appear as processing completes.";
      segmentList.appendChild(li);
      return;
    }

    state.segments.forEach((seg) => {
      const li = document.createElement("li");
      li.className = "seg-item";
      const title =
        seg.topic_title ||
        seg.topic ||
        seg.title ||
        (seg.segment_id ? `Segment ${seg.segment_id}` : "Segment");
      const status = seg.quizzes?.length
        ? `${seg.quizzes.length} quizzes`
        : "No quizzes";
      li.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <div>
            <div style="font-weight:600;">${title}</div>
            <div class="muted">${fmtTime(seg.start_time)} - ${fmtTime(seg.end_time)}</div>
          </div>
          <span class="badge">${status}</span>
        </div>
      `;
      li.addEventListener("click", () => {
        if (typeof seg.start_time === "number") {
          sendMessage("video:seek", {
            start_time: Math.max(0, seg.start_time),
          });
        }
      });
      segmentList.appendChild(li);
    });
  }

  function renderActivity(message) {
    if (!activityList) return;
    const entry = document.createElement("div");
    entry.className = "pill";
    entry.textContent = message;
    activityList.prepend(entry);
    while (activityList.children.length > 5) {
      activityList.lastChild.remove();
    }
  }

  function fmtTime(seconds) {
    const s = Math.floor(seconds || 0);
    const m = Math.floor(s / 60);
    const ss = String(s % 60).padStart(2, "0");
    return `${m}:${ss}`;
  }

  function setDebug(progress, stage, status) {
    if (typeof progress === "number") setProgress(progress);
    if (debugStatusEl && status) setText(debugStatusEl, status);
    if (debugStageEl)
      setText(debugStageEl, stage || debugStageEl.textContent || "Waiting…");
  }

  function updateUserStats(stats) {
    const videos = stats?.total_videos_watched ?? stats?.videos_watched ?? 0;
    const answered =
      stats?.total_questions_answered ?? stats?.total_answered ?? 0;
    const correct = stats?.total_correct_answers ?? stats?.total_correct ?? 0;
    const accuracy = Number(stats?.accuracy ?? 0).toFixed(1);

    setText(statVideos, `Videos: ${videos}`);
    setText(statAnswered, `Answered: ${answered}`);
    setText(statCorrect, `Correct: ${correct}`);
    setText(statAccuracy, `Accuracy: ${accuracy}%`);
  }

  // ---------- Event handlers ----------
  async function handleLogin() {
    const email = emailInput?.value?.trim();
    const password = passwordInput?.value;
    if (!email || !password) {
      setText(authStatus, "Email and password required");
      return;
    }
    setText(authStatus, "Signing in…");
    loginBtn.disabled = true;
    registerBtn.disabled = true;
    try {
      const res = await sendMessage("auth:login", { email, password });
      console.info("sidepanel login result", res);
      if (res?.ok) {
        state.user = res.data?.user || { email };
        applyUser();
        setText(authStatus, "Signed in");
        renderActivity("Signed in");
      } else {
        console.error("sidepanel login error", res);
        setText(authStatus, res?.error || "Login failed");
      }
    } catch (err) {
      console.error("sidepanel login exception", err);
      setText(authStatus, "Login failed");
    } finally {
      loginBtn.disabled = false;
      registerBtn.disabled = false;
    }
  }

  async function handleRegister() {
    const email = emailInput?.value?.trim();
    const password = passwordInput?.value;
    if (!email || !password) {
      setText(authStatus, "Email and password required");
      return;
    }
    setText(authStatus, "Registering…");
    loginBtn.disabled = true;
    registerBtn.disabled = true;
    try {
      const res = await sendMessage("auth:register", { email, password });
      console.info("sidepanel register result", res);
      if (res?.ok) {
        setText(authStatus, "Registered. Please log in.");
        renderActivity("Registered successfully");
      } else {
        console.error("sidepanel register error", res);
        setText(authStatus, res?.error || "Register failed");
      }
    } catch (err) {
      console.error("sidepanel register exception", err);
      setText(authStatus, "Register failed");
    } finally {
      loginBtn.disabled = false;
      registerBtn.disabled = false;
    }
  }

  async function handleLogout() {
    await sendMessage("auth:logout");
    state.user = null;
    applyUser();
  }

  async function handleSaveSettings() {
    const payload = {
      backendUrl: backendInput?.value?.trim() || state.backendUrl,
      language: languageSelect?.value || state.language,
      enabled: !!toggleEnabled?.checked,
    };
    saveSettingsBtn.disabled = true;
    const res = await sendMessage("config:set", payload);
    if (res?.ok) {
      state.backendUrl = payload.backendUrl;
      state.language = payload.language;
      state.enabled = payload.enabled;
      renderActivity("Settings saved");
    } else {
      renderActivity(res?.error || "Failed to save settings");
    }
    saveSettingsBtn.disabled = false;
  }

  // ---------- WS updates ----------
  function setStatusProcessing(msg) {
    setText(statusBadge, "processing");
    setText(stageLabel, msg || "Processing…");
    setDebug(undefined, msg || "Processing…", "processing");
  }

  function setStatusCompleted(msg) {
    setText(statusBadge, "completed");
    setProgress(100);
    setText(stageLabel, msg || "Completed");
    setDebug(100, msg || "Completed", "completed");
  }

  function handleWsMessage(message) {
    const { payload, taskId } = message || {};
    if (!payload) return;

    if (!state.currentTaskId && taskId) state.currentTaskId = taskId;

    switch (payload.event) {
      case "connected":
        renderActivity(`WebSocket connected (${taskId})`);
        setStatusProcessing("Processing…");
        setDebug(undefined, "Connected", "connected");
        break;
      case "segment_ready":
        if (payload.segment) {
          state.segments.push(payload.segment);
          renderSegments();
          renderActivity(`Segment #${payload.segment.segment_id} ready`);
          setStatusProcessing("Segments updating…");
          setDebug(undefined, "Segments updating…", "processing");
        }
        break;
      case "progress":
        setStatusProcessing(payload.current_stage || "Processing…");
        setDebug(
          payload.progress ?? 0,
          payload.current_stage || "Processing…",
          payload.status || "processing",
        );
        break;
      case "completed":
        setStatusCompleted("Completed");
        setDebug(100, "Completed", "completed");
        renderActivity("Processing completed");
        break;
      case "error":
        setText(statusBadge, "error");
        setText(stageLabel, payload.message || "Error");
        setDebug(0, payload.message || "Error", "error");
        renderActivity("Processing error");
        break;
      default:
        break;
    }
  }

  // ---------- Apply state ----------
  function applyConfig(cfg) {
    if (!cfg) return;
    state.backendUrl = cfg.backendUrl || state.backendUrl;
    state.language = cfg.language || state.language;
    state.enabled = cfg.enabled ?? state.enabled;
    state.user = cfg.user || null;
    state.currentTaskId = cfg.currentTaskId || state.currentTaskId;
    state.currentVideoUrl = cfg.currentVideoUrl || state.currentVideoUrl;
    state.segments = cfg.segments || state.segments;

    if (backendInput) backendInput.value = state.backendUrl;
    if (languageSelect) languageSelect.value = state.language;
    if (toggleEnabled) toggleEnabled.checked = !!state.enabled;

    applyUser();
    setCurrentVideo();
    renderSegments();
    updateChart();
  }

  function setCurrentVideo() {
    if (!videoTitleEl) return;
    const title = state.currentVideoUrl || "No video detected";
    const trimmed = title.length > 64 ? `${title.slice(0, 61)}...` : title;
    setText(videoTitleEl, trimmed);
  }

  async function refreshUserData() {
    try {
      const statsRes = await sendMessage("user:stats");
      const stats = statsRes?.data || statsRes;
      updateUserStats(stats);
      updateChart(stats);
      setText(authStatus, "");
    } catch (e) {
      console.warn("stats fetch failed", e);
    }
  }

  function applyUser() {
    const loggedIn = !!state.user;
    showAuth(loggedIn);
    if (state.user && qs("user-email")) {
      setText(qs("user-email"), state.user.email || "Signed in");
      refreshUserData();
    } else {
      // reset chart when logged out
      updateChart({
        total_videos_watched: 0,
        total_correct_answers: 0,
        total_questions_answered: 0,
      });
    }
  }

  // ---------- Init ----------
  function attachListeners() {
    loginBtn?.addEventListener("click", handleLogin);
    registerBtn?.addEventListener("click", handleRegister);
    logoutBtn?.addEventListener("click", handleLogout);
    saveSettingsBtn?.addEventListener("click", handleSaveSettings);

    // collapse settings by default
    const settingsDetails = document.getElementById("settings-section");
    if (settingsDetails) settingsDetails.open = false;
  }

  async function bootstrap() {
    attachListeners();
    setText(authStatus, "Loading…");
    const cfg = await sendMessage("config:get");
    applyConfig(cfg?.data || cfg);

    if (!state.user) {
      setText(authStatus, "Please sign in");
      setText(statusBadge, "login required");
      setText(stageLabel, "Sign in to start");
      setDebug(0, "Sign in to start", "login required");
      renderSegments();
      return;
    }

    if (state.currentTaskId) {
      setStatusProcessing("Processing…");
    }

    if (state.currentTaskId && (!state.segments || !state.segments.length)) {
      const segRes = await sendMessage("video:segments", {
        taskId: state.currentTaskId,
      });
      if (segRes?.data?.segments) {
        state.segments = segRes.data.segments;
        renderSegments();
        if (state.segments.length) {
          setStatusCompleted("Loaded");
          setDebug(100, "Loaded", "completed");
        } else {
          setStatusProcessing("Processing…");
        }
      } else {
        setStatusProcessing("Processing…");
      }
    }
    setText(authStatus, "Ready");
    if (state.currentTaskId && state.segments?.length) {
      setStatusCompleted("Loaded");
      setDebug(100, "Loaded", "completed");
    }

    chrome.runtime.onMessage.addListener((req) => {
      if (req?.channel === "ws") {
        handleWsMessage(req);
      }
      if (req?.channel === "video" && req?.type === "current") {
        state.currentTaskId = req.taskId || state.currentTaskId;
        state.currentVideoUrl = req.url || state.currentVideoUrl;
        setCurrentVideo();
        setStatusProcessing("Processing…");
      }
    });
  }

  bootstrap();
})();

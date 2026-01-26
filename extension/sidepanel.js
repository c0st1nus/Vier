/* AI Video Quiz Assistant - Side Panel Script
 * Wires UI to background service worker: auth, settings, status, segments list.
 */

(() => {
  console.log("========================================");
  console.log("SIDEPANEL SCRIPT LOADING");
  console.log("========================================");

  const qs = (id) => {
    const el = document.getElementById(id);
    console.log(`DOM element '${id}':`, el ? "FOUND" : "NOT FOUND");
    return el;
  };

  console.log("Querying DOM elements...");
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

  console.log("========================================");
  console.log("DOM ELEMENTS INITIALIZATION SUMMARY:");
  console.log("Critical elements for status updates:");
  console.log("  statusBadge:", statusBadge ? "✓" : "✗");
  console.log("  stageLabel:", stageLabel ? "✓" : "✗");
  console.log("  progressBar:", progressBar ? "✓" : "✗");
  console.log("  debugStatusEl:", debugStatusEl ? "✓" : "✗");
  console.log("  debugStageEl:", debugStageEl ? "✓" : "✗");
  console.log("========================================");

  let state = {
    backendUrl: "http://16.171.11.38:2135",
    language: "en",
    enabled: true,
    user: null,
    currentTaskId: null,
    segments: [],
    statusPollInterval: null,
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
    console.log("SIDEPANEL setText called:", {
      element: el,
      text: text,
      tagName: el?.tagName,
      id: el?.id,
    });
    if (el) {
      el.textContent = text;
      console.log(
        "SIDEPANEL setText completed, new textContent:",
        el.textContent,
      );
    } else {
      console.warn("SIDEPANEL setText: element is null/undefined");
    }
  }

  function setProgress(value) {
    console.log("SIDEPANEL setProgress called with:", value);
    console.log("progressBar element:", progressBar);
    if (progressBar) {
      const clamped = Math.max(0, Math.min(100, value || 0));
      progressBar.style.width = `${clamped}%`;
      console.log(
        "SIDEPANEL setProgress completed, new width:",
        progressBar.style.width,
      );
    } else {
      console.warn(
        "SIDEPANEL setProgress: progressBar element is null/undefined",
      );
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
    console.log("SIDEPANEL setDebug called with:", {
      progress,
      stage,
      status,
    });
    console.log("Elements:", {
      progressBar: progressBar,
      debugStatusEl: debugStatusEl,
      debugStageEl: debugStageEl,
    });

    if (typeof progress === "number") {
      console.log("SIDEPANEL setDebug: setting progress to", progress);
      setProgress(progress);
    }
    if (debugStatusEl && status) {
      console.log("SIDEPANEL setDebug: setting debugStatusEl to", status);
      setText(debugStatusEl, status);
    }
    if (debugStageEl) {
      const stageText = stage || debugStageEl.textContent || "Waiting…";
      console.log("SIDEPANEL setDebug: setting debugStageEl to", stageText);
      setText(debugStageEl, stageText);
    }

    console.log("SIDEPANEL setDebug completed");
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
    console.log("SIDEPANEL setStatusProcessing called with:", msg);
    console.log("statusBadge element:", statusBadge);
    console.log("stageLabel element:", stageLabel);

    setText(statusBadge, "processing");
    setText(stageLabel, msg || "Processing…");
    setDebug(undefined, msg || "Processing…", "processing");
    startStatusPolling();

    console.log("SIDEPANEL setStatusProcessing completed");
    console.log("statusBadge text:", statusBadge?.textContent);
    console.log("stageLabel text:", stageLabel?.textContent);
  }

  function setStatusCompleted(msg) {
    setText(statusBadge, "completed");
    setProgress(100);
    setText(stageLabel, msg || "Completed");
    setDebug(100, msg || "Completed", "completed");
    stopStatusPolling();
  }

  function startStatusPolling() {
    if (state.statusPollInterval) return;
    console.info("Starting status polling");
    state.statusPollInterval = setInterval(async () => {
      if (!state.currentTaskId) {
        stopStatusPolling();
        return;
      }
      try {
        const statusRes = await sendMessage("video:status", {
          taskId: state.currentTaskId,
        });
        if (statusRes?.data) {
          const status = statusRes.data.status || statusRes.data.task_status;
          const progress = statusRes.data.progress ?? 0;
          const stage = statusRes.data.current_stage || "Processing…";

          console.debug("Status poll:", status, progress, stage);

          if (status === "completed") {
            setStatusCompleted(stage);
            // Load segments if we don't have them
            if (!state.segments || !state.segments.length) {
              const segRes = await sendMessage("video:segments", {
                taskId: state.currentTaskId,
              });
              if (segRes?.data?.segments) {
                state.segments = segRes.data.segments;
                renderSegments();
              }
            }
          } else if (status === "failed") {
            setText(statusBadge, "error");
            setText(stageLabel, statusRes.data.error_message || "Error");
            setDebug(0, statusRes.data.error_message || "Error", "error");
            stopStatusPolling();
          } else if (status === "processing" || status === "pending") {
            setDebug(progress, stage, "processing");
          }
        }
      } catch (e) {
        console.error("Status poll failed:", e);
      }
    }, 5000);
  }

  function stopStatusPolling() {
    if (state.statusPollInterval) {
      console.info("Stopping status polling");
      clearInterval(state.statusPollInterval);
      state.statusPollInterval = null;
    }
  }

  function handleWsMessage(message) {
    console.log("========================================");
    console.log("SIDEPANEL handleWsMessage received");
    console.log("Message:", message);
    console.log("========================================");

    const { payload, taskId } = message || {};
    if (!payload) {
      console.warn("sidepanel handleWsMessage: no payload", message);
      return;
    }

    if (!state.currentTaskId && taskId) state.currentTaskId = taskId;

    console.log("========================================");
    console.log("SIDEPANEL handling WS event:", payload.event);
    console.log("TaskId:", taskId);
    console.log("Full payload:", payload);
    console.log("========================================");

    try {
      switch (payload.event) {
        case "connected":
          console.log("SIDEPANEL: Processing 'connected' event");
          renderActivity(`WebSocket connected (${taskId})`);
          setStatusProcessing("Processing…");
          setDebug(undefined, "Connected", "connected");
          stopStatusPolling(); // Stop polling when WebSocket connects
          break;
        case "segment_ready":
          console.log("SIDEPANEL: Processing 'segment_ready' event");
          if (payload.segment) {
            state.segments.push(payload.segment);
            renderSegments();
            renderActivity(`Segment #${payload.segment.segment_id} ready`);
            setStatusProcessing("Segments updating…");
            setDebug(undefined, "Segments updating…", "processing");
          }
          break;
        case "progress":
          console.log("========================================");
          console.log("SIDEPANEL: Processing 'progress' event");
          console.log("Progress value:", payload.progress);
          console.log("Current stage:", payload.current_stage);
          console.log("Status:", payload.status);
          console.log("Message:", payload.message);
          console.log("========================================");

          const progressStage = payload.current_stage || "Processing…";
          const progressValue = payload.progress ?? 0;
          const progressStatus = payload.status || "processing";

          console.log(
            "SIDEPANEL: Calling setStatusProcessing with:",
            progressStage,
          );
          setStatusProcessing(progressStage);

          console.log("SIDEPANEL: Calling setDebug with:", {
            progress: progressValue,
            stage: progressStage,
            status: progressStatus,
          });
          setDebug(progressValue, progressStage, progressStatus);

          console.log("SIDEPANEL: Progress UI update completed");
          console.log("Current status badge text:", statusBadge?.textContent);
          console.log("Current stage label text:", stageLabel?.textContent);
          console.log("Current progress bar width:", progressBar?.style.width);
          console.log("Current debug status text:", debugStatusEl?.textContent);
          console.log("Current debug stage text:", debugStageEl?.textContent);
          console.log("========================================");
          break;
        case "completed":
          console.log("========================================");
          console.log("SIDEPANEL: received COMPLETED event");
          console.log("========================================");
          setStatusCompleted("Completed");
          setDebug(100, "Completed", "completed");
          renderActivity("Processing completed");
          break;
        case "error":
          console.log("SIDEPANEL: Processing 'error' event");
          setText(statusBadge, "error");
          setText(stageLabel, payload.message || "Error");
          setDebug(0, payload.message || "Error", "error");
          renderActivity("Processing error");
          stopStatusPolling();
          break;
        case "disconnected":
          console.warn(
            "WebSocket disconnected, starting status polling as fallback",
          );
          renderActivity("WebSocket disconnected - using polling");
          startStatusPolling();
          break;
        default:
          console.warn("sidepanel: unknown WS event", payload.event, payload);
          break;
      }
    } catch (e) {
      console.error("========================================");
      console.error("SIDEPANEL handleWsMessage ERROR:", e);
      console.error("Message:", message);
      console.error("Stack:", e.stack);
      console.error("========================================");
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
    console.log("========================================");
    console.log("SIDEPANEL BOOTSTRAP STARTING");
    console.log("========================================");

    attachListeners();
    setText(authStatus, "Loading…");

    console.log("Requesting config from background...");
    const cfg = await sendMessage("config:get");
    console.log("Config received:", cfg);
    applyConfig(cfg?.data || cfg);

    if (!state.user) {
      console.log("No user logged in");
      setText(authStatus, "Please sign in");
      setText(statusBadge, "login required");
      setText(stageLabel, "Sign in to start");
      setDebug(0, "Sign in to start", "login required");
      renderSegments();
      return;
    }

    console.log("User logged in:", state.user.email);
    console.log("Current task ID:", state.currentTaskId);

    if (state.currentTaskId) {
      console.log("Checking task status for:", state.currentTaskId);
      // Check task status first
      const statusRes = await sendMessage("video:status", {
        taskId: state.currentTaskId,
      });
      console.log("Task status response:", statusRes);

      if (statusRes?.data) {
        const status = statusRes.data.status || statusRes.data.task_status;
        const progress = statusRes.data.progress ?? 0;
        const stage = statusRes.data.current_stage || "Processing…";

        console.log(
          "Task status:",
          status,
          "progress:",
          progress,
          "stage:",
          stage,
        );

        if (status === "completed") {
          console.log("Task is COMPLETED");
          setStatusCompleted(stage);
          setDebug(100, stage, "completed");
        } else if (status === "failed") {
          console.log("Task FAILED");
          setText(statusBadge, "error");
          setText(stageLabel, statusRes.data.error_message || "Error");
          setDebug(0, statusRes.data.error_message || "Error", "error");
        } else if (status === "processing" || status === "pending") {
          console.log("Task is PROCESSING/PENDING, connecting WebSocket...");
          // Task is still processing - ensure WebSocket is connected
          setStatusProcessing(stage);
          setDebug(progress, stage, "processing");
          // Reconnect to WebSocket to receive live updates
          console.log(
            "Requesting WebSocket connection for task:",
            state.currentTaskId,
          );
          const wsRes = await sendMessage("ws:connect", {
            taskId: state.currentTaskId,
          });
          console.log("WebSocket connect response:", wsRes);
        } else {
          console.log("Unknown status:", status);
          setStatusProcessing("Processing…");
        }
      } else {
        console.log("No status data received");
        setStatusProcessing("Processing…");
      }

      // Load segments if available
      if (!state.segments || !state.segments.length) {
        console.log("Loading segments...");
        const segRes = await sendMessage("video:segments", {
          taskId: state.currentTaskId,
        });
        console.log("Segments response:", segRes);
        if (segRes?.data?.segments) {
          state.segments = segRes.data.segments;
          console.log("Loaded segments:", state.segments.length);
          renderSegments();
        }
      } else {
        console.log("Already have segments:", state.segments.length);
      }
    }
    setText(authStatus, "Ready");

    console.log("Setting up message listeners...");
    chrome.runtime.onMessage.addListener((req) => {
      console.log("========================================");
      console.log("SIDEPANEL RECEIVED MESSAGE");
      console.log("Channel:", req?.channel);
      console.log("Type:", req?.type);
      console.log("Full request:", req);
      console.log("========================================");

      if (req?.channel === "ws") {
        console.log("Handling WebSocket message");
        handleWsMessage(req);
      }
      if (req?.channel === "video" && req?.type === "current") {
        console.log("Video current event");
        state.currentTaskId = req.taskId || state.currentTaskId;
        state.currentVideoUrl = req.url || state.currentVideoUrl;
        setCurrentVideo();
        setStatusProcessing("Processing…");
      }
    });

    // Stop polling when page unloads
    window.addEventListener("beforeunload", () => {
      console.log("Sidepanel unloading, stopping polling");
      stopStatusPolling();
    });

    console.log("========================================");
    console.log("SIDEPANEL BOOTSTRAP COMPLETE");
    console.log("========================================");
  }

  console.log("Starting sidepanel bootstrap...");
  bootstrap();
})();

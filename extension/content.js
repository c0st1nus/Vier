// AI Video Quiz Assistant - Content Script
// Responsibilities:
// - Detect <video> element on YouTube pages
// - Notify background about current video URL for processing
// - Show floating quiz button near video player around segment end
// - Inject quiz overlay (Shadow DOM) by loading overlay.html/css via fetch
// - Route messages between page UI and background service worker

(() => {
  const POLL_INTERVAL_MS = 800;
  const TIMEUPDATE_THROTTLE_MS = 500;
  const SHOW_EARLY_SECONDS = 3;
  const HIDE_LATE_SECONDS = 3;

  let videoEl = null;
  let lastTimeUpdate = 0;
  let currentTaskId = null;
  let segments = [];
  let activeSegment = null;
  let overlayRoot = null;
  let overlayContainer = null;
  let quizButton = null;
  let isOverlayLoaded = false;
  let keyListenerBound = false;
  let overlayVisible = false;
  const openedSegmentIds = new Set();

  const state = {
    language: "en",
    enabled: true,
    user: null,
  };

  let navigationListenerBound = false;
  let initializing = false;

  // ---------------- Messaging Helpers ----------------
  function sendMessage(type, payload = {}) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type, payload }, (response) => {
        const err = chrome.runtime.lastError;
        if (err) {
          console.error("content sendMessage error", type, err);
          resolve(null);
          return;
        }
        resolve(response);
      });
    });
  }

  function onBackgroundMessage(request) {
    if (request?.channel === "ws") {
      handleWsUpdate(request);
    }
    if (
      request?.type === "video:seek" &&
      typeof request?.payload?.start_time === "number" &&
      videoEl
    ) {
      const t = Math.max(0, request.payload.start_time);
      videoEl.currentTime = t;
      videoEl.play();
    }
  }

  chrome.runtime.onMessage.addListener(onBackgroundMessage);

  // ---------------- Video Detection ----------------
  function bindNavigationListener() {
    if (navigationListenerBound) return;
    navigationListenerBound = true;
    window.addEventListener("yt-navigate-finish", () => {
      resetVideoState();
      setTimeout(() => init(), 200);
    });
  }

  function resetVideoState() {
    if (videoEl) {
      videoEl.removeEventListener("play", onPlay);
      videoEl.removeEventListener("timeupdate", onTimeUpdate);
    }
    videoEl = null;
    activeSegment = null;
    segments = [];
    currentTaskId = null;
  }

  async function detectVideo() {
    const candidate =
      document.querySelector("video.html5-main-video") ||
      document.querySelector("video");
    if (!candidate) return null;
    return candidate;
  }

  async function init() {
    if (initializing) return;
    initializing = true;
    try {
      console.info("content init start");
      const cfg = await sendMessage("config:get");
      console.info("content config:get", cfg);
      if (cfg?.data) {
        state.language = cfg.data.language || state.language;
        state.enabled = cfg.data.enabled ?? state.enabled;
        state.user = cfg.data.user || null;
      }
      if (!state.enabled) {
        console.info("content disabled, aborting init");
        return;
      }
      if (!state.user) {
        console.info("content user missing, aborting processing");
        return;
      }

      bindNavigationListener();

      resetVideoState();
      videoEl = await waitForVideo();
      if (!videoEl) {
        console.warn("content waitForVideo returned null");
        return;
      }
      console.info("content video detected");

      const url = window.location.href;
      const language =
        state.language || navigator.language?.slice(0, 2) || "en";

      const check = await sendMessage("video:check", { url, language });
      console.info("content video:check response", check);
      const exists = check?.data?.exists && check.data.task_id;
      if (exists) {
        currentTaskId = check.data.task_id;
        await sendMessage("ws:connect", { taskId: currentTaskId });
        await fetchSegments(currentTaskId);
        console.info("content reused task", currentTaskId);
      } else {
        const upload = await sendMessage("video:upload", { url, language });
        console.info("content video:upload response", upload);
        currentTaskId = upload?.data?.task_id || upload?.task_id;
        if (currentTaskId) {
          await sendMessage("ws:connect", { taskId: currentTaskId });
          console.info("content new task", currentTaskId);
        } else {
          console.warn("content upload returned no task_id");
        }
      }

      bindVideoEvents();
      await ensureOverlayLoaded();
      ensureQuizButton();
      bindKeyboardShortcuts();
    } finally {
      initializing = false;
    }
  }

  async function fetchSegments(taskId) {
    const res = await sendMessage("video:segments", { taskId });
    if (res?.data?.segments) {
      segments = res.data.segments;
    }
  }

  function waitForVideo() {
    return new Promise((resolve) => {
      const attempt = () => {
        detectVideo().then((v) => {
          if (v) resolve(v);
          else setTimeout(attempt, POLL_INTERVAL_MS);
        });
      };
      attempt();
    });
  }

  // ---------------- Video Event Binding ----------------
  function bindVideoEvents() {
    if (!videoEl) return;
    videoEl.addEventListener("play", onPlay);
    videoEl.addEventListener("timeupdate", onTimeUpdate);
  }

  function onPlay() {
    // No-op for now; could be used to resume overlay state
  }

  function onTimeUpdate() {
    const now = performance.now();
    if (now - lastTimeUpdate < TIMEUPDATE_THROTTLE_MS) return;
    lastTimeUpdate = now;

    const currentTime = videoEl.currentTime;
    activeSegment = findSegmentForTime(currentTime);
    updateQuizButtonPosition();
    updateQuizButtonVisibility(currentTime, activeSegment);
    maybeAutoOpenOverlay(currentTime, activeSegment);
  }

  function findSegmentForTime(time) {
    if (!segments || !segments.length) return null;
    return segments.find(
      (seg) => time >= seg.start_time && time <= seg.end_time,
    );
  }

  // ---------------- Floating Quiz Button ----------------
  function ensureQuizButton() {
    if (quizButton) return;
    quizButton = document.createElement("button");
    quizButton.textContent = "🎓";
    quizButton.setAttribute("aria-label", "Open quiz");
    quizButton.style.cssText = `
      position: fixed;
      z-index: 999999;
      width: 48px;
      height: 48px;
      border-radius: 24px;
      border: none;
      background: #2563eb;
      color: #fff;
      font-size: 22px;
      box-shadow: 0 6px 16px rgba(0,0,0,0.25);
      cursor: pointer;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.2s ease, transform 0.2s ease;
      transform: translateY(12px);
    `;
    quizButton.addEventListener("click", openOverlay);
    document.body.appendChild(quizButton);
    updateQuizButtonPosition();
    window.addEventListener("resize", updateQuizButtonPosition, {
      passive: true,
    });
    window.addEventListener("scroll", updateQuizButtonPosition, {
      passive: true,
    });
  }

  function updateQuizButtonPosition() {
    if (!quizButton || !videoEl) return;
    const rect = videoEl.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) return;
    const margin = 12;
    const top = Math.max(8, rect.top + margin);
    const left = Math.max(8, rect.left + margin);
    quizButton.style.top = `${top}px`;
    quizButton.style.left = `${left}px`;
    quizButton.style.right = "auto";
    quizButton.style.bottom = "auto";
  }

  function updateQuizButtonVisibility(currentTime, segment) {
    if (!quizButton || !segment) {
      hideQuizButton();
      return;
    }
    if (currentTime >= segment.start_time && currentTime <= segment.end_time) {
      showQuizButton();
    } else {
      hideQuizButton();
    }
  }

  function showQuizButton() {
    quizButton.style.opacity = "1";
    quizButton.style.pointerEvents = "auto";
    quizButton.style.transform = "translateY(0)";
  }

  function hideQuizButton() {
    quizButton.style.opacity = "0";
    quizButton.style.pointerEvents = "none";
    quizButton.style.transform = "translateY(12px)";
  }

  function maybeAutoOpenOverlay(currentTime, segment) {
    if (!segment || overlayVisible) return;
    const segId = segment.id || segment.segment_id;
    if (!segId || openedSegmentIds.has(segId)) return;
    const windowStart = Math.max(
      segment.start_time || 0,
      (segment.end_time || 0) - SHOW_EARLY_SECONDS,
    );
    const windowEnd = (segment.end_time || 0) + HIDE_LATE_SECONDS;
    if (currentTime >= windowStart && currentTime <= windowEnd) {
      openOverlay();
    }
  }

  function bindKeyboardShortcuts() {
    if (keyListenerBound) return;
    window.addEventListener("keydown", onKeydown, false);
    keyListenerBound = true;
  }

  function onKeydown(e) {
    if (e.key === "Escape") {
      if (overlayVisible) {
        e.preventDefault();
        closeOverlay();
      }
      return;
    }
    if (!state.enabled) return;
    if (!overlayContainer || !activeSegment) return;
    if (e.altKey && (e.key === "q" || e.key === "Q")) {
      e.preventDefault();
      openOverlay();
    }
  }

  // ---------------- Overlay ----------------
  function isDarkColor(rgbString) {
    if (!rgbString) return false;
    const match = rgbString.match(/rgba?\(([^)]+)\)/i);
    if (!match) return false;
    const parts = match[1].split(",").map((p) => Number(p.trim()));
    const [r, g, b] = parts;
    if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) return false;
    const luminance = 0.299 * r + 0.587 * g + 0.114 * b;
    return luminance < 128; // simple heuristic
  }

  function resolveYoutubeTheme() {
    const doc = document;
    const attrDark = doc.documentElement?.hasAttribute("dark");
    const bodyClass = (doc.body?.className || "").toLowerCase();
    const bodyDark =
      bodyClass.includes("dark") ||
      bodyClass.includes("night") ||
      bodyClass.includes("themed");
    const bgColor = getComputedStyle(
      doc.body || doc.documentElement,
    ).backgroundColor;
    if (attrDark || bodyDark || isDarkColor(bgColor)) return "dark";
    return "light";
  }

  async function ensureOverlayLoaded() {
    if (isOverlayLoaded) return;
    const overlayHtml = await loadResource(
      chrome.runtime.getURL("overlay.html"),
    );
    const overlayCss = await loadResource(chrome.runtime.getURL("overlay.css"));
    const theme = resolveYoutubeTheme();
    const themeCss =
      theme === "dark"
        ? `:host { --overlay-backdrop: rgba(0,0,0,0.78); --panel-bg: #111827; --panel-border: #1f2937; --text: #f8fafc; --muted: #cbd5e1; }`
        : `:host { --overlay-backdrop: rgba(255,255,255,0.78); --panel-bg: #ffffff; --panel-border: #e2e8f0; --text: #0f172a; --muted: #475569; }`;

    overlayContainer = document.createElement("div");
    overlayContainer.style.position = "fixed";
    overlayContainer.style.top = "0";
    overlayContainer.style.left = "0";
    overlayContainer.style.width = "100%";
    overlayContainer.style.height = "100%";
    overlayContainer.style.zIndex = "1000000";
    overlayContainer.style.display = "none";

    overlayRoot = overlayContainer.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = `${overlayCss}
  ${themeCss}`;
    overlayRoot.appendChild(style);

    const wrapper = document.createElement("div");
    wrapper.innerHTML = overlayHtml;
    overlayRoot.appendChild(wrapper);

    document.body.appendChild(overlayContainer);
    wireOverlayControls();
    isOverlayLoaded = true;
  }

  function wireOverlayControls() {
    const closeBtn = overlayRoot.querySelector("[data-quiz-close]");
    if (closeBtn) {
      closeBtn.addEventListener("click", closeOverlay);
    }
    const overlayEl = overlayRoot.querySelector(".quiz-overlay");
    if (overlayEl) {
      overlayEl.addEventListener("click", (e) => {
        if (e.target === overlayEl) {
          closeOverlay();
        }
      });
    }
  }

  function openOverlay() {
    if (!overlayContainer || !activeSegment || overlayVisible) return;
    overlayContainer.style.display = "block";
    overlayVisible = true;
    if (videoEl) videoEl.pause();

    const segmentId = activeSegment.id || activeSegment.segment_id;
    if (segmentId) {
      openedSegmentIds.add(segmentId);
    }
    const reviewPromise = segmentId
      ? sendMessage("quiz:review", { segmentId })
      : Promise.resolve({ data: [] });

    reviewPromise
      .then((res) => {
        const data = res?.data ?? res ?? [];
        renderOverlay(activeSegment, Array.isArray(data) ? data : []);
      })
      .catch(() => {
        renderOverlay(activeSegment, []);
      });
  }

  function closeOverlay() {
    if (!overlayContainer) return;
    overlayContainer.style.display = "none";
    overlayVisible = false;
    if (videoEl) videoEl.play();
  }

  function renderOverlay(segment, reviewItems) {
    const formatTime = (value) => {
      const s = Math.max(0, Math.floor(value || 0));
      const m = Math.floor(s / 60);
      const ss = String(s % 60).padStart(2, "0");
      return `${m}:${ss}`;
    };

    const titleEl = overlayRoot.querySelector("[data-quiz-title]");
    if (titleEl) {
      titleEl.textContent =
        segment.topic_title || `Segment ${segment.segment_id}`;
    }

    const metaEl = overlayRoot.querySelector("[data-quiz-meta]");
    if (metaEl) {
      const totalQuizzes = (segment.quizzes || []).length;
      metaEl.innerHTML = `
        <span class="quiz-overlay__chip">
          <span class="dot"></span>
          ${formatTime(segment.start_time)} - ${formatTime(segment.end_time)}
        </span>
        <span class="quiz-overlay__chip">
          <span class="dot"></span>
          ${totalQuizzes} question${totalQuizzes === 1 ? "" : "s"}
        </span>
      `;
    }

    const listEl = overlayRoot.querySelector("[data-quiz-list]");
    if (!listEl) return;
    listEl.innerHTML = "";

    if (
      segment.short_summary ||
      (segment.keywords && segment.keywords.length)
    ) {
      const summary = document.createElement("div");
      summary.className = "quiz-summary";

      const summaryTitle = document.createElement("p");
      summaryTitle.className = "quiz-summary__title";
      summaryTitle.textContent = "Кратко о сегменте";
      summary.appendChild(summaryTitle);

      if (segment.short_summary) {
        const summaryText = document.createElement("p");
        summaryText.className = "quiz-summary__text";
        summaryText.textContent = segment.short_summary;
        summary.appendChild(summaryText);
      }

      if (segment.keywords && segment.keywords.length) {
        const kwWrap = document.createElement("div");
        kwWrap.className = "quiz-keywords";
        segment.keywords.forEach((kw) => {
          const chip = document.createElement("span");
          chip.className = "quiz-keyword";
          chip.textContent = kw;
          kwWrap.appendChild(chip);
        });
        summary.appendChild(kwWrap);
      }

      listEl.appendChild(summary);
    }

    const quizzes = segment.quizzes || [];
    if (!quizzes.length) {
      const empty = document.createElement("div");
      empty.className = "quiz-overlay__empty";
      empty.textContent = "Нет квизов для этого сегмента.";
      listEl.appendChild(empty);
      return;
    }

    quizzes.forEach((quiz) => {
      const item = document.createElement("div");
      item.className = "quiz-item";
      item.dataset.quizId = String(quiz.id);

      const question = document.createElement("h3");
      question.textContent = quiz.question;
      item.appendChild(question);

      const answers = document.createElement("div");
      answers.className = "quiz-options";

      const review = reviewItems.find((r) => r.quiz_id === quiz.id);

      quiz.options.forEach((opt, idx) => {
        const btn = document.createElement("button");
        btn.textContent = opt;
        btn.className = "quiz-option";
        btn.dataset.quizId = String(quiz.id);
        btn.dataset.optionIndex = String(idx);

        if (review) {
          btn.disabled = true;
          const selectedIdx =
            typeof review.selected_index === "number"
              ? review.selected_index
              : null;
          const correctIdx =
            typeof review.correct_index === "number"
              ? review.correct_index
              : null;

          if (idx === selectedIdx) {
            btn.classList.add("is-selected");
          }
          if (correctIdx !== null && idx === correctIdx) {
            btn.classList.add("correct");
          } else if (selectedIdx === idx && review.is_correct === false) {
            btn.classList.add("incorrect");
          }
        }

        btn.addEventListener("click", () =>
          handleAnswer(quiz.id, idx, btn, item),
        );
        answers.appendChild(btn);
      });

      item.appendChild(answers);

      const status =
        item.querySelector(".quiz-review") || document.createElement("div");
      status.className = "quiz-review";
      if (review) {
        status.textContent = review.is_correct
          ? "✅ Ответ верный"
          : "❌ Ответ неверный";
      } else {
        status.textContent = "";
      }
      if (!status.parentElement) {
        item.appendChild(status);
      }

      listEl.appendChild(item);
    });
  }

  async function handleAnswer(quizId, selectedIndex, buttonEl, quizItemEl) {
    const container = quizItemEl || buttonEl.closest(".quiz-item");
    const optionButtons = container
      ? Array.from(container.querySelectorAll(".quiz-option"))
      : [buttonEl];
    const statusEl =
      (container && container.querySelector(".quiz-review")) || null;

    optionButtons.forEach((btn) => {
      btn.disabled = true;
      btn.classList.remove("correct", "incorrect", "is-selected");
    });
    buttonEl.classList.add("is-selected");

    try {
      const res = await sendMessage("quiz:answer", {
        quizId,
        selectedIndex,
      });
      const data = res?.data ?? res;
      const correctIndex =
        data && typeof data.correct_index === "number"
          ? data.correct_index
          : null;
      const isCorrect = !!data?.is_correct;

      optionButtons.forEach((btn) => {
        const idx = Number(btn.dataset.optionIndex);
        if (correctIndex !== null && idx === correctIndex) {
          btn.classList.add("correct");
        }
        if (idx === selectedIndex && !isCorrect) {
          btn.classList.add("incorrect");
        }
      });

      if (statusEl) {
        statusEl.textContent = isCorrect
          ? "✅ Ответ верный"
          : "❌ Ответ неверный";
      }
    } catch (e) {
      console.warn("Answer submit failed", e);
      if (statusEl) {
        statusEl.textContent =
          "❗ Не удалось отправить ответ. Попробуйте снова.";
      }
    } finally {
      optionButtons.forEach((btn) => (btn.disabled = false));
    }
  }

  async function loadResource(url) {
    const res = await fetch(url);
    return res.text();
  }

  // ---------------- WebSocket Handling ----------------
  function handleWsUpdate(message) {
    const { payload } = message;
    if (!payload) return;
    switch (payload.event) {
      case "segment_ready": {
        if (payload.segment) {
          segments.push(payload.segment);
        }
        break;
      }
      case "completed": {
        fetchSegments(currentTaskId);
        break;
      }
      default:
        break;
    }
  }

  // ---------------- Bootstrap ----------------
  init();
})();

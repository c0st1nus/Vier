// VideoPlayer component with synchronized quiz overlays
import React, { useState, useRef, useEffect } from "react";
import { useTranslation } from "../contexts/LanguageContext";
import {
  getQuizTranslation,
  getSegmentTranslation,
} from "../utils/multilingualHelper";
import "./VideoPlayer.css";

const VideoPlayer = ({ videoUrl, segments, taskId }) => {
  const { language } = useTranslation();
  const videoRef = useRef(null);
  const answeredQuizzesRef = useRef(new Set()); // Используем ref для немедленного отслеживания
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showQuiz, setShowQuiz] = useState(false);
  const [currentQuiz, setCurrentQuiz] = useState(null);
  const [quizAnswer, setQuizAnswer] = useState(null);
  const [quizResult, setQuizResult] = useState(null);
  const [answeredQuizzes, setAnsweredQuizzes] = useState(new Set());
  const [videoError, setVideoError] = useState(null);

  // Track current time
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime);
      checkForQuiz(video.currentTime);
    };

    const handleLoadedMetadata = () => {
      setDuration(video.duration);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleError = (e) => {
      console.error("Video loading error:", e);
      setVideoError("Failed to load video. Please try again.");
    };

    video.addEventListener("timeupdate", handleTimeUpdate);
    video.addEventListener("loadedmetadata", handleLoadedMetadata);
    video.addEventListener("play", handlePlay);
    video.addEventListener("pause", handlePause);
    video.addEventListener("error", handleError);

    return () => {
      video.removeEventListener("timeupdate", handleTimeUpdate);
      video.removeEventListener("loadedmetadata", handleLoadedMetadata);
      video.removeEventListener("play", handlePlay);
      video.removeEventListener("pause", handlePause);
      video.removeEventListener("error", handleError);
    };
  }, [segments]);

  // Log segments when they change
  useEffect(() => {
    if (segments && segments.length > 0) {
      const quizSegments = segments.filter(
        (s) => s.quizzes && s.quizzes.length > 0,
      );
      console.log(
        `📚 Загружено ${segments.length} сегментов, из них ${quizSegments.length} с квизами`,
      );
      quizSegments.forEach((s) => {
        const quizTime = s.end_time + 1.0;
        const segmentTranslation = getSegmentTranslation(s, language);
        console.log(
          `  - "${segmentTranslation.topic_title}": квиз ожидается на ${quizTime.toFixed(2)}с`,
        );
      });
    }
  }, [segments]);

  // Check if we should show a quiz
  const checkForQuiz = (time) => {
    if (!segments || segments.length === 0 || !duration) return;

    for (const segment of segments) {
      if (!segment.quizzes || segment.quizzes.length === 0) continue;

      // Get quiz question in current language for key
      const quizTranslation = getQuizTranslation(segment.quizzes[0], language);
      const quizKey = `${segment.start_time}-${quizTranslation.question}`;

      // Skip if already answered or quiz is already showing
      if (answeredQuizzesRef.current.has(quizKey)) continue;
      if (showQuiz) continue;

      // Calculate quiz time: 1 second after segment ends
      let quizTime = segment.end_time + 1.0;

      // If quiz time exceeds video duration, show it 1-5 seconds before video ends
      if (quizTime > duration) {
        // Try to show 3 seconds before end (middle of 1-5 range)
        quizTime = Math.max(segment.end_time, duration - 3.0);
        // Make sure it's not before the segment ends
        if (quizTime < segment.end_time) {
          quizTime = segment.end_time;
        }
      }

      const tolerance = 0.3; // Show quiz within 0.3 seconds of quiz time

      // Check if we're at the quiz time
      if (time >= quizTime - tolerance && time <= quizTime + tolerance) {
        const segmentTranslation = getSegmentTranslation(segment, language);
        console.log(
          `🎯 Ожидается квиз на времени ${quizTime.toFixed(2)}с для сегмента "${segmentTranslation.topic_title}"`,
        );
        console.log(`✅ ПОКАЗЫВАЕМ КВИЗ: "${quizTranslation.question}"`);

        setCurrentQuiz({
          ...segment.quizzes[0],
          segmentTitle: segmentTranslation.topic_title,
          quizKey: quizKey,
          currentLanguage: language,
        });
        setShowQuiz(true);
        setQuizAnswer(null);
        setQuizResult(null);
        pauseVideo();

        // Immediately mark as being shown to prevent re-triggering
        answeredQuizzesRef.current.add(quizKey);
        setAnsweredQuizzes((prev) => new Set([...prev, quizKey]));
        break; // Only show one quiz at a time
      } else if (Math.abs(time - quizTime) < 1.0) {
        // Log when we're close to quiz time
        const segmentTranslation = getSegmentTranslation(segment, language);
        console.log(
          `🎯 Ожидается квиз на времени ${quizTime.toFixed(2)}с для сегмента "${segmentTranslation.topic_title}" (текущее время: ${time.toFixed(2)}с)`,
        );
      }
    }
  };

  // Video controls
  const togglePlayPause = () => {
    const video = videoRef.current;
    if (!video) return;

    if (video.paused) {
      video.play();
    } else {
      video.pause();
    }
  };

  const pauseVideo = () => {
    const video = videoRef.current;
    if (video && !video.paused) {
      video.pause();
    }
  };

  const handleSeek = (e) => {
    const video = videoRef.current;
    if (!video) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const pos = (e.clientX - rect.left) / rect.width;
    video.currentTime = pos * video.duration;
  };

  const handleVolumeChange = (e) => {
    const video = videoRef.current;
    if (!video) return;

    const newVolume = parseFloat(e.target.value);
    setVolume(newVolume);
    video.volume = newVolume;
    setIsMuted(newVolume === 0);
  };

  const toggleMute = () => {
    const video = videoRef.current;
    if (!video) return;

    if (isMuted) {
      video.volume = volume;
      setIsMuted(false);
    } else {
      video.volume = 0;
      setIsMuted(true);
    }
  };

  const toggleFullscreen = () => {
    const container = videoRef.current?.parentElement;
    if (!container) return;

    if (!document.fullscreenElement) {
      container.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  const skipToSegment = (segment) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = segment.start_time;
  };

  // Quiz handling
  const handleQuizAnswer = (answerIndex) => {
    setQuizAnswer(answerIndex);
  };

  const submitQuizAnswer = () => {
    if (quizAnswer === null || !currentQuiz) return;

    const isCorrect = quizAnswer === currentQuiz.correct_index;
    console.log(`📝 Ответ ${isCorrect ? "✅ ПРАВИЛЬНЫЙ" : "❌ НЕПРАВИЛЬНЫЙ"}`);
    setQuizResult(isCorrect);

    // Quiz is already marked as answered in checkForQuiz when it's shown
  };

  // Get current quiz translation
  const getCurrentQuizTranslation = () => {
    if (!currentQuiz) return null;
    return getQuizTranslation(
      currentQuiz,
      currentQuiz.currentLanguage || language,
    );
  };

  const closeQuiz = () => {
    const quizTranslation = getCurrentQuizTranslation();
    console.log(`❌ Квиз "${quizTranslation?.question}" закрыт/пропущен`);

    // Quiz is already marked as answered in checkForQuiz when it's shown
    setShowQuiz(false);
    setCurrentQuiz(null);
    setQuizAnswer(null);
    setQuizResult(null);

    videoRef.current?.play();
  };

  // Format time
  const formatTime = (seconds) => {
    if (isNaN(seconds)) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Calculate progress percentage
  const progressPercentage = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="video-player-container">
      {/* Video Element */}
      <div className="video-wrapper">
        {videoError ? (
          <div className="video-error">
            <svg
              width="64"
              height="64"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p>{videoError}</p>
            <button
              onClick={() => {
                setVideoError(null);
                if (videoRef.current) {
                  videoRef.current.load();
                }
              }}
            >
              Retry
            </button>
          </div>
        ) : (
          <video
            ref={videoRef}
            className="video-element"
            src={videoUrl}
            onClick={togglePlayPause}
            crossOrigin="anonymous"
          />
        )}

        {/* Quiz Overlay */}
        {showQuiz && currentQuiz && (
          <div className="quiz-overlay">
            <div className="quiz-overlay-content">
              <div className="quiz-overlay-header">
                <h3 className="quiz-overlay-title">
                  Quiz: {currentQuiz.segmentTitle}
                </h3>
              </div>

              <div className="quiz-overlay-body">
                <p className="quiz-overlay-question">
                  {getCurrentQuizTranslation()?.question}
                </p>

                <div className="quiz-overlay-options">
                  {getCurrentQuizTranslation()?.options.map((option, index) => (
                    <button
                      key={index}
                      className={`quiz-overlay-option ${
                        quizAnswer === index ? "selected" : ""
                      } ${
                        quizResult !== null
                          ? index === currentQuiz.correct_index
                            ? "correct"
                            : quizAnswer === index
                              ? "incorrect"
                              : ""
                          : ""
                      }`}
                      onClick={() => handleQuizAnswer(index)}
                      disabled={quizResult !== null}
                    >
                      <span className="option-letter">
                        {String.fromCharCode(65 + index)}
                      </span>
                      <span className="option-text">{option}</span>
                    </button>
                  ))}
                </div>

                {quizResult !== null && (
                  <div
                    className={`quiz-overlay-result ${quizResult ? "correct" : "incorrect"}`}
                  >
                    {quizResult ? (
                      <>
                        <svg
                          width="24"
                          height="24"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                        <span>Correct! Well done!</span>
                      </>
                    ) : (
                      <>
                        <svg
                          width="24"
                          height="24"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth="2"
                            d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                        <span>
                          Incorrect. The correct answer is{" "}
                          {String.fromCharCode(65 + currentQuiz.correct_index)}:{" "}
                          {
                            getCurrentQuizTranslation()?.options[
                              currentQuiz.correct_index
                            ]
                          }
                        </span>
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Show explanation if available */}
              {quizResult !== null &&
                getCurrentQuizTranslation()?.explanation && (
                  <div className="quiz-explanation">
                    <strong>💡 Explanation:</strong>{" "}
                    {getCurrentQuizTranslation()?.explanation}
                  </div>
                )}

              <div className="quiz-overlay-footer">
                {quizResult === null ? (
                  <>
                    <button
                      className="quiz-overlay-button secondary"
                      onClick={closeQuiz}
                    >
                      Skip
                    </button>
                    <button
                      className="quiz-overlay-button primary"
                      onClick={submitQuizAnswer}
                      disabled={quizAnswer === null}
                    >
                      Submit Answer
                    </button>
                  </>
                ) : (
                  <button
                    className="quiz-overlay-button primary"
                    onClick={closeQuiz}
                  >
                    Continue Watching
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Play/Pause overlay button */}
        {!isPlaying && !showQuiz && (
          <button className="play-overlay-button" onClick={togglePlayPause}>
            <svg width="80" height="80" viewBox="0 0 24 24" fill="currentColor">
              <path d="M8 5v14l11-7z" />
            </svg>
          </button>
        )}
      </div>

      {/* Video Controls */}
      <div className="video-controls">
        {/* Progress Bar */}
        <div className="progress-container" onClick={handleSeek}>
          <div className="progress-bar">
            <div
              className="progress-filled"
              style={{ width: `${progressPercentage}%` }}
            />
            {/* Segment markers */}
            {segments &&
              segments.map((segment, index) => {
                const position =
                  duration > 0 ? (segment.start_time / duration) * 100 : 0;
                return (
                  <div
                    key={index}
                    className="segment-marker"
                    style={{ left: `${position}%` }}
                    title={segment.topic_title}
                  />
                );
              })}
          </div>
        </div>

        {/* Control Buttons */}
        <div className="controls-row">
          <div className="controls-left">
            {/* Play/Pause */}
            <button
              className="control-button"
              onClick={togglePlayPause}
              title={isPlaying ? "Pause" : "Play"}
            >
              {isPlaying ? (
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                </svg>
              ) : (
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M8 5v14l11-7z" />
                </svg>
              )}
            </button>

            {/* Volume */}
            <div className="volume-control">
              <button
                className="control-button"
                onClick={toggleMute}
                title={isMuted ? "Unmute" : "Mute"}
              >
                {isMuted || volume === 0 ? (
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M17 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2"
                    />
                  </svg>
                ) : (
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M15.536 8.464a5 5 0 010 7.072m2.828-9.9a9 9 0 010 12.728M5.586 15H4a1 1 0 01-1-1v-4a1 1 0 011-1h1.586l4.707-4.707C10.923 3.663 12 4.109 12 5v14c0 .891-1.077 1.337-1.707.707L5.586 15z"
                    />
                  </svg>
                )}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={isMuted ? 0 : volume}
                onChange={handleVolumeChange}
                className="volume-slider"
              />
            </div>

            {/* Time */}
            <span className="time-display">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          <div className="controls-right">
            {/* Fullscreen */}
            <button
              className="control-button"
              onClick={toggleFullscreen}
              title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
            >
              {isFullscreen ? (
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M6 9V6h3M18 9V6h-3M18 15v3h-3M6 15v3h3"
                  />
                </svg>
              ) : (
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
                  />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Chapters/Segments */}
      {segments && segments.length > 0 && (
        <div className="video-chapters">
          <h4 className="chapters-title">Chapters</h4>
          <div className="chapters-list">
            {segments.map((segment, index) => (
              <button
                key={index}
                className={`chapter-item ${
                  currentTime >= segment.start_time &&
                  currentTime < segment.end_time
                    ? "active"
                    : ""
                }`}
                onClick={() => skipToSegment(segment)}
              >
                <span className="chapter-time">
                  {formatTime(segment.start_time)}
                </span>
                <span className="chapter-title">{segment.topic_title}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default VideoPlayer;

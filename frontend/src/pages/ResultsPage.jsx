// Results Page - Display segments with interactive quizzes
import React, { useState } from "react";
import { useTranslation } from "../contexts/LanguageContext";
import {
  getQuizTranslation,
  getSegmentTranslation,
} from "../utils/multilingualHelper";
import VideoPlayer from "../components/VideoPlayer";
import "./ResultsPage.css";

const ResultsPage = ({ segments, videoUrl, taskId, onReset }) => {
  const { language } = useTranslation();
  const [viewMode, setViewMode] = useState("video"); // 'video' or 'quiz'
  const [expandedSegments, setExpandedSegments] = useState(new Set([0]));
  const [answers, setAnswers] = useState({});
  const [showResults, setShowResults] = useState({});

  // Toggle segment expansion
  const toggleSegment = (index) => {
    const newExpanded = new Set(expandedSegments);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedSegments(newExpanded);
  };

  // Handle answer selection
  const handleAnswer = (segmentIndex, quizIndex, answerIndex) => {
    const key = `${segmentIndex}-${quizIndex}`;
    setAnswers((prev) => ({
      ...prev,
      [key]: answerIndex,
    }));
  };

  // Check answer
  const checkAnswer = (segmentIndex, quizIndex) => {
    const key = `${segmentIndex}-${quizIndex}`;
    setShowResults((prev) => ({
      ...prev,
      [key]: true,
    }));
  };

  // Format time
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  // Calculate quiz statistics
  const calculateStats = () => {
    let totalQuizzes = 0;
    let answeredQuizzes = 0;
    let correctAnswers = 0;

    // Ensure segments is an array
    const segmentsArray = Array.isArray(segments) ? segments : [];

    segmentsArray.forEach((segment, segIndex) => {
      const quizzes = Array.isArray(segment.quizzes) ? segment.quizzes : [];
      quizzes.forEach((quiz, quizIndex) => {
        totalQuizzes++;
        const key = `${segIndex}-${quizIndex}`;
        if (answers[key] !== undefined) {
          answeredQuizzes++;
          if (answers[key] === quiz.correct_index) {
            correctAnswers++;
          }
        }
      });
    });

    return {
      total: totalQuizzes,
      answered: answeredQuizzes,
      correct: correctAnswers,
      percentage:
        answeredQuizzes > 0
          ? Math.round((correctAnswers / answeredQuizzes) * 100)
          : 0,
    };
  };

  const stats = calculateStats();

  // Ensure segments is an array for rendering
  const segmentsArray = Array.isArray(segments) ? segments : [];

  // Show error if no segments
  if (!segments || segmentsArray.length === 0) {
    return (
      <div className="results-page">
        <div className="container container-sm">
          <div className="error-card">
            <div className="error-icon">
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
            </div>
            <h2 className="error-title">No Results Available</h2>
            <p className="error-message">
              No quiz segments were generated. Please try processing the video
              again.
            </p>
            <button className="primary-button" onClick={onReset}>
              Try Again
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="results-page">
      <div className="container">
        {/* Header */}
        <div className="results-header">
          <div className="results-header-content">
            <div>
              <h2 className="results-title">Your Quiz Results</h2>
              <p className="results-description">
                {segmentsArray.length} segments generated with {stats.total}{" "}
                quiz questions
              </p>
            </div>
            <div className="header-actions">
              {/* View Mode Toggle */}
              <div className="view-mode-toggle">
                <button
                  className={`mode-toggle-btn ${viewMode === "video" ? "active" : ""}`}
                  onClick={() => setViewMode("video")}
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                    />
                  </svg>
                  Watch Video
                </button>
                <button
                  className={`mode-toggle-btn ${viewMode === "quiz" ? "active" : ""}`}
                  onClick={() => setViewMode("quiz")}
                >
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                    />
                  </svg>
                  Take Quiz
                </button>
              </div>
            </div>
            <button className="new-video-button" onClick={onReset}>
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M12 4v16m8-8H4"
                />
              </svg>
              New Video
            </button>
          </div>

          {/* Statistics */}
          <div className="stats-container">
            <div className="stat-card">
              <div className="stat-icon">
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
                    d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"
                  />
                </svg>
              </div>
              <div className="stat-info">
                <div className="stat-value">{stats.total}</div>
                <div className="stat-label">Total Questions</div>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon">
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
                    d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                  />
                </svg>
              </div>
              <div className="stat-info">
                <div className="stat-value">{stats.answered}</div>
                <div className="stat-label">Answered</div>
              </div>
            </div>

            <div className="stat-card">
              <div className="stat-icon stat-icon-success">
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
              </div>
              <div className="stat-info">
                <div className="stat-value">{stats.correct}</div>
                <div className="stat-label">Correct</div>
              </div>
            </div>

            <div className="stat-card stat-card-primary">
              <div className="stat-icon">
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
                    d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"
                  />
                </svg>
              </div>
              <div className="stat-info">
                <div className="stat-value">{stats.percentage}%</div>
                <div className="stat-label">Score</div>
              </div>
            </div>
          </div>
        </div>

        {/* Video Player Mode */}
        {viewMode === "video" && videoUrl && (
          <div className="video-section">
            <VideoPlayer
              videoUrl={videoUrl}
              segments={segmentsArray}
              taskId={taskId}
            />
          </div>
        )}

        {/* Quiz Mode - Segments */}
        {viewMode === "quiz" && (
          <div className="segments-container">
            {segmentsArray.map((segment, segmentIndex) => (
              <div
                key={segmentIndex}
                className={`segment-card ${expandedSegments.has(segmentIndex) ? "expanded" : ""}`}
              >
                {/* Segment Header */}
                <div
                  className="segment-header"
                  onClick={() => toggleSegment(segmentIndex)}
                >
                  <div className="segment-header-left">
                    <div className="segment-number">{segmentIndex + 1}</div>
                    <div className="segment-info">
                      <h3 className="segment-title">
                        {getSegmentTranslation(segment, language).topic_title}
                      </h3>
                      <div className="segment-meta">
                        <span className="segment-time">
                          <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                          {formatTime(segment.start_time)} -{" "}
                          {formatTime(segment.end_time)}
                        </span>
                        <span className="segment-quiz-count">
                          <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth="2"
                              d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                            />
                          </svg>
                          {segment.quizzes.length}{" "}
                          {segment.quizzes.length === 1 ? "Quiz" : "Quizzes"}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="segment-expand-icon">
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
                        d="M19 9l-7 7-7-7"
                      />
                    </svg>
                  </div>
                </div>

                {/* Segment Content */}
                {expandedSegments.has(segmentIndex) && (
                  <div className="segment-content">
                    {/* Summary */}
                    <div className="segment-summary">
                      <h4 className="summary-title">Summary</h4>
                      <p className="summary-text">
                        {getSegmentTranslation(segment, language).short_summary}
                      </p>
                    </div>

                    {/* Keywords */}
                    {segment.keywords && segment.keywords.length > 0 && (
                      <div className="segment-keywords">
                        <h4 className="keywords-title">Key Topics</h4>
                        <div className="keywords-list">
                          {segment.keywords.map((keyword, index) => (
                            <span key={index} className="keyword-tag">
                              {keyword}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Quizzes */}
                    <div className="quizzes-container">
                      <h4 className="quizzes-title">Quiz Questions</h4>
                      {segment.quizzes.map((quiz, quizIndex) => {
                        const key = `${segmentIndex}-${quizIndex}`;
                        const selectedAnswer = answers[key];
                        const isAnswered = selectedAnswer !== undefined;
                        const showResult = showResults[key];
                        const isCorrect =
                          isAnswered && selectedAnswer === quiz.correct_index;

                        // Get quiz translation for current language
                        const quizTranslation = getQuizTranslation(
                          quiz,
                          language,
                        );

                        return (
                          <div key={quizIndex} className="quiz-card">
                            <div className="quiz-header">
                              <span className="quiz-number">
                                Question {quizIndex + 1}
                              </span>
                              {showResult && (
                                <span
                                  className={`quiz-result ${isCorrect ? "correct" : "incorrect"}`}
                                >
                                  {isCorrect ? (
                                    <>
                                      <svg
                                        width="16"
                                        height="16"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="currentColor"
                                      >
                                        <path
                                          strokeLinecap="round"
                                          strokeLinejoin="round"
                                          strokeWidth="2"
                                          d="M5 13l4 4L19 7"
                                        />
                                      </svg>
                                      Correct
                                    </>
                                  ) : (
                                    <>
                                      <svg
                                        width="16"
                                        height="16"
                                        viewBox="0 0 24 24"
                                        fill="none"
                                        stroke="currentColor"
                                      >
                                        <path
                                          strokeLinecap="round"
                                          strokeLinejoin="round"
                                          strokeWidth="2"
                                          d="M6 18L18 6M6 6l12 12"
                                        />
                                      </svg>
                                      Incorrect
                                    </>
                                  )}
                                </span>
                              )}
                            </div>

                            <p className="quiz-question">
                              {quizTranslation.question}
                            </p>

                            <div className="quiz-options">
                              {quizTranslation.options.map(
                                (option, optionIndex) => {
                                  const isSelected =
                                    selectedAnswer === optionIndex;
                                  const isCorrectOption =
                                    optionIndex === quiz.correct_index;
                                  const showCorrect =
                                    showResult && isCorrectOption;
                                  const showIncorrect =
                                    showResult &&
                                    isSelected &&
                                    !isCorrectOption;

                                  return (
                                    <button
                                      key={optionIndex}
                                      className={`quiz-option ${isSelected ? "selected" : ""} ${showCorrect ? "correct" : ""} ${showIncorrect ? "incorrect" : ""}`}
                                      onClick={() =>
                                        !showResult &&
                                        handleAnswer(
                                          segmentIndex,
                                          quizIndex,
                                          optionIndex,
                                        )
                                      }
                                      disabled={showResult}
                                    >
                                      <span className="option-indicator">
                                        {showCorrect ? (
                                          <svg
                                            width="20"
                                            height="20"
                                            viewBox="0 0 24 24"
                                            fill="none"
                                            stroke="currentColor"
                                          >
                                            <path
                                              strokeLinecap="round"
                                              strokeLinejoin="round"
                                              strokeWidth="2"
                                              d="M5 13l4 4L19 7"
                                            />
                                          </svg>
                                        ) : showIncorrect ? (
                                          <svg
                                            width="20"
                                            height="20"
                                            viewBox="0 0 24 24"
                                            fill="none"
                                            stroke="currentColor"
                                          >
                                            <path
                                              strokeLinecap="round"
                                              strokeLinejoin="round"
                                              strokeWidth="2"
                                              d="M6 18L18 6M6 6l12 12"
                                            />
                                          </svg>
                                        ) : (
                                          String.fromCharCode(65 + optionIndex)
                                        )}
                                      </span>
                                      <span className="option-text">
                                        {option}
                                      </span>
                                    </button>
                                  );
                                },
                              )}
                            </div>

                            {isAnswered && !showResult && (
                              <button
                                className="check-answer-button"
                                onClick={() =>
                                  checkAnswer(segmentIndex, quizIndex)
                                }
                              >
                                Check Answer
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ResultsPage;

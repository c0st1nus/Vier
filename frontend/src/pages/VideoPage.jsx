import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ProcessingPage from "./ProcessingPage";
import ResultsPage from "./ResultsPage";

const API_BASE_URL = "http://localhost:8000/api";

function VideoPage() {
  const { taskId } = useParams();
  const navigate = useNavigate();

  const [status, setStatus] = useState("pending");
  const [progress, setProgress] = useState(0);
  const [currentStage, setCurrentStage] = useState(null);
  const [segments, setSegments] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  // Poll for status updates
  useEffect(() => {
    if (!taskId) return;

    let pollInterval;

    const fetchStatus = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/video/${taskId}/status`);

        if (!response.ok) {
          throw new Error("Failed to fetch task status");
        }

        const data = await response.json();
        setStatus(data.status);
        setProgress(data.progress || 0);
        setCurrentStage(data.current_stage);
        setError(data.error);
        setLoading(false);

        // If completed, fetch segments
        if (data.status === "completed") {
          fetchSegments();
          if (pollInterval) {
            clearInterval(pollInterval);
          }
        }

        // If failed, stop polling
        if (data.status === "failed") {
          if (pollInterval) {
            clearInterval(pollInterval);
          }
        }
      } catch (err) {
        console.error("Error fetching status:", err);
        setError(err.message);
        setLoading(false);
        if (pollInterval) {
          clearInterval(pollInterval);
        }
      }
    };

    const fetchSegments = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/video/${taskId}/segments`
        );

        if (!response.ok) {
          throw new Error("Failed to fetch segments");
        }

        const data = await response.json();
        setSegments(data.segments);
        setVideoUrl(`${API_BASE_URL}/video/${taskId}/file`);
      } catch (err) {
        console.error("Error fetching segments:", err);
        setError(err.message);
      }
    };

    // Initial fetch
    fetchStatus();

    // Poll every 2 seconds while processing
    pollInterval = setInterval(() => {
      if (status !== "completed" && status !== "failed") {
        fetchStatus();
      }
    }, 2000);

    return () => {
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [taskId, status]);

  const handleReset = () => {
    navigate("/");
  };

  // Loading state
  if (loading) {
    return (
      <div className="container" style={{ textAlign: "center", marginTop: "4rem" }}>
        <div className="spinner" style={{ margin: "0 auto 1rem" }}></div>
        <p>Загрузка данных...</p>
      </div>
    );
  }

  // Error state
  if (error && status === "failed") {
    return (
      <div className="error-container">
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
            <h2 className="error-title">Processing Failed</h2>
            <p className="error-message">
              {error || "An unexpected error occurred. Please try again."}
            </p>
            <div className="error-actions">
              <button className="primary-button" onClick={handleReset}>
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
                    d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                  />
                </svg>
                Try Again
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Completed state - show results
  if (status === "completed" && segments) {
    return (
      <ResultsPage
        segments={segments}
        videoUrl={videoUrl}
        taskId={taskId}
        onReset={handleReset}
      />
    );
  }

  // Processing state
  return (
    <ProcessingPage
      taskId={taskId}
      status={status}
      progress={progress}
      currentStage={currentStage}
      uploadProgress={0}
    />
  );
}

export default VideoPage;

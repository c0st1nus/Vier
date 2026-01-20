import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ResultsPage from "./ResultsPage";

const API_BASE_URL = "http://localhost:8000/api";

function SharedVideoPage() {
  const { shareToken } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [taskData, setTaskData] = useState(null);

  useEffect(() => {
    const fetchSharedVideo = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/shared/${shareToken}`
        );

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("Shared video not found");
          } else if (response.status === 403) {
            throw new Error("This video is not publicly shared");
          } else {
            throw new Error("Failed to load shared video");
          }
        }

        const data = await response.json();
        setTaskData(data);
      } catch (err) {
        console.error("Error fetching shared video:", err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    if (shareToken) {
      fetchSharedVideo();
    }
  }, [shareToken]);

  if (loading) {
    return (
      <div className="container" style={{ textAlign: "center", marginTop: "4rem" }}>
        <div className="spinner" style={{ margin: "0 auto 1rem" }}></div>
        <p>Загрузка видео...</p>
      </div>
    );
  }

  if (error) {
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
            <h2 className="error-title">Ошибка</h2>
            <p className="error-message">{error}</p>
            <div className="error-actions">
              <button className="primary-button" onClick={() => navigate("/")}>
                На главную
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!taskData || !taskData.segments) {
    return (
      <div className="error-container">
        <div className="container container-sm">
          <div className="error-card">
            <h2 className="error-title">Видео не найдено</h2>
            <p className="error-message">
              Это видео недоступно или еще не обработано.
            </p>
            <button className="primary-button" onClick={() => navigate("/")}>
              На главную
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Parse segments if they're in JSON format
  const segments = Array.isArray(taskData.segments)
    ? taskData.segments
    : [];

  const videoUrl = `${API_BASE_URL}/video/${taskData.id}/file`;

  return (
    <div>
      <div className="container" style={{ marginBottom: "1rem", paddingTop: "1rem" }}>
        <div style={{
          background: "rgba(99, 102, 241, 0.1)",
          border: "1px solid rgba(99, 102, 241, 0.3)",
          borderRadius: "8px",
          padding: "1rem",
          display: "flex",
          alignItems: "center",
          gap: "0.75rem"
        }}>
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            style={{ color: "#6366f1", flexShrink: 0 }}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
            />
          </svg>
          <div style={{ flex: 1 }}>
            <p style={{ margin: 0, fontSize: "0.875rem", color: "#6366f1", fontWeight: 500 }}>
              Общий доступ
            </p>
            <p style={{ margin: 0, fontSize: "0.75rem", color: "#64748b", marginTop: "0.25rem" }}>
              Кто-то поделился с вами этим видео с интерактивными вопросами
            </p>
          </div>
        </div>
      </div>

      <ResultsPage
        segments={segments}
        videoUrl={videoUrl}
        taskId={taskData.id}
        onReset={() => navigate("/")}
        isShared={true}
      />
    </div>
  );
}

export default SharedVideoPage;

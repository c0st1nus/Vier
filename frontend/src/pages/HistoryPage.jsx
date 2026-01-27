import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "../contexts/LanguageContext";
import "./HistoryPage.css";

const HistoryPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("all"); // all, completed, processing, failed
  const [sortBy, setSortBy] = useState("newest"); // newest, oldest, duration

  useEffect(() => {
    fetchHistory();
  }, [filter]);

  const fetchHistory = async () => {
    setLoading(true);
    setError(null);

    try {
      const statusParam = filter !== "all" ? `?status=${filter}` : "";
      const response = await fetch(
        `http://16.170.208.132:2135/api/history${statusParam}`,
      );

      if (!response.ok) {
        throw new Error("Failed to load history");
      }

      const data = await response.json();
      setTasks(data.tasks || []);
    } catch (err) {
      console.error("Error fetching history:", err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (taskId, event) => {
    event.stopPropagation();

    if (!window.confirm(t("history.deleteConfirm"))) {
      return;
    }

    try {
      const response = await fetch(
        `http://16.170.208.132:2135/api/video/${taskId}`,
        {
          method: "DELETE",
        },
      );

      if (!response.ok) {
        throw new Error("Failed to delete task");
      }

      // Remove from local state
      setTasks(tasks.filter((task) => task.task_id !== taskId));
    } catch (err) {
      console.error("Error deleting task:", err);
      alert(`Failed to delete: ${err.message}`);
    }
  };

  const handleShare = async (taskId, event) => {
    event.stopPropagation();

    try {
      const response = await fetch(
        `http://16.170.208.132:2135/api/video/${taskId}/share`,
        {
          method: "POST",
        },
      );

      if (!response.ok) {
        throw new Error("Failed to create share link");
      }

      const data = await response.json();
      const shareUrl = `${window.location.origin}${data.share_url}`;

      // Copy to clipboard
      await navigator.clipboard.writeText(shareUrl);
      alert(t("history.shareSuccess"));
    } catch (err) {
      console.error("Error creating share link:", err);
      alert(`${t("history.errors.shareFailed")}: ${err.message}`);
    }
  };

  const handleTaskClick = (taskId) => {
    navigate(`/video/${taskId}`);
  };

  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    const date = new Date(dateString);
    return date.toLocaleString("ru-RU", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const formatDuration = (seconds) => {
    if (!seconds) return "N/A";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, "0")}`;
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return "N/A";
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(1)} MB`;
  };

  const getStatusBadge = (status) => {
    const badges = {
      completed: {
        text: t("processing.status.completed"),
        class: "status-completed",
      },
      processing: {
        text: t("processing.status.processing"),
        class: "status-processing",
      },
      pending: {
        text: t("processing.status.pending"),
        class: "status-pending",
      },
      failed: { text: t("processing.status.failed"), class: "status-failed" },
    };

    const badge = badges[status] || { text: status, class: "status-unknown" };
    return <span className={`status-badge ${badge.class}`}>{badge.text}</span>;
  };

  const sortedTasks = () => {
    const sorted = [...tasks];

    switch (sortBy) {
      case "newest":
        sorted.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        break;
      case "oldest":
        sorted.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
        break;
      case "duration":
        sorted.sort((a, b) => (b.duration || 0) - (a.duration || 0));
        break;
      default:
        break;
    }

    return sorted;
  };

  return (
    <div className="history-page">
      <div className="history-container">
        <div className="history-header">
          <h1>{t("history.title")}</h1>
          <button className="new-upload-btn" onClick={() => navigate("/")}>
            {t("history.newUpload")}
          </button>
        </div>

        <div className="history-controls">
          <div className="filter-group">
            <label>{t("history.filter")}:</label>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">{t("history.filters.all")}</option>
              <option value="completed">
                {t("history.filters.completed")}
              </option>
              <option value="processing">
                {t("history.filters.processing")}
              </option>
              <option value="failed">{t("history.filters.failed")}</option>
            </select>
          </div>

          <div className="filter-group">
            <label>{t("history.sort")}:</label>
            <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
              <option value="newest">{t("history.sortOptions.newest")}</option>
              <option value="oldest">{t("history.sortOptions.oldest")}</option>
              <option value="duration">
                {t("history.sortOptions.duration")}
              </option>
            </select>
          </div>

          <button className="refresh-btn" onClick={fetchHistory}>
            {t("history.refresh")}
          </button>
        </div>

        {loading && (
          <div className="history-loading">
            <div className="spinner"></div>
            <p>{t("common.loading")}</p>
          </div>
        )}

        {error && (
          <div className="history-error">
            <p>
              ❌ {t("common.error")}: {error}
            </p>
            <button onClick={fetchHistory}>{t("errors.tryAgain")}</button>
          </div>
        )}

        {!loading && !error && tasks.length === 0 && (
          <div className="history-empty">
            <h2>{t("history.empty.title")}</h2>
            <p>{t("history.empty.message")}</p>
            <button onClick={() => navigate("/")}>
              {t("history.empty.action")}
            </button>
          </div>
        )}

        {!loading && !error && tasks.length > 0 && (
          <div className="history-grid">
            {sortedTasks().map((task) => (
              <div
                key={task.task_id}
                className={`history-card ${task.status === "completed" ? "clickable" : ""}`}
                onClick={() =>
                  task.status === "completed" && handleTaskClick(task.task_id)
                }
              >
                <div className="card-header">
                  <div className="card-title-row">
                    <h3 title={task.video_title || task.original_filename}>
                      {task.video_title || task.original_filename || "Untitled"}
                    </h3>
                    {getStatusBadge(task.status)}
                  </div>
                  <div className="card-actions">
                    {task.status === "completed" && (
                      <button
                        className="action-btn share-btn"
                        onClick={(e) => handleShare(task.task_id, e)}
                        title="Поделиться"
                      >
                        🔗
                      </button>
                    )}
                    <button
                      className="action-btn delete-btn"
                      onClick={(e) => handleDelete(task.task_id, e)}
                      title="Удалить"
                    >
                      🗑️
                    </button>
                  </div>
                </div>

                <div className="card-info">
                  <div className="info-row">
                    <span className="info-label">
                      📅 {t("history.card.created")}:
                    </span>
                    <span className="info-value">
                      {formatDate(task.created_at)}
                    </span>
                  </div>

                  {task.duration && (
                    <div className="info-row">
                      <span className="info-label">
                        ⏱️ {t("history.card.duration")}:
                      </span>
                      <span className="info-value">
                        {formatDuration(task.duration)}
                      </span>
                    </div>
                  )}

                  {task.file_size && (
                    <div className="info-row">
                      <span className="info-label">
                        💾 {t("history.card.size")}:
                      </span>
                      <span className="info-value">
                        {formatFileSize(task.file_size)}
                      </span>
                    </div>
                  )}

                  {task.total_segments && (
                    <div className="info-row">
                      <span className="info-label">
                        📝 {t("history.card.segments")}:
                      </span>
                      <span className="info-value">{task.total_segments}</span>
                    </div>
                  )}

                  {task.total_quizzes && (
                    <div className="info-row">
                      <span className="info-label">
                        ❓ {t("history.card.quizzes")}:
                      </span>
                      <span className="info-value">{task.total_quizzes}</span>
                    </div>
                  )}

                  {task.status === "processing" &&
                    task.progress !== undefined && (
                      <div className="progress-bar-container">
                        <div
                          className="progress-bar"
                          style={{ width: `${task.progress}%` }}
                        ></div>
                        <span className="progress-text">
                          {Math.round(task.progress)}%
                        </span>
                      </div>
                    )}

                  {task.status === "completed" && (
                    <div className="completed-date">
                      ✅ {t("history.card.completed")}:{" "}
                      {formatDate(task.completed_at)}
                    </div>
                  )}

                  {task.is_public && (
                    <div className="public-badge">
                      🌐 {t("history.card.publicLink")}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default HistoryPage;

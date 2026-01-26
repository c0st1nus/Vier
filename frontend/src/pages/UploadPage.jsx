// Upload Page - Main page for video upload
import React, { useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "../contexts/LanguageContext";
import "./UploadPage.css";

const API_BASE_URL = "http://16.171.11.38:2135/api";

const UploadPage = () => {
  const navigate = useNavigate();
  const { language } = useTranslation();
  const [uploadMode, setUploadMode] = useState("file"); // 'file' or 'url'
  const [url, setUrl] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef(null);

  // Supported video formats
  const SUPPORTED_FORMATS = [
    ".mp4",
    ".avi",
    ".mov",
    ".mkv",
    ".webm",
    ".flv",
    ".wmv",
  ];
  const MAX_FILE_SIZE = 500 * 1024 * 1024; // 500 MB

  // Handle drag events
  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  // Handle file drop
  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    setError(null);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelection(e.dataTransfer.files[0]);
    }
  };

  // Validate file
  const validateFile = (file) => {
    // Check file type
    const fileExtension = "." + file.name.split(".").pop().toLowerCase();
    if (!SUPPORTED_FORMATS.includes(fileExtension)) {
      return `Unsupported file format. Please upload: ${SUPPORTED_FORMATS.join(", ")}`;
    }

    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      return `File size exceeds 500 MB limit. Your file is ${(file.size / (1024 * 1024)).toFixed(2)} MB`;
    }

    return null;
  };

  // Handle file selection
  const handleFileSelection = (file) => {
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    setError(null);
  };

  // Handle file input change
  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelection(e.target.files[0]);
    }
  };

  // Handle URL validation
  const validateUrl = (urlString) => {
    try {
      const urlObj = new URL(urlString);
      // Check if it's a valid HTTP/HTTPS URL
      if (!["http:", "https:"].includes(urlObj.protocol)) {
        return "Please enter a valid HTTP or HTTPS URL";
      }
      return null;
    } catch {
      return "Please enter a valid URL";
    }
  };

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      if (uploadMode === "file") {
        if (!selectedFile) {
          setError("Please select a video file");
          setIsLoading(false);
          return;
        }

        // Upload file
        const formData = new FormData();
        formData.append("file", selectedFile);

        const response = await fetch(`${API_BASE_URL}/upload/file`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Failed to upload file");
        }

        const data = await response.json();

        // Redirect to video page
        navigate(`/video/${data.task_id}`);
      } else {
        if (!url.trim()) {
          setError("Please enter a video URL");
          setIsLoading(false);
          return;
        }

        const urlError = validateUrl(url);
        if (urlError) {
          setError(urlError);
          setIsLoading(false);
          return;
        }

        // Submit URL
        const response = await fetch(`${API_BASE_URL}/video/upload/url`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ url, language }),
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Failed to submit URL");
        }

        const data = await response.json();

        // Redirect to video page
        navigate(`/video/${data.task_id}`);
      }
    } catch (err) {
      console.error("Upload error:", err);
      setError(err.message || "An error occurred during upload");
      setIsLoading(false);
    }
  };

  // Format file size
  const formatFileSize = (bytes) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + " " + sizes[i];
  };

  return (
    <div className="upload-page">
      <div className="container container-sm">
        <div className="upload-container">
          {/* Hero Section */}
          <div className="upload-hero">
            <h2 className="upload-title">Upload Your Video</h2>
            <p className="upload-description">
              Transform any educational video into interactive quizzes with AI.
              Upload a file or paste a video URL to get started.
            </p>
          </div>

          {/* Upload Mode Selector */}
          <div className="mode-selector">
            <button
              type="button"
              className={`mode-button ${uploadMode === "file" ? "active" : ""}`}
              onClick={() => {
                setUploadMode("file");
                setError(null);
              }}
              disabled={isLoading}
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
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
              Upload File
            </button>
            <button
              type="button"
              className={`mode-button ${uploadMode === "url" ? "active" : ""}`}
              onClick={() => {
                setUploadMode("url");
                setError(null);
              }}
              disabled={isLoading}
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
                  d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                />
              </svg>
              Video URL
            </button>
          </div>

          {/* Upload Form */}
          <form onSubmit={handleSubmit} className="upload-form">
            {uploadMode === "file" ? (
              <div className="file-upload-section">
                {/* Drag and Drop Area */}
                <div
                  className={`drop-zone ${dragActive ? "drag-active" : ""} ${selectedFile ? "has-file" : ""}`}
                  onDragEnter={handleDrag}
                  onDragLeave={handleDrag}
                  onDragOver={handleDrag}
                  onDrop={handleDrop}
                  onClick={() => !isLoading && fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept={SUPPORTED_FORMATS.join(",")}
                    onChange={handleFileChange}
                    disabled={isLoading}
                    style={{ display: "none" }}
                  />

                  {selectedFile ? (
                    <div className="file-info">
                      <div className="file-icon">
                        <svg
                          width="48"
                          height="48"
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
                      </div>
                      <div className="file-details">
                        <p className="file-name">{selectedFile.name}</p>
                        <p className="file-size">
                          {formatFileSize(selectedFile.size)}
                        </p>
                      </div>
                      {!isLoading && (
                        <button
                          type="button"
                          className="file-remove"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedFile(null);
                            setError(null);
                          }}
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
                              d="M6 18L18 6M6 6l12 12"
                            />
                          </svg>
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="drop-zone-content">
                      <div className="drop-zone-icon">
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
                            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                          />
                        </svg>
                      </div>
                      <p className="drop-zone-text">
                        <strong>Click to upload</strong> or drag and drop
                      </p>
                      <p className="drop-zone-hint">
                        {SUPPORTED_FORMATS.join(", ").toUpperCase()} (Max 500
                        MB)
                      </p>
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="url-upload-section">
                <div className="input-group">
                  <div className="input-icon">
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
                        d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                      />
                    </svg>
                  </div>
                  <input
                    type="url"
                    className="url-input"
                    placeholder="https://www.youtube.com/watch?v=..."
                    value={url}
                    onChange={(e) => {
                      setUrl(e.target.value);
                      setError(null);
                    }}
                    disabled={isLoading}
                  />
                </div>
                <p className="url-hint">
                  Supports YouTube, Vimeo, and most video hosting platforms
                </p>
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div className="error-message">
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
                    d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                {error}
              </div>
            )}

            {/* Submit Button */}
            <button
              type="submit"
              className="submit-button"
              disabled={
                isLoading ||
                (uploadMode === "file" && !selectedFile) ||
                (uploadMode === "url" && !url.trim())
              }
            >
              {isLoading ? (
                <>
                  <span className="spinner"></span>
                  Processing...
                </>
              ) : (
                <>
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
                      d="M13 10V3L4 14h7v7l9-11h-7z"
                    />
                  </svg>
                  Generate Quiz
                </>
              )}
            </button>
          </form>

          {/* Info Cards */}
          <div className="info-cards">
            <div className="info-card">
              <div className="info-card-icon">
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
                    d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                  />
                </svg>
              </div>
              <h3 className="info-card-title">AI-Powered</h3>
              <p className="info-card-text">
                Advanced AI analyzes video content and generates relevant quiz
                questions
              </p>
            </div>

            <div className="info-card">
              <div className="info-card-icon">
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
                    d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <h3 className="info-card-title">Fast Processing</h3>
              <p className="info-card-text">
                Get your quiz ready in minutes with optimized AI processing
              </p>
            </div>

            <div className="info-card">
              <div className="info-card-icon">
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
              <h3 className="info-card-title">Interactive</h3>
              <p className="info-card-text">
                Engaging quizzes that make learning fun and effective
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default UploadPage;

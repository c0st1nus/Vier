// Custom hook for managing video processing workflow
import { useState, useCallback, useRef } from "react";
import apiService from "../services/api";

/**
 * Custom hook for video processing workflow
 * Manages upload, polling, and result fetching
 */
export const useVideoProcessing = () => {
  const [state, setState] = useState({
    taskId: null,
    status: "idle", // idle, uploading, processing, completed, failed
    progress: 0,
    currentStage: "",
    uploadProgress: 0,
    segments: null,
    videoUrl: null,
    error: null,
  });

  const abortControllerRef = useRef(null);
  const pollingIntervalRef = useRef(null);

  /**
   * Reset state to initial
   */
  const reset = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setState({
      taskId: null,
      status: "idle",
      progress: 0,
      currentStage: "",
      uploadProgress: 0,
      segments: null,
      videoUrl: null,
      error: null,
    });
  }, []);

  /**
   * Update state immutably
   */
  const updateState = useCallback((updates) => {
    setState((prev) => ({ ...prev, ...updates }));
  }, []);

  /**
   * Upload a video file
   */
  const uploadFile = useCallback(
    async (file) => {
      reset();
      updateState({ status: "uploading" });

      try {
        const response = await apiService.uploadFile(file, (progress) => {
          updateState({ uploadProgress: Math.round(progress) });
        });

        updateState({
          taskId: response.task_id,
          status: "processing",
          uploadProgress: 100,
        });

        // Start polling for status
        await startPolling(response.task_id);
      } catch (error) {
        updateState({
          status: "failed",
          error: error.message || "Failed to upload file",
        });
        throw error;
      }
    },
    [reset, updateState],
  );

  /**
   * Submit a video URL
   */
  const submitUrl = useCallback(
    async (url) => {
      reset();
      updateState({ status: "uploading" });

      try {
        const response = await apiService.uploadUrl(url);

        updateState({
          taskId: response.task_id,
          status: "processing",
          uploadProgress: 100,
        });

        // Start polling for status
        await startPolling(response.task_id);
      } catch (error) {
        updateState({
          status: "failed",
          error: error.message || "Failed to submit URL",
        });
        throw error;
      }
    },
    [reset, updateState],
  );

  /**
   * Start polling for processing status
   */
  const startPolling = useCallback(
    async (taskId) => {
      const poll = async () => {
        try {
          const statusData = await apiService.getStatus(taskId);

          updateState({
            progress: statusData.progress || 0,
            currentStage: statusData.current_stage || "",
          });

          if (statusData.status === "completed") {
            // Fetch segments
            const segmentsData = await apiService.getSegments(taskId);
            updateState({
              status: "completed",
              segments: segmentsData.segments || segmentsData,
              videoUrl: segmentsData.video_url || `/api/video/${taskId}/file`,
              progress: 100,
            });

            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current);
              pollingIntervalRef.current = null;
            }
          } else if (statusData.status === "failed") {
            updateState({
              status: "failed",
              error: "Processing failed on the server",
            });

            if (pollingIntervalRef.current) {
              clearInterval(pollingIntervalRef.current);
              pollingIntervalRef.current = null;
            }
          }
        } catch (error) {
          updateState({
            status: "failed",
            error: error.message || "Failed to get status",
          });

          if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
          }
        }
      };

      // Start interval polling immediately
      pollingIntervalRef.current = setInterval(poll, 2000);

      // Also do initial poll
      await poll();
    },
    [updateState],
  );

  /**
   * Fetch results for an existing task ID
   */
  const fetchResults = useCallback(
    async (taskId) => {
      reset();
      updateState({ status: "processing", taskId });

      try {
        const statusData = await apiService.getStatus(taskId);

        if (statusData.status === "completed") {
          const segmentsData = await apiService.getSegments(taskId);
          updateState({
            status: "completed",
            segments: segmentsData.segments || segmentsData,
            videoUrl: segmentsData.video_url || `/api/video/${taskId}/file`,
            progress: 100,
          });
        } else if (statusData.status === "failed") {
          updateState({
            status: "failed",
            error: "Processing failed",
          });
        } else {
          updateState({
            progress: statusData.progress || 0,
            currentStage: statusData.current_stage || "",
          });
          await startPolling(taskId);
        }
      } catch (error) {
        updateState({
          status: "failed",
          error: error.message || "Failed to fetch results",
        });
        throw error;
      }
    },
    [reset, updateState, startPolling],
  );

  return {
    // State
    taskId: state.taskId,
    status: state.status,
    progress: state.progress,
    currentStage: state.currentStage,
    uploadProgress: state.uploadProgress,
    segments: state.segments,
    videoUrl: state.videoUrl,
    error: state.error,

    // State checks
    isIdle: state.status === "idle",
    isUploading: state.status === "uploading",
    isProcessing: state.status === "processing",
    isCompleted: state.status === "completed",
    isFailed: state.status === "failed",
    isLoading: state.status === "uploading" || state.status === "processing",

    // Actions
    uploadFile,
    submitUrl,
    fetchResults,
    reset,
  };
};

export default useVideoProcessing;

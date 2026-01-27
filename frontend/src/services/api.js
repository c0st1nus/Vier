// API Service for backend communication
export const API_BASE_URL =
  import.meta.env.VITE_API_URL || "http://16.171.11.38:2135";

class ApiService {
  constructor() {
    this.baseUrl = API_BASE_URL;
  }

  /**
   * Upload a video file
   * @param {File} file - The video file to upload
   * @param {Function} onProgress - Progress callback
   * @returns {Promise<{task_id: string, status: string, message: string}>}
   */
  async uploadFile(file, onProgress = null) {
    const formData = new FormData();
    formData.append("file", file);

    const xhr = new XMLHttpRequest();

    return new Promise((resolve, reject) => {
      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable && onProgress) {
          const percentComplete = (e.loaded / e.total) * 100;
          onProgress(percentComplete);
        }
      });

      xhr.addEventListener("load", () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const response = JSON.parse(xhr.responseText);
            resolve(response);
          } catch (err) {
            reject(new Error("Failed to parse response"));
          }
        } else {
          try {
            const err = JSON.parse(xhr.responseText);
            reject(new Error(err.detail || "Upload failed"));
          } catch {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        }
      });

      xhr.addEventListener("error", () => {
        reject(new Error("Network error during upload"));
      });

      xhr.addEventListener("abort", () => {
        reject(new Error("Upload aborted"));
      });

      xhr.open("POST", `${this.baseUrl}/api/upload/file`);
      xhr.send(formData);
    });
  }

  /**
   * Submit a video URL
   * @param {string} url - The video URL (e.g., YouTube)
   * @param {string} language - Language for quiz generation (en, ru, kk)
   * @returns {Promise<{task_id: string, status: string}>}
   */
  async uploadUrl(url, language = "en") {
    try {
      const response = await fetch(`${this.baseUrl}/api/video/upload/url`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ url, language }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to submit URL");
      }

      return await response.json();
    } catch (error) {
      if (error instanceof TypeError) {
        throw new Error("Network error. Please check your connection.");
      }
      throw error;
    }
  }

  /**
   * Get processing status for a task
   * @param {string} taskId - The task ID
   * @returns {Promise<{task_id: string, status: string, progress: number, current_stage: string}>}
   */
  async getStatus(taskId) {
    try {
      const response = await fetch(
        `${this.baseUrl}/api/video/${taskId}/status`,
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to get status");
      }

      return await response.json();
    } catch (error) {
      if (error instanceof TypeError) {
        throw new Error("Network error. Please check your connection.");
      }
      throw error;
    }
  }

  /**
   * Get processed segments with quizzes
   * @param {string} taskId - The task ID
   * @returns {Promise<Array<{start_time: number, end_time: number, topic_title: string, short_summary: string, keywords: Array<string>, quizzes: Array}>>}
   */
  async getSegments(taskId) {
    try {
      const response = await fetch(
        `${this.baseUrl}/api/video/${taskId}/segments`,
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "Failed to get segments");
      }

      const data = await response.json();
      // API returns {task_id, segments, total_duration, video_title}
      // Return full data including video URL
      return {
        segments: data.segments || [],
        video_url: `${this.baseUrl}/api/video/${taskId}/file`,
        task_id: data.task_id,
        total_duration: data.total_duration,
        video_title: data.video_title,
      };
    } catch (error) {
      if (error instanceof TypeError) {
        throw new Error("Network error. Please check your connection.");
      }
      throw error;
    }
  }

  /**
   * Poll status until processing is complete or fails
   * @param {string} taskId - The task ID
   * @param {Function} onProgress - Progress callback
   * @param {number} interval - Polling interval in ms
   * @returns {Promise<{task_id: string, status: string, progress: number, current_stage: string}>}
   */
  async pollStatus(taskId, onProgress = null, interval = 2000) {
    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          const status = await this.getStatus(taskId);

          if (onProgress) {
            onProgress(status);
          }

          if (status.status === "completed") {
            resolve(status);
          } else if (status.status === "failed") {
            reject(new Error("Processing failed"));
          } else {
            setTimeout(poll, interval);
          }
        } catch (error) {
          reject(error);
        }
      };

      poll();
    });
  }

  /**
   * Check if API is available
   * @returns {Promise<boolean>}
   */
  async checkHealth() {
    try {
      const response = await fetch(`${this.baseUrl}/health`, {
        method: "GET",
      });
      return response.ok;
    } catch {
      return false;
    }
  }
}

// Export singleton instance
const apiService = new ApiService();
export default apiService;

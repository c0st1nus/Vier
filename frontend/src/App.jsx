import React from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";
import Header from "./components/Header";
import UploadPage from "./pages/UploadPage";
import VideoPage from "./pages/VideoPage";
import HistoryPage from "./pages/HistoryPage";
import SharedVideoPage from "./pages/SharedVideoPage";
import "./App.css";

function App() {
  return (
    <Router>
      <div className="app">
        <Header />
        <main className="main-content">
          <Routes>
            {/* Upload page - главная страница */}
            <Route path="/" element={<UploadPage />} />

            {/* Video page - показывает статус обработки и результаты */}
            <Route path="/video/:taskId" element={<VideoPage />} />

            {/* History page - история всех видео */}
            <Route path="/history" element={<HistoryPage />} />

            {/* Shared video page - публичный доступ по токену */}
            <Route path="/shared/:shareToken" element={<SharedVideoPage />} />

            {/* Redirect old routes */}
            <Route
              path="/results/:taskId"
              element={<Navigate to="/video/:taskId" replace />}
            />
          </Routes>
        </main>
        <footer className="footer">
          <div className="container">
            <div className="footer-content">
              <p className="footer-text">
                © {new Date().getFullYear()} AI Video Quiz Generator. Powered
                by open-source AI.
              </p>
              <div className="footer-links">
                <a href="/history" className="footer-link">
                  История
                </a>
                <span className="footer-divider">•</span>
                <a href="#" className="footer-link">
                  Privacy Policy
                </a>
                <span className="footer-divider">•</span>
                <a href="#" className="footer-link">
                  Terms of Service
                </a>
                <span className="footer-divider">•</span>
                <a href="#" className="footer-link">
                  About
                </a>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </Router>
  );
}

export default App;

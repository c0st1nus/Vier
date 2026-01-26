// Header component with branding and navigation
import { Link } from "react-router-dom";
import { useTranslation } from "../contexts/LanguageContext";
import LanguageSwitcher from "./LanguageSwitcher";
import { useAuth } from "../contexts/AuthContext.jsx";
import "./Header.css";

const Header = () => {
  const { t } = useTranslation();
  const { user } = useAuth();

  return (
    <header className="header">
      <div className="container">
        <div className="header-content">
          <Link
            to="/"
            className="header-brand"
            style={{ textDecoration: "none", color: "inherit" }}
          >
            <div className="brand-icon">
              <svg
                width="32"
                height="32"
                viewBox="0 0 32 32"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                aria-label="Logo"
              >
                <rect
                  x="4"
                  y="4"
                  width="24"
                  height="24"
                  rx="4"
                  fill="currentColor"
                  opacity="0.2"
                />
                <path
                  d="M10 13L16 19L22 13"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <circle cx="16" cy="16" r="2" fill="currentColor" />
              </svg>
            </div>
            <div className="brand-text">
              <h1 className="brand-title">{t("header.title")}</h1>
              <p className="brand-subtitle">{t("upload.subtitle")}</p>
            </div>
          </Link>

          <nav className="header-nav">
            <Link to="/" className="nav-link">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                aria-label="Home icon"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
                />
              </svg>
              {t("header.upload")}
            </Link>
            <Link to="/history" className="nav-link">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                aria-label="History icon"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              {t("header.history")}
            </Link>
            <LanguageSwitcher />
            {user ? (
              <Link to="/history" className="nav-link">
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  aria-label="User icon"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M5.121 17.804A9 9 0 0112 15a9 9 0 016.879 2.804M15 11a3 3 0 10-6 0 3 3 0 006 0z"
                  />
                </svg>
                {user.email || t("header.about")}
              </Link>
            ) : (
              <Link to="/auth" className="nav-link">
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  aria-label="Auth icon"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M5 12h14M12 5l7 7-7 7"
                  />
                </svg>
                Войти
              </Link>
            )}
          </nav>
        </div>
      </div>
    </header>
  );
};

export default Header;

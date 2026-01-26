import React from "react";
import { useTranslation } from "../contexts/LanguageContext";
import "./LanguageSwitcher.css";

const LanguageSwitcher = () => {
  const { language, changeLanguage } = useTranslation();

  const languages = [
    { code: "ru", name: "Русский", flag: "🇷🇺" },
    { code: "en", name: "English", flag: "🇬🇧" },
    { code: "kk", name: "Қазақша", flag: "🇰🇿" },
  ];

  return (
    <div className="language-switcher">
      <button className="language-button">
        <span className="current-language">
          {languages.find((lang) => lang.code === language)?.flag || "🌐"}
        </span>
      </button>
      <div className="language-dropdown">
        {languages.map((lang) => (
          <button
            key={lang.code}
            className={`language-option ${language === lang.code ? "active" : ""}`}
            onClick={() => changeLanguage(lang.code)}
          >
            <span className="language-flag">{lang.flag}</span>
            <span className="language-name">{lang.name}</span>
            {language === lang.code && <span className="checkmark">✓</span>}
          </button>
        ))}
      </div>
    </div>
  );
};

export default LanguageSwitcher;

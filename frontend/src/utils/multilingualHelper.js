/**
 * Helper functions for working with multilingual video data
 */

/**
 * Get translation for a specific language from multilingual object
 * @param {Object} translations - Object with translations {ru: {...}, en: {...}, kk: {...}}
 * @param {string} language - Language code (ru, en, kk)
 * @param {string} fallbackLang - Fallback language if requested language not found
 * @returns {Object} Translation object for the specified language
 */
export const getTranslation = (translations, language, fallbackLang = "ru") => {
  if (!translations || typeof translations !== "object") {
    return null;
  }

  // Try to get requested language
  if (translations[language]) {
    return translations[language];
  }

  // Try fallback language
  if (translations[fallbackLang]) {
    return translations[fallbackLang];
  }

  // Return first available translation
  const availableLanguages = Object.keys(translations);
  if (availableLanguages.length > 0) {
    return translations[availableLanguages[0]];
  }

  return null;
};

/**
 * Get quiz translation for a specific language
 * @param {Object} quiz - Quiz object with translations
 * @param {string} language - Language code (ru, en, kk)
 * @returns {Object} Quiz translation {question, options, explanation}
 */
export const getQuizTranslation = (quiz, language) => {
  if (!quiz || !quiz.translations) {
    // Fallback for old format (backward compatibility)
    return {
      question: quiz?.question || "Question?",
      options: quiz?.options || ["A", "B", "C", "D"],
      explanation: quiz?.explanation || null,
    };
  }

  const translation = getTranslation(quiz.translations, language);

  if (!translation) {
    return {
      question: "Question not available",
      options: ["A", "B", "C", "D"],
      explanation: null,
    };
  }

  return {
    question: translation.question || "Question?",
    options: translation.options || ["A", "B", "C", "D"],
    explanation: translation.explanation || null,
  };
};

/**
 * Get segment translation for a specific language
 * @param {Object} segment - Segment object with translations
 * @param {string} language - Language code (ru, en, kk)
 * @returns {Object} Segment translation {topic_title, short_summary}
 */
export const getSegmentTranslation = (segment, language) => {
  if (!segment || !segment.translations) {
    // Fallback for old format (backward compatibility)
    return {
      topic_title: segment?.topic_title || "Segment",
      short_summary: segment?.short_summary || "Video content segment",
    };
  }

  const translation = getTranslation(segment.translations, language);

  if (!translation) {
    return {
      topic_title: "Segment",
      short_summary: "Video content segment",
    };
  }

  return {
    topic_title: translation.topic_title || "Segment",
    short_summary: translation.short_summary || "Video content segment",
  };
};

/**
 * Check if data has multilingual support
 * @param {Object} data - Quiz or segment object
 * @returns {boolean} True if data has translations
 */
export const hasMultilingualSupport = (data) => {
  return data && data.translations && typeof data.translations === "object";
};

/**
 * Get available languages for a multilingual object
 * @param {Object} data - Quiz or segment object with translations
 * @returns {string[]} Array of available language codes
 */
export const getAvailableLanguages = (data) => {
  if (!hasMultilingualSupport(data)) {
    return [];
  }

  return Object.keys(data.translations).filter(
    (lang) => lang === "ru" || lang === "en" || lang === "kk"
  );
};

/**
 * Validate that all required languages are present
 * @param {Object} data - Quiz or segment object with translations
 * @param {string[]} requiredLanguages - Array of required language codes
 * @returns {boolean} True if all required languages are present
 */
export const hasAllLanguages = (
  data,
  requiredLanguages = ["ru", "en", "kk"]
) => {
  if (!hasMultilingualSupport(data)) {
    return false;
  }

  return requiredLanguages.every((lang) => data.translations[lang]);
};

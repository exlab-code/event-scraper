/**
 * Category mappings from machine-readable IDs to human-readable names
 * This file is generated from event_categories_config.json
 */

export const categoryMappings = {
  "datenschutz_sicherheit": "Datenschutz & Sicherheit",
  "ki_nonprofit": "KI für Non-Profits",
  "digitale_kommunikation": "Digitale Kommunikation & Social Media",
  "foerderung_finanzierung": "Förderprogramme & Finanzierung",
  "ehrenamt_engagement": "Ehrenamt & Engagemententwicklung",
  "daten_projektmanagement": "Daten & Projektmanagement",
  "weiterbildung_qualifizierung": "Weiterbildung & Qualifizierung",
  "digitale_transformation": "Digitale Transformation & Strategie",
  "tools_anwendungen": "Tools & Anwendungen"
};

/**
 * Get the human-readable name for a category ID
 * @param {string} categoryId - The machine-readable category ID
 * @returns {string} - The human-readable category name or the original ID if not found
 */
export function getCategoryName(categoryId) {
  if (!categoryId) return '';
  return categoryMappings[categoryId] || categoryId;
}

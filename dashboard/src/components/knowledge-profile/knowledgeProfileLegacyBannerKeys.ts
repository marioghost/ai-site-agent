/** i18n keys for the Knowledge Profile legacy migration banner (RFC-100 Step 016). */
export const KNOWLEDGE_PROFILE_LEGACY_BANNER_KEYS = [
  "knowledge_profile.legacy_banner.title",
  "knowledge_profile.legacy_banner.intro",
  "knowledge_profile.legacy_banner.available",
  "knowledge_profile.legacy_banner.future",
  "knowledge_profile.legacy_banner.guidance",
] as const;

export type KnowledgeProfileLegacyBannerKey =
  (typeof KNOWLEDGE_PROFILE_LEGACY_BANNER_KEYS)[number];

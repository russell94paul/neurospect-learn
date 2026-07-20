// ============================================================
// Auth (mirrors backend app/schemas/auth.py)
// ============================================================

export interface User {
  id: string;
  discord_id: string;
  discord_username: string | null;
  discord_avatar_url: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

// ============================================================
// Content API (mirrors backend app/schemas/content.py)
// ============================================================

export interface ContentPageSummary {
  slug: string;
  title: string;
  category: string | null;
  u_stage: string | null;
  tier: string | null;
  label: string | null;
  source_path: string | null;
}

export interface ConceptBadge {
  code: string | null;
  tier: string | null;
  label: string | null;
  watch_only: boolean;
}

export interface ContentPageDetail extends ContentPageSummary {
  body: string;
  tags: string[] | null;
  wikilink_targets: string[] | null;
  badge: ConceptBadge | null;
}

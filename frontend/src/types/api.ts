export type SyncStatus = "never_synced" | "running" | "paused" | "failed" | "synced";

export interface Repository {
  id: string;
  full_name: string;
  html_url: string;
  description: string | null;
  last_synced_at: string | null;
  last_sync_error: string | null;
  sync_status: SyncStatus;
  created_at: string;
}

export interface RepositoryDetail extends Repository {
  discussion_count: number;
  comment_count: number;
  decision_count: number;
}

export interface ImportEstimate {
  items: number;
  api_calls: number;
  token_recommended: boolean;
  message: string | null;
}

export interface RepositoryRegistered {
  repository: Repository;
  estimate: ImportEstimate;
}

export interface StartedJob {
  repository_id: string;
  message: string;
}

export interface Decision {
  id: string;
  title: string;
  decision: string;
  rationale: string[];
  alternatives: { approach: string; rejection_reason: string }[];
  evidence: { excerpt: string; source_url: string }[];
}

export interface Citation {
  content: string;
  source_url: string;
  discussion_number: number;
  discussion_title: string;
  author: string | null;
}

export interface AskResponse {
  question: string;
  status: "answered" | "insufficient_evidence";
  answer: string | null;
  citations: Citation[];
  limitations: string | null;
}

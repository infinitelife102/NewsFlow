// ============================================
// NewsFlow Frontend Types
// ============================================

export interface Article {
  id: string;
  title: string;
  content: string;
  summary?: string;
  url: string;
  source: string;
  author?: string;
  published_at?: string;
  cluster_id?: string;
  /** When article is in a cluster that has been summarized (from Clusters tab Summarize). */
  cluster_name?: string;
  ai_summary?: string;
  ai_key_points?: string[];
  keywords?: string[];
  status: "active" | "archived" | "deleted";
  created_at: string;
  updated_at: string;
}

export interface Cluster {
  id: string;
  name: string;
  description?: string;
  article_count: number;
  similarity_threshold: number;
  status: "active" | "merged" | "archived";
  created_at: string;
  updated_at: string;
  centroid?: number[];
  // Joined fields
  articles?: Article[];
  summary?: string;
  key_points?: string[];
  impact?: string;
  use_cases?: string[];
}

export interface Summary {
  id: string;
  cluster_id: string;
  content: string;
  key_points: string[];
  impact?: string;
  use_cases?: string[];
  model_used?: string;
  tokens_used?: number;
  created_at: string;
  updated_at: string;
}

export interface CrawlHistoryItem {
  id: string;
  source: string;
  url?: string;
  status: "success" | "failed" | "pending" | "running";
  articles_found: number;
  articles_added: number;
  error_message?: string;
  started_at: string;
  completed_at?: string;
  duration_ms?: number;
}

export interface SystemStats {
  articles: {
    total: number;
  };
  clusters: {
    active: number;
  };
  summaries: {
    total: number;
  };
  recent_crawls: CrawlHistoryItem[];
}

export interface HealthStatus {
  status: string;
  database: string;
  version: string;
  timestamp: string;
  environment: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
  meta?: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

export type ViewMode = "articles" | "clusters";
export type SortOption = "newest" | "oldest" | "source";

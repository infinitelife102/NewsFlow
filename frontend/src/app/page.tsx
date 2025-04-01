"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast, Toaster } from "sonner";

import { Header } from "@/components/layout/Header";
import { ActionBar } from "@/components/ActionBar";
import { NewsCard } from "@/components/NewsCard";
import { ClusterCard } from "@/components/ClusterCard";
import { AdminPanel } from "@/components/AdminPanel";
import { Button } from "@/components/ui/Button";
import { Loader2, AlertCircle, ArrowLeft } from "lucide-react";

import {
  fetchArticles,
  fetchClusters,
  fetchStats,
  fetchCrawlStatus,
  fetchClusterStatus,
  triggerCrawl,
  triggerClustering,
  summarizeArticle,
  summarizeArticles,
  runFullPipeline,
  resetClustering,
  deleteArticle,
  deleteCluster,
  deleteArticlesBatch,
  deleteAllArticles,
} from "@/lib/api";
import type { Article, Cluster } from "@/types";

const CRAWL_POLL_INTERVAL_MS = 1500;
const TASK_POLL_INTERVAL_MS = 1500;

function formatDuration(ms: number): string {
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`;
  return `${ms}ms`;
}

export default function HomePage() {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<"articles" | "clusters">("articles");
  const [isAdminOpen, setIsAdminOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [clusterFilterId, setClusterFilterId] = useState<string | null>(null);
  const [summarizingArticleId, setSummarizingArticleId] = useState<string | null>(null);
  const [summarizeVisibleInProgress, setSummarizeVisibleInProgress] = useState(false);
  const [crawlInProgress, setCrawlInProgress] = useState(false);
  const [clusterInProgress, setClusterInProgress] = useState(false);
  const [runAllInProgress, setRunAllInProgress] = useState(false);

  // Prevent duplicate "finished" toasts (e.g. strict mode or rapid poll)
  const crawlFinishedToastShown = useRef(false);
  const clusterFinishedToastShown = useRef(false);
  const runAllFinishedToastShown = useRef(false);
  const crawlStartTime = useRef<number>(0);
  const clusterStartTime = useRef<number>(0);
  const runAllStartTime = useRef<number>(0);

  // ============================================
  // DATA FETCHING
  // ============================================

  const PER_PAGE = 21;

  const {
    data: articlesData,
    isLoading: isLoadingArticles,
    error: articlesError,
    isFetching: isFetchingArticles,
    refetch: refetchArticles,
  } = useQuery({
    queryKey: ["articles", page, clusterFilterId],
    queryFn: () => fetchArticles(page, PER_PAGE, undefined, clusterFilterId ?? undefined),
    retry: 2,
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 5000),
    staleTime: 5 * 1000, // 5s so UI stays in sync with DB after Fetch News / Delete
  });

  const {
    data: clustersData,
    isLoading: isLoadingClusters,
    error: clustersError,
  } = useQuery({
    queryKey: ["clusters", page],
    queryFn: () => fetchClusters(page, 20),
    enabled: viewMode === "clusters",
    staleTime: 5 * 1000,
  });

  const {
    data: stats,
    isLoading: isLoadingStats,
    refetch: refetchStats,
  } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
    staleTime: 0, // always refetch so article/cluster counts are accurate
    refetchOnWindowFocus: true,
  });

  const articles = Array.isArray(articlesData?.data) ? articlesData.data : [];
  const clusters = Array.isArray(clustersData?.data) ? clustersData.data : [];
  const articlesMeta = articlesData?.meta;
  const totalArticles = articlesMeta?.total ?? 0;
  const totalPages = Math.max(1, articlesMeta?.total_pages ?? 1);

  // ============================================
  // MUTATIONS
  // ============================================

  const crawlMutation = useMutation({
    mutationFn: triggerCrawl,
    onSuccess: () => {
      crawlFinishedToastShown.current = false;
      crawlStartTime.current = Date.now();
      setCrawlInProgress(true);
      toast.info("Fetching news…", { description: "List will update when finished." });
    },
    onError: (error: any) => {
      toast.error("Crawl failed", {
        description: error.message || "Failed to start news crawl",
      });
    },
  });

  // Poll crawl status until finished; keep loading state until data arrives
  useEffect(() => {
    if (!crawlInProgress) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const st = await fetchCrawlStatus();
        if (!st.running && !cancelled) {
          // Data refetch first, THEN remove loading state so user never sees "No articles yet"
          setPage(1);
          queryClient.invalidateQueries({ queryKey: ["articles"] });
          queryClient.invalidateQueries({ queryKey: ["stats"] });
          await Promise.all([
            queryClient.refetchQueries({ queryKey: ["articles"] }),
            queryClient.refetchQueries({ queryKey: ["stats"] }),
          ]);
          // Now articles are in cache — safe to stop loading
          setCrawlInProgress(false);
          const cached = queryClient.getQueryData<{ articles?: { total?: number } }>(["stats"]);
          const total = cached?.articles?.total ?? 0;
          const elapsed = Date.now() - crawlStartTime.current;
          if (!crawlFinishedToastShown.current) {
            crawlFinishedToastShown.current = true;
            toast.success("Crawl finished", {
              description: `${total} article(s) · ${formatDuration(elapsed)}`,
            });
          }
          return;
        }
      } catch {
        // Keep polling on transient errors
      }
    };

    const id = setInterval(poll, CRAWL_POLL_INTERVAL_MS);
    poll();
    return () => { cancelled = true; clearInterval(id); };
  }, [crawlInProgress, queryClient]);

  // Poll cluster status; keep loading until data arrives
  useEffect(() => {
    if (!clusterInProgress) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const st = await fetchClusterStatus();
        if (!st.running && !cancelled) {
          setViewMode("clusters");
          queryClient.invalidateQueries({ queryKey: ["clusters"] });
          queryClient.invalidateQueries({ queryKey: ["stats"] });
          await Promise.all([
            queryClient.refetchQueries({ queryKey: ["clusters"] }),
            queryClient.refetchQueries({ queryKey: ["stats"] }),
          ]);
          setClusterInProgress(false);
          const elapsed = Date.now() - clusterStartTime.current;
          if (!clusterFinishedToastShown.current) {
            clusterFinishedToastShown.current = true;
            toast.success("Clustering finished", {
              description: `Switched to Clusters tab · ${formatDuration(elapsed)}`,
            });
          }
          return;
        }
      } catch {
        // keep polling
      }
    };
    const id = setInterval(poll, TASK_POLL_INTERVAL_MS);
    poll();
    return () => { cancelled = true; clearInterval(id); };
  }, [clusterInProgress, queryClient]);

  // Run All: poll until both done; keep loading until data arrives
  useEffect(() => {
    if (!runAllInProgress) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const [crawl, cluster] = await Promise.all([
          fetchCrawlStatus(),
          fetchClusterStatus(),
        ]);
        if (!crawl.running && !cluster.running && !cancelled) {
          queryClient.invalidateQueries({ queryKey: ["articles"] });
          queryClient.invalidateQueries({ queryKey: ["clusters"] });
          queryClient.invalidateQueries({ queryKey: ["stats"] });
          await Promise.all([
            queryClient.refetchQueries({ queryKey: ["articles"] }),
            queryClient.refetchQueries({ queryKey: ["clusters"] }),
            queryClient.refetchQueries({ queryKey: ["stats"] }),
          ]);
          setRunAllInProgress(false);
          setCrawlInProgress(false);
          setClusterInProgress(false);
          const elapsed = Date.now() - runAllStartTime.current;
          if (!runAllFinishedToastShown.current) {
            runAllFinishedToastShown.current = true;
            toast.success("Run All finished", {
              description: `Crawl → Cluster completed · ${formatDuration(elapsed)}`,
            });
          }
          return;
        }
      } catch {
        // keep polling
      }
    };
    const id = setInterval(poll, TASK_POLL_INTERVAL_MS);
    poll();
    return () => { cancelled = true; clearInterval(id); };
  }, [runAllInProgress, queryClient]);

  const clusterMutation = useMutation({
    mutationFn: triggerClustering,
    onSuccess: () => {
      clusterFinishedToastShown.current = false;
      clusterStartTime.current = Date.now();
      setClusterInProgress(true);
      toast.success("Clustering started", {
        description: "Grouping similar articles...",
      });
    },
    onError: (error: any) => {
      toast.error("Clustering failed", {
        description: error.message || "Failed to start clustering",
      });
    },
  });

  const runAllMutation = useMutation({
    mutationFn: runFullPipeline,
    onSuccess: () => {
      runAllFinishedToastShown.current = false;
      runAllStartTime.current = Date.now();
      toast.success("Pipeline started", {
        description: "Running: crawl → cluster",
      });
    },
    onError: (error: any) => {
      toast.error("Pipeline failed", {
        description: error.message || "Failed to start pipeline",
      });
    },
  });

  /** Instantly patch the stats cache so badge updates without waiting for API */
  const patchStats = useCallback(
    (patch: { articlesDelta?: number; articlesTotal?: number; clustersDelta?: number; clustersTotal?: number }) => {
      queryClient.setQueryData(["stats"], (old: any) => {
        if (!old) return old;
        const arts = old.articles?.total ?? 0;
        const cls = old.clusters?.active ?? 0;
        return {
          ...old,
          articles: { ...old.articles, total: patch.articlesTotal ?? Math.max(0, arts + (patch.articlesDelta ?? 0)) },
          clusters: { ...old.clusters, active: patch.clustersTotal ?? Math.max(0, cls + (patch.clustersDelta ?? 0)) },
        };
      });
    },
    [queryClient]
  );

  const deleteArticleMutation = useMutation({
    mutationFn: deleteArticle,
    onSuccess: () => {
      patchStats({ articlesDelta: -1 });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      toast.success("Article deleted");
    },
    onError: (error: any) => {
      toast.error("Failed to delete article", { description: error.message });
    },
  });

  const deleteBatchMutation = useMutation({
    mutationFn: deleteArticlesBatch,
    onSuccess: (data: { deleted: number; duration_ms?: number }) => {
      patchStats({ articlesDelta: -data.deleted });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      const time = data.duration_ms != null ? ` · ${formatDuration(data.duration_ms)}` : "";
      toast.success(`Deleted ${data.deleted} article(s)${time}`);
    },
    onError: (error: any) => {
      toast.error("Delete failed", { description: (error as Error)?.message });
    },
  });

  const deleteAllMutation = useMutation({
    mutationFn: deleteAllArticles,
    onSuccess: (data: { deleted: number; duration_ms?: number }) => {
      patchStats({ articlesTotal: 0 });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      const time = data.duration_ms != null ? ` · ${formatDuration(data.duration_ms)}` : "";
      toast.success(`Deleted ${data.deleted} article(s). DB cleared.${time}`);
    },
    onError: (error: any) => {
      toast.error("Delete all failed", { description: (error as Error)?.message });
    },
  });

  const deleteClusterMutation = useMutation({
    mutationFn: deleteCluster,
    onSuccess: () => {
      patchStats({ clustersDelta: -1 });
      queryClient.invalidateQueries({ queryKey: ["clusters"] });
      toast.success("Cluster deleted");
    },
    onError: (error: any) => {
      toast.error("Failed to delete cluster", { description: error.message });
    },
  });

  const resetClusteringMutation = useMutation({
    mutationFn: resetClustering,
    onSuccess: (data: { articles_updated: number; clusters_deleted: number; duration_ms?: number }) => {
      patchStats({ clustersTotal: 0 });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["clusters"] });
      const time = data.duration_ms != null ? ` · ${formatDuration(data.duration_ms)}` : "";
      toast.success("Clustering reset", {
        description: `${data.articles_updated} articles unassigned, ${data.clusters_deleted} clusters removed${time}`,
      });
    },
    onError: (error: any) => {
      toast.error("Reset failed", { description: error.message });
    },
  });

  // ============================================
  // HANDLERS
  // ============================================

  const handleFetchNews = useCallback(() => {
    crawlMutation.mutate({ limit: 50 });
  }, [crawlMutation]);

  const handleCluster = useCallback(() => {
    const hasClusters = (stats?.clusters?.active ?? 0) > 0;
    if (hasClusters && !confirm("This will clear existing clusters and re-run clustering. Continue?")) return;
    if (hasClusters) {
      resetClusteringMutation.mutate(undefined, {
        onSuccess: () => {
          clusterMutation.mutate({});
        },
      });
    } else {
      clusterMutation.mutate({});
    }
  }, [clusterMutation, resetClusteringMutation, stats?.clusters?.active]);

  const handleRunAll = useCallback(() => {
    setRunAllInProgress(true);
    runAllMutation.mutate();
  }, [runAllMutation]);

  const handleDeleteArticle = useCallback(
    (id: string) => {
      deleteArticleMutation.mutate(id);
    },
    [deleteArticleMutation]
  );

  const handleDeleteCluster = useCallback(
    (id: string) => {
      deleteClusterMutation.mutate(id);
    },
    [deleteClusterMutation]
  );

  const handleResetClustering = useCallback(() => {
    if (!confirm("Clear all clusters? Articles will stay. You can run Cluster again after this.")) return;
    resetClusteringMutation.mutate();
  }, [resetClusteringMutation]);

  // 기사 카드에서 요약(Sparkles) 클릭 시: 이 기사만 동기로 요약 → API 완료 후 articles refetch → 카드에 summary 표시
  const handleSummarizeArticle = useCallback(
    async (articleId: string) => {
      // Only single-article summarize from card (POST /news/:id/summarize), never batch
      const id = typeof articleId === "string" && articleId && !articleId.includes(",")
        ? articleId
        : null;
      if (!id) {
        toast.error("Invalid request", { description: "Only one article can be summarized at a time from the card." });
        return;
      }
      setSummarizingArticleId(id);
      try {
        await summarizeArticle(id); // single-article API only
        queryClient.invalidateQueries({ queryKey: ["articles"] });
        queryClient.refetchQueries({ queryKey: ["articles"] }); // keep UI in sync with DB
        toast.success("Article summarized", {
          description: "The summary appears under the title on the card.",
        });
      } finally {
        setSummarizingArticleId(null);
      }
    },
    [queryClient]
  );

  const handleSummarizeVisibleArticles = useCallback(async () => {
    if (articles.length === 0) {
      toast.info("No articles on this page to summarize");
      return;
    }
    const ids = articles.map((a) => a.id);
    setSummarizeVisibleInProgress(true);
    try {
      await summarizeArticles(ids);
      toast.success(`Summarizing ${ids.length} article(s) in background. List will update as summaries complete.`);
      // Poll so list and stats refresh as summaries complete (backend runs in background)
      const pollIntervalMs = 5000;
      const pollDurationMs = 90 * 1000;
      const tid = setInterval(() => {
        queryClient.invalidateQueries({ queryKey: ["articles"] });
        queryClient.invalidateQueries({ queryKey: ["stats"] });
        refetchArticles();
        refetchStats();
      }, pollIntervalMs);
      setTimeout(() => {
        clearInterval(tid);
        setSummarizeVisibleInProgress(false);
        queryClient.invalidateQueries({ queryKey: ["articles"] });
        queryClient.invalidateQueries({ queryKey: ["stats"] });
        refetchArticles();
        refetchStats();
      }, pollDurationMs);
    } catch (e: any) {
      toast.error("Summarize failed", { description: e?.message || "Could not start summarization" });
      setSummarizeVisibleInProgress(false);
    }
  }, [articles, queryClient, refetchArticles, refetchStats]);

  const handleDeleteVisibleArticles = useCallback(() => {
    if (articles.length === 0) {
      toast.info("No articles on this page to delete");
      return;
    }
    if (!confirm(`Delete ${articles.length} article(s) on this page?`)) return;
    deleteBatchMutation.mutate(articles.map((a) => a.id));
  }, [articles, deleteBatchMutation]);

  const handleDeleteAllArticles = useCallback(() => {
    if (!confirm("Delete ALL articles? This cannot be undone.")) return;
    deleteAllMutation.mutate();
  }, [deleteAllMutation]);

  const handleViewArticles = useCallback((clusterId: string) => {
    setClusterFilterId(clusterId);
    setViewMode("articles");
    setPage(1);
  }, []);

  const handleBackToClusters = useCallback(() => {
    setClusterFilterId(null);
    setViewMode("clusters");
    setPage(1);
  }, []);

  // ============================================
  // RENDER
  // ============================================

  // Show spinner on initial load OR when moving modes. (Removed isFetchingArticles so it doesn't spin on focus)
  const isLoading = viewMode === "articles" ? isLoadingArticles : isLoadingClusters;
  const error = viewMode === "articles" ? articlesError : clustersError;

  // Derive counts using meta when available so it updates instantly with the list
  const currentArticleCount =
    viewMode === "articles" && !clusterFilterId && articlesMeta
      ? articlesMeta.total
      : stats?.articles?.total;

  const currentClusterCount =
    viewMode === "clusters" && clustersData?.meta
      ? clustersData.meta.total
      : stats?.clusters?.active;

  return (
    <div className="min-h-screen bg-background">
      <Toaster position="top-right" richColors />

      <Header onAdminClick={() => setIsAdminOpen(true)} />

      <ActionBar
        viewMode={viewMode}
        onViewModeChange={(mode) => {
          setViewMode(mode);
          setPage(1);
          if (mode === "clusters") setClusterFilterId(null);
        }}
        onFetchNews={handleFetchNews}
        onCluster={handleCluster}
        onRunAll={handleRunAll}
        onResetClustering={handleResetClustering}
        isFetching={crawlMutation.isPending || crawlInProgress}
        isClustering={clusterMutation.isPending || clusterInProgress}
        isRunningAll={runAllMutation.isPending || runAllInProgress}
        isResettingClustering={resetClusteringMutation.isPending}
        articleCount={currentArticleCount}
        clusterCount={currentClusterCount}
      />

      <main className="container mx-auto px-4 py-6">
        {/* Crawl in progress banner */}
        {crawlInProgress && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin shrink-0" />
            <span>Fetching news… List will update when finished.</span>
          </div>
        )}
        {/* Cluster in progress banner */}
        {clusterInProgress && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin shrink-0" />
            <span>Clustering articles… Switch to Clusters tab when finished.</span>
          </div>
        )}
        {/* Run All in progress banner */}
        {runAllInProgress && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border bg-primary/10 px-4 py-3 text-sm text-foreground">
            <Loader2 className="h-4 w-4 animate-spin shrink-0" />
            <span>Run All in progress: Fetch News → Cluster. This may take a few minutes.</span>
          </div>
        )}
        {/* Summarize visible in progress banner */}
        {summarizeVisibleInProgress && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border bg-primary/10 px-4 py-3 text-sm text-foreground">
            <Loader2 className="h-4 w-4 animate-spin shrink-0" />
            <span>Summarizing visible articles in background… List and counts will refresh automatically.</span>
          </div>
        )}
        {/* Deleting in progress banner */}
        {(deleteArticleMutation.isPending || deleteBatchMutation.isPending || deleteAllMutation.isPending) && (
          <div className="mb-4 flex items-center gap-2 rounded-lg border bg-muted/50 px-4 py-3 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin shrink-0" />
            <span>Deleting articles…</span>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <AlertCircle className="h-12 w-12 text-destructive mb-4" />
            <h3 className="text-lg font-semibold mb-2">Failed to load data</h3>
            <p className="text-muted-foreground mb-4">
              {(error as Error).message || "Something went wrong"}
            </p>
            <Button
              onClick={() => {
                setPage(1);
                queryClient.invalidateQueries({ queryKey: ["articles"] });
                queryClient.invalidateQueries({ queryKey: ["clusters"] });
              }}
            >
              Try Again
            </Button>
          </div>
        )}

        {/* Loading State */}
        {isLoading && !error && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Empty State */}
        {!isLoading && !error && viewMode === "articles" && articles.length === 0 && (
          <div className="text-center py-12">
            <h3 className="text-lg font-semibold mb-2">No articles yet</h3>
            <p className="text-muted-foreground mb-4">
              Click &quot;Fetch News&quot; to start collecting articles
            </p>
            <Button onClick={handleFetchNews} isLoading={crawlMutation.isPending || crawlInProgress}>
              Fetch News
            </Button>
          </div>
        )}

        {!isLoading && !error && viewMode === "clusters" && clusters.length === 0 && (
          <div className="text-center py-12">
            <h3 className="text-lg font-semibold mb-2">No clusters yet</h3>
            <p className="text-muted-foreground mb-4">
              Run <strong>Cluster</strong> to group similar articles.
            </p>
            <Button onClick={handleCluster} isLoading={clusterMutation.isPending || clusterInProgress}>
              Cluster Articles
            </Button>
          </div>
        )}

        {/* Articles Grid */}
        {!isLoading && !error && viewMode === "articles" && articles.length > 0 && (
          <>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
              {clusterFilterId ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleBackToClusters}
                  title="Back to Clusters tab"
                >
                  <ArrowLeft className="h-4 w-4 mr-1" />
                  Back to Clusters
                </Button>
              ) : (
                <span />
              )}
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleSummarizeVisibleArticles}
                  title="Generate AI summary for each article on this page"
                >
                  Summarize visible ({articles.length})
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDeleteVisibleArticles}
                  title="Delete all articles on this page"
                  className="text-destructive hover:text-destructive"
                >
                  Delete page ({articles.length})
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleDeleteAllArticles}
                  title="Delete all articles in the database"
                  className="text-destructive hover:text-destructive"
                >
                  Delete all
                </Button>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {articles.map((article: Article) => (
                <NewsCard
                  key={article.id}
                  article={article}
                  onDelete={handleDeleteArticle}
                  onSummarize={handleSummarizeArticle}
                  showClusterInfo
                  isSummarizing={summarizingArticleId === article.id}
                />
              ))}
            </div>
          </>
        )}

        {/* Clusters Grid */}
        {!isLoading && !error && viewMode === "clusters" && clusters.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2">
            {clusters.map((cluster: Cluster) => (
              <ClusterCard
                key={cluster.id}
                cluster={cluster}
                onDelete={handleDeleteCluster}
                onViewArticles={handleViewArticles}
              />
            ))}
          </div>
        )}

        {/* Pagination: 20 per page, Previous / Next */}
        {!isLoading && !error && viewMode === "articles" && totalArticles > 0 && (
          <div className="mt-8 flex flex-wrap items-center justify-center gap-4 border-t pt-6">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1 || isFetchingArticles}
            >
              ← Previous
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
              {totalArticles > 0 && (
                <span className="ml-1">
                  ({((page - 1) * PER_PAGE) + 1}–{Math.min(page * PER_PAGE, totalArticles)} of {totalArticles})
                </span>
              )}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages || isFetchingArticles}
            >
              Next →
            </Button>
          </div>
        )}
      </main>

      {/* Admin Panel */}
      <AdminPanel
        isOpen={isAdminOpen}
        onClose={() => setIsAdminOpen(false)}
        stats={stats}
        isLoading={isLoadingStats}
      />
    </div>
  );
}

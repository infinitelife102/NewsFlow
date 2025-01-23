"use client";

import React, { useState, useEffect, useCallback } from "react";
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

const CRAWL_POLL_INTERVAL_MS = 2500;
const TASK_POLL_INTERVAL_MS = 2500;

export default function HomePage() {
  const queryClient = useQueryClient();
  const [viewMode, setViewMode] = useState<"articles" | "clusters">("articles");
  const [isAdminOpen, setIsAdminOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [clusterFilterId, setClusterFilterId] = useState<string | null>(null);
  const [summarizingArticleId, setSummarizingArticleId] = useState<string | null>(null);
  const [crawlInProgress, setCrawlInProgress] = useState(false);
  const [clusterInProgress, setClusterInProgress] = useState(false);
  const [runAllInProgress, setRunAllInProgress] = useState(false);

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
    staleTime: 30 * 1000, // 30s: revisiting same page uses cache, faster
  });

  const {
    data: clustersData,
    isLoading: isLoadingClusters,
    error: clustersError,
  } = useQuery({
    queryKey: ["clusters", page],
    queryFn: () => fetchClusters(page, 20),
    enabled: viewMode === "clusters",
  });

  const {
    data: stats,
    isLoading: isLoadingStats,
    refetch: refetchStats,
  } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
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
      setCrawlInProgress(true);
      toast.info("Fetching news…", { description: "List will update when finished." });
    },
    onError: (error: any) => {
      toast.error("Crawl failed", {
        description: error.message || "Failed to start news crawl",
      });
    },
  });

  // Poll crawl status until finished; then show one message and refresh the list
  useEffect(() => {
    if (!crawlInProgress) return;

    const poll = async () => {
      try {
        const status = await fetchCrawlStatus();
        if (!status.running) {
          setCrawlInProgress(false);
          setPage(1);
          queryClient.invalidateQueries({ queryKey: ["articles"] });
          await queryClient.refetchQueries({ queryKey: ["articles"] });
          await refetchStats();
          const freshStats = await fetchStats();
          const total = freshStats?.articles?.total ?? 0;
          toast.success("Crawl finished", {
            description: `${total} article(s). List updated.`,
          });
          return;
        }
      } catch {
        // Keep polling on transient errors
      }
    };

    const id = setInterval(poll, CRAWL_POLL_INTERVAL_MS);
    poll();
    return () => clearInterval(id);
  }, [crawlInProgress, queryClient, refetchStats]);

  // Poll cluster status until finished, then refetch clusters and stats
  useEffect(() => {
    if (!clusterInProgress) return;
    const poll = async () => {
      try {
        const status = await fetchClusterStatus();
        if (!status.running) {
          setClusterInProgress(false);
          setViewMode("clusters");
          queryClient.invalidateQueries({ queryKey: ["clusters"] });
          await queryClient.refetchQueries({ queryKey: ["clusters"] });
          refetchStats();
          toast.success("Clustering finished", { description: "Switched to Clusters tab." });
          return;
        }
      } catch {
        // keep polling
      }
    };
    const id = setInterval(poll, TASK_POLL_INTERVAL_MS);
    poll();
    return () => clearInterval(id);
  }, [clusterInProgress, queryClient, refetchStats]);

  // When Run All is in progress, poll until crawl + cluster are both finished
  useEffect(() => {
    if (!runAllInProgress) return;
    const poll = async () => {
      try {
        const [crawl, cluster] = await Promise.all([
          fetchCrawlStatus(),
          fetchClusterStatus(),
        ]);
        if (!crawl.running && !cluster.running) {
          setRunAllInProgress(false);
          setCrawlInProgress(false);
          setClusterInProgress(false);
          queryClient.invalidateQueries({ queryKey: ["articles"] });
          queryClient.invalidateQueries({ queryKey: ["clusters"] });
          refetchStats();
          toast.success("Run All finished", { description: "Crawl → Cluster completed." });
          return;
        }
      } catch {
        // keep polling
      }
    };
    const id = setInterval(poll, TASK_POLL_INTERVAL_MS);
    poll();
    return () => clearInterval(id);
  }, [runAllInProgress, queryClient, refetchStats]);

  const clusterMutation = useMutation({
    mutationFn: triggerClustering,
    onSuccess: () => {
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
      toast.success("Pipeline started", {
        description: "Running: crawl → cluster",
      });
      setTimeout(() => {
        refetchStats();
        queryClient.invalidateQueries({ queryKey: ["articles"] });
        queryClient.invalidateQueries({ queryKey: ["clusters"] });
      }, 20000);
    },
    onError: (error: any) => {
      toast.error("Pipeline failed", {
        description: error.message || "Failed to start pipeline",
      });
    },
  });

  const deleteArticleMutation = useMutation({
    mutationFn: deleteArticle,
    onSuccess: async () => {
      toast.success("Article deleted");
      await queryClient.refetchQueries({ queryKey: ["articles"] });
      await queryClient.refetchQueries({ queryKey: ["stats"] });
    },
    onError: (error: any) => {
      toast.error("Failed to delete article", {
        description: error.message,
      });
    },
  });

  const deleteBatchMutation = useMutation({
    mutationFn: deleteArticlesBatch,
    onSuccess: async (data, variables) => {
      toast.success(`Deleted ${data.deleted} article(s)`);
      await queryClient.refetchQueries({ queryKey: ["articles"] });
      await queryClient.refetchQueries({ queryKey: ["stats"] });
    },
    onError: (error: any) => {
      toast.error("Delete failed", { description: (error as Error)?.message });
    },
  });

  const deleteAllMutation = useMutation({
    mutationFn: deleteAllArticles,
    onSuccess: async (data) => {
      toast.success(`Deleted ${data.deleted} article(s)`);
      await queryClient.refetchQueries({ queryKey: ["articles"] });
      await queryClient.refetchQueries({ queryKey: ["stats"] });
    },
    onError: (error: any) => {
      toast.error("Delete all failed", { description: (error as Error)?.message });
    },
  });

  const deleteClusterMutation = useMutation({
    mutationFn: deleteCluster,
    onSuccess: () => {
      toast.success("Cluster deleted");
      queryClient.invalidateQueries({ queryKey: ["clusters"] });
      refetchStats();
    },
    onError: (error: any) => {
      toast.error("Failed to delete cluster", {
        description: error.message,
      });
    },
  });

  const resetClusteringMutation = useMutation({
    mutationFn: resetClustering,
    onSuccess: (data) => {
      toast.success("Clustering reset", {
        description: `${data.articles_updated} articles unassigned, ${data.clusters_deleted} clusters removed. You can run Cluster again.`,
      });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["clusters"] });
      refetchStats();
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

  const handleSummarizeArticle = useCallback(
    async (articleId: string) => {
      setSummarizingArticleId(articleId);
      try {
        await summarizeArticle(articleId);
        queryClient.invalidateQueries({ queryKey: ["articles"] });
        toast.success("Article summarized", {
          description: "The summary appears under the title on the card.",
        });
      } finally {
        setSummarizingArticleId(null);
      }
    },
    [queryClient]
  );

  const handleSummarizeVisibleArticles = useCallback(() => {
    if (articles.length === 0) {
      toast.info("No articles on this page to summarize");
      return;
    }
    summarizeArticles(articles.map((a) => a.id));
    toast.success(`Summarizing ${articles.length} article(s) in background. Refresh the list to see updates.`);
  }, [articles]);

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

  const isLoading = isLoadingArticles || isLoadingClusters;
  const error = articlesError || clustersError;

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
        articleCount={stats?.articles.total}
        clusterCount={stats?.clusters.active}
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

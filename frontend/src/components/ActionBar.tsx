"use client";

import React from "react";
import { RefreshCw, Layers, Play, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";

interface ActionBarProps {
  viewMode: "articles" | "clusters";
  onViewModeChange: (mode: "articles" | "clusters") => void;
  onFetchNews: () => void;
  onCluster: () => void;
  onRunAll: () => void;
  onResetClustering?: () => void;
  isFetching: boolean;
  isClustering: boolean;
  isRunningAll: boolean;
  isResettingClustering?: boolean;
  articleCount?: number;
  clusterCount?: number;
}

export function ActionBar({
  viewMode,
  onViewModeChange,
  onFetchNews,
  onCluster,
  onRunAll,
  onResetClustering,
  isFetching,
  isClustering,
  isRunningAll,
  isResettingClustering = false,
  articleCount,
  clusterCount,
}: ActionBarProps) {
  return (
    <div className="sticky top-16 z-40 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 py-4">
      <div className="container mx-auto px-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          {/* View Mode Toggle */}
          <div className="flex items-center gap-2 bg-muted p-1 rounded-lg">
            <button
              onClick={() => onViewModeChange("articles")}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                viewMode === "articles"
                  ? "bg-background shadow-sm text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Articles
              {articleCount !== undefined && (
                <Badge variant="secondary" className="ml-2 text-xs">
                  {articleCount}
                </Badge>
              )}
            </button>
            <button
              onClick={() => onViewModeChange("clusters")}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                viewMode === "clusters"
                  ? "bg-background shadow-sm text-foreground"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Clusters
              {clusterCount !== undefined && (
                <Badge variant="secondary" className="ml-2 text-xs">
                  {clusterCount}
                </Badge>
              )}
            </button>
          </div>

          {/* Action Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={onFetchNews}
              isLoading={isFetching}
              leftIcon={<RefreshCw className="h-4 w-4" />}
            >
              Fetch News
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onCluster}
              isLoading={isClustering}
              leftIcon={<Layers className="h-4 w-4" />}
            >
              Cluster
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={onRunAll}
              isLoading={isRunningAll}
              leftIcon={<Play className="h-4 w-4" />}
              title="Run full pipeline: Fetch News → Cluster (in sequence)"
            >
              Run All
            </Button>
            {onResetClustering && (
              <Button
                variant="outline"
                size="sm"
                onClick={onResetClustering}
                isLoading={isResettingClustering}
                leftIcon={<RotateCcw className="h-4 w-4" />}
                title="Clear all clusters so you can run Cluster again"
              >
                Reset Clustering
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default ActionBar;

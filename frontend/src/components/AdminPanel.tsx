"use client";

import React from "react";
import { X, Activity, Database, Clock, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatRelativeTime, formatDate } from "@/lib/utils";
import type { SystemStats, CrawlHistoryItem } from "@/types";

interface AdminPanelProps {
  isOpen: boolean;
  onClose: () => void;
  stats?: SystemStats;
  isLoading: boolean;
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "success":
      return (
        <Badge variant="success" className="flex items-center gap-1">
          <CheckCircle className="h-3 w-3" />
          Success
        </Badge>
      );
    case "failed":
      return (
        <Badge variant="destructive" className="flex items-center gap-1">
          <AlertCircle className="h-3 w-3" />
          Failed
        </Badge>
      );
    case "running":
      return (
        <Badge variant="info" className="flex items-center gap-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          Running
        </Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

export function AdminPanel({ isOpen, onClose, stats, isLoading }: AdminPanelProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-sm">
      <div className="fixed inset-y-0 right-0 w-full max-w-md bg-background border-l shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Admin Panel
          </h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-muted rounded-lg transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4 overflow-y-auto h-[calc(100vh-73px)]">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : stats ? (
            <>
              {/* Stats Cards */}
              <div className="grid grid-cols-3 gap-3">
                <Card>
                  <CardContent className="p-4 text-center">
                    <Database className="h-5 w-5 mx-auto mb-2 text-primary" />
                    <div className="text-2xl font-bold">{stats.articles.total}</div>
                    <div className="text-xs text-muted-foreground">Articles</div>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-4 text-center">
                    <Activity className="h-5 w-5 mx-auto mb-2 text-green-500" />
                    <div className="text-2xl font-bold">{stats.clusters.active}</div>
                    <div className="text-xs text-muted-foreground">Clusters</div>
                  </CardContent>
                </Card>
              </div>

              {/* Crawl History */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium flex items-center gap-2">
                    <Clock className="h-4 w-4" />
                    Recent Crawl History
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-0">
                  {stats.recent_crawls.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No crawl history yet
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {stats.recent_crawls.map((crawl) => (
                        <div
                          key={crawl.id}
                          className="flex items-start justify-between p-3 bg-muted rounded-lg"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="font-medium text-sm">{crawl.source}</span>
                              <StatusBadge status={crawl.status} />
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {crawl.articles_found} found, {crawl.articles_added} added
                            </div>
                            {crawl.error_message && (
                              <div className="text-xs text-destructive mt-1">
                                {crawl.error_message}
                              </div>
                            )}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {formatRelativeTime(crawl.started_at)}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* System Info */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium">System Information</CardTitle>
                </CardHeader>
                <CardContent className="pt-0 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">API Status</span>
                    <Badge variant="success">Connected</Badge>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Database</span>
                    <Badge variant="success">Connected</Badge>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-muted-foreground">Last Updated</span>
                    <span>{formatDate(new Date())}</span>
                  </div>
                </CardContent>
              </Card>
            </>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              Failed to load stats
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default AdminPanel;

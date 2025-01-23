"use client";

import React, { useState } from "react";
import { ExternalLink, Trash2, Calendar, User, Tag, Sparkles, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  formatRelativeTime,
  formatDate,
  truncateText,
  extractDomain,
} from "@/lib/utils";
import type { Article } from "@/types";

const SUMMARY_PREVIEW_LEN = 200;

interface NewsCardProps {
  article: Article;
  onDelete?: (id: string) => void;
  onSummarize?: (id: string) => void;
  showClusterInfo?: boolean;
  /** When true, show loading overlay on the card (set by parent during summarize). */
  isSummarizing?: boolean;
}

export function NewsCard({ article, onDelete, onSummarize, showClusterInfo, isSummarizing = false }: NewsCardProps) {
  const [summarizing, setSummarizing] = useState(false);
  const [summaryExpanded, setSummaryExpanded] = useState(false);
  const [clusterSummaryExpanded, setClusterSummaryExpanded] = useState(false);
  const summarizingAny = summarizing || isSummarizing;

  const handleDelete = () => {
    if (onDelete && confirm("Are you sure you want to delete this article?")) {
      onDelete(article.id);
    }
  };

  const domain = extractDomain(article.url);
  const displayDate = article.published_at || article.created_at;

  return (
    <Card className={`group hover:shadow-lg transition-shadow duration-200 relative ${summarizingAny ? "opacity-90" : ""}`}>
      {summarizingAny && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-background/80 backdrop-blur-[1px]">
          <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-8 w-8 animate-spin" />
            <span>Summarizing…</span>
          </div>
        </div>
      )}
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold leading-tight mb-2 group-hover:text-primary transition-colors">
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer"
                className="hover:underline"
              >
                {article.title}
              </a>
            </h3>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <Badge variant="secondary" className="font-medium">
                {article.source}
              </Badge>
              <span className="flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5" />
                {formatRelativeTime(displayDate)}
              </span>
              {article.author && (
                <span className="flex items-center gap-1">
                  <User className="h-3.5 w-3.5" />
                  {truncateText(article.author, 20)}
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            {onSummarize && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={async () => {
                  setSummarizing(true);
                  try {
                    await onSummarize(article.id);
                  } finally {
                    setSummarizing(false);
                  }
                }}
                disabled={summarizingAny}
                title={article.summary ? "Re-summarize this article only" : "Generate AI summary for this article only (not the whole list)"}
              >
                <Sparkles className={`h-4 w-4 ${summarizingAny ? "animate-pulse" : ""}`} />
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={handleDelete}
              title="Delete article"
            >
              <Trash2 className="h-4 w-4 text-destructive" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              asChild
              title="Open original article"
            >
              <a href={article.url} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="h-4 w-4" />
              </a>
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        {article.summary && (
          <div className="mb-3">
            <p className="text-xs font-medium text-muted-foreground mb-1">Summary</p>
            <p className={`text-sm text-muted-foreground whitespace-pre-wrap ${!summaryExpanded && article.summary.length > SUMMARY_PREVIEW_LEN ? "line-clamp-3" : ""}`}>
              {summaryExpanded ? article.summary : (article.summary.length <= SUMMARY_PREVIEW_LEN ? article.summary : `${article.summary.slice(0, SUMMARY_PREVIEW_LEN)}${article.summary.length > SUMMARY_PREVIEW_LEN ? "…" : ""}`)}
            </p>
            {article.summary.length > SUMMARY_PREVIEW_LEN && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs mt-1"
                onClick={() => setSummaryExpanded((e) => !e)}
              >
                {summaryExpanded ? <>Show less <ChevronUp className="h-3 w-3 inline ml-0.5" /></> : <>Show more <ChevronDown className="h-3 w-3 inline ml-0.5" /></>}
              </Button>
            )}
          </div>
        )}

        {!article.summary && article.content && (
          <p className="text-sm text-muted-foreground mb-3 line-clamp-3">
            {truncateText(article.content, 200)}
          </p>
        )}

        {article.keywords && article.keywords.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mt-3">
            <Tag className="h-3.5 w-3.5 text-muted-foreground" />
            {article.keywords.slice(0, 5).map((keyword, index) => (
              <Badge key={index} variant="outline" className="text-xs">
                {keyword}
              </Badge>
            ))}
            {article.keywords.length > 5 && (
              <Badge variant="outline" className="text-xs">
                +{article.keywords.length - 5}
              </Badge>
            )}
          </div>
        )}

        {showClusterInfo && article.cluster_id && (
          <div className="mt-3 pt-3 border-t space-y-2">
            <Badge variant="info" className="text-xs">
              {article.cluster_name ? `Cluster: ${article.cluster_name}` : "Part of cluster"}
            </Badge>
            {(article.ai_summary || (article.ai_key_points && article.ai_key_points.length > 0)) && (
              <div className="rounded-md bg-muted/60 p-2 text-sm">
                <p className="font-medium text-foreground/90 mb-1">Cluster AI summary</p>
                {article.ai_summary && (
                  <>
                    <p className={`text-muted-foreground leading-relaxed text-xs whitespace-pre-wrap ${!clusterSummaryExpanded && article.ai_summary.length > 220 ? "" : ""}`}>
                      {clusterSummaryExpanded ? article.ai_summary : truncateText(article.ai_summary, 220)}
                    </p>
                    {article.ai_summary.length > 220 && (
                      <Button variant="ghost" size="sm" className="h-6 text-xs mt-1" onClick={() => setClusterSummaryExpanded((e) => !e)}>
                        {clusterSummaryExpanded ? "Show less" : "Show more"}
                      </Button>
                    )}
                  </>
                )}
                {article.ai_key_points && article.ai_key_points.length > 0 && (
                  <ul className="mt-1.5 list-disc list-inside text-xs text-muted-foreground space-y-0.5">
                    {(clusterSummaryExpanded ? article.ai_key_points : article.ai_key_points.slice(0, 3)).map((point, i) => (
                      <li key={i}>{truncateText(point, clusterSummaryExpanded ? 500 : 80)}</li>
                    ))}
                    {!clusterSummaryExpanded && article.ai_key_points.length > 3 && (
                      <li>+{article.ai_key_points.length - 3} more</li>
                    )}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default NewsCard;

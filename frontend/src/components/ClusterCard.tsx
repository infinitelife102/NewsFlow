"use client";

import React from "react";
import { Trash2 } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import type { Cluster } from "@/types";

interface ClusterCardProps {
  cluster: Cluster;
  onDelete?: (id: string) => void;
  onViewArticles?: (id: string) => void;
}

export function ClusterCard({ cluster, onDelete, onViewArticles }: ClusterCardProps) {
  const handleDelete = () => {
    if (onDelete && confirm("Are you sure you want to delete this cluster? Articles will be unassigned but not deleted.")) {
      onDelete(cluster.id);
    }
  };

  return (
    <Card className="group hover:shadow-lg transition-shadow duration-200">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <h3 className="text-lg font-semibold leading-tight">
                {cluster.name}
              </h3>
              <Badge variant="secondary" className="text-xs">
                {cluster.article_count} articles
              </Badge>
            </div>
            {cluster.description && (
              <p className="text-sm text-muted-foreground">
                {cluster.description}
              </p>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={handleDelete}
            title="Delete cluster"
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </CardHeader>

      <CardContent className="pt-0">
        <div className="flex flex-wrap items-center gap-2 pt-3 border-t">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onViewArticles?.(cluster.id)}
          >
            View Articles
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default ClusterCard;

"use client";

import React from "react";
import Link from "next/link";
import { Newspaper, Settings } from "lucide-react";
import { Button } from "@/components/ui/Button";

interface HeaderProps {
  onAdminClick?: () => void;
}

export function Header({ onAdminClick }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2 hover:opacity-80 transition-opacity">
          <div className="bg-primary p-2 rounded-lg">
            <Newspaper className="h-5 w-5 text-primary-foreground" />
          </div>
          <div className="flex flex-col">
            <span className="text-xl font-bold leading-none">NewsFlow</span>
            <span className="text-xs text-muted-foreground">AI News Aggregator</span>
          </div>
        </Link>

        {/* Navigation */}
        <nav className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={onAdminClick}
            title="Admin Panel"
          >
            <Settings className="h-5 w-5" />
          </Button>
        </nav>
      </div>
    </header>
  );
}

export default Header;

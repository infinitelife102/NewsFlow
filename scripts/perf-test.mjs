#!/usr/bin/env node
/**
 * Measure API response times for NewsFlow.
 * Run with: node scripts/perf-test.mjs
 * Requires: Backend running at NEXT_PUBLIC_API_URL or http://localhost:8000
 */
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function measure(name, fn) {
  const start = performance.now();
  let result;
  try {
    result = await fn();
  } finally {
    const ms = Math.round(performance.now() - start);
    return { name, ms, ok: !result?.error, ...result };
  }
}

async function main() {
  console.log("NewsFlow API performance (base URL:", BASE, ")\n");

  const results = [];

  // GET /api/v1/admin/stats
  const stats = await measure("GET /admin/stats", async () => {
    const res = await fetch(`${BASE}/api/v1/admin/stats`);
    const data = await res.json().catch(() => ({}));
    return { status: res.status, data };
  });
  results.push(stats);

  // GET /api/v1/news (list articles)
  const list = await measure("GET /news?page=1&per_page=21", async () => {
    const res = await fetch(`${BASE}/api/v1/news?page=1&per_page=21`);
    const data = await res.json().catch(() => ({}));
    return { status: res.status, count: data?.data?.length ?? 0 };
  });
  results.push(list);

  // POST /admin/articles/delete-batch (empty = no-op, returns deleted: 0 + duration_ms)
  const batch = await measure("POST /admin/articles/delete-batch (no-op)", async () => {
    const res = await fetch(`${BASE}/api/v1/admin/articles/delete-batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ article_ids: [] }),
    });
    const data = await res.json().catch(() => ({}));
    return { status: res.status, server_ms: data.duration_ms };
  });
  results.push(batch);

  // Table
  const maxName = Math.max(...results.map((r) => r.name.length), 10);
  console.log("| " + "Endpoint".padEnd(maxName) + " | Client (ms) | Server (ms) |");
  console.log("| " + "-".repeat(maxName) + " | ------------ | ----------- |");
  for (const r of results) {
    const client = String(r.ms).padStart(10);
    const server = r.server_ms != null ? String(r.server_ms) : "-";
    console.log("| " + r.name.padEnd(maxName) + " | " + client + " | " + server.padStart(11) + " |");
  }
  console.log("\nDone. In the UI, Crawl/Cluster/Delete toasts also show execution time.");
}

main().catch((e) => {
  console.error("Error:", e.message);
  process.exit(1);
});

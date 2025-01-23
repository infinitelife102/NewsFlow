import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Providers } from "@/lib/providers";
import "./globals.css";

const inter = Inter({ 
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "NewsFlow - AI News Aggregator",
  description: "AI-powered IT and tech news aggregation platform with intelligent clustering and summarization",
  keywords: ["AI", "news", "tech", "aggregation", "machine learning", "developer tools"],
  authors: [{ name: "NewsFlow" }],
  icons: {
    icon: "/favicon.svg",
    apple: "/favicon.svg",
  },
  openGraph: {
    title: "NewsFlow - AI News Aggregator",
    description: "AI-powered IT and tech news aggregation platform",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "pubmed-evidence-agents - Medical Evidence Retrieval Agent",
  description:
    "Agentic RAG over PubMed: PICO extraction, retrieval, cited generation, and evidence-grounded verification.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans">{children}</body>
    </html>
  );
}

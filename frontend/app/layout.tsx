import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "ResearchLens AI — Your research, in focus",
  description:
    "RAG-Powered Research Paper Analysis and Comparison. Organize papers and explore source-grounded research.",
  openGraph: {
    title: "ResearchLens AI",
    description: "RAG-Powered Research Paper Analysis and Comparison",
  },
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { BookOpen, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Citation } from "@/lib/types";
import { openPaper, request, type Paper } from "@/lib/api";

export function Markdown({ text }: { text: string }) {
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          a: ({ children, href }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

export function Sources({ sources }: { sources: Citation[] }) {
  const [selected, setSelected] = useState<Citation | null>(null);
  const [error, setError] = useState("");
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (selected) ref.current?.showModal();
    else ref.current?.close();
  }, [selected]);
  async function select(source: Citation) {
    setSelected(source);
    setError("");
    try {
      await request<Paper>(`/documents/${source.document_id}`);
    } catch {
      setError(
        "Source document deleted or unavailable. The original excerpt is preserved below.",
      );
    }
  }
  async function open() {
    try {
      await openPaper(selected!.document_id, selected!.page_number);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  if (!sources.length) return null;
  return (
    <div className="sources">
      <div className="sources-heading">Sources</div>
      <div className="source-badges">
        {sources.map((source) => (
          <button key={source.chunk_id} onClick={() => void select(source)}>
            <BookOpen size={13} />
            {source.source_id && `[${source.source_id}] `}
            {source.document_title}, p. {source.page_number}
          </button>
        ))}
      </div>
      <dialog
        ref={ref}
        className="dialog detail-dialog"
        onCancel={() => setSelected(null)}
      >
        <button
          className="dialog-close icon-button"
          aria-label="Close source"
          onClick={() => setSelected(null)}
        >
          <X size={20} />
        </button>
        {selected && (
          <>
            <span className="tag">SOURCE EVIDENCE</span>
            <h2>{selected.document_title}</h2>
            <p>
              Page {selected.page_number}
              {selected.section_title && ` · ${selected.section_title}`}
            </p>
            {error && (
              <div role="status" className="alert error">
                {error}
              </div>
            )}
            <blockquote>{selected.excerpt}</blockquote>
            <button
              className="primary"
              onClick={() => void open()}
              disabled={!!error}
            >
              Open source PDF <BookOpen size={15} />
            </button>
          </>
        )}
      </dialog>
    </div>
  );
}

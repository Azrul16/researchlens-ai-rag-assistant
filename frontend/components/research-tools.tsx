"use client";
import { useEffect, useState } from "react";
import {
  BookOpen,
  GitCompareArrows,
  LoaderCircle,
  MessageSquare,
  Plus,
  Search,
  Send,
  Sparkles,
  Trash2,
} from "lucide-react";
import { researchApi, type Paper } from "@/lib/api";
import type {
  AnalysisResult,
  Citation,
  Comparison,
  Summary,
} from "@/lib/types";
import { useChat } from "@/hooks/use-chat";
import { Markdown, Sources } from "./evidence";

type Props = { workspace: string; papers: Paper[]; initialPaper?: string };
function ErrorMessage({ error }: { error: string }) {
  return error ? (
    <div role="alert" className="alert error">
      {error}
    </div>
  ) : null;
}
function EmptyResearch() {
  return (
    <div className="empty">
      <BookOpen size={30} />
      <h3>No research papers ready yet.</h3>
      <p>Upload a text-based PDF and wait for processing to finish.</p>
    </div>
  );
}
function PaperFilter({
  papers,
  value,
  onChange,
}: {
  papers: Paper[];
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <label className="filter-label">
      Search scope
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">All ready papers</option>
        {papers
          .filter((p) => p.processing_status === "ready")
          .map((p) => (
            <option key={p.id} value={p.id}>
              {p.title || p.original_filename}
            </option>
          ))}
      </select>
    </label>
  );
}

export function ChatPane({ workspace, papers, initialPaper }: Props) {
  const chat = useChat(workspace);
  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState(initialPaper || "");
  const ready = papers.some((p) => p.processing_status === "ready");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (await chat.send(question, scope ? [scope] : [])) setQuestion("");
  }
  return (
    <section className="research-panel">
      <div className="tool-header">
        <div>
          <h2>Ask your papers</h2>
          <p>
            Answers grounded in your uploaded research, with page citations.
          </p>
        </div>
        <button
          className="secondary"
          disabled={chat.busy}
          onClick={chat.newChat}
        >
          <Plus size={14} />
          New conversation
        </button>
      </div>
      <ErrorMessage error={chat.error} />
      <div className="chat-layout">
        <aside className="conversations">
          <strong>CONVERSATIONS</strong>
          {chat.conversations.map((c) => (
            <button
              disabled={chat.busy}
              className={chat.conversation?.id === c.id ? "active" : ""}
              key={c.id}
              onClick={() => void chat.load(c.id)}
            >
              <MessageSquare size={13} />
              {c.title}
            </button>
          ))}
          {!chat.conversations.length && (
            <p>Ask a question to start your first conversation.</p>
          )}
        </aside>
        <div className="chat-main">
          <PaperFilter papers={papers} value={scope} onChange={setScope} />
          <div className="messages" aria-live="polite">
            {chat.conversation?.messages.map((message) => (
              <article key={message.id} className={`message ${message.role}`}>
                <span className="message-label">
                  {message.role === "user" ? "YOU" : "RESEARCHLENS AI"}
                </span>
                <Markdown text={message.content} />
                <Sources sources={message.sources} />
              </article>
            ))}
            {!chat.conversation?.messages.length &&
              (ready ? (
                <div className="chat-welcome">
                  <Sparkles size={30} />
                  <h3>What would you like to understand?</h3>
                  <p>Explore methods, datasets, findings, and limitations.</p>
                  <div className="suggestions">
                    {[
                      "What methodology is used?",
                      "Which datasets are used?",
                      "What are the main results?",
                      "What limitations are mentioned?",
                    ].map((q) => (
                      <button key={q} onClick={() => setQuestion(q)}>
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyResearch />
              ))}
            {chat.busy && (
              <div className="loading" role="status">
                <LoaderCircle className="spin" size={18} />
                Retrieving evidence and preparing an answer…
              </div>
            )}
          </div>
          <form className="chat-input" onSubmit={submit}>
            <label className="sr-only" htmlFor="question">
              Your research question
            </label>
            <textarea
              id="question"
              value={question}
              maxLength={2000}
              rows={2}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about your papers…"
              disabled={chat.busy || !ready}
            />
            <button
              className="primary"
              disabled={chat.busy || !ready || !question.trim()}
              aria-label="Send question"
            >
              <Send size={17} />
            </button>
          </form>
          <div className="chat-footnote">
            <span>
              Evidence may be incomplete. Check cited source passages.
            </span>
            {chat.conversation && (
              <button
                disabled={chat.busy}
                onClick={() => {
                  if (
                    window.confirm(
                      "Delete this conversation and all its messages?",
                    )
                  )
                    void chat.clear();
                }}
              >
                <Trash2 size={12} />
                Clear conversation
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export function SearchPane({ workspace, papers }: Props) {
  const [query, setQuery] = useState("");
  const [scope, setScope] = useState("");
  const [results, setResults] = useState<Citation[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function search(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResults(
        (await researchApi.search(workspace, query, scope ? [scope] : []))
          .results,
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="research-panel">
      <div className="tool-header">
        <div>
          <h2>Semantic search</h2>
          <p>
            Find research concepts across your collection. Search uses
            embeddings without an LLM.
          </p>
        </div>
        <Search size={22} />
      </div>
      <ErrorMessage error={error} />
      <form className="search-form" onSubmit={search}>
        <label className="sr-only" htmlFor="search-query">
          Search research concepts
        </label>
        <input
          id="search-query"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          required
          maxLength={2000}
          placeholder="e.g. multi-head attention for anomaly detection"
        />
        <button className="primary" disabled={busy || !query.trim()}>
          {busy ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <Search size={16} />
          )}
          Search
        </button>
      </form>
      <PaperFilter papers={papers} value={scope} onChange={setScope} />
      {results?.map((source) => (
        <article className="search-result" key={source.chunk_id}>
          <div>
            <strong>{source.document_title}</strong>
            <span>
              Page {source.page_number}
              {source.section_title && ` · ${source.section_title}`}
            </span>
          </div>
          <p>{source.excerpt}</p>
          <span className="similarity">
            Cosine similarity: {source.score.toFixed(3)} · Higher means closer
            semantic match
          </span>
          <Sources sources={[source]} />
        </article>
      ))}
      {results?.length === 0 && (
        <div className="empty">
          <Search size={30} />
          <h3>No sufficiently relevant passages found.</h3>
          <p>Try another concept or upload a paper that discusses it.</p>
        </div>
      )}
      {results === null && (
        <div className="empty">
          <Search size={30} />
          <h3>Find the passage behind the idea.</h3>
          <p>Search by meaning across your research papers.</p>
        </div>
      )}
    </section>
  );
}

export function AnalysisPane({ papers, initialPaper }: Props) {
  const [selected, setSelected] = useState(
    initialPaper ||
      papers.find((p) => p.processing_status === "ready")?.id ||
      "",
  );
  const [summary, setSummary] = useState<Summary | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run(mode: "summary" | "analysis") {
    setBusy(true);
    setError("");
    try {
      if (mode === "summary") {
        setSummary(await researchApi.summarize(selected));
        setAnalysis(null);
      } else {
        setAnalysis(await researchApi.analyze(selected));
        setSummary(null);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const paper = papers.find((p) => p.id === selected);
  return (
    <section className="research-panel">
      <div className="tool-header">
        <div>
          <h2>Paper analysis</h2>
          <p>Summarize the study or extract structured research findings.</p>
        </div>
        <Sparkles size={22} />
      </div>
      <ErrorMessage error={error} />
      <label className="filter-label">
        Select a paper
        <select
          value={selected}
          disabled={busy}
          onChange={(e) => {
            setSelected(e.target.value);
            setSummary(null);
            setAnalysis(null);
          }}
        >
          <option value="">Choose a ready paper</option>
          {papers
            .filter((p) => p.processing_status === "ready")
            .map((p) => (
              <option key={p.id} value={p.id}>
                {p.title || p.original_filename}
              </option>
            ))}
        </select>
      </label>
      {paper && (
        <div className="paper-metadata">
          <span>
            {paper.page_count} pages · {paper.chunk_count} passages
          </span>
          {paper.authors.length > 0 && <p>{paper.authors.join(", ")}</p>}
          {paper.abstract && (
            <p>
              <strong>Abstract: </strong>
              {paper.abstract}
            </p>
          )}
        </div>
      )}
      <div className="tool-actions">
        <button
          className="primary"
          disabled={busy || !selected}
          onClick={() => void run("summary")}
        >
          {busy ? (
            <LoaderCircle className="spin" size={16} />
          ) : (
            <BookOpen size={16} />
          )}
          Summarize paper
        </button>
        <button
          className="secondary"
          disabled={busy || !selected}
          onClick={() => void run("analysis")}
        >
          Structured analysis
        </button>
      </div>
      {(summary || analysis) && (
        <>
          <div className="coverage-note">
            {(summary || analysis)!.context_complete
              ? "All extracted passages were included."
              : "This analysis covers selected passages within the context limit. Review the full paper for additional findings."}
          </div>
          {summary && <Markdown text={summary.summary} />}{" "}
          {analysis && (
            <div className="analysis-grid">
              {Object.entries(analysis.analysis)
                .filter(([key]) => !["title", "authors"].includes(key))
                .map(([key, value]) => (
                  <article key={key}>
                    <h3>{key.replaceAll("_", " ")}</h3>
                    {(Array.isArray(value) ? value : [value]).length ? (
                      (Array.isArray(value) ? value : [value]).map(
                        (finding, i) =>
                          typeof finding === "object" && (
                            <p key={i}>
                              {finding.text}{" "}
                              {finding.source_ids
                                .map((id) => `[${id}]`)
                                .join(" ")}
                            </p>
                          ),
                      )
                    ) : (
                      <p>Not clearly stated in the paper.</p>
                    )}
                  </article>
                ))}
            </div>
          )}
          <Sources sources={(summary || analysis)!.sources} />
        </>
      )}
      {!selected && <EmptyResearch />}
    </section>
  );
}

export function ComparePane({ workspace, papers }: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const [focus, setFocus] = useState(
    "Compare methodologies, datasets, results and limitations.",
  );
  const [result, setResult] = useState<Comparison | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  function toggle(id: string) {
    setResult(null);
    setSelected((prev) =>
      prev.includes(id)
        ? prev.filter((i) => i !== id)
        : prev.length < 8
          ? [...prev, id]
          : prev,
    );
  }
  async function compare() {
    setBusy(true);
    setError("");
    try {
      setResult(await researchApi.compare(workspace, selected, focus));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="research-panel">
      <div className="tool-header">
        <div>
          <h2>Compare papers</h2>
          <p>
            Select 2–8 papers to compare approaches and findings with source
            evidence.
          </p>
        </div>
        <GitCompareArrows size={22} />
      </div>
      <ErrorMessage error={error} />
      <div className="paper-picker">
        {papers
          .filter((p) => p.processing_status === "ready")
          .map((p) => (
            <label key={p.id}>
              <input
                type="checkbox"
                checked={selected.includes(p.id)}
                disabled={
                  busy || (!selected.includes(p.id) && selected.length >= 8)
                }
                onChange={() => toggle(p.id)}
              />
              <FileName paper={p} />
            </label>
          ))}
      </div>
      <label className="filter-label">
        Comparison focus
        <select
          value={focus}
          disabled={busy}
          onChange={(e) => {
            setFocus(e.target.value);
            setResult(null);
          }}
        >
          {[
            "Compare methodologies, datasets, results and limitations.",
            "Compare methodology and model architectures.",
            "Compare datasets and evaluation protocols.",
            "Compare results and reported metrics.",
            "Compare limitations and computational requirements.",
          ].map((f) => (
            <option key={f}>{f}</option>
          ))}
        </select>
      </label>
      <button
        className="primary"
        disabled={busy || selected.length < 2}
        onClick={() => void compare()}
      >
        {busy ? (
          <LoaderCircle className="spin" size={16} />
        ) : (
          <GitCompareArrows size={16} />
        )}
        Compare {selected.length} papers
      </button>
      {result && (
        <>
          <div className="coverage-note">
            {result.comparable
              ? "The sources describe aligned evaluation settings; review the caveats before comparing results."
              : "Different settings may prevent a direct numerical comparison."}
            {result.caveats.map((c, i) => (
              <p key={i}>{c}</p>
            ))}
          </div>
          <div className="comparison-table">
            <table>
              <thead>
                <tr>
                  <th>Paper</th>
                  <th>Approach</th>
                  <th>Dataset</th>
                  <th>Metrics</th>
                  <th>Key result</th>
                  <th>Strength</th>
                  <th>Limitation</th>
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row) => (
                  <tr key={row.document_id}>
                    <td>
                      {row.paper}
                      <small>
                        {row.year} ·{" "}
                        {row.source_ids.map((id) => `[${id}]`).join(" ")}
                      </small>
                    </td>
                    <td>{row.approach}</td>
                    <td>{row.dataset}</td>
                    <td>{row.metrics}</td>
                    <td>{row.key_result}</td>
                    <td>{row.strength}</td>
                    <td>{row.limitation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Markdown text={result.narrative} />
          <details className="comparison-details">
            <summary>
              Training setup, preprocessing and computational requirements
            </summary>
            {result.rows.map((row) => (
              <article key={row.document_id}>
                <h3>{row.paper}</h3>
                <p>Objective: {row.objective}</p>
                <p>Dataset size: {row.dataset_size}</p>
                <p>Preprocessing: {row.preprocessing}</p>
                <p>Training: {row.training_setup}</p>
                <p>Computation: {row.computational_requirements}</p>
              </article>
            ))}
          </details>
          <Sources sources={result.sources} />
        </>
      )}
      {papers.filter((p) => p.processing_status === "ready").length < 2 && (
        <div className="empty">
          <GitCompareArrows size={30} />
          <h3>Bring two perspectives together.</h3>
          <p>Upload at least two papers to begin a comparison.</p>
        </div>
      )}
    </section>
  );
}
function FileName({ paper }: { paper: Paper }) {
  return (
    <span>
      <strong>{paper.title || paper.original_filename}</strong>
      <small>
        {paper.page_count} pages · {paper.original_filename}
      </small>
    </span>
  );
}

export function RecentConversations({
  workspace,
  onOpen,
}: {
  workspace: string;
  onOpen: () => void;
}) {
  const [items, setItems] = useState<string[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    researchApi
      .conversations(workspace)
      .then((result) => {
        if (!cancelled) setItems(result.slice(0, 3).map((c) => c.title));
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [workspace]);
  return (
    <section className="recent-conversations">
      <ErrorMessage error={error} />
      <div className="section-heading">
        <h2>Recent conversations</h2>
        <button className="text-action" onClick={onOpen}>
          Ask papers <ChevronIcon />
        </button>
      </div>
      {items.length ? (
        items.map((title, i) => (
          <button key={i} onClick={onOpen}>
            <MessageSquare size={14} />
            {title}
          </button>
        ))
      ) : (
        <p>Ask a question about your papers to start a conversation.</p>
      )}
    </section>
  );
}
function ChevronIcon() {
  return <span aria-hidden="true">→</span>;
}

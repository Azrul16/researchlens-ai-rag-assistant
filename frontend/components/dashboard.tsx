"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowDownToLine,
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  CircleHelp,
  FileText,
  FlaskConical,
  FolderOpen,
  Layers,
  MessageSquare,
  Search,
  GitCompareArrows,
  Settings,
  LoaderCircle,
  Plus,
  ScanLine,
  Sparkles,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import {
  API,
  Chunk,
  createWorkspace,
  openPaper,
  researchApi,
  Paper,
  request,
  uploadPaper,
  Workspace,
} from "@/lib/api";

import {
  ChatPane,
  SearchPane,
  AnalysisPane,
  ComparePane,
  RecentConversations,
} from "./research-tools";
import type { Health } from "@/lib/types";
import { workspacePath, type View } from "@/lib/navigation";
import { uploadDate } from "@/lib/format";

export default function Dashboard({
  initialWorkspaceId,
  initialView = "Overview",
  initialPaperId,
}: {
  initialWorkspaceId?: string;
  initialView?: View;
  initialPaperId?: string;
}) {
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [active, setActive] = useState<Workspace | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [modal, setModal] = useState(false);
  const [busy, setBusy] = useState(false);
  const [upload, setUpload] = useState<{
    name: string;
    progress: number;
  } | null>(null);
  const [view, setView] = useState<View>(initialView);
  const [selectedPaper, setSelectedPaper] = useState<string | undefined>(
    initialPaperId,
  );
  const [health, setHealth] = useState<Health | null>(null);
  const [editing, setEditing] = useState(false);
  const [detail, setDetail] = useState<Paper | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const modalRef = useRef<HTMLDialogElement>(null);
  const detailRef = useRef<HTMLDialogElement>(null);
  const reload = useCallback(async (id: string) => {
    const result = await request<Paper[]>(`/workspaces/${id}/documents`);
    setPapers(result);
  }, []);

  useEffect(() => {
    request<Workspace[]>("/workspaces")
      .then((result) => {
        setWorkspaces(result);
        setActive(
          (initialWorkspaceId
            ? result.find((w) => w.id === initialWorkspaceId)
            : result[0]) || null,
        );
        if (
          initialWorkspaceId &&
          !result.some((w) => w.id === initialWorkspaceId)
        )
          setError("This workspace does not exist.");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [initialWorkspaceId]);
  useEffect(() => {
    request<Health>("/health")
      .then(setHealth)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    request<Paper[]>(`/workspaces/${active.id}/documents`)
      .then((result) => {
        if (!cancelled) setPapers(result);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [active]);
  useEffect(() => {
    if (modal) {
      modalRef.current?.showModal();
      modalRef.current
        ?.querySelector<HTMLInputElement>('input[name="name"]')
        ?.focus();
    } else modalRef.current?.close();
  }, [modal]);
  useEffect(() => {
    if (detail) detailRef.current?.showModal();
    else detailRef.current?.close();
  }, [detail]);

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (upload) {
      setError(
        "Wait for the current upload to finish before changing workspaces.",
      );
      return;
    }
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const values = {
        name: String(form.get("name")),
        description: String(form.get("description")),
      };
      const workspace =
        editing && active
          ? await request<Workspace>(`/workspaces/${active.id}`, {
              method: "PATCH",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(values),
            })
          : await createWorkspace(values.name, values.description);
      setWorkspaces((previous) => [
        workspace,
        ...previous.filter((w) => w.id !== workspace.id),
      ]);
      setPapers([]);
      setActive(workspace);
      setModal(false);
      setNotice(
        editing
          ? "Workspace updated."
          : "Your workspace is ready. Upload a PDF to begin.",
      );
      setEditing(false);
      if (!editing) router.push(workspacePath(workspace.id, "Overview"));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function uploadFiles(files: FileList | File[]) {
    if (!active) {
      setModal(true);
      return;
    }
    setError("");
    setNotice("");
    for (const file of Array.from(files)) {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError(`${file.name}: Only PDF files are supported.`);
        continue;
      }
      setUpload({ name: file.name, progress: 0 });
      try {
        const paper = await uploadPaper(active.id, file, (progress) =>
          setUpload({ name: file.name, progress }),
        );
        if (paper.processing_error) setError(paper.processing_error);
        else
          setNotice(
            `${file.name} indexed successfully. You can now ask questions.`,
          );
        await reload(active.id);
      } catch (e) {
        setError((e as Error).message);
      }
    }
    setUpload(null);
    if (input.current) input.current.value = "";
  }
  async function remove(paper: Paper) {
    if (
      !window.confirm(
        `Delete ${paper.original_filename} and its extracted passages?`,
      )
    )
      return;
    setBusy(true);
    try {
      await request(`/documents/${paper.id}`, { method: "DELETE" });
      await reload(active!.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function inspect(paper: Paper) {
    setDetail(paper);
    setChunks([]);
    setChunksLoading(true);
    try {
      setChunks(await request<Chunk[]>(`/documents/${paper.id}/chunks`));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setChunksLoading(false);
    }
  }
  function selectWorkspace(workspace: Workspace) {
    if (workspace.id === active?.id || upload || busy) return;
    setPapers([]);
    setActive(workspace);
    setError("");
    setNotice("");
    router.push(workspacePath(workspace.id, view));
  }

  function newWorkspace() {
    setEditing(false);
    setModal(true);
  }

  function navigate(next: View, paper?: string) {
    setSelectedPaper(paper);
    setView(next);
    if (active)
      router.push(
        workspacePath(active.id, next) + (paper ? `?paper=${paper}` : ""),
      );
  }
  async function deleteWorkspace() {
    if (
      !active ||
      !window.confirm(
        `Delete workspace ${active.name}, all papers and conversations?`,
      )
    )
      return;
    try {
      await request(`/workspaces/${active.id}`, { method: "DELETE" });
      const remaining = workspaces.filter((w) => w.id !== active.id);
      setWorkspaces(remaining);
      setActive(remaining[0] || null);
      setPapers([]);
      setView("Overview");
      router.replace(
        remaining[0] ? workspacePath(remaining[0].id, "Overview") : "/",
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function open(id: string) {
    try {
      await openPaper(id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function retry(id: string) {
    setBusy(true);
    try {
      await researchApi.retry(id);
      await reload(active!.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const extracted = papers.filter((p) => p.processing_status === "ready");
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link className="brand" href="/">
          <span className="brand-mark">
            <ScanLine size={23} />
          </span>
          <span>
            ResearchLens<span className="ai">AI</span>
          </span>
        </Link>
        <div className="sidebar-label">RESEARCH LIBRARY</div>
        <button
          className={`nav-link ${view === "Overview" ? "selected" : ""}`}
          onClick={() => navigate("Overview")}
        >
          <Layers size={18} />
          Overview
        </button>
        <button
          className={`nav-link ${view === "Papers" ? "selected" : ""}`}
          onClick={() => navigate("Papers")}
        >
          <BookOpen size={18} />
          My papers<span className="nav-count">{papers.length}</span>
        </button>
        {(
          [
            { view: "Ask Papers", icon: MessageSquare },
            { view: "Compare", icon: GitCompareArrows },
            { view: "Semantic Search", icon: Search },
            { view: "Analysis", icon: Sparkles },
          ] as const
        ).map((item) => (
          <button
            key={item.view}
            className={`nav-link ${view === item.view ? "selected" : ""}`}
            onClick={() => navigate(item.view)}
          >
            <item.icon size={18} />
            {item.view}
          </button>
        ))}
        <div className="sidebar-label space-between">
          WORKSPACES
          <button
            className="icon-button"
            aria-label="Create workspace"
            onClick={() => {
              setEditing(false);
              setModal(true);
            }}
          >
            <Plus size={16} />
          </button>
        </div>
        {workspaces.map((workspace) => (
          <button
            key={workspace.id}
            onClick={() => selectWorkspace(workspace)}
            className={`workspace-link ${active?.id === workspace.id ? "current" : ""}`}
          >
            <FolderOpen size={16} />
            <span>{workspace.name}</span>
          </button>
        ))}
        {!workspaces.length && (
          <p className="sidebar-empty">A home for every research question.</p>
        )}
        <button
          className="new-workspace"
          onClick={() => {
            setEditing(false);
            setModal(true);
          }}
        >
          <Plus size={16} /> New workspace
        </button>
        <div className="sidebar-bottom">
          <div className="phase-card">
            <FlaskConical size={19} />
            <strong>Built for careful research</strong>
            <p>Keep original papers and their source pages together.</p>
          </div>
          <a
            className="nav-link"
            href={`${API.replace(/\/api\/v1$/, "")}/docs`}
            target="_blank"
            rel="noreferrer"
          >
            <CircleHelp size={17} />
            API documentation
            <ArrowRight size={15} />
          </a>
          <div className="profile">
            <span className="avatar">R</span>
            <div>
              <strong>Researcher</strong>
              <small>Local development workspace</small>
            </div>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            My library <ChevronRight size={14} />
            <span>{active?.name || "Overview"}</span>
          </div>
          <select
            className="workspace-selector"
            aria-label="Current workspace"
            value={active?.id || ""}
            onChange={(e) => {
              const w = workspaces.find((w) => w.id === e.target.value);
              if (w) selectWorkspace(w);
            }}
          >
            <option value="">Select workspace</option>
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
          <button
            className="icon-button"
            aria-label="Set API access token"
            onClick={() => {
              const token = window.prompt(
                "API access token (only needed if your server requires one). This is not your LLM provider key.",
              );
              if (token !== null) {
                if (token) sessionStorage.setItem("researchlens-token", token);
                else sessionStorage.removeItem("researchlens-token");
                window.location.reload();
              }
            }}
          >
            <Settings size={17} />
          </button>
          <span className="local-badge">
            <span />{" "}
            {health?.llm_configured
              ? `${health.llm_provider} connected`
              : "AI provider not configured"}
          </span>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">YOUR RESEARCH, IN FOCUS</div>
              <h1>
                {view === "Papers"
                  ? "Your paper collection"
                  : view === "Overview"
                    ? "A clearer view of your research."
                    : view}
              </h1>
              <p>
                Upload papers, ask questions, and compare studies with
                source-grounded citations.
              </p>
            </div>
            <button
              className="primary"
              disabled={!!upload}
              onClick={() => {
                if (active) {
                  navigate("Papers");
                  window.setTimeout(() => input.current?.click(), 0);
                } else {
                  setEditing(false);
                  setModal(true);
                }
              }}
            >
              <Plus size={17} />
              {active ? "Upload papers" : "Create workspace"}
            </button>
          </div>
          {error && (
            <div role="alert" className="alert error">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div role="status" className="alert success">
              <Check size={16} />
              {notice}
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {loading ? (
            <div className="loading">
              <LoaderCircle className="spin" />
              Loading your research library…
            </div>
          ) : (
            <>
              {view === "Overview" && (
                <section className="welcome-panel">
                  <div>
                    <span className="tag">
                      <Sparkles size={13} /> ResearchLens AI
                    </span>
                    <h2>
                      Understand research
                      <br />
                      papers faster.
                    </h2>
                    <p>
                      Upload papers, ask questions, and compare studies.
                      <br />
                      Receive evidence-grounded answers with citations.
                    </p>
                    <button className="text-action" onClick={newWorkspace}>
                      Start a new workspace <ArrowRight size={17} />
                    </button>
                  </div>
                  <div className="paper-art" aria-hidden="true">
                    <div className="art-orbit" />
                    <div className="art-sheet back" />
                    <div className="art-sheet">
                      <div className="art-caption">RESEARCH PAPER</div>
                      <div className="art-title" />
                      <div className="art-line" />
                      <div className="art-line short" />
                      <div className="art-chart">
                        <i />
                        <i />
                        <i />
                        <i />
                        <i />
                      </div>
                      <div className="art-line" />
                      <div className="art-line" />
                      <div className="art-line short" />
                      <span className="art-check">
                        <Check size={18} />
                        Source preserved
                      </span>
                    </div>
                    <span className="art-float">
                      <ScanLine size={24} />
                    </span>
                  </div>
                </section>
              )}
              {(view === "Overview" || view === "Papers") && (
                <>
                  <section className="stats" aria-label="Collection statistics">
                    {[
                      {
                        label: "Papers uploaded",
                        value: papers.length,
                        icon: FileText,
                        hint: "In this workspace",
                      },
                      {
                        label: "Pages extracted",
                        value: extracted.reduce((n, p) => n + p.page_count, 0),
                        icon: BookOpen,
                        hint: "Original page numbers retained",
                      },
                      {
                        label: "Source passages",
                        value: extracted.reduce((n, p) => n + p.chunk_count, 0),
                        icon: Layers,
                        hint: "Indexed for semantic retrieval",
                      },
                    ].map((stat) => (
                      <div className="stat" key={stat.label}>
                        <div className="stat-top">
                          {stat.label}
                          <stat.icon size={18} />
                        </div>
                        <strong>
                          {stat.value.toString().padStart(2, "0")}
                        </strong>
                        <small>{stat.hint}</small>
                      </div>
                    ))}
                  </section>
                  <section className="collection">
                    <div className="section-heading">
                      <div>
                        <h2>{active?.name || "Your research papers"}</h2>
                        <p>
                          {active?.description ||
                            "One place for your sources, ideas, and discoveries."}
                        </p>
                      </div>
                      {active && (
                        <div className="workspace-actions">
                          <button
                            className="icon-button"
                            aria-label="Edit workspace"
                            onClick={() => {
                              setEditing(true);
                              setModal(true);
                            }}
                          >
                            <Settings size={16} />
                          </button>
                          <button
                            className="icon-button delete"
                            aria-label="Delete workspace"
                            onClick={() => void deleteWorkspace()}
                          >
                            <Trash2 size={16} />
                          </button>
                          <span className="subtle">{papers.length} papers</span>
                        </div>
                      )}
                    </div>
                    <input
                      ref={input}
                      className="sr-only"
                      type="file"
                      accept="application/pdf,.pdf"
                      multiple
                      aria-label="Upload PDF papers"
                      disabled={!!upload}
                      onChange={(event) =>
                        event.target.files &&
                        void uploadFiles(event.target.files)
                      }
                    />
                    <button
                      className={`dropzone ${dragging ? "dragging" : ""}`}
                      disabled={!!upload}
                      onClick={() =>
                        active ? input.current?.click() : setModal(true)
                      }
                      onDragOver={(e) => {
                        e.preventDefault();
                        setDragging(true);
                      }}
                      onDragLeave={() => setDragging(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setDragging(false);
                        if (!upload) void uploadFiles(e.dataTransfer.files);
                      }}
                    >
                      <span className="upload-icon">
                        {upload ? (
                          <LoaderCircle className="spin" size={23} />
                        ) : (
                          <Upload size={23} />
                        )}
                      </span>
                      <span>
                        <strong>
                          {upload
                            ? `${upload.name} · ${upload.progress}%`
                            : "Drop your research papers here"}
                        </strong>
                        <small>
                          {upload
                            ? upload.progress === 100
                              ? "Extracting text and generating embeddings…"
                              : "Uploading…"
                            : `or click to browse · PDF files up to ${health?.max_upload_mb || 25} MB each`}
                        </small>
                      </span>
                      {!upload && (
                        <span className="browse-button">
                          Browse files <ArrowRight size={15} />
                        </span>
                      )}
                    </button>
                    {papers.length > 0 ? (
                      <div className="paper-list">
                        {papers.map((paper) => (
                          <article className="paper-row" key={paper.id}>
                            <span className="file-icon">
                              <FileText size={21} />
                              <small>PDF</small>
                            </span>
                            <button
                              className="paper-title"
                              onClick={() => void inspect(paper)}
                            >
                              <strong>
                                {paper.title || paper.original_filename}
                              </strong>
                              <small>
                                {paper.original_filename} · {paper.page_count}{" "}
                                pages · {(paper.file_size / 1024).toFixed(0)} KB
                                · Uploaded {uploadDate(paper.created_at)}
                              </small>
                            </button>
                            <span
                              className={`status ${paper.processing_status === "failed" ? "failed" : ""}`}
                            >
                              {paper.processing_status === "failed"
                                ? "Needs attention"
                                : paper.processing_status === "ready"
                                  ? "Ready"
                                  : paper.processing_status}
                            </span>
                            <button
                              className="icon-button"
                              aria-label={`Open ${paper.original_filename}`}
                              onClick={() => void open(paper.id)}
                            >
                              <ArrowDownToLine size={17} />
                            </button>
                            {paper.processing_status === "ready" && (
                              <button
                                className="icon-button"
                                aria-label={`Ask ${paper.original_filename}`}
                                onClick={() => navigate("Ask Papers", paper.id)}
                              >
                                <MessageSquare size={17} />
                              </button>
                            )}
                            {paper.processing_status === "failed" &&
                              paper.chunk_count > 0 && (
                                <button
                                  className="secondary"
                                  disabled={busy}
                                  onClick={() => void retry(paper.id)}
                                >
                                  Retry
                                </button>
                              )}
                            <button
                              className="icon-button delete"
                              disabled={busy}
                              aria-label={`Delete ${paper.original_filename}`}
                              onClick={() => void remove(paper)}
                            >
                              <Trash2 size={17} />
                            </button>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <div className="empty">
                        <BookOpen size={30} />
                        <h3>
                          {active
                            ? "Every discovery starts with a paper."
                            : "Give your research a workspace."}
                        </h3>
                        <p>
                          {active
                            ? "Upload your first PDF to build your collection."
                            : "Create a workspace, then add the papers you want to explore."}
                        </p>
                        {!active && (
                          <button
                            className="text-action"
                            onClick={newWorkspace}
                          >
                            Create your first workspace <ArrowRight size={16} />
                          </button>
                        )}
                      </div>
                    )}
                  </section>
                </>
              )}
              {active && view === "Overview" && (
                <>
                  <RecentConversations
                    key={active.id}
                    workspace={active.id}
                    onOpen={() => navigate("Ask Papers")}
                  />
                  <div className="quick-actions">
                    <button onClick={() => navigate("Ask Papers")}>
                      <MessageSquare size={20} />
                      <strong>Ask your papers</strong>
                      <small>Grounded answers with citations</small>
                    </button>
                    <button onClick={() => navigate("Compare")}>
                      <GitCompareArrows size={20} />
                      <strong>Compare studies</strong>
                      <small>Methods, datasets, and limitations</small>
                    </button>
                    <button onClick={() => navigate("Semantic Search")}>
                      <Search size={20} />
                      <strong>Find a research concept</strong>
                      <small>Search by meaning, across papers</small>
                    </button>
                  </div>
                </>
              )}
              {active && view === "Ask Papers" && (
                <ChatPane
                  key={`${active.id}:${selectedPaper}`}
                  workspace={active.id}
                  papers={papers}
                  initialPaper={selectedPaper}
                />
              )}
              {active && view === "Semantic Search" && (
                <SearchPane
                  key={active.id}
                  workspace={active.id}
                  papers={papers}
                />
              )}
              {active && view === "Analysis" && (
                <AnalysisPane
                  key={`${active.id}:${selectedPaper}`}
                  workspace={active.id}
                  papers={papers}
                  initialPaper={selectedPaper}
                />
              )}
              {active && view === "Compare" && (
                <ComparePane
                  key={active.id}
                  workspace={active.id}
                  papers={papers}
                />
              )}
              {!active && !["Overview", "Papers"].includes(view) && (
                <div className="empty">
                  <FolderOpen size={30} />
                  <h3>Create a workspace to begin.</h3>
                  <button className="primary" onClick={newWorkspace}>
                    Create workspace
                  </button>
                </div>
              )}
              <footer>
                <span>
                  <ScanLine size={15} /> ResearchLens AI
                </span>
                <span>RAG-Powered Research Paper Analysis and Comparison</span>
              </footer>
            </>
          )}
        </div>
      </main>
      <dialog
        ref={modalRef}
        onCancel={() => setModal(false)}
        className="dialog"
      >
        <button
          className="dialog-close icon-button"
          aria-label="Close dialog"
          onClick={() => setModal(false)}
        >
          <X size={20} />
        </button>
        <span className="dialog-icon">
          <FolderOpen size={24} />
        </span>
        <h2>{editing ? "Edit workspace" : "Create a workspace"}</h2>
        <p>A focused place for papers around one research topic.</p>
        <form onSubmit={create}>
          <label htmlFor="name">Workspace name</label>
          <input
            id="name"
            name="name"
            required
            maxLength={120}
            defaultValue={editing ? active?.name : ""}
            key={`name-${editing ? active?.id : "new"}`}
            placeholder="e.g. Log anomaly detection"
            autoFocus
          />
          <label htmlFor="description">
            Description <span>(optional)</span>
          </label>
          <textarea
            id="description"
            name="description"
            maxLength={2000}
            defaultValue={editing ? active?.description || "" : ""}
            key={`description-${editing ? active?.id : "new"}`}
            placeholder="What are you investigating?"
            rows={3}
          />
          <button className="primary" disabled={busy || !!upload}>
            {busy ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Plus size={17} />
            )}
            {editing ? "Save changes" : "Create workspace"}
          </button>
        </form>
      </dialog>
      <dialog
        ref={detailRef}
        onCancel={() => setDetail(null)}
        className="dialog detail-dialog"
      >
        <button
          className="dialog-close icon-button"
          aria-label="Close paper"
          onClick={() => setDetail(null)}
        >
          <X size={20} />
        </button>
        {detail && (
          <>
            <span className="tag">SOURCE PASSAGES</span>
            <h2>{detail.title || detail.original_filename}</h2>
            <p>
              {detail.page_count} pages · {detail.chunk_count} passages ·
              Showing the first 50 passages
            </p>
            {detail.processing_error && (
              <div className="alert error">{detail.processing_error}</div>
            )}
            <div className="tool-actions">
              <button
                className="primary"
                disabled={detail.processing_status !== "ready"}
                onClick={() => {
                  setDetail(null);
                  navigate("Ask Papers", detail.id);
                }}
              >
                Ask this paper
              </button>
              <button
                className="secondary"
                disabled={detail.processing_status !== "ready"}
                onClick={() => {
                  setDetail(null);
                  navigate("Analysis", detail.id);
                }}
              >
                Summarize / Analyze
              </button>
            </div>
            {detail.authors.length > 0 && <p>{detail.authors.join(", ")}</p>}
            {detail.abstract && <p>{detail.abstract}</p>}
            {chunksLoading && <p role="status">Loading source passages…</p>}
            {chunks.map((chunk) => (
              <article className="chunk" key={chunk.id}>
                <div>
                  Page {chunk.page_number}
                  {chunk.section_title && ` · ${chunk.section_title}`}
                </div>
                <p>{chunk.content}</p>
              </article>
            ))}
          </>
        )}
      </dialog>
    </div>
  );
}

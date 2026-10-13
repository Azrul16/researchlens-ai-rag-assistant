export type Workspace = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
};
export type Paper = {
  id: string;
  title: string | null;
  original_filename: string;
  page_count: number;
  chunk_count: number;
  processing_status: string;
  processing_error: string | null;
  file_size: number;
  created_at: string;
  authors: string[];
  abstract: string | null;
};
export type Chunk = {
  id: string;
  page_number: number;
  section_title: string | null;
  content: string;
};
export const API =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export function accessHeaders(): Record<string, string> {
  const token =
    typeof window !== "undefined"
      ? sessionStorage.getItem("researchlens-token")
      : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}
export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API}${path}`, {
      ...options,
      headers: { ...accessHeaders(), ...options?.headers },
    });
  } catch {
    throw new Error(
      "Cannot connect to the backend. Make sure it is running on port 8000.",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.error?.message || `Request failed (${response.status}).`,
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
export const createWorkspace = (name: string, description: string) =>
  request<Workspace>("/workspaces", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, description }),
  });
export function uploadPaper(
  workspace: string,
  file: File,
  progress: (value: number) => void,
): Promise<Paper> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API}/workspaces/${workspace}/documents`);
    for (const [name, value] of Object.entries(accessHeaders()))
      xhr.setRequestHeader(name, value);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable)
        progress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onerror = () =>
      reject(new Error("Upload failed. Check your backend connection."));
    xhr.onload = () => {
      try {
        const body = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) resolve(body);
        else reject(new Error(body?.error?.message || "Upload failed."));
      } catch {
        reject(new Error("The server returned an invalid upload response."));
      }
    };
    const body = new FormData();
    body.append("file", file);
    xhr.send(body);
  });
}

function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
}
import type {
  AnalysisResult,
  Answer,
  Citation,
  Comparison,
  Conversation,
  ConversationDetail,
  Summary,
} from "./types";
export const researchApi = {
  conversations: (workspace: string) =>
    request<Conversation[]>(`/workspaces/${workspace}/conversations`),
  createConversation: (workspace: string) =>
    post<Conversation>(`/workspaces/${workspace}/conversations`),
  conversation: (id: string) =>
    request<ConversationDetail>(`/conversations/${id}`),
  deleteConversation: (id: string) =>
    request<void>(`/conversations/${id}`, { method: "DELETE" }),
  sendMessage: (id: string, content: string, document_ids: string[]) =>
    post<Answer>(`/conversations/${id}/messages`, { content, document_ids }),
  search: (workspace: string, query: string, document_ids: string[]) =>
    post<{ results: Citation[] }>(`/workspaces/${workspace}/search`, {
      query,
      document_ids,
    }),
  summarize: (id: string, refresh = false) =>
    post<Summary>(`/documents/${id}/summary?refresh=${refresh}`),
  analyze: (id: string, refresh = false) =>
    post<AnalysisResult>(`/documents/${id}/analyze?refresh=${refresh}`),
  compare: (workspace: string, document_ids: string[], focus: string) =>
    post<Comparison>(`/workspaces/${workspace}/compare`, {
      document_ids,
      focus,
    }),
  retry: (id: string) => post<Paper>(`/documents/${id}/retry`),
  rebuild: (workspace: string) =>
    post<{ status: string; chunks: number }>(
      `/workspaces/${workspace}/rebuild-index`,
    ),
};

export async function openPaper(id: string, page = 1) {
  const response = await fetch(`${API}/documents/${id}/file`, {
    headers: accessHeaders(),
  });
  if (!response.ok)
    throw new Error(
      response.status === 404
        ? "Source document deleted."
        : "Could not open the source PDF.",
    );
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = `${url}#page=${page}`;
  link.target = "_blank";
  link.rel = "noopener";
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export type Citation = {
  source_id: string;
  document_id: string;
  document_title: string;
  page_number: number;
  chunk_id: string;
  section_title: string | null;
  excerpt: string;
  score: number;
};
export type Conversation = {
  id: string;
  workspace_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};
export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Citation[];
  created_at: string;
};
export type ConversationDetail = Conversation & { messages: ChatMessage[] };
export type Answer = {
  answer: string;
  sources: Citation[];
  sufficient_evidence: boolean;
};
export type Finding = { text: string; source_ids: string[] };
export type PaperAnalysis = {
  title: string;
  authors: string[];
  research_problem: Finding;
  methodology: Finding;
  objectives: Finding[];
  datasets: Finding[];
  models: Finding[];
  metrics: Finding[];
  key_results: Finding[];
  contributions: Finding[];
  limitations: Finding[];
  future_work: Finding[];
};
export type AnalysisResult = {
  analysis: PaperAnalysis;
  sources: Citation[];
  context_complete: boolean;
};
export type Summary = {
  summary: string;
  sources: Citation[];
  context_complete: boolean;
};
export type ComparisonRow = {
  document_id: string;
  paper: string;
  year: string;
  objective: string;
  approach: string;
  dataset: string;
  dataset_size: string;
  preprocessing: string;
  training_setup: string;
  metrics: string;
  key_result: string;
  strength: string;
  limitation: string;
  computational_requirements: string;
  source_ids: string[];
};
export type Comparison = {
  rows: ComparisonRow[];
  narrative: string;
  comparable: boolean;
  caveats: string[];
  source_ids: string[];
  sources: Citation[];
};
export type Health = {
  status: string;
  database: string;
  vector_store: string;
  llm_provider: string;
  llm_configured: boolean;
  max_upload_mb: number;
};

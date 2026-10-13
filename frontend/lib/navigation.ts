export type View =
  | "Overview"
  | "Papers"
  | "Ask Papers"
  | "Compare"
  | "Semantic Search"
  | "Analysis";
export const sections: Record<string, View> = {
  papers: "Papers",
  chat: "Ask Papers",
  compare: "Compare",
  search: "Semantic Search",
  analysis: "Analysis",
};
export function workspacePath(id: string, view: View) {
  const section = Object.entries(sections).find(
    ([, name]) => name === view,
  )?.[0];
  return `/workspace/${id}${section ? `/${section}` : ""}`;
}

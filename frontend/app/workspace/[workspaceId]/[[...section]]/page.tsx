import { notFound } from "next/navigation";
import Dashboard from "@/components/dashboard";
import { sections } from "@/lib/navigation";

export default async function Page({
  params,
  searchParams,
}: {
  params: Promise<{ workspaceId: string; section?: string[] }>;
  searchParams: Promise<{ paper?: string }>;
}) {
  const { workspaceId, section } = await params;
  const { paper } = await searchParams;
  if (
    !/^[a-f0-9-]{36}$/i.test(workspaceId) ||
    (section && (section.length !== 1 || !sections[section[0]]))
  )
    notFound();
  return (
    <Dashboard
      key={`${workspaceId}:${section?.[0]}:${paper}`}
      initialWorkspaceId={workspaceId}
      initialView={section ? sections[section[0]] : "Overview"}
      initialPaperId={
        paper && /^[a-f0-9-]{36}$/i.test(paper) ? paper : undefined
      }
    />
  );
}

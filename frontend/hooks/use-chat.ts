"use client";
import { useEffect, useState } from "react";
import { researchApi } from "@/lib/api";
import type { Conversation, ConversationDetail } from "@/lib/types";

export function useChat(workspace: string) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversation, setConversation] = useState<ConversationDetail | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    researchApi
      .conversations(workspace)
      .then((result) => {
        if (!cancelled) setConversations(result);
      })
      .catch((e) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [workspace]);
  async function load(id: string) {
    setBusy(true);
    setError("");
    try {
      setConversation(await researchApi.conversation(id));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function send(content: string, documentIds: string[]) {
    if (!content.trim() || busy) return false;
    setBusy(true);
    setError("");
    try {
      const target =
        conversation || (await researchApi.createConversation(workspace));
      if (!conversation) {
        setConversation({ ...target, messages: [] });
        setConversations((previous) => [target, ...previous]);
      }
      await researchApi.sendMessage(target.id, content, documentIds);
      setConversation(await researchApi.conversation(target.id));
      setConversations(await researchApi.conversations(workspace));
      return true;
    } catch (e) {
      setError((e as Error).message);
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function clear() {
    if (!conversation || busy) return;
    setBusy(true);
    setError("");
    try {
      await researchApi.deleteConversation(conversation.id);
      setConversation(null);
      setConversations(await researchApi.conversations(workspace));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return {
    conversations,
    conversation,
    busy,
    error,
    load,
    send,
    clear,
    newChat: () => setConversation(null),
  };
}

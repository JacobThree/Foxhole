"use client";

import { type FormEvent, useState } from "react";
import { ConfirmationPanel } from "@/components/confirmation-panel";
import { ToolCallCard } from "@/components/tool-call-card";
import { ChatResponse, ToolTrace, fetchApi, isApiError } from "@/lib/api-client";
import { Send } from "lucide-react";

type Message =
  | { id: string; role: "user"; content: string }
  | { id: string; role: "assistant"; response: ChatResponse }
  | { id: string; role: "status"; content: string; tone: "error" | "info" };

function newId() {
  return globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
}

function traceStatus(trace: ToolTrace) {
  if (trace.result.write_action.confirmation_required) return "awaiting_confirmation";
  return trace.result.success ? "success" : "error";
}

function statusText(error: unknown) {
  if (!isApiError(error)) return "Foxhole could not complete the request.";
  if (error.status === 401) return "Session expired. Open Settings and sign in again.";
  if (error.status === 503) return "Backend is not ready. Check the API token and Redis settings.";
  return `Request failed with ${error.status}.`;
}

export default function ChatPage() {
  const [prompt, setPrompt] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [lastPrompt, setLastPrompt] = useState("");
  const [loading, setLoading] = useState(false);

  const submitPrompt = async (
    message: string,
    confirmationTokens: Record<string, string> = {},
    echoUserMessage = true,
  ) => {
    const trimmed = message.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setLastPrompt(trimmed);
    if (echoUserMessage) {
      setMessages((current) => [...current, { id: newId(), role: "user", content: trimmed }]);
    }

    try {
      const response = await fetchApi<ChatResponse>("/chat", {
        method: "POST",
        body: JSON.stringify({
          message: trimmed,
          conversation_id: conversationId,
          confirmation_tokens: confirmationTokens,
        }),
      });
      setConversationId(response.conversation_id);
      setMessages((current) => [...current, { id: newId(), role: "assistant", response }]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        { id: newId(), role: "status", content: statusText(error), tone: "error" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = prompt;
    setPrompt("");
    void submitPrompt(message);
  };

  return (
    <div className="flex h-full flex-col bg-slate-950">
      <div className="border-b border-slate-800 bg-slate-900/50 p-4">
        <h1 className="text-xl font-bold">Diagnostics Chat</h1>
        <p className="text-sm text-slate-400">Evidence-backed investigations across your homelab</p>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
          {messages.length === 0 && (
            <div className="rounded border border-slate-800 bg-slate-900 p-5 text-sm text-slate-300">
              Ask about a service, import failure, storage warning, or suspicious network event.
            </div>
          )}

          {messages.map((message) => {
            if (message.role === "user") {
              return (
                <div
                  key={message.id}
                  className="max-w-[80%] self-end rounded border border-blue-500/30 bg-blue-600/20 p-4 text-blue-100"
                >
                  {message.content}
                </div>
              );
            }

            if (message.role === "status") {
              return (
                <div
                  key={message.id}
                  className="rounded border border-red-900/60 bg-red-950/30 p-4 text-sm text-red-200"
                >
                  {message.content}
                </div>
              );
            }

            return (
              <div
                key={message.id}
                className="w-full max-w-[85%] self-start rounded border border-slate-800 bg-slate-900 p-4"
              >
                <p className="whitespace-pre-wrap text-slate-200">{message.response.answer}</p>

                {message.response.findings.length > 0 && (
                  <div className="mt-4 grid gap-2">
                    {message.response.findings.map((finding) => (
                      <div
                        key={`${message.id}-${finding.title}`}
                        className="rounded border border-slate-800 bg-slate-950 p-3 text-sm"
                      >
                        <div className="font-medium text-slate-100">{finding.title}</div>
                        <div className="mt-1 text-slate-400">{finding.summary}</div>
                        <div className="mt-2 text-xs uppercase tracking-wide text-slate-500">
                          {finding.risk} risk / {finding.confidence} confidence
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {message.response.tool_traces.map((trace) => (
                  <div key={trace.tool_call_id} className="mt-4">
                    <ToolCallCard
                      toolName={trace.tool_name}
                      arguments={trace.arguments}
                      status={traceStatus(trace)}
                      duration={`${(trace.result.duration_ms / 1000).toFixed(2)}s`}
                      result={{
                        success: trace.result.success,
                        data: trace.result.data,
                        error: trace.result.error,
                      }}
                    />
                    {trace.result.write_action.confirmation_required && (
                      <ConfirmationPanel
                        title="Confirmation Required"
                        description={trace.result.error ?? "This write action needs manual approval."}
                        targetInfo={`Tool: ${trace.tool_name}`}
                        expectedToken={trace.result.write_action.confirmation_token}
                        disabled={loading}
                        onConfirm={(token) =>
                          void submitPrompt(lastPrompt, { [trace.tool_name]: token }, false)
                        }
                      />
                    )}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
      </div>

      <form onSubmit={handleSubmit} className="border-t border-slate-800 bg-slate-900 p-4">
        <div className="mx-auto flex max-w-4xl gap-3">
          <input
            type="text"
            className="min-w-0 flex-1 rounded border border-slate-800 bg-slate-950 px-4 py-3 text-slate-200 transition-all placeholder:text-slate-500 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            placeholder="Why did Radarr fail to import the last download?"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || prompt.trim().length === 0}
            className="flex items-center gap-2 rounded bg-blue-600 px-5 py-3 font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
          >
            <span>{loading ? "Sending" : "Send"}</span>
            <Send size={18} />
          </button>
        </div>
      </form>
    </div>
  );
}

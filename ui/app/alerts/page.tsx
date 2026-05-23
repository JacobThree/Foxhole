"use client";

import { useEffect, useState } from "react";
import { EventItem, EventSeverity, EventTable } from "@/components/event-table";
import { ApiEvent, fetchApi, isApiError } from "@/lib/api-client";
import { RefreshCw } from "lucide-react";

type LoadState = "loading" | "ready" | "unauthenticated" | "error";

function normalizeSeverity(severity: string): EventSeverity {
  const value = severity.toLowerCase();
  if (value === "critical" || value === "error" || value === "high") return "critical";
  if (value === "warning" || value === "warn" || value === "medium") return "warning";
  return "info";
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

function toEventItem(event: ApiEvent): EventItem {
  const severity = normalizeSeverity(event.severity);
  return {
    id: event.id,
    timestamp: formatTimestamp(event.timestamp),
    severity,
    source: event.source,
    message: event.payload_summary,
    correlationId: event.correlation_id,
    incidentId:
      severity === "info" ? null : `generated:${event.source}:${event.correlation_id || event.type}`,
  };
}

export default function AlertsPage() {
  const [events, setEvents] = useState<EventItem[]>([]);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  const loadEvents = async () => {
    setState("loading");
    setError(null);
    try {
      const data = await fetchApi<ApiEvent[]>("/events?limit=100");
      setEvents(data.map(toEventItem));
      setState("ready");
    } catch (err) {
      if (isApiError(err) && err.status === 401) {
        setState("unauthenticated");
        return;
      }
      setError(err instanceof Error ? err.message : "Could not load events.");
      setState("error");
    }
  };

  useEffect(() => {
    let cancelled = false;
    fetchApi<ApiEvent[]>("/events?limit=100")
      .then((data) => {
        if (cancelled) return;
        setEvents(data.map(toEventItem));
        setState("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        if (isApiError(err) && err.status === 401) {
          setState("unauthenticated");
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load events.");
        setState("error");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Alerts & Events</h1>
          <p className="text-sm text-slate-400 mt-1">
            System events and diagnostic findings
          </p>
        </div>
        <button
          type="button"
          onClick={loadEvents}
          disabled={state === "loading"}
          className="flex items-center gap-2 bg-slate-900 border border-slate-800 hover:bg-slate-800 disabled:text-slate-600 text-slate-300 px-4 py-2 rounded-lg transition-colors text-sm font-medium"
        >
          <RefreshCw size={16} className={state === "loading" ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>

      {state === "loading" && (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
          Loading events...
        </div>
      )}
      {state === "unauthenticated" && (
        <div className="rounded-lg border border-yellow-900/60 bg-yellow-950/30 p-6 text-sm text-yellow-200">
          Sign in from Settings before viewing events.
        </div>
      )}
      {state === "error" && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/30 p-6 text-sm text-red-200">
          {error}
        </div>
      )}
      {state === "ready" && <EventTable events={events} />}
    </div>
  );
}

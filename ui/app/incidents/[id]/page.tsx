"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AlertCircle, AlertTriangle, ArrowLeft, Info } from "lucide-react";
import { fetchApi, IncidentDetail, isApiError } from "@/lib/api-client";

type LoadState = "loading" | "ready" | "unauthenticated" | "missing" | "error";

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium",
  }).format(date);
}

function severityIcon(severity: string) {
  const value = severity.toLowerCase();
  if (value === "critical") return <AlertCircle className="text-red-400" size={18} />;
  if (value === "warning") return <AlertTriangle className="text-yellow-400" size={18} />;
  return <Info className="text-blue-400" size={18} />;
}

export default function IncidentDetailPage() {
  const params = useParams<{ id: string }>();
  const incidentId = useMemo(() => decodeURIComponent(params.id), [params.id]);
  const [detail, setDetail] = useState<IncidentDetail | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchApi<IncidentDetail>(`/incidents/${encodeURIComponent(incidentId)}`)
      .then((data) => {
        if (cancelled) return;
        setDetail(data);
        setState("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        if (isApiError(err) && err.status === 401) {
          setState("unauthenticated");
          return;
        }
        if (isApiError(err) && err.status === 404) {
          setState("missing");
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load incident.");
        setState("error");
      });

    return () => {
      cancelled = true;
    };
  }, [incidentId]);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <Link
          href="/alerts"
          className="mb-4 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200"
        >
          <ArrowLeft size={16} />
          Alerts
        </Link>
        <h1 className="text-3xl font-bold">Incident Timeline</h1>
      </div>

      {state === "loading" && (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
          Loading incident...
        </div>
      )}
      {state === "unauthenticated" && (
        <div className="rounded-lg border border-yellow-900/60 bg-yellow-950/30 p-6 text-sm text-yellow-200">
          Sign in from Settings before viewing incidents.
        </div>
      )}
      {state === "missing" && (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
          Incident not found.
        </div>
      )}
      {state === "error" && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/30 p-6 text-sm text-red-200">
          {error}
        </div>
      )}

      {state === "ready" && detail && (
        <div className="space-y-6">
          <section className="rounded-lg border border-slate-800 bg-slate-900 p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-sm uppercase text-slate-500">{detail.incident.source}</div>
                <h2 className="mt-1 text-xl font-semibold text-slate-100">
                  {detail.incident.title}
                </h2>
                <div className="mt-2 text-sm text-slate-400">
                  {detail.incident.event_count} events since{" "}
                  {formatTimestamp(detail.incident.created_at)}
                </div>
              </div>
              <div className="flex items-center gap-2 rounded border border-slate-700 px-3 py-2 text-sm text-slate-200">
                {severityIcon(detail.incident.severity)}
                {detail.incident.severity}
              </div>
            </div>
            {detail.incident.correlation_id && (
              <div className="mt-4 text-xs text-slate-500">
                {detail.incident.correlation_id}
              </div>
            )}
          </section>

          <section className="rounded-lg border border-slate-800 bg-slate-900">
            <div className="border-b border-slate-800 px-5 py-3 text-sm font-semibold text-slate-300">
              Timeline
            </div>
            <div className="divide-y divide-slate-800">
              {detail.timeline.map((entry) => (
                <div key={`${entry.timestamp}-${entry.event_id || entry.audit_id}`} className="p-5">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-3">
                      {severityIcon(entry.severity)}
                      <div>
                        <div className="font-medium text-slate-100">{entry.summary}</div>
                        <div className="text-xs text-slate-500">
                          {entry.source} · {formatTimestamp(entry.timestamp)}
                        </div>
                      </div>
                    </div>
                  </div>
                  {(entry.evidence_summary || entry.suggested_action) && (
                    <div className="mt-3 grid gap-2 text-sm text-slate-300">
                      {entry.evidence_summary && <div>{entry.evidence_summary}</div>}
                      {entry.suggested_action && (
                        <div className="text-cyan-200">{entry.suggested_action}</div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}


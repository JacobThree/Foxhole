"use client";

import { useEffect, useState } from "react";
import { EventItem, EventSeverity, EventTable } from "@/components/event-table";
import { ServiceItem, ServiceTable } from "@/components/service-table";
import { Status, StatusBadge } from "@/components/status-badge";
import {
  ApiEvent,
  CheckSummary,
  DashboardSummary,
  fetchApi,
  IntegrationState,
  isApiError,
} from "@/lib/api-client";

type LoadState = "loading" | "ready" | "unauthenticated" | "error";

function normalizeSeverity(severity: string): EventSeverity {
  const value = severity.toLowerCase();
  if (value === "critical" || value === "error" || value === "high") return "critical";
  if (value === "warning" || value === "warn" || value === "medium") return "warning";
  return "info";
}

function severityStatus(severity: string): Status {
  const normalized = normalizeSeverity(severity);
  if (normalized === "critical") return "degraded";
  if (normalized === "warning") return "warning";
  return "healthy";
}

function readinessStatus(readiness: Record<string, boolean>): Status {
  return Object.values(readiness).every(Boolean) ? "healthy" : "degraded";
}

function integrationToService(integration: IntegrationState & { name: string }): ServiceItem {
  const missing = integration.missing_configuration.join(", ");
  return {
    id: integration.name,
    name: integration.name,
    status: integration.configured ? "healthy" : integration.enabled ? "warning" : "unknown",
    detail: integration.configured
      ? "Configured"
      : integration.enabled
        ? `Missing ${missing || "configuration"}`
        : "Disabled",
  };
}

function checkToService(check: CheckSummary): ServiceItem {
  return {
    id: check.id,
    name: check.source,
    status: severityStatus(check.severity),
    detail: check.summary,
    updatedAt: formatTimestamp(check.timestamp),
  };
}

function formatTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function toEventItem(event: ApiEvent): EventItem {
  return {
    id: event.id,
    timestamp: formatTimestamp(event.timestamp),
    severity: normalizeSeverity(event.severity),
    source: event.source,
    message: event.payload_summary,
    correlationId: event.correlation_id,
  };
}

export default function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchApi<DashboardSummary>("/dashboard/summary")
      .then((data) => {
        if (cancelled) return;
        setSummary(data);
        setState("ready");
      })
      .catch((err) => {
        if (cancelled) return;
        if (isApiError(err) && err.status === 401) {
          setState("unauthenticated");
          return;
        }
        setError(err instanceof Error ? err.message : "Could not load dashboard summary.");
        setState("error");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const status = summary ? readinessStatus(summary.readiness) : "unknown";
  const integrationServices = summary?.integrations.map(integrationToService) ?? [];
  const latestChecks = summary?.latest_checks.map(checkToService) ?? [];
  const recentEvents = summary?.recent_events.map(toEventItem) ?? [];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold">Overview</h1>
        <div className="text-sm text-slate-400">
          {summary ? "Live API data" : "Loading"}
        </div>
      </div>

      {state === "loading" && (
        <div className="rounded-lg border border-slate-800 bg-slate-900 p-6 text-sm text-slate-400">
          Loading dashboard...
        </div>
      )}
      {state === "unauthenticated" && (
        <div className="rounded-lg border border-yellow-900/60 bg-yellow-950/30 p-6 text-sm text-yellow-200">
          Sign in from Settings before viewing the dashboard.
        </div>
      )}
      {state === "error" && (
        <div className="rounded-lg border border-red-900/60 bg-red-950/30 p-6 text-sm text-red-200">
          {error}
        </div>
      )}

      {state === "ready" && summary && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 flex flex-col gap-4">
              <h2 className="text-sm font-semibold text-slate-400">Agent Status</h2>
              <StatusBadge status={status} label={status === "healthy" ? "Ready" : "Degraded"} />
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
              <div className="text-sm font-semibold text-slate-400">Critical Events</div>
              <div className="mt-3 text-3xl font-bold text-red-300">
                {summary.severity_counts.critical ?? 0}
              </div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
              <div className="text-sm font-semibold text-slate-400">Warnings</div>
              <div className="mt-3 text-3xl font-bold text-yellow-300">
                {summary.severity_counts.warning ?? 0}
              </div>
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
              <div className="text-sm font-semibold text-slate-400">Configured Integrations</div>
              <div className="mt-3 text-3xl font-bold text-slate-100">
                {summary.integrations.filter((integration) => integration.configured).length}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
            <ServiceTable title="Integrations" services={integrationServices} />
            <ServiceTable title="Latest Checks" services={latestChecks} />
          </div>

          <section>
            <h2 className="mb-3 text-lg font-semibold text-slate-100">Recent Critical & Warning Events</h2>
            <EventTable events={recentEvents} />
          </section>
        </>
      )}
    </div>
  );
}

"use client";

import { type FormEvent, useEffect, useState } from "react";
import { FormGroup, SettingsForm } from "@/components/settings-form";
import {
  ReadyResponse,
  fetchApi,
  isApiError,
  loginWithBearerToken,
  logoutSession,
} from "@/lib/api-client";
import { LogIn, LogOut } from "lucide-react";

type SessionState = "checking" | "authenticated" | "unauthenticated" | "unconfigured";

function sessionMessage(state: SessionState, error: string | null) {
  if (error) return error;
  if (state === "authenticated") return "Browser session is active.";
  if (state === "unconfigured") return "Backend API token is not configured.";
  if (state === "unauthenticated") return "Sign in with the configured bearer token.";
  return "Checking browser session.";
}

export default function GeneralSettingsPage() {
  const [sessionState, setSessionState] = useState<SessionState>("checking");
  const [token, setToken] = useState("");
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const checkSession = async () => {
    try {
      await fetchApi<ReadyResponse>("/readyz");
      setSessionState("authenticated");
      setSessionError(null);
    } catch (error) {
      if (isApiError(error) && error.status === 401) {
        setSessionState("unauthenticated");
        setSessionError(null);
        return;
      }
      if (isApiError(error) && error.status === 503) {
        setSessionState("unconfigured");
        setSessionError(null);
        return;
      }
      setSessionState("unauthenticated");
      setSessionError("Could not reach the backend.");
    }
  };

  useEffect(() => {
    let cancelled = false;
    fetchApi<ReadyResponse>("/readyz")
      .then(() => {
        if (cancelled) return;
        setSessionState("authenticated");
        setSessionError(null);
      })
      .catch((error) => {
        if (cancelled) return;
        if (isApiError(error) && error.status === 401) {
          setSessionState("unauthenticated");
          setSessionError(null);
          return;
        }
        if (isApiError(error) && error.status === 503) {
          setSessionState("unconfigured");
          setSessionError(null);
          return;
        }
        setSessionState("unauthenticated");
        setSessionError("Could not reach the backend.");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setSessionError(null);
    try {
      await loginWithBearerToken(token);
      setToken("");
      await checkSession();
    } catch (error) {
      if (isApiError(error) && error.status === 503) {
        setSessionState("unconfigured");
      } else {
        setSessionState("unauthenticated");
      }
      setSessionError(isApiError(error) ? `Sign-in failed with ${error.status}.` : "Sign-in failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleLogout = async () => {
    setSubmitting(true);
    try {
      await logoutSession();
      setSessionState("unauthenticated");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
  };

  return (
    <div>
      <section className="mb-8 rounded border border-slate-800 bg-slate-900">
        <div className="border-b border-slate-800 p-6">
          <h2 className="text-xl font-semibold text-slate-100">Browser Session</h2>
          <p className="mt-1 text-sm text-slate-400">{sessionMessage(sessionState, sessionError)}</p>
        </div>
        <div className="p-6">
          {sessionState === "authenticated" ? (
            <button
              type="button"
              onClick={handleLogout}
              disabled={submitting}
              className="flex items-center gap-2 rounded border border-slate-700 bg-slate-950 px-4 py-2 text-sm font-medium text-slate-200 transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:text-slate-500"
            >
              <LogOut size={16} />
              Clear Session
            </button>
          ) : (
            <form onSubmit={handleLogin} className="flex max-w-xl flex-col gap-3 sm:flex-row">
              <input
                type="password"
                value={token}
                onChange={(event) => setToken(event.target.value)}
                className="min-w-0 flex-1 rounded border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 placeholder:text-slate-500 focus:border-blue-500 focus:outline-none"
                placeholder="Bearer token"
                disabled={submitting || sessionState === "unconfigured"}
              />
              <button
                type="submit"
                disabled={submitting || token.trim().length === 0 || sessionState === "unconfigured"}
                className="flex items-center justify-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
              >
                <LogIn size={16} />
                Sign In
              </button>
            </form>
          )}
        </div>
      </section>

      <SettingsForm
        title="Agent Behavior"
        description="Configure how Foxhole interacts with your homelab."
        onSubmit={handleSubmit}
      >
        <FormGroup label="Write-Action Mode" description="Control the safety level of the agent.">
          <select className="w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 focus:border-blue-500 focus:outline-none">
            <option value="stage1">Stage 1: Read-Only</option>
            <option value="stage2">Stage 2: Confirmed Writes</option>
            <option value="stage3" disabled>
              Stage 3: Autonomous
            </option>
          </select>
        </FormGroup>

        <FormGroup
          label="Allowed Scan Subnets"
          description="Comma-separated list of CIDR blocks the agent is allowed to scan."
        >
          <input
            type="text"
            defaultValue="192.168.1.0/24"
            className="w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 focus:border-blue-500 focus:outline-none"
          />
        </FormGroup>
      </SettingsForm>

      <SettingsForm title="Alert Destinations" onSubmit={handleSubmit}>
        <FormGroup label="Telegram Bot Token" description="Leave blank to disable Telegram alerts.">
          <input
            type="password"
            placeholder="••••••••••••••••••••"
            className="w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 focus:border-blue-500 focus:outline-none"
          />
        </FormGroup>

        <FormGroup label="Telegram Chat ID">
          <input
            type="text"
            className="w-full rounded border border-slate-800 bg-slate-950 px-3 py-2 text-slate-200 focus:border-blue-500 focus:outline-none"
          />
        </FormGroup>
      </SettingsForm>
    </div>
  );
}

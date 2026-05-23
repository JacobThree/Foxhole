"use client";

import { type FormEvent, useState, useEffect } from "react";
import { SettingsForm, FormGroup } from "@/components/settings-form";
import {
  IntegrationCapabilities,
  IntegrationManifest,
  ReadyResponse,
  fetchApi,
  isApiError,
} from "@/lib/api-client";

export default function IntegrationsSettingsPage() {
  const [settings, setSettings] = useState<ReadyResponse["settings"] | null>(null);
  const [capabilities, setCapabilities] = useState<IntegrationCapabilities[]>([]);
  const [manifests, setManifests] = useState<IntegrationManifest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const manifestsById = Object.fromEntries(manifests.map((manifest) => [manifest.id, manifest]));
  const configuredCount = capabilities.filter((item) => item.configured).length;
  const visibleCapabilityCount = capabilities.reduce(
    (total, item) => total + item.capabilities.length,
    0,
  );
  const writeCapabilityCount = capabilities.reduce(
    (total, item) =>
      total +
      item.capabilities.filter((capability) => capability.safety !== "read_only").length,
    0,
  );

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchApi<ReadyResponse>("/readyz"),
      fetchApi<IntegrationCapabilities[]>("/capabilities"),
      fetchApi<IntegrationManifest[]>("/integration-manifests"),
    ])
      .then(([ready, capabilityData, manifestData]) => {
        if (cancelled) return;
        setSettings(ready.settings);
        setCapabilities(capabilityData);
        setManifests(manifestData);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        if (isApiError(err) && err.status === 401) {
          setError("Session expired. Open General settings and sign in again.");
        } else if (isApiError(err) && err.status === 503) {
          setError("Backend is not ready. Check API token and Redis settings.");
        } else {
          setError(err instanceof Error ? err.message : "Error loading settings.");
        }
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async (e: FormEvent, integrationName: string) => {
    e.preventDefault();
    const formData = new FormData(e.target as HTMLFormElement);
    const updates: Record<string, string | boolean> = {};
    
    // Convert form data to updates object
    formData.forEach((value, key) => {
      // Checkboxes send "on" or are missing. We'll handle checkboxes explicitly.
      if (typeof value !== "string") return;
      if (value === "") return; // Don't send empty strings for secrets
      updates[key] = value;
    });

    // Handle checkboxes
    const enabledKey = `${integrationName}_enabled`;
    updates[enabledKey] = formData.get(enabledKey) === "on";

    try {
      const response = await fetchApi<ReadyResponse["settings"]>("/settings", {
        method: "PATCH",
        body: JSON.stringify({ updates }),
      });
      setSettings(response);
      const [capabilityData, manifestData] = await Promise.all([
        fetchApi<IntegrationCapabilities[]>("/capabilities"),
        fetchApi<IntegrationManifest[]>("/integration-manifests"),
      ]);
      setCapabilities(capabilityData);
      setManifests(manifestData);
      alert(`${integrationName} settings saved successfully!`);
    } catch (err) {
      const message = err instanceof Error ? err.message : "unknown error";
      alert(`Failed to save: ${message}`);
    }
  };

  if (loading) return <div className="text-slate-400">Loading settings...</div>;
  if (error) return <div className="text-red-400">Error loading settings: {error}</div>;

  return (
    <div className="space-y-8">
      <section className="rounded-lg border border-slate-800 bg-slate-900">
        <div className="border-b border-slate-800 p-6">
          <h2 className="text-xl font-semibold text-slate-100">What Foxhole Can See</h2>
          <p className="mt-1 text-sm text-slate-400">
            Configured integrations, read-only capabilities, and confirmation-gated actions.
          </p>
          <div className="mt-5 grid gap-3 md:grid-cols-3">
            <div className="border border-slate-800 bg-slate-950 p-3">
              <div className="text-xs uppercase text-slate-500">Configured integrations</div>
              <div className="mt-1 text-lg font-semibold text-slate-100">
                {configuredCount} / {capabilities.length}
              </div>
            </div>
            <div className="border border-slate-800 bg-slate-950 p-3">
              <div className="text-xs uppercase text-slate-500">Visible capabilities</div>
              <div className="mt-1 text-lg font-semibold text-slate-100">
                {visibleCapabilityCount}
              </div>
            </div>
            <div className="border border-slate-800 bg-slate-950 p-3">
              <div className="text-xs uppercase text-slate-500">Write-capable tools</div>
              <div className="mt-1 text-lg font-semibold text-slate-100">
                {writeCapabilityCount}
              </div>
            </div>
          </div>
        </div>
        <div className="divide-y divide-slate-800">
          {capabilities.map((item) => (
            <div key={item.integration} className="p-6">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <h3 className="font-semibold text-slate-100">{item.integration}</h3>
                  <div className="mt-1 text-sm text-slate-400">
                    {item.configured
                      ? "Configured"
                      : item.enabled
                        ? `Missing ${item.missing_configuration.join(", ") || "configuration"}`
                        : "Disabled"}
                  </div>
                </div>
                <span
                  className={`w-fit rounded px-2.5 py-1 text-xs font-medium ${
                    item.configured
                      ? "bg-green-950 text-green-300"
                      : item.enabled
                        ? "bg-yellow-950 text-yellow-300"
                        : "bg-slate-800 text-slate-400"
                  }`}
                >
                  {item.configured ? "Configured" : item.enabled ? "Incomplete" : "Disabled"}
                </span>
              </div>
              {item.capabilities.length > 0 ? (
                <div className="mt-4 grid gap-3">
                  {item.capabilities.map((capability) => (
                    <div
                      key={capability.tool_name}
                      className="rounded border border-slate-800 bg-slate-950 p-4"
                    >
                      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                        <div>
                          <div className="font-medium text-slate-200">{capability.tool_name}</div>
                          <div className="mt-1 text-sm text-slate-400">
                            {capability.description}
                          </div>
                        </div>
                        <span
                          className={`w-fit rounded px-2 py-1 text-xs font-medium ${
                            capability.safety === "read_only"
                              ? "bg-emerald-950 text-emerald-300"
                              : "bg-amber-950 text-amber-300"
                          }`}
                        >
                          {formatSafety(capability.safety)}
                        </span>
                      </div>
                      <div className="mt-3 text-xs font-medium uppercase text-slate-500">
                        Write-stage behavior
                      </div>
                      <div className="mt-1 text-xs text-slate-400">
                        {capability.stage_behavior}
                      </div>
                      {capability.capability_ids.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {capability.capability_ids.map((capabilityId) => (
                            <span
                              key={capabilityId}
                              className="rounded bg-slate-900 px-2 py-1 text-xs text-slate-400"
                            >
                              {capabilityId}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="mt-4 text-sm text-slate-500">
                  No active capabilities for this integration.
                </div>
              )}
              {manifestsById[item.integration] && (
                <div className="mt-4 border-t border-slate-800 pt-4 text-xs text-slate-500">
                  Manifest: {manifestsById[item.integration].name} v
                  {manifestsById[item.integration].version} ·{" "}
                  {manifestsById[item.integration].category}
                  {manifestsById[item.integration].resource_uris.length > 0 && (
                    <span>
                      {" "}
                      · Resources:{" "}
                      {manifestsById[item.integration].resource_uris.join(", ")}
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </section>

      <SettingsForm 
        title="Docker (Local API)" 
        description="Enable the agent to manage local Docker containers."
        onSubmit={(e) => handleSubmit(e, "docker")}
      >
        <FormGroup label="Enable Docker">
          <input 
            type="checkbox" 
            name="docker_enabled"
            defaultChecked={settings?.integrations?.docker}
            className="w-5 h-5 bg-slate-950 border-slate-800 rounded text-blue-500 focus:ring-blue-500" 
          />
        </FormGroup>

        <FormGroup label="Docker Socket Proxy URL">
          <input 
            type="text" 
            name="docker_socket_proxy_url"
            placeholder="tcp://docker-socket-proxy:2375"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>
      </SettingsForm>

      <SettingsForm 
        title="Plex Media Server" 
        description="Connect Foxhole to your Plex server for active stream and transcode monitoring."
        onSubmit={(e) => handleSubmit(e, "plex")}
      >
        <FormGroup label="Enable Plex">
          <input 
            type="checkbox" 
            name="plex_enabled"
            defaultChecked={settings?.integrations?.plex}
            className="w-5 h-5 bg-slate-950 border-slate-800 rounded text-blue-500 focus:ring-blue-500" 
          />
        </FormGroup>
        
        <FormGroup label="Plex Base URL">
          <input 
            type="text" 
            name="plex_base_url"
            placeholder="http://plex.local:32400"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>

        <FormGroup label="Plex Token" description="Provide the X-Plex-Token (Leave blank to keep existing)">
          <input 
            type="password" 
            name="plex_token"
            placeholder="••••••••••••••••••••"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>
      </SettingsForm>
      
      <SettingsForm 
        title="Proxmox VE" 
        description="Connect Foxhole to Proxmox for VM, LXC, and Backup Storage monitoring."
        onSubmit={(e) => handleSubmit(e, "proxmox")}
      >
        <FormGroup label="Enable Proxmox">
          <input 
            type="checkbox" 
            name="proxmox_enabled"
            defaultChecked={settings?.integrations?.proxmox}
            className="w-5 h-5 bg-slate-950 border-slate-800 rounded text-blue-500 focus:ring-blue-500" 
          />
        </FormGroup>
        
        <FormGroup label="Proxmox Host URL">
          <input 
            type="text" 
            name="proxmox_host"
            placeholder="https://pve.local:8006"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>

        <FormGroup label="Token ID">
          <input 
            type="text" 
            name="proxmox_token_id"
            placeholder="root@pam!foxhole"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>
        
        <FormGroup label="Token Secret" description="Leave blank to keep existing">
          <input 
            type="password" 
            name="proxmox_token_secret"
            placeholder="••••••••••••••••••••"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>
      </SettingsForm>

      <SettingsForm
        title="Uptime Kuma"
        description="Import monitor status and recent failures for read-only correlation."
        onSubmit={(e) => handleSubmit(e, "uptime_kuma")}
      >
        <FormGroup label="Enable Uptime Kuma">
          <input
            type="checkbox"
            name="uptime_kuma_enabled"
            defaultChecked={settings?.integrations?.uptime_kuma}
            className="w-5 h-5 bg-slate-950 border-slate-800 rounded text-blue-500 focus:ring-blue-500"
          />
        </FormGroup>

        <FormGroup label="Uptime Kuma Base URL">
          <input
            type="text"
            name="uptime_kuma_base_url"
            placeholder="http://uptime-kuma.local:3001"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500"
          />
        </FormGroup>

        <FormGroup label="API Token" description="Leave blank to keep existing">
          <input
            type="password"
            name="uptime_kuma_api_token"
            placeholder="••••••••••••••••••••"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500"
          />
        </FormGroup>
      </SettingsForm>

      <SettingsForm
        title="Caddy"
        description="Read reverse-proxy routes and upstream targets without editing config."
        onSubmit={(e) => handleSubmit(e, "caddy")}
      >
        <FormGroup label="Enable Caddy">
          <input
            type="checkbox"
            name="caddy_enabled"
            defaultChecked={settings?.integrations?.caddy}
            className="w-5 h-5 bg-slate-950 border-slate-800 rounded text-blue-500 focus:ring-blue-500"
          />
        </FormGroup>

        <FormGroup label="Caddyfile Path">
          <input
            type="text"
            name="caddy_config_path"
            placeholder="/etc/caddy/Caddyfile"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500"
          />
        </FormGroup>

        <FormGroup label="Caddy Admin API URL">
          <input
            type="text"
            name="caddy_admin_api_url"
            placeholder="http://localhost:2019"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500"
          />
        </FormGroup>
      </SettingsForm>

    </div>
  );
}

function formatSafety(safety: string) {
  if (safety === "read_only") return "Read-only";
  if (safety === "requires_confirmation") return "Confirmation required";
  if (safety === "autonomous_allowed") return "Policy-gated write";
  return safety;
}

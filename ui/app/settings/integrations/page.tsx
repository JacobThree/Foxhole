"use client";

import { type FormEvent, useState, useEffect } from "react";
import { SettingsForm, FormGroup } from "@/components/settings-form";
import { ReadyResponse, fetchApi, isApiError } from "@/lib/api-client";

export default function IntegrationsSettingsPage() {
  const [settings, setSettings] = useState<ReadyResponse["settings"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // We fetch the current status from /readyz to know what is enabled
  useEffect(() => {
    fetchApi<ReadyResponse>("/readyz")
      .then((data) => {
        setSettings(data.settings);
        setLoading(false);
      })
      .catch((err) => {
        if (isApiError(err) && err.status === 401) {
          setError("Session expired. Open General settings and sign in again.");
        } else if (isApiError(err) && err.status === 503) {
          setError("Backend is not ready. Check API token and Redis settings.");
        } else {
          setError(err instanceof Error ? err.message : "Error loading settings.");
        }
        setLoading(false);
      });
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

    </div>
  );
}

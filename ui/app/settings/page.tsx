"use client";

import { SettingsForm, FormGroup } from "@/components/settings-form";

export default function GeneralSettingsPage() {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Saving general settings");
  };

  return (
    <div>
      <SettingsForm 
        title="Agent Behavior" 
        description="Configure how Foxhole interacts with your homelab."
        onSubmit={handleSubmit}
      >
        <FormGroup 
          label="Write-Action Mode" 
          description="Control the safety level of the agent."
        >
          <select className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500">
            <option value="stage1">Stage 1: Read-Only (Safe)</option>
            <option value="stage2">Stage 2: Confirmed Writes</option>
            <option value="stage3" disabled>Stage 3: Autonomous (Coming Soon)</option>
          </select>
        </FormGroup>

        <FormGroup 
          label="Allowed Scan Subnets" 
          description="Comma-separated list of CIDR blocks the agent is allowed to scan (RFC1918 only)."
        >
          <input 
            type="text" 
            defaultValue="192.168.1.0/24"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>
      </SettingsForm>

      <SettingsForm 
        title="Alert Destinations" 
        onSubmit={handleSubmit}
      >
        <FormGroup 
          label="Telegram Bot Token" 
          description="Leave blank to disable Telegram alerts."
        >
          <input 
            type="password" 
            placeholder="••••••••••••••••••••"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>

        <FormGroup label="Telegram Chat ID">
          <input 
            type="text" 
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>
      </SettingsForm>
    </div>
  );
}

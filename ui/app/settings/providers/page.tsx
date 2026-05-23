"use client";

import { SettingsForm, FormGroup } from "@/components/settings-form";

export default function ProvidersSettingsPage() {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log("Saving provider settings");
  };

  return (
    <div>
      <SettingsForm 
        title="LLM Providers" 
        description="Configure the language models Foxhole uses for reasoning."
        onSubmit={handleSubmit}
      >
        <FormGroup 
          label="Primary Model (agent-primary)" 
          description="The main model used for complex reasoning and orchestrating tool calls."
        >
          <input 
            type="text" 
            defaultValue="gpt-4o"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>

        <FormGroup label="API Base URL (Optional)">
          <input 
            type="text" 
            placeholder="e.g. https://api.openai.com/v1"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>

        <FormGroup label="API Key">
          <input 
            type="password" 
            placeholder="••••••••••••••••••••"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>
      </SettingsForm>

      <SettingsForm 
        title="Local Model Fallback" 
        description="Configure Ollama or vLLM for local fallback."
        onSubmit={handleSubmit}
      >
        <FormGroup label="Local Model (agent-local)">
          <input 
            type="text" 
            defaultValue="ollama/llama3"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>

        <FormGroup label="Local API Base URL">
          <input 
            type="text" 
            defaultValue="http://localhost:11434"
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" 
          />
        </FormGroup>
      </SettingsForm>
    </div>
  );
}

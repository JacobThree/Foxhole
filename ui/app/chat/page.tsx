"use client";

import { useState } from "react";
import { ToolCallCard } from "@/components/tool-call-card";
import { ConfirmationPanel } from "@/components/confirmation-panel";
import { Send } from "lucide-react";

export default function ChatPage() {
  const [prompt, setPrompt] = useState("");
  
  return (
    <div className="flex flex-col h-full bg-slate-950">
      <div className="p-4 border-b border-slate-800 bg-slate-900/50">
        <h1 className="text-xl font-bold">Diagnostics Chat</h1>
        <p className="text-sm text-slate-400">Ask Foxhole to investigate issues across your homelab</p>
      </div>

      <div className="flex-1 overflow-auto p-4 space-y-6">
        <div className="flex flex-col gap-4 max-w-4xl mx-auto w-full">
          {/* Example Chat Message (User) */}
          <div className="self-end bg-blue-600/20 text-blue-100 border border-blue-500/30 rounded-lg p-4 max-w-[80%]">
            <p>Why is the Plex media server buffering for remote users?</p>
          </div>

          {/* Example Chat Message (Agent) */}
          <div className="self-start bg-slate-900 border border-slate-800 rounded-lg p-4 max-w-[85%] w-full">
            <p className="mb-4 text-slate-200">
              I&apos;m checking the current status of the Plex server and recent sessions.
            </p>
            
            <ToolCallCard
              toolName="plex_inspect_sessions"
              arguments='{"include_transcode_state": true}'
              status="success"
              duration="1.2s"
              result='{"active_sessions": 2, "transcoding": 2, "hardware_acceleration": false, "cpu_usage": "98%"}'
            />
            
            <p className="mt-4 text-slate-200">
              It looks like there are two active sessions currently transcoding. However, hardware acceleration is disabled and CPU usage is maxed out at 98%, which is likely causing the buffering.
            </p>
          </div>

          {/* Example Tool Call needing confirmation */}
          <div className="self-start w-full max-w-[85%]">
             <ToolCallCard
              toolName="docker_restart_container"
              arguments='{"container_name": "plex-media-server", "force": false}'
              status="awaiting_confirmation"
            />
            <ConfirmationPanel
              title="Restart Container Requested"
              description="The agent is attempting to restart the Plex container to see if it clears a stuck transcode process."
              targetInfo="Target: plex-media-server"
              onApprove={() => console.log('Approved')}
              onCancel={() => console.log('Cancelled')}
            />
          </div>
        </div>
      </div>

      <div className="p-4 bg-slate-900 border-t border-slate-800">
        <div className="max-w-4xl mx-auto flex gap-3">
          <input
            type="text"
            className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
            placeholder="E.g., Why did Radarr fail to import the last download?"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <button className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-lg font-medium transition-colors flex items-center gap-2">
            <span>Send</span>
            <Send size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}

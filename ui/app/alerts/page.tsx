"use client";

import { useState } from "react";
import { EventTable, EventItem } from "@/components/event-table";
import { Filter } from "lucide-react";

export default function AlertsPage() {
  const [events, setEvents] = useState<EventItem[]>([
    {
      id: "ev_1",
      timestamp: "2026-05-23 00:15:22",
      severity: "critical",
      source: "plex-media-server",
      message: "Database corruption warning detected in Plex logs.",
      acknowledged: false,
    },
    {
      id: "ev_2",
      timestamp: "2026-05-22 23:45:10",
      severity: "warning",
      source: "pve-backup",
      message: "Proxmox datastore 'backups' is above 85% capacity.",
      acknowledged: true,
    },
    {
      id: "ev_3",
      timestamp: "2026-05-22 21:05:01",
      severity: "info",
      source: "network-scan",
      message: "New unknown MAC address detected on VLAN 10.",
      acknowledged: false,
    }
  ]);

  const handleAcknowledge = (id: string) => {
    setEvents(events.map(ev => 
      ev.id === id ? { ...ev, acknowledged: true } : ev
    ));
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold">Alerts & Events</h1>
          <p className="text-sm text-slate-400 mt-1">
            System events and diagnostic findings
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 px-4 py-2 rounded-lg transition-colors text-sm font-medium">
            <Filter size={16} />
            Filter
          </button>
        </div>
      </div>

      <EventTable events={events} onAcknowledge={handleAcknowledge} />
    </div>
  );
}

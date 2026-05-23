import { ServiceTable, ServiceItem } from "@/components/service-table";
import { StatusBadge } from "@/components/status-badge";

export default function DashboardPage() {
  const dockerServices: ServiceItem[] = [
    { id: "1", name: "foxhole-api", status: "healthy", detail: "Uptime: 2 days" },
    { id: "2", name: "foxhole-worker", status: "healthy", detail: "Uptime: 2 days" },
    { id: "3", name: "plex-media-server", status: "warning", detail: "High CPU usage" },
  ];

  const proxmoxNodes: ServiceItem[] = [
    { id: "1", name: "pve-01", status: "healthy", detail: "Storage: 60% used" },
    { id: "2", name: "pve-backup", status: "degraded", detail: "Last backup failed" },
  ];

  const networkStatus: ServiceItem[] = [
    { id: "1", name: "Pi-hole DNS", status: "healthy", detail: "21,000 domains blocked" },
    { id: "2", name: "Unbound", status: "healthy", detail: "Latency: 12ms" },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold">Overview</h1>
        <div className="text-sm text-slate-400">
          Last updated: Just now
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6 flex flex-col justify-between">
          <h2 className="text-sm font-semibold text-slate-400 mb-4">Agent Status</h2>
          <div className="text-2xl font-bold flex items-center gap-2">
            <StatusBadge status="healthy" label="Online & Connected" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <ServiceTable title="Docker Containers" services={dockerServices} />
        <ServiceTable title="Proxmox Nodes & Storage" services={proxmoxNodes} />
        <ServiceTable title="Network & Security" services={networkStatus} />
      </div>
    </div>
  );
}

import Link from 'next/link';
import { LayoutDashboard, MessageSquare, AlertTriangle, Settings } from 'lucide-react';

export function Nav() {
  return (
    <nav className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col">
      <div className="p-4 border-b border-slate-800">
        <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
          Foxhole
        </h1>
        <p className="text-xs text-slate-400 mt-1">Homelab Control Plane</p>
      </div>
      <div className="p-4 flex-1 flex flex-col gap-2">
        <Link href="/" className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors">
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </Link>
        <Link href="/chat" className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors">
          <MessageSquare size={18} />
          <span>Chat</span>
        </Link>
        <Link href="/alerts" className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors">
          <AlertTriangle size={18} />
          <span>Alerts</span>
        </Link>
        <Link href="/settings" className="flex items-center gap-3 px-3 py-2 rounded-md hover:bg-slate-800 text-slate-300 hover:text-slate-100 transition-colors">
          <Settings size={18} />
          <span>Settings</span>
        </Link>
      </div>
    </nav>
  );
}

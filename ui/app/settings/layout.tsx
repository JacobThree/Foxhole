"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const tabs = [
    { name: "General", href: "/settings" },
    { name: "Providers", href: "/settings/providers" },
    { name: "Integrations", href: "/settings/integrations" },
  ];

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-sm text-slate-400 mt-1">Configure Foxhole agent behavior and integrations.</p>
      </div>

      <div className="flex border-b border-slate-800 mb-8">
        {tabs.map((tab) => (
          <Link
            key={tab.name}
            href={tab.href}
            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
              pathname === tab.href 
                ? "border-blue-500 text-blue-400" 
                : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700"
            }`}
          >
            {tab.name}
          </Link>
        ))}
      </div>

      <div>
        {children}
      </div>
    </div>
  );
}

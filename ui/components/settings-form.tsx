import { ReactNode } from "react";

interface SettingsFormProps {
  title: string;
  description?: string;
  children: ReactNode;
  onSubmit: (e: React.FormEvent) => void;
}

export function SettingsForm({ title, description, children, onSubmit }: SettingsFormProps) {
  return (
    <form onSubmit={onSubmit} className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden mb-8">
      <div className="p-6 border-b border-slate-800">
        <h2 className="text-xl font-semibold text-slate-100">{title}</h2>
        {description && <p className="text-sm text-slate-400 mt-1">{description}</p>}
      </div>
      <div className="p-6 space-y-6">
        {children}
      </div>
      <div className="p-6 bg-slate-900/50 border-t border-slate-800 flex justify-end gap-3">
        <button type="button" className="px-4 py-2 text-sm font-medium text-slate-300 hover:text-slate-100 transition-colors">
          Reset
        </button>
        <button type="submit" className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded transition-colors">
          Save Changes
        </button>
      </div>
    </form>
  );
}

export function FormGroup({ label, description, children }: { label: string, description?: string, children: ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-200 mb-1">{label}</label>
      {description && <p className="text-xs text-slate-400 mb-2">{description}</p>}
      {children}
    </div>
  );
}

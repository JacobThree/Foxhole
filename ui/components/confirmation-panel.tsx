import { AlertTriangle, Check, X } from 'lucide-react';

interface ConfirmationPanelProps {
  title: string;
  description: string;
  targetInfo: string;
  onApprove: () => void;
  onCancel: () => void;
}

export function ConfirmationPanel({ title, description, targetInfo, onApprove, onCancel }: ConfirmationPanelProps) {
  return (
    <div className="bg-amber-950/30 border border-amber-900/50 rounded-lg p-5 my-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="text-amber-500 shrink-0 mt-0.5" size={20} />
        <div className="flex-1">
          <h3 className="font-bold text-amber-500 mb-1">{title}</h3>
          <p className="text-sm text-slate-300 mb-3">{description}</p>
          <div className="bg-black/40 p-3 rounded text-sm font-mono text-slate-300 mb-4 border border-amber-900/30">
            {targetInfo}
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={onApprove}
              className="flex items-center gap-2 bg-amber-600 hover:bg-amber-500 text-white px-4 py-2 rounded transition-colors text-sm font-medium"
            >
              <Check size={16} />
              Approve Action
            </button>
            <button
              onClick={onCancel}
              className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 px-4 py-2 rounded transition-colors text-sm font-medium border border-slate-700"
            >
              <X size={16} />
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

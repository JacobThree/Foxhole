"use client";

import { type FormEvent, useState } from 'react';
import { AlertTriangle, Check } from 'lucide-react';

interface ConfirmationPanelProps {
  title: string;
  description: string;
  targetInfo: string;
  expectedToken?: string | null;
  onConfirm: (token: string) => void;
  disabled?: boolean;
}

export function ConfirmationPanel({
  title,
  description,
  targetInfo,
  expectedToken,
  onConfirm,
  disabled = false,
}: ConfirmationPanelProps) {
  const [token, setToken] = useState('');

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onConfirm(token.trim());
  };

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
          {expectedToken && (
            <div className="mb-3 text-xs text-amber-200">
              Confirmation token: <span className="font-mono">{expectedToken}</span>
            </div>
          )}
          <form onSubmit={handleSubmit} className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <input
              type="text"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              className="min-w-0 flex-1 rounded border border-amber-900/50 bg-slate-950 px-3 py-2 font-mono text-sm text-slate-100 placeholder:text-slate-500 focus:border-amber-500 focus:outline-none"
              placeholder="Paste confirmation token"
              disabled={disabled}
            />
            <button
              type="submit"
              disabled={disabled || token.trim().length === 0}
              className="flex items-center justify-center gap-2 rounded bg-amber-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-500 disabled:cursor-not-allowed disabled:bg-amber-900 disabled:text-amber-200"
            >
              <Check size={16} />
              Resubmit
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

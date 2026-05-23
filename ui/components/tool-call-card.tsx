import { CheckCircle2, Clock, XCircle, AlertCircle } from 'lucide-react';

interface ToolCallCardProps {
  toolName: string;
  arguments: unknown;
  status: 'running' | 'success' | 'error' | 'awaiting_confirmation';
  duration?: string;
  result?: unknown;
}

export function ToolCallCard({ toolName, arguments: args, status, duration, result }: ToolCallCardProps) {
  const formatJson = (value: unknown) => {
    if (typeof value === 'string') return value;
    return JSON.stringify(value, null, 2);
  };

  const getStatusIcon = () => {
    switch (status) {
      case 'running':
        return <Clock className="animate-pulse text-blue-400" size={16} />;
      case 'success':
        return <CheckCircle2 className="text-green-400" size={16} />;
      case 'error':
        return <XCircle className="text-red-400" size={16} />;
      case 'awaiting_confirmation':
        return <AlertCircle className="text-amber-400 animate-pulse" size={16} />;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg p-4 my-2 text-sm font-mono">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <span className="font-semibold text-slate-200">Tool: {toolName}</span>
        </div>
        {duration && <span className="text-slate-500">{duration}</span>}
      </div>
      <div className="bg-slate-950 p-2 rounded border border-slate-800 text-slate-300 mb-2 whitespace-pre-wrap">
        {formatJson(args)}
      </div>
      {result !== undefined && result !== null && (
        <div className="mt-2 border-t border-slate-800 pt-2 text-slate-400 whitespace-pre-wrap">
          {formatJson(result)}
        </div>
      )}
    </div>
  );
}

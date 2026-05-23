export type Status = 'healthy' | 'warning' | 'degraded' | 'unknown';

interface StatusBadgeProps {
  status: Status;
  label?: string;
}

export function StatusBadge({ status, label }: StatusBadgeProps) {
  const getStatusConfig = () => {
    switch (status) {
      case 'healthy':
        return { color: 'bg-green-400', text: 'text-green-400', defaultLabel: 'Healthy' };
      case 'warning':
        return { color: 'bg-yellow-400', text: 'text-yellow-400', defaultLabel: 'Warning' };
      case 'degraded':
        return { color: 'bg-red-400', text: 'text-red-400', defaultLabel: 'Degraded' };
      default:
        return { color: 'bg-slate-400', text: 'text-slate-400', defaultLabel: 'Unknown' };
    }
  };

  const config = getStatusConfig();

  return (
    <div className={`flex items-center gap-2 ${config.text} text-sm font-medium`}>
      <div className={`w-2 h-2 rounded-full ${config.color}`}></div>
      {label || config.defaultLabel}
    </div>
  );
}

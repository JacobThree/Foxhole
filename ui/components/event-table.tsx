import { AlertCircle, AlertTriangle, Info } from 'lucide-react';
import Link from 'next/link';

export type EventSeverity = 'info' | 'warning' | 'critical';

export interface EventItem {
  id: string;
  timestamp: string;
  severity: EventSeverity;
  source: string;
  message: string;
  correlationId?: string | null;
  incidentId?: string | null;
  acknowledged?: boolean;
}

interface EventTableProps {
  events: EventItem[];
  onAcknowledge?: (id: string) => void;
}

export function EventTable({ events, onAcknowledge }: EventTableProps) {
  const getSeverityIcon = (severity: EventSeverity) => {
    switch (severity) {
      case 'info':
        return <Info className="text-blue-400" size={18} />;
      case 'warning':
        return <AlertTriangle className="text-yellow-400" size={18} />;
      case 'critical':
        return <AlertCircle className="text-red-400" size={18} />;
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900/80 border-b border-slate-800 text-slate-400 uppercase text-xs">
            <tr>
              <th className="px-4 py-3 w-12"></th>
              <th className="px-4 py-3">Timestamp</th>
              <th className="px-4 py-3">Source</th>
              <th className="px-4 py-3">Message</th>
              {onAcknowledge && <th className="px-4 py-3 text-right">Actions</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {events.map((event) => (
              <tr key={event.id} className={`hover:bg-slate-800/50 transition-colors ${event.acknowledged ? 'opacity-50' : ''}`}>
                <td className="px-4 py-3 text-center">
                  {getSeverityIcon(event.severity)}
                </td>
                <td className="px-4 py-3 text-slate-300 whitespace-nowrap">
                  {event.timestamp}
                </td>
                <td className="px-4 py-3 font-medium text-slate-200">
                  {event.source}
                </td>
                <td className="px-4 py-3 text-slate-300">
                  <div>{event.message}</div>
                  {event.correlationId && (
                    <div className="mt-1 text-xs text-slate-500">{event.correlationId}</div>
                  )}
                  {event.incidentId && (
                    <Link
                      href={`/incidents/${encodeURIComponent(event.incidentId)}`}
                      className="mt-2 inline-flex text-xs font-medium text-cyan-300 hover:text-cyan-200"
                    >
                      Incident timeline
                    </Link>
                  )}
                </td>
                {onAcknowledge && (
                  <td className="px-4 py-3 text-right">
                    {!event.acknowledged && (
                      <button 
                        onClick={() => onAcknowledge(event.id)}
                        className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-3 py-1.5 rounded transition-colors"
                      >
                        Acknowledge
                      </button>
                    )}
                    {event.acknowledged && (
                      <span className="text-xs text-slate-500">Acknowledged</span>
                    )}
                  </td>
                )}
              </tr>
            ))}
            {events.length === 0 && (
              <tr>
                <td colSpan={onAcknowledge ? 5 : 4} className="px-4 py-8 text-center text-slate-500">
                  No events found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

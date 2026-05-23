import { Status, StatusBadge } from './status-badge';

export interface ServiceItem {
  id: string;
  name: string;
  status: Status;
  detail?: string;
  updatedAt?: string;
}

interface ServiceTableProps {
  title: string;
  services: ServiceItem[];
}

export function ServiceTable({ title, services }: ServiceTableProps) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-lg overflow-hidden">
      <div className="p-4 border-b border-slate-800 bg-slate-900/50">
        <h2 className="font-semibold text-slate-100">{title}</h2>
      </div>
      {services.length === 0 ? (
        <div className="p-4 text-slate-400 text-sm">No services found.</div>
      ) : (
        <ul className="divide-y divide-slate-800/50">
          {services.map((service) => (
            <li key={service.id} className="p-4 flex items-center justify-between">
              <div>
                <div className="font-medium text-slate-200">{service.name}</div>
                {service.detail && (
                  <div className="text-xs text-slate-400 mt-1">{service.detail}</div>
                )}
              </div>
              <div className="flex flex-col items-end gap-1">
                <StatusBadge status={service.status} />
                {service.updatedAt && (
                  <span className="text-xs text-slate-500">{service.updatedAt}</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

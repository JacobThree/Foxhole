export default function DashboardPage() {
  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <div className="text-sm text-slate-400">
          Last updated: Just now
        </div>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {/* Placeholder cards for dashboard metrics */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
          <h2 className="text-sm font-semibold text-slate-400 mb-2">Backend API</h2>
          <div className="text-2xl font-bold text-green-400 flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-400"></div>
            Healthy
          </div>
        </div>
      </div>
    </div>
  );
}

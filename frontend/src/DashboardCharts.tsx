import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

type TicketChartData = {
  name: string
  value: number
}

/**
 * Affiche les graphiques statistiques du tableau de bord.
 */
type DashboardChartsProps = {
  ticketData: TicketChartData[]
  totalTickets: number
}

export default function DashboardCharts({
  ticketData,
  totalTickets,
}: DashboardChartsProps) {
  return (
    <section className="grid grid-cols-1 gap-5 xl:grid-cols-3">
      <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm xl:col-span-2">
        <div className="mb-6">
          <h3 className="font-bold text-slate-900">Activité générale</h3>
          <p className="mt-1 text-xs text-slate-400">
            Répartition actuelle des tickets par statut
          </p>
        </div>

        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={ticketData}>
              <defs>
                <linearGradient
                  id="clientPulseGradient"
                  x1="0"
                  y1="0"
                  x2="0"
                  y2="1"
                >
                  <stop offset="0%" stopColor="#2563eb" stopOpacity={0.22} />
                  <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="#eef2f7"
              />
              <XAxis dataKey="name" axisLine={false} tickLine={false} />
              <YAxis
                allowDecimals={false}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip />
              <Area
                type="monotone"
                dataKey="value"
                name="Tickets"
                stroke="#2563eb"
                strokeWidth={2.5}
                fill="url(#clientPulseGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </article>

      <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-5">
          <h3 className="font-bold text-slate-900">État des tickets</h3>
          <p className="mt-1 text-xs text-slate-400">
            Répartition par statut
          </p>
        </div>

        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={ticketData} layout="vertical">
              <CartesianGrid
                strokeDasharray="3 3"
                horizontal={false}
                stroke="#eef2f7"
              />
              <XAxis type="number" allowDecimals={false} hide />
              <YAxis
                type="category"
                dataKey="name"
                axisLine={false}
                tickLine={false}
                width={75}
              />
              <Tooltip />
              <Bar
                dataKey="value"
                name="Tickets"
                fill="#3b82f6"
                radius={[0, 6, 6, 0]}
                barSize={18}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="mt-4 rounded-xl bg-blue-50 p-4">
          <p className="text-xs font-medium text-blue-600">
            Total des tickets
          </p>
          <p className="mt-1 text-2xl font-bold text-blue-900">
            {totalTickets}
          </p>
        </div>
      </article>
    </section>
  )
}

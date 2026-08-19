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

const currency = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'CNY',
  maximumFractionDigits: 2,
})

export function TrendChart({ data }: { data: { date: string; revenue: number }[] }) {
  const mondayTicks = data
    .filter((point) => new Date(`${point.date}T00:00:00Z`).getUTCDay() === 1)
    .map((point) => point.date)
  const weeklyTicks =
    mondayTicks.length > 0
      ? mondayTicks
      : [data.at(0)?.date, data.at(-1)?.date].filter((date): date is string => Boolean(date))

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 14, right: 8, left: -12, bottom: 0 }}>
        <defs>
          <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#b8e93b" stopOpacity={0.36} />
            <stop offset="95%" stopColor="#b8e93b" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#e8ece6" vertical={false} />
        <XAxis
          dataKey="date"
          axisLine={false}
          tickLine={false}
          ticks={weeklyTicks}
          interval="equidistantPreserveStart"
          tick={{ fill: '#7b857e', fontSize: 12 }}
          tickFormatter={(value: string) => value.slice(5)}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#7b857e', fontSize: 12 }}
          tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
        />
        <Tooltip
          formatter={(value) => currency.format(Number(value))}
          labelFormatter={(label) => String(label)}
          contentStyle={{ borderRadius: 12, borderColor: '#dfe5dd', fontSize: 12 }}
        />
        <Area
          type="monotone"
          dataKey="revenue"
          stroke="#7fae12"
          strokeWidth={2.5}
          fill="url(#revenueFill)"
          activeDot={{ r: 5, fill: '#17231a' }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

export function ProductsChart({ data }: { data: { name: string; revenue: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 18 }}>
        <CartesianGrid stroke="#eef1ec" horizontal={false} />
        <XAxis
          type="number"
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#7b857e', fontSize: 12 }}
          tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={88}
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#3d4941', fontSize: 13 }}
        />
        <Tooltip
          formatter={(value) => currency.format(Number(value))}
          cursor={{ fill: '#f4f7f1' }}
          contentStyle={{ borderRadius: 12, borderColor: '#dfe5dd', fontSize: 12 }}
        />
        <Bar dataKey="revenue" fill="#1d2d21" radius={[0, 6, 6, 0]} barSize={15} />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function AovTrendChart({ data }: { data: { month: string; value: number }[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 16, right: 12, left: 4, bottom: 0 }}>
        <defs>
          <linearGradient id="aovFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#17231a" stopOpacity={0.18} />
            <stop offset="95%" stopColor="#17231a" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#e8ece6" vertical={false} />
        <XAxis
          dataKey="month"
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#7b857e', fontSize: 12 }}
        />
        <YAxis
          domain={['auto', 'auto']}
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#7b857e', fontSize: 12 }}
          tickFormatter={(value: number) => currency.format(value)}
          width={72}
        />
        <Tooltip
          formatter={(value) => currency.format(Number(value))}
          labelFormatter={(label) => `${String(label)} 客单价`}
          contentStyle={{ borderRadius: 12, borderColor: '#dfe5dd', fontSize: 12 }}
        />
        <Area
          type="monotone"
          dataKey="value"
          stroke="#17231a"
          strokeWidth={2.5}
          fill="url(#aovFill)"
          activeDot={{ r: 5, fill: '#a8db2d' }}
        />
      </AreaChart>
    </ResponsiveContainer>
  )
}

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
          minTickGap={28}
          tick={{ fill: '#7b857e', fontSize: 11 }}
        />
        <YAxis
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#7b857e', fontSize: 11 }}
          tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
        />
        <Tooltip
          formatter={(value) => currency.format(Number(value))}
          labelFormatter={(label) => `2026-${label}`}
          contentStyle={{ borderRadius: 12, borderColor: '#dfe5dd' }}
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
          tick={{ fill: '#7b857e', fontSize: 11 }}
          tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={88}
          axisLine={false}
          tickLine={false}
          tick={{ fill: '#3d4941', fontSize: 12 }}
        />
        <Tooltip
          formatter={(value) => currency.format(Number(value))}
          cursor={{ fill: '#f4f7f1' }}
          contentStyle={{ borderRadius: 12, borderColor: '#dfe5dd' }}
        />
        <Bar dataKey="revenue" fill="#1d2d21" radius={[0, 6, 6, 0]} barSize={15} />
      </BarChart>
    </ResponsiveContainer>
  )
}

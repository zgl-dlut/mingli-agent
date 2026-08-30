import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

interface TrendPoint {
  version: string
  value: number
}

interface TrendChartProps {
  data: TrendPoint[]
  title?: string
  height?: number
  color?: string
  showGrid?: boolean
  showLegend?: boolean
}

export default function TrendChart({
  data,
  title,
  height = 300,
  color = '#3b82f6',
  showGrid = true,
  showLegend = false,
}: TrendChartProps) {
  if (data.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        {title && <div className="text-sm font-medium text-gray-700 mb-2">{title}</div>}
        <div className="flex items-center justify-center text-gray-400" style={{ height }}>
          暂无数据
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow p-4">
      {title && <div className="text-sm font-medium text-gray-700 mb-2">{title}</div>}
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data}>
          {showGrid && <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />}
          <XAxis 
            dataKey="version" 
            tick={{ fontSize: 12 }}
            tickLine={false}
          />
          <YAxis 
            tick={{ fontSize: 12 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip
            contentStyle={{ fontSize: '12px', padding: '8px 12px' }}
            formatter={(value: any) => [Number(value).toFixed(2), '值']}
            labelFormatter={(label) => `版本: ${label}`}
          />
          {showLegend && <Legend />}
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={{ fill: color, r: 4 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

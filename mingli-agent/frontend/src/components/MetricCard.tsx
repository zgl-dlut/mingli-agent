import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'

interface TrendPoint {
  version: string
  value: number
}

interface Delta {
  value: number
  type: 'increase' | 'decrease' | 'unchanged'
}

interface MetricCardProps {
  title: string
  value: number
  unit?: string
  trend?: TrendPoint[]
  delta?: Delta
  color?: string
  description?: string
}

export default function MetricCard({
  title,
  value,
  unit = '%',
  trend = [],
  delta,
  color = '#3b82f6',
  description,
}: MetricCardProps) {
  const getDeltaDisplay = () => {
    if (!delta || delta.type === 'unchanged') return null
    
    const isPositive = delta.type === 'increase'
    const arrow = isPositive ? '↑' : '↓'
    const colorClass = isPositive ? 'text-green-600' : 'text-red-600'
    
    return (
      <span className={`text-xs font-medium ${colorClass}`}>
        {arrow} {Math.abs(delta.value).toFixed(1)}{unit}
      </span>
    )
  }

  return (
    <div className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <div className="flex-1">
          <div className="text-sm text-gray-600 mb-1">{title}</div>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-bold text-gray-900">
              {value.toFixed(1)}
            </span>
            <span className="text-sm text-gray-500">{unit}</span>
            {getDeltaDisplay()}
          </div>
          {description && (
            <div className="text-xs text-gray-500 mt-1">{description}</div>
          )}
        </div>
      </div>
      
      {trend.length > 0 && (
        <div className="h-16 mt-3">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trend}>
              <Tooltip
                contentStyle={{ fontSize: '12px', padding: '4px 8px' }}
                formatter={(value: any) => [`${Number(value).toFixed(1)}${unit}`, title]}
                labelFormatter={(label) => `版本: ${label}`}
              />
              <Line
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}

import React from 'react'

interface DateSelectData {
  type?: string
  error?: string
  recommended_dates?: Array<{
    date: string
    ganzhi: string
    weekday: string
    shishen?: string
    reason: string
    score: number
  }>
  conflict_note?: string
  summary?: string
}

/** 判断 content 是否为择日 Agent 输出 */
export function isDateSelectReport(content: string): boolean {
  if (!content || !content.trim().startsWith('{')) return false
  try {
    const parsed = JSON.parse(content)
    return parsed.type === 'date_select'
  } catch {
    return false
  }
}

export const DateSelectCard = React.memo(({ content }: { content: string }) => {
  let data: DateSelectData = {}
  try {
    data = JSON.parse(content)
  } catch {
    return <div className="text-red-500 text-sm">择日结果解析失败</div>
  }

  // 错误情况
  if (data.error) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center">
        <p className="text-amber-700 text-sm">{data.error}</p>
      </div>
    )
  }

  const dates = data.recommended_dates || []

  return (
    <div className="space-y-3">
      {/* 无推荐日期 */}
      {dates.length === 0 && !data.error && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-center">
          <p className="text-amber-700 text-sm">
            {data.conflict_note || '未找到符合条件的吉日，请放宽条件后重试'}
          </p>
        </div>
      )}

      {/* 日期卡片 */}
      {dates.map((d, idx) => (
        <div
          key={d.date}
          className={`rounded-xl border p-4 ${
            d.score >= 90
              ? 'bg-green-50 border-green-200'
              : d.score >= 70
              ? 'bg-blue-50 border-blue-200'
              : 'bg-gray-50 border-gray-200'
          }`}
        >
          <div className="flex items-start justify-between mb-2">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold text-gray-800">{d.date}</span>
                <span className="text-sm text-gray-500">{d.weekday}</span>
                {idx === 0 && d.score >= 90 && (
                  <span className="text-xs bg-green-500 text-white px-1.5 py-0.5 rounded-full">最佳</span>
                )}
              </div>
              <div className="text-sm text-gray-600 mt-0.5">
                {d.ganzhi}
                {d.shishen && <span className="ml-2 text-gray-400">十神：{d.shishen}</span>}
              </div>
            </div>
            <div className="text-right">
              <div
                className={`text-2xl font-bold ${
                  d.score >= 90 ? 'text-green-600' : d.score >= 70 ? 'text-blue-600' : 'text-gray-500'
                }`}
              >
                {d.score}
              </div>
              <div className="text-[10px] text-gray-400">吉日评分</div>
            </div>
          </div>
          <p className="text-xs text-gray-600 leading-relaxed mt-1">{d.reason}</p>
        </div>
      ))}

      {/* 冲突说明 */}
      {data.conflict_note && dates.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg px-3 py-2">
          <p className="text-xs text-yellow-700">
            <span className="font-medium">⚠ 约束提示：</span>
            {data.conflict_note}
          </p>
        </div>
      )}

      {/* 总结 */}
      {data.summary && (
        <div className="bg-brand-bgCard rounded-xl px-4 py-3 border border-brand-inputBorder/30">
          <p className="text-sm text-brand-brownStrong leading-relaxed">{data.summary}</p>
        </div>
      )}
    </div>
  )
})

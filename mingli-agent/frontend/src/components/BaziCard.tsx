import { useEffect, useState } from 'react'
import type { AnalyzeResult } from '../api/bazi'

interface BaziCardProps {
  baziResult: AnalyzeResult
  onStartReading: () => void
  phase: 'flipping' | 'ready' | 'exiting'
}

export default function BaziCard({ baziResult, onStartReading, phase }: BaziCardProps) {
  const [showButton, setShowButton] = useState(false)

  useEffect(() => {
    if (phase === 'ready') {
      const timer = setTimeout(() => setShowButton(true), 800)
      return () => clearTimeout(timer)
    }
    setShowButton(false)
  }, [phase])

  const isExiting = phase === 'exiting'

  return (
    <div className={`bazi-card-container ${isExiting ? 'card-exit' : 'card-enter'}`}>
      {/* 翻牌卡片 */}
      <div className={`bazi-card-flip ${phase === 'ready' || phase === 'exiting' ? 'flipped' : ''}`}>
        {/* 卡片背面 */}
        <div className="bazi-card-back">
          <div className="bazi-card-back-inner">
            <div className="bazi-card-mystic">☯</div>
            <p className="bazi-card-back-title">命运之牌</p>
            <p className="bazi-card-back-subtitle">正在揭示你的命格密码...</p>
          </div>
        </div>

        {/* 卡片正面 */}
        <div className="bazi-card-front">
          <div className="bazi-card-content">
            {/* 顶部生肖标签 */}
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs text-indigo-300 bg-indigo-900/40 px-2 py-0.5 rounded-full">
                {baziResult.生肖}
              </span>
              <span className="text-xs text-amber-300">🔮 命格概括</span>
            </div>

            {/* 四柱 */}
            <div className="bazi-card-sizu">
              <p className="text-2xl font-bold text-white tracking-[0.3em] text-center">
                {baziResult.四柱}
              </p>
            </div>

            {/* 日主 · 旺衰 · 格局 */}
            <div className="flex items-center justify-center gap-2 mb-4">
              <span className="text-sm text-indigo-200">{baziResult.日主}</span>
              <span className="text-indigo-600">·</span>
              <span className="text-sm text-indigo-200">{baziResult.旺衰结论}</span>
              <span className="text-indigo-600">·</span>
              <span className="text-sm text-indigo-200">{baziResult.格局}</span>
            </div>

            {/* 用神 / 喜神 / 忌神 */}
            <div className="grid grid-cols-3 gap-2 mb-4">
              <div className="bg-red-500/20 border border-red-400/30 rounded-lg p-2 text-center">
                <p className="text-[10px] text-red-300">用神</p>
                <p className="text-lg font-bold text-red-400">{baziResult.用神}</p>
              </div>
              <div className="bg-emerald-500/20 border border-emerald-400/30 rounded-lg p-2 text-center">
                <p className="text-[10px] text-emerald-300">喜神</p>
                <p className="text-lg font-bold text-emerald-400">{baziResult.喜神}</p>
              </div>
              <div className="bg-gray-500/20 border border-gray-400/30 rounded-lg p-2 text-center">
                <p className="text-[10px] text-gray-300">忌神</p>
                <p className="text-lg font-bold text-gray-400">{baziResult.忌神}</p>
              </div>
            </div>

            {/* 补充信息 */}
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between text-indigo-200">
                <span>月令</span>
                <span className="text-white">{baziResult.月令}</span>
              </div>
              <div className="flex justify-between text-indigo-200">
                <span>当前大运</span>
                <span className="text-white">{baziResult.当前大运}</span>
              </div>
              <div className="flex justify-between text-indigo-200">
                <span>调候</span>
                <span className="text-white text-right max-w-[60%]">{baziResult.调候描述}</span>
              </div>
            </div>

            {/* 重点流年 */}
            {baziResult.重点流年 && baziResult.重点流年.length > 0 && (
              <div className="mt-3 pt-3 border-t border-indigo-700/50">
                <p className="text-[10px] text-indigo-400 mb-1.5">重点流年</p>
                <div className="flex flex-wrap gap-1.5">
                  {baziResult.重点流年.slice(0, 5).map((ly) => (
                    <span
                      key={ly.year}
                      className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium ${
                        ly.judge === '大吉' || ly.judge === '吉'
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : ly.judge === '大凶' || ly.judge === '凶'
                          ? 'bg-red-500/20 text-red-300'
                          : 'bg-amber-500/20 text-amber-300'
                      }`}
                    >
                      {ly.year} {ly.ganzhi} {ly.judge}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 开始解读按钮 */}
      <div className={`start-reading-btn ${showButton ? 'visible' : ''}`}>
        <button
          onClick={onStartReading}
          className="w-full py-3.5 rounded-xl text-white font-semibold text-base shadow-lg active:scale-[0.98] transition-all"
          style={{ backgroundColor: '#4A4E8F' }}
        >
          ✨ 开始解读
        </button>
        <p className="text-center text-indigo-300/60 text-xs mt-2">消耗 160 积分</p>
      </div>
    </div>
  )
}

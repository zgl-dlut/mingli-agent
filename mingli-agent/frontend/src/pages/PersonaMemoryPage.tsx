import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { personaApi, type PersonaMemory } from '../api/persona'
import { color, radius } from '../theme/tokens'

export default function PersonaMemoryPage() {
  const navigate = useNavigate()
  const { personaId } = useParams<{ personaId: string }>()
  const id = Number(personaId)
  const [memory, setMemory] = useState<PersonaMemory | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!id) return
    void personaApi.getMemory(id).then(({ data }) => setMemory(data))
  }, [id])

  const toggle = async () => {
    if (!memory) return
    setSaving(true)
    try {
      const { data } = await personaApi.updateMemory(id, !memory.enabled)
      setMemory(data)
    } finally {
      setSaving(false)
    }
  }

  const clear = async () => {
    if (!window.confirm('清空后无法恢复，确定清空全部人格记忆吗？')) return
    setSaving(true)
    try {
      await personaApi.clearMemory(id)
      const { data } = await personaApi.getMemory(id)
      setMemory(data)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="px-4 pb-8">
      <div className="flex items-center mb-4">
        <button onClick={() => navigate(-1)} aria-label="返回" className="w-8 text-xl" style={{ color: color.ink }}>‹</button>
        <h1 className="m-0 flex-1 text-center text-lg font-bold" style={{ color: color.ink }}>人格记忆</h1>
        <span className="w-8" />
      </div>

      {!memory ? (
        <div className="py-16 text-center text-sm" style={{ color: color.ink2 }}>加载中…</div>
      ) : (
        <>
          <section className="p-4" style={{ backgroundColor: color.card, borderRadius: radius.card }}>
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-sm font-bold" style={{ color: color.ink }}>在对话中使用记忆</div>
                <p className="m-0 mt-1 text-xs leading-5" style={{ color: color.ink2 }}>关闭后不再更新，也不会注入后续 Prompt。</p>
              </div>
              <button
                onClick={() => void toggle()}
                disabled={saving}
                role="switch"
                aria-checked={memory.enabled}
                className="relative h-7 w-12 flex-none disabled:opacity-50"
                style={{ backgroundColor: memory.enabled ? color.brand : color.segBg, borderRadius: radius.pill }}
              >
                <span
                  className="absolute top-1 h-5 w-5 rounded-full bg-white transition-all"
                  style={{ left: memory.enabled ? '24px' : '4px' }}
                />
              </button>
            </div>
          </section>

          <section className="mt-3 p-4" style={{ backgroundColor: color.card, borderRadius: radius.card }}>
            <div className="text-sm font-bold" style={{ color: color.ink }}>当前摘要</div>
            <div className="mt-3 space-y-3 text-xs leading-6">
              <div>
                <div style={{ color: color.ink2 }}>称呼</div>
                <div style={{ color: color.ink }}>{memory.preferred_name || '尚未记录'}</div>
              </div>
              <div>
                <div style={{ color: color.ink2 }}>近况</div>
                <div style={{ color: color.ink }}>{memory.current_context.length ? memory.current_context.join('；') : '尚未形成摘要'}</div>
              </div>
              <div>
                <div style={{ color: color.ink2 }}>阶段摘要</div>
                <div style={{ color: color.ink }}>{memory.stage_summary || '完成 6 个用户回合后自动更新'}</div>
              </div>
            </div>
          </section>

          <button
            onClick={() => void clear()}
            disabled={saving}
            className="mt-4 w-full py-3 text-sm disabled:opacity-50"
            style={{ color: color.danger, backgroundColor: color.card, borderRadius: '10px' }}
          >
            清空全部记忆
          </button>
          <p className="px-3 text-center text-[11px] leading-5" style={{ color: color.ink2 }}>清空会物理删除摘要正文，仅保留不含内容的审计记录。</p>
        </>
      )}
    </div>
  )
}

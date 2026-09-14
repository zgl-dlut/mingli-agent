import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

interface Section {
  title: string
  content: string
}

interface LegalDoc {
  title: string
  version: string
  updated_at: string
  sections: Section[]
}

interface LegalPageProps {
  type: 'terms' | 'privacy'
}

export default function LegalPage({ type }: LegalPageProps) {
  const navigate = useNavigate()
  const [doc, setDoc] = useState<LegalDoc | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchDoc = async () => {
      try {
        const res = await fetch(`/api/legal/${type}`)
        const data = await res.json()
        setDoc(data)
      } catch {
        setDoc(null)
      } finally {
        setLoading(false)
      }
    }
    fetchDoc()
    window.scrollTo(0, 0)
  }, [type])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#f2f0ed' }}>
        <div className="text-gray-500">加载中...</div>
      </div>
    )
  }

  if (!doc) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#f2f0ed' }}>
        <div className="text-center">
          <p className="text-gray-500 mb-4">加载失败</p>
          <button
            onClick={() => navigate(-1)}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg"
          >
            返回
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#f2f0ed' }}>
      {/* Header */}
      <header className="sticky top-0 z-10 bg-white/80 backdrop-blur-md border-b border-gray-100">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center justify-between">
          <button
            onClick={() => navigate(-1)}
            className="flex items-center gap-2 text-gray-600 hover:text-purple-600 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            返回
          </button>
          <div className="text-sm text-gray-400">
            v{doc.version} · 更新于 {doc.updated_at}
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-3xl mx-auto px-4 py-8">
        <div className="bg-white rounded-2xl shadow-sm p-6 md:p-10">
          {/* Title */}
          <h1 className="text-2xl md:text-3xl font-bold text-gray-800 text-center mb-2">
            {doc.title}
          </h1>
          <div className="text-center text-sm text-gray-400 mb-8">
            版本 {doc.version} · 最后更新：{doc.updated_at}
          </div>

          {/* Sections */}
          <div className="space-y-8">
            {doc.sections.map((section, index) => (
              <section key={index}>
                <h2 className="text-lg md:text-xl font-semibold text-gray-800 mb-3 pb-2 border-b border-purple-100">
                  {section.title}
                </h2>
                <div className="text-gray-600 leading-relaxed text-sm md:text-base whitespace-pre-line">
                  {section.content}
                </div>
              </section>
            ))}
          </div>

          {/* Footer */}
          <div className="mt-10 pt-6 border-t border-gray-100 text-center text-sm text-gray-400">
            <p>如您对本{type === 'terms' ? '协议' : '政策'}有任何疑问，可联系：</p>
            <p className="mt-1">support@qusuansuan.com</p>
          </div>
        </div>
      </main>
    </div>
  )
}
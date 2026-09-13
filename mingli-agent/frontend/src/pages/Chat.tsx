import React, { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useChatStore } from '../store/chatStore'
import { usePersonStore } from '../store/personStore'
import { useUserStore } from '../store/userStore'
import { chatApi } from '../api/chat'
import { personApi } from '../api/person'
import RechargeModal from '../components/RechargeModal'
import type { Person } from '../types'
import { analyzeBazi, AnalyzeResult } from '../api/bazi'
import Logo from '../components/Logo'
import { FollowupReportView, isStructuredReport } from '../components/FollowupReportView'
import { DateSelectCard, isDateSelectReport } from '../components/DateSelectCard'
import { normalizeReportContent } from '../utils/reportFormat'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { createLogger, traceId } from '../utils/logger'

const logger = createLogger('ChatPage')
const sseLogger = createLogger('SSE')

/** 从 assistant 消息 content（JSON字符串）中提取 suggested_questions */
function extractSuggestedQuestions(content: string): string[] | null {
  if (!content || !content.trim().startsWith('{')) return null
  try {
    const parsed = JSON.parse(content)
    const sq = parsed.suggested_questions
    if (Array.isArray(sq) && sq.length > 0 && sq.every(q => typeof q === 'string' && q.trim())) {
      return sq.map(q => q.trim())
    }
    return null
  } catch {
    return null
  }
}

/** 过滤掉已问过的推荐问题（精确匹配+包含匹配） */
function filterAsked(suggested: string[], messages: { role: string; content: string }[]): string[] {
  const askedSet = new Set(
    messages
      .filter(m => m.role === 'user')
      .map(m => m.content.replace(/\s+/g, ' ').trim())
  )
  return suggested.filter(q => {
    const normalized = q.replace(/\s+/g, ' ').trim()
    if (askedSet.has(normalized)) return false
    // 包含匹配：用户可能问了更长的版本
    for (const asked of askedSet) {
      if (asked.includes(normalized) || normalized.includes(asked)) return false
    }
    return true
  })
}

/** 报告内容渲染组件
 * 架构：
 * 1. 结构化 JSON 报告（追问）→ FollowupReportView 直渲染 React 组件（不走 Markdown）
 * 2. Markdown 报告（首次报告）→ normalizeReportContent 归一化 → react-markdown 解析
 *
 * 追问报告用 JSON 结构化，格式 100% 由组件控制，不依赖 Markdown 解析。
 * 首次报告仍用 Markdown + react-markdown，两条链路隔离互不影响。
 */
const HtmlContent = React.memo(({ content }: { content: string }) => {
  // 择日 Agent 结果：JSON 直渲染为日期卡片
  if (isDateSelectReport(content)) {
    return <DateSelectCard content={content} />
  }
  // 追问报告：JSON 直渲染
  if (isStructuredReport(content)) {
    return <FollowupReportView content={content} />
  }
  // 首次报告：Markdown + react-markdown
  const normalized = normalizeReportContent(content || '')
  return (
    <div className="report-content">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ node, ...props }) => <h2 {...props} />,
          h2: ({ node, ...props }) => <h2 {...props} />,
          h3: ({ node, ...props }) => <h3 {...props} />,
          h4: ({ node, ...props }) => <h4 {...props} />,
        }}
      >
        {normalized}
      </ReactMarkdown>
    </div>
  )
})

/** 读取 response.body 流，按文本块处理，每收到一个 chunk 调用 onChunk */
async function parseSSEStream(response: Response, onChunk: (text: string) => void): Promise<void> {
  sseLogger.debug(`parseSSEStream 开始`, { ok: response.ok, status: response.status })
  const reader = response.body?.getReader()
  if (!reader) throw new Error('No readable stream')

  const decoder = new TextDecoder('utf-8')
  let chunkCount = 0
  let totalBytes = 0

  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      sseLogger.debug(`parseSSEStream 完成`, { totalChunks: chunkCount, totalBytes })
      break
    }

    const text = decoder.decode(value, { stream: true })
    if (text.trim()) {
      chunkCount++
      totalBytes += value.byteLength
      onChunk(text)
    }
  }
}

function buildGejuSummary(result: AnalyzeResult): string {
  const sizhu = (result.四柱 || '').trim()
  if (!sizhu) return '命格概括'
  return sizhu
}

export default function Chat() {
  const { personId } = useParams<{ personId: string }>()
  const navigate = useNavigate()

  const { getPerson } = usePersonStore()
  const {
    messages,
    currentMessage,
    fetchMessages,
    setCurrentPerson,
    setCurrentMessage,
    setPersonGenerating,
    isPersonGenerating,
    generatingPersonIds,
    hasFirstReading,
    setFirstReadingGenerated,
  } = useChatStore()
  const { user, fetchUserInfo } = useUserStore()

  // 动态获取真实可见视口高度与偏移（解决移动端 100vh 包含地址栏 + iOS 键盘弹出时输入框位置错乱的问题）
  // iOS 键盘弹出时 visualViewport.height 变小且 offsetTop 增大（可视区被向上推），
  // fixed 容器需同时跟随 height 和 offsetTop，才能始终贴在键盘正上方
  const [viewportHeight, setViewportHeight] = useState(
    () => window.visualViewport?.height ?? window.innerHeight
  )
  const [viewportOffsetTop, setViewportOffsetTop] = useState(0)
  useEffect(() => {
    const vv = window.visualViewport
    if (!vv) return
    const handleUpdate = () => {
      setViewportHeight(vv.height)
      setViewportOffsetTop(vv.offsetTop)
    }
    handleUpdate()
    vv.addEventListener('resize', handleUpdate)
    // 键盘弹出/收起动画过程中 offsetTop 持续变化，scroll 事件负责实时跟随
    vv.addEventListener('scroll', handleUpdate)
    return () => {
      vv.removeEventListener('resize', handleUpdate)
      vv.removeEventListener('scroll', handleUpdate)
    }
  }, [])

  const [person, setPerson] = useState<Person | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [inputValue, setInputValue] = useState('')
  // 推荐追问Chip条：仅AI刚回答完时显示，刷新/重新进入不显示
  const [showSuggested, setShowSuggested] = useState(false)
  const [baziResult, setBaziResult] = useState<AnalyzeResult | null>(null)
  const [, setBaziLoading] = useState(false)
  const [cardPhase, setCardPhase] = useState<'loading' | 'ready' | 'done' | 'error'>('loading')
  const [isRechargeOpen, setIsRechargeOpen] = useState(false)
  // 生成进度相关状态（按人独立，支持并发生成）
  const [progressMap, setProgressMap] = useState<Record<number, { percent: number; time: string }>>({})
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  // 滚动控制状态
  const [showScrollUp, setShowScrollUp] = useState(false)
  const [showScrollDown, setShowScrollDown] = useState(false)
  // optimistic用户消息：发送追问时立即显示，fetchMessages后自动清除
  const [pendingUserMsg, setPendingUserMsg] = useState<string | null>(null)
  // optimistic 消息所属的 personId，防止切换会话后泄漏到其他人的对话框
  const [pendingUserMsgPid, setPendingUserMsgPid] = useState<number | null>(null)
  
  // 同步锁（按人独立），防止同一人物快速重复发送；不同人物可并发
  const isSendingMapRef = useRef<Map<number, boolean>>(new Map())

  // 最后发送内容与时间戳，用于拦截重复提交（点击/回车二次触发、移动端双击等）
  const lastSentContentRef = useRef<string>('')
  const lastSentTimeRef = useRef<number>(0)

  // 🛡️ 第二层：requestAnimationFrame 级别防抖，防止同一帧内 click + touchend 双重触发
  const sendPendingRef = useRef(false)

  // AbortController（按人独立），用于取消该人物之前的请求
  const abortControllersRef = useRef<Map<number, AbortController>>(new Map())
  // 生成代际计数（按人），防止同人物重发时旧 finally 误清新生成状态
  const genCounterRef = useRef<Map<number, number>>(new Map())

  // 防抖滚动引用
  const debounceScrollRef = useRef<number | null>(null)
  
  // 进度条定时器引用（按人独立）
  const progressTimersRef = useRef<Map<number, number>>(new Map())
  // 生成状态轮询定时器（按人独立）：刷新后恢复进度条时，轮询后端任务状态直到完成
  const generatingPollRef = useRef<Map<number, number>>(new Map())
  
  // 上一次滚动位置
  const lastScrollTopRef = useRef(0)

  // debug 日志仅输出到 console（避免 async 函数中频繁 setState 触发不必要的重渲染）
  const dlog = (msg: string) => {
    const ts = new Date().toLocaleTimeString()
    console.log(`[${ts}] ${msg}`)
  }

  // 检查并更新滚动按钮状态
  const checkScrollButtons = () => {
    const container = scrollContainerRef.current
    if (!container) return

    const scrollTop = container.scrollTop
    const scrollHeight = container.scrollHeight
    const clientHeight = container.clientHeight
    
    lastScrollTopRef.current = scrollTop

    // 判断内容是否可以滚动（内容高度大于容器高度）
    const canScroll = scrollHeight > clientHeight + 10
    
    // 只有在可以滚动的前提下，才根据位置显示按钮
    // 向上按钮：可以滚动 且 不在顶部（距离顶部 > 100px）
    setShowScrollUp(canScroll && scrollTop > 100)
    // 向下按钮：可以滚动 且 不在底部（距离底部 > 100px）
    setShowScrollDown(canScroll && scrollTop < scrollHeight - clientHeight - 100)
  }

  // 滚动监听，智能显示翻页按钮（不自动隐藏）
  // 注意：person 未加载时主容器未渲染，scrollContainerRef 为 null，
  // 依赖 person?.id 确保容器真正挂载后再绑定监听器，否则监听器永远不会生效
  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return

    container.addEventListener('scroll', checkScrollButtons, { passive: true })
    // 初始检查一次，确保按钮状态正确
    checkScrollButtons()
    return () => {
      container.removeEventListener('scroll', checkScrollButtons)
    }
  }, [person?.id])

  // 内容变化后重新检查滚动按钮状态（解决异步加载内容后按钮不显示的问题）
  // 键盘弹出会改变容器高度（viewportHeight 变化），也需要重新检查
  useEffect(() => {
    // 延迟检查，等待DOM更新完成
    const timer = setTimeout(() => {
      checkScrollButtons()
    }, 100)
    return () => clearTimeout(timer)
  }, [messages, currentMessage, pendingUserMsg, cardPhase, viewportHeight])

  /** 判断用户是否已经在页面底部附近（阈值 150px） */
  const isNearBottom = () => {
    const container = scrollContainerRef.current
    if (!container) return true
    const { scrollTop, scrollHeight, clientHeight } = container
    return scrollTop + clientHeight >= scrollHeight - 150
  }

  const scrollToBottom = (options: { force?: boolean } = {}) => {
    // 除非强制滚动，否则只在用户已经接近底部时才自动滚动
    // 避免用户手动上翻看历史消息时，被流式输出反复拉到底部
    if (!options.force && !isNearBottom()) {
      return
    }

    // 取消之前的滚动任务
    if (debounceScrollRef.current) {
      clearTimeout(debounceScrollRef.current)
    }
    // 设置防抖滚动，避免频繁滚动导致闪烁
    debounceScrollRef.current = window.setTimeout(() => {
      const container = scrollContainerRef.current
      if (!container) return
      // 使用容器的 scrollTo 而非元素的 scrollIntoView，避免影响外部布局
      container.scrollTo({
        top: container.scrollHeight - container.clientHeight,
        behavior: 'smooth'
      })
    }, 100)
  }

  // 🔍 诊断日志：监控 messages 数组变化
  useEffect(() => {
    const userMsgs = messages.filter(Boolean).filter(m => m.role === 'user').length
    const assistantMsgs = messages.filter(Boolean).filter(m => m.role === 'assistant').length
    const ids = messages.filter(Boolean).map(m => `${m.id}:${m.role[0]}`)
    logger.debug(`[Render] messages变化`, {
      total: messages.length,
      user: userMsgs,
      assistant: assistantMsgs,
      ids: ids.join(','),
    })
  }, [messages])

  const scrollToTop = () => {
    // 点击后立即隐藏按钮，不等待 scroll 事件回调，避免视觉延迟
    setShowScrollUp(false)
    scrollContainerRef.current?.scrollTo({
      top: 0,
      behavior: 'smooth'
    })
  }

  // 启动进度条和预计时间更新（按人独立）
  // elapsedOffset：刷新恢复时传入后端返回的真实已耗时秒数，避免进度条从10%重置
  const startProgress = (personId: number, elapsedOffset = 0) => {
    // 进度/预计时间计算（初始化和定时器共用）
    const compute = (elapsed: number) => {
      // 模拟进度：前60秒到30%，中间60秒到70%，最后60秒到95%
      let percent = 10 // 初始10%
      if (elapsed <= 60) {
        percent = 10 + Math.min(20, (elapsed / 60) * 20)
      } else if (elapsed <= 120) {
        percent = 30 + Math.min(40, ((elapsed - 60) / 60) * 40)
      } else {
        percent = 70 + Math.min(25, ((elapsed - 120) / 60) * 25)
      }
      const time = elapsed < 60 ? '预计1-2分钟' : elapsed < 120 ? '预计1分钟内' : '即将完成...'
      return { percent: Math.round(percent), time }
    }

    // 立即按已耗时显示进度（新发送时 offset=0 显示10%，刷新恢复时按真实耗时显示）
    let elapsed = Math.max(0, elapsedOffset)
    setProgressMap(prev => ({ ...prev, [personId]: compute(elapsed) }))

    // 清掉该人旧定时器
    const oldTimer = progressTimersRef.current.get(personId)
    if (oldTimer) clearInterval(oldTimer)

    const timer = window.setInterval(() => {
      elapsed += 1
      setProgressMap(prev => ({ ...prev, [personId]: compute(elapsed) }))
    }, 1000)
    progressTimersRef.current.set(personId, timer)
  }

  // 停止进度条（按人独立）
  const stopProgress = (personId: number) => {
    const timer = progressTimersRef.current.get(personId)
    if (timer) {
      clearInterval(timer)
      progressTimersRef.current.delete(personId)
    }
    setProgressMap(prev => {
      if (!prev[personId]) return prev
      const next = { ...prev }
      delete next[personId]
      return next
    })
  }

  // 启动生成状态轮询（刷新后恢复用）：每 3 秒查后端任务是否完成，完成后拉取消息
  const startGeneratingPoll = (personId: number, sid: number) => {
    const oldTimer = generatingPollRef.current.get(personId)
    if (oldTimer) clearInterval(oldTimer)
    const timer = window.setInterval(async () => {
      try {
        const { generating, error } = await chatApi.getGeneratingStatus(sid)
        if (error) {
          // 任务异常：显示错误提示，停止进度条
          logger.error(`[Resume] 后台生成异常`, { personId, error })
          clearInterval(timer)
          generatingPollRef.current.delete(personId)
          setPersonGenerating(personId, false)
          stopProgress(personId)
          setPendingUserMsg(null)
          setPendingUserMsgPid(null)
          alert(`生成失败，请稍后重试`)
          await fetchUserInfo()
        } else if (!generating) {
          logger.info(`[Resume] 后台生成完成，拉取消息并停止进度条`, { personId })
          clearInterval(timer)
          generatingPollRef.current.delete(personId)
          setPersonGenerating(personId, false)
          stopProgress(personId)
          await fetchMessages(personId, sid)
          setShowSuggested(true)  // 后台生成完成，显示推荐Chip
          await fetchUserInfo()
        }
      } catch (e) {
        logger.warn(`[Resume] 轮询失败`, String(e))
      }
    }, 3000)
    generatingPollRef.current.set(personId, timer)
  }

  // 消息或流式内容变化时：只在用户已经接近底部，或正在生成回复时自动滚动
  // 这样用户手动上翻看历史消息时不会被强制拉回底部
  useEffect(() => {
    scrollToBottom({ force: false })
  }, [messages, currentMessage, pendingUserMsg])

  // 追问/首次报告完成后的滚动定位：本轮"用户问题"贴可视区顶部，回答在下方展开（短回答自动整屏可见）。
  // 三个要点（此前版本三连 bug 的原因）：
  //  1) 触发信号用"最后一条消息id变化"，不能只依赖 showSuggested——连续追问时它恒为 true，effect 不再触发；
  //  2) 必须等生成结束（进度条移除、消息替换、面板出现都稳定后）再定位，否则高度继续变化会跳到中间；
  //  3) 用 rAF + 延迟等布局稳定，瞬时定位避免微信 webview smooth 动画被吞。
  const isThisGenerating = generatingPersonIds.includes(parseInt(personId || '0'))
  const safeMessages = messages.filter(Boolean)
  const lastMsg = safeMessages.length ? safeMessages[safeMessages.length - 1] : null
  const lastMsgId = lastMsg?.id ?? 0
  const lastMsgRole = lastMsg?.role ?? ''
  const suggestedVisible = showSuggested && !inputValue
  useEffect(() => {
    if (!suggestedVisible) return
    if (isThisGenerating) return  // 进度条还在（高度还会变），等其移除后本 effect 自动再触发
    let raf1 = 0
    let raf2 = 0
    const timer = window.setTimeout(() => {
      raf1 = requestAnimationFrame(() => {
        raf2 = requestAnimationFrame(() => {
          const container = scrollContainerRef.current
          if (!container) return
          // 取消消息滚动 effect 残留的防抖任务，避免它稍后把页面拽回底部覆盖定位
          if (debounceScrollRef.current) {
            clearTimeout(debounceScrollRef.current)
            debounceScrollRef.current = null
          }
          const bubbles = container.querySelectorAll('[data-role="user"]')
          const lastQuestion = bubbles[bubbles.length - 1] as HTMLElement | undefined
          if (!lastQuestion) {
            // 无用户问题气泡：回退滚到底
            container.scrollTo({ top: container.scrollHeight - container.clientHeight, behavior: 'auto' })
            return
          }
          if (!isNearBottom()) return  // 用户上翻阅读时不拽回
          const cRect = container.getBoundingClientRect()
          const qRect = lastQuestion.getBoundingClientRect()
          const target = container.scrollTop + (qRect.top - cRect.top) - 8
          container.scrollTo({ top: Math.max(0, target), behavior: 'auto' })
        })
      })
    }, 150)  // 等进度条移除、面板出现、消息替换等布局变化全部落定
    return () => {
      window.clearTimeout(timer)
      cancelAnimationFrame(raf1)
      cancelAnimationFrame(raf2)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestedVisible, isThisGenerating, lastMsgId, lastMsgRole])

  // optimistic 问题在生成完成（finally/catch 里 fetchMessages 后）清除，不在此 effect 提前清除
  // 提前清除会导致重试场景（messages 已有历史相同问题）optimistic 被误清，问题不显示

  useEffect(() => {
    if (!personId) return
    logger.info(`[Lifecycle] Chat组件 personId变更`, { personId })
    setShowSuggested(false)  // 切换/重新进入时隐藏推荐Chip
    const id = parseInt(personId)
    const p = getPerson(id)
    if (!p) {
      logger.warn(`[Lifecycle] person未找到，跳转首页`, { personId })
      navigate('/')
      return
    }
    // 如果 person 缺少 bazi_data（旧缓存），从 API 拉取最新数据
    if (!p.bazi_data || Object.keys(p.bazi_data).length === 0) {
      logger.info(`[Lifecycle] person缺少bazi_data，从API拉取`, { personId: id })
      personApi.get(id).then(res => {
        if (res.data.bazi_data) {
          // 更新 store 中的 person
          const updatedPerson = { ...p, bazi_data: res.data.bazi_data }
          usePersonStore.getState().setPersons(
            usePersonStore.getState().persons.map(pp => pp.id === id ? updatedPerson : pp)
          )
          setPerson(updatedPerson)
          logger.info(`[Lifecycle] 已从API获取bazi_data`, { personId: id })
        } else {
          // API 返回也没有 bazi_data，使用原始 person
          setPerson(p)
        }
      }).catch(err => {
        logger.error(`[Lifecycle] 获取person详情失败`, String(err))
        // 失败时使用原始 person
        setPerson(p)
      })
    } else {
      // person 有 bazi_data，直接设置
      setPerson(p)
    }
    // 切换当前会话（加载本地缓存，不重置生成状态，让生成中切换后进度条保留）
    setCurrentPerson(id)
    // 获取 session_id 并从后端拉取消息（person-safe：仅当前会话才更新可视列表）
    chatApi.getSessions().then(async sessions => {
      const s = sessions.find(s => s.person_id === id)
      if (s) {
        setSessionId(s.id)
        await fetchMessages(id, s.id)
        // 刷新后恢复：查询该会话是否在后台生成中（任务化，SSE 断开不影响生成）
        try {
          const { generating, error, elapsed_seconds } = await chatApi.getGeneratingStatus(s.id)
          if (error) {
            // 上次任务异常：显示错误提示（不恢复进度条）
            logger.error(`[Resume] 上次生成异常`, { personId: id, error })
            alert(`生成失败，请稍后重试`)
          } else if (generating && !isPersonGenerating(id)) {
            logger.info(`[Resume] 后台生成中，恢复进度条并启动轮询`, { personId: id, elapsed_seconds })
            setPersonGenerating(id, true)
            // 按后端返回的真实已耗时恢复进度，避免从10%重置
            startProgress(id, elapsed_seconds || 0)
            // 首次报告生成中刷新：隐藏"查看完整解读"按钮，避免用户重复点击触发生成
            setCardPhase('done')
            startGeneratingPoll(id, s.id)
          }
        } catch (e) {
          logger.warn(`[Resume] generating-status 查询失败`, String(e))
        }
      } else {
        // 该 person 没有对应的 session（session 被清空/删除等异常情况）
        // 调用 ensure-session 重建 session，避免沿用上一个人物的 sessionId 导致生成/拉取到错误人物的内容
        logger.warn(`[Lifecycle] 未找到 person 对应的 session，调用 ensure-session 重建`, {
          personId: id,
          sessionPersonIds: sessions.map(s => s.person_id),
        })
        try {
          const { data } = await personApi.ensureSession(id)
          setSessionId(data.session_id)
          await fetchMessages(id, data.session_id)
          logger.info(`[Lifecycle] ensure-session 重建完成`, { personId: id, sessionId: data.session_id, created: data.created })
        } catch (e) {
          logger.error(`[Lifecycle] ensure-session 重建失败，重置 sessionId 为 null`, { personId: id, error: String(e) })
          setSessionId(null)
        }
      }
    }).catch(err => {
      logger.error(`获取sessions失败`, String(err))
    })
    // 不在 personId 切换时 abort，让生成在后台继续；abort 移到下方卸载 effect
  }, [personId])

  // 仅在组件真正卸载（离开 /chat 路由）时中断所有人物的流式请求并清理进度/轮询定时器；
  // personId 切换不触发此 cleanup，保证后台生成继续、切回时进度条仍在
  useEffect(() => {
    return () => {
      logger.info(`[Lifecycle] Chat组件真正卸载，abort所有人物的流式请求`)
      abortControllersRef.current.forEach((c) => c.abort())
      abortControllersRef.current.clear()
      progressTimersRef.current.forEach((t) => clearInterval(t))
      progressTimersRef.current.clear()
      generatingPollRef.current.forEach((t) => clearInterval(t))
      generatingPollRef.current.clear()
    }
  }, [])

  // person 删除后的跳转由 HistoryPanel 的 navigate 负责，避免双重 navigate 冲突
  // SSE 流未中断的部分由 catch 里的 personExists 检查静默处理

  // 加载命理分析数据
  useEffect(() => {
    if (!person) return
    setCardPhase(hasFirstReading(person.id) ? 'done' : 'loading')
    setBaziLoading(true)
    setBaziResult(null)
    
    // 优先从 Person 对象获取已持久化的排盘数据
    if (person.bazi_data && Object.keys(person.bazi_data).length > 0) {
      setBaziResult(person.bazi_data as unknown as AnalyzeResult)
      setBaziLoading(false)
      if (!hasFirstReading(person.id)) {
        setCardPhase('ready')
      }
      return
    }
    
    // 如果 Person 没有排盘数据，调用 analyzeBazi 获取（兼容旧数据）
    analyzeBazi({
      birth_date: person.birth_date,
      birth_time: person.birth_time,
      longitude: person.longitude || 116.4,
      latitude: person.latitude || 39.9,
      gender: person.gender,
      location: person.birth_place || '',
    })
      .then((result) => {
        setBaziResult(result)
        if (!hasFirstReading(person.id)) {
          setCardPhase('ready')
        }
      })
      .catch((err) => {
        console.error('命理分析失败:', err)
        setBaziResult(null)
        if (!hasFirstReading(person.id)) {
          setCardPhase('error')
        }
      })
      .finally(() => {
        setBaziLoading(false)
      })
  }, [person?.id, person?.bazi_data])

  const handleGenerateFirstReading = async () => {
    const callId = traceId()
    const pid = person?.id
    logger.info(`[${callId}] handleGenerateFirstReading 入口`, {
      isSending: pid != null ? isSendingMapRef.current.get(pid) : undefined,
      hasPerson: !!person,
      isGenerating: pid != null ? isPersonGenerating(pid) : undefined,
      hasBaziResult: !!baziResult,
      userPoints: user?.points ?? 'unknown',
    })
    if (!person || pid == null) return
    if (isSendingMapRef.current.get(pid)) {
      logger.warn(`[${callId}] 被ref锁拦截`)
      return
    }
    isSendingMapRef.current.set(pid, true)

    if (isPersonGenerating(pid)) {
      logger.warn(`[${callId}] 前置条件不满足`, { isGenerating: true })
      isSendingMapRef.current.set(pid, false)
      return
    }
    if (!baziResult) {
      logger.warn(`[${callId}] baziResult为null`)
      alert('命理分析数据未就绪，请稍后重试')
      isSendingMapRef.current.set(pid, false)
      return
    }
    if (!sessionId) {
      logger.warn(`[${callId}] sessionId未就绪`)
      alert('会话未就绪，请稍后重试')
      isSendingMapRef.current.set(pid, false)
      return
    }
    // 注意：首次解读费用在创建 person 时已扣除（后端 person.py 扣 POINTS_FIRST_READING），
    // first-reading 接口不再扣分，此处无需积分检查与本地扣分

    // 取消该人物之前的请求
    abortControllersRef.current.get(pid)?.abort()
    const controller = new AbortController()
    abortControllersRef.current.set(pid, controller)

    // 生成代际：防止同人物重发时旧 finally 误清新状态
    const myGen = (genCounterRef.current.get(pid) ?? 0) + 1
    genCounterRef.current.set(pid, myGen)

    setPersonGenerating(pid, true)
    setCurrentMessage('')
    startProgress(pid)

    try {
      scrollToBottom({ force: true })
      logger.info(`[${callId}] 调用 getFirstReadingStream`, { sessionId })

      const response = await chatApi.getFirstReadingStream(sessionId, controller.signal)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const contentType = response.headers.get('content-type') || ''
      if (contentType.includes('application/json')) {
        logger.info(`[${callId}] 首次解读已存在（JSON响应），拉取消息`)
        await fetchMessages(pid, sessionId)
        setFirstReadingGenerated(pid)
      } else {
        let acc = ''
        let saved = false
        logger.info(`[${callId}] SSE连接建立，开始接收首次解读chunks`)
        await parseSSEStream(response, (chunk) => {
          acc += chunk
          const savedIdx = acc.indexOf('__SAVED__')
          if (savedIdx >= 0) {
            saved = true
            const display = acc.slice(0, savedIdx).replace(/\n+$/, '')
            setCurrentMessage(display, pid)
          } else {
            setCurrentMessage(acc, pid)
          }
        })
        logger.success(`[${callId}] SSE流完成`, { accLen: acc.length, saved })

        if (saved) {
          setCurrentMessage('')
          await fetchMessages(pid, sessionId)
          setFirstReadingGenerated(pid)
          setShowSuggested(true)  // 首次报告完成，显示推荐Chip
          await fetchUserInfo()
        }
      }
    } catch (err: any) {
      const personExists = usePersonStore.getState().persons.some(p => p.id === parseInt(personId || '0'))
      if (err?.name === 'AbortError' || !personExists) {
        logger.info(`[${callId}] 请求被中断或person已删除`)
      } else if (String(err?.message || err).includes('409')) {
        // 首次报告已在后台生成中（刷新后重复点击）：不视为失败，
        // 移交轮询机制等待完成，进度条按真实已耗时恢复
        logger.info(`[${callId}] 首次报告已在生成中(409)，转轮询等待完成`)
        genCounterRef.current.set(pid, myGen + 1)  // 使 finally 不清状态，保留进度条
        isSendingMapRef.current.set(pid, false)
        abortControllersRef.current.delete(pid)
        try {
          const { elapsed_seconds } = await chatApi.getGeneratingStatus(sessionId)
          startProgress(pid, elapsed_seconds || 0)
        } catch {
          // 查询失败则保持当前进度条
        }
        startGeneratingPoll(pid, sessionId)
      } else {
        logger.error(`[${callId}] 生成失败`, { error: String(err) })
        alert(`生成失败: ${String(err).replace('Error: ', '')}`)
      }
      await fetchUserInfo()
    } finally {
      // 仅当代际匹配（即没有被更新的发送覆盖）才清状态
      if (genCounterRef.current.get(pid) === myGen) {
        setPersonGenerating(pid, false)
        isSendingMapRef.current.set(pid, false)
        abortControllersRef.current.delete(pid)
        stopProgress(pid)
        logger.info(`[${callId}] 完成，锁已释放`, { pid })
      } else {
        logger.info(`[${callId}] 旧代际完成，跳过清状态`, { pid, myGen, current: genCounterRef.current.get(pid) })
      }
    }
  }

  const handleSend = async (overrideQuestion?: string) => {
    const callId = traceId()
    const pid = person?.id
    const isResume = !!overrideQuestion
    dlog(`handleSend入口 callId=${callId} pid=${pid} isResume=${isResume} inputLen=${(overrideQuestion ?? inputValue).length}`)
    logger.info(`[${callId}] handleSend 入口`, {
      isSending: pid != null ? isSendingMapRef.current.get(pid) : undefined,
      sendPending: sendPendingRef.current,
      inputLen: (overrideQuestion ?? inputValue).length,
      isResume,
      isGenerating: pid != null ? isPersonGenerating(pid) : undefined,
      hasPerson: !!person,
      hasBaziResult: !!baziResult,
      userPoints: user?.points ?? 'unknown',
    })

    // 🛡️ 第二层：rAF 帧级防抖，解决移动端 click + touchend 双重触发（恢复场景跳过）
    if (!isResume && sendPendingRef.current) {
      logger.warn(`[${callId}] 被rAF帧防抖拦截`, { sendPending: true })
      return
    }
    sendPendingRef.current = true
    requestAnimationFrame(() => { sendPendingRef.current = false })

    if (!person || pid == null) return
    // 同人物发送锁：防止同一人物快速重复发送；不同人物可并发
    if (isSendingMapRef.current.get(pid)) {
      dlog(`被ref锁拦截，退出`)
      logger.warn(`[${callId}] 被该人物ref锁拦截`, { pid })
      return
    }
    isSendingMapRef.current.set(pid, true)
    dlog(`锁已获取，进入主流程`)
    logger.info(`[${callId}] 锁已获取，进入主流程`, { pid })

    // 预处理输入：移除换行符和多余空白字符，防止文字被截断
    const normalizedInput = (overrideQuestion ?? inputValue).replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim()

    if (!normalizedInput) {
      dlog(`输入为空，退出`)
      logger.warn(`[${callId}] 输入为空，退出`)
      isSendingMapRef.current.set(pid, false)
      return
    }
    // 使用 baziResult 或 person.bazi_data（兜底）
    const baziDataToSend = baziResult || (person.bazi_data && Object.keys(person.bazi_data).length > 0 ? person.bazi_data as unknown as AnalyzeResult : null)
    
    if (!baziDataToSend) {
      dlog(`baziResult未就绪，退出`)
      logger.warn(`[${callId}] baziResult未就绪，退出`, { hasBaziResult: !!baziResult, hasPersonBaziData: !!person.bazi_data })
      alert('命理数据未就绪，请稍等或刷新页面重试')
      isSendingMapRef.current.set(pid, false)
      return
    }
    if (!sessionId) {
      dlog(`sessionId未就绪，退出`)
      logger.warn(`[${callId}] sessionId未就绪，退出`)
      alert('会话未就绪，请稍后重试')
      isSendingMapRef.current.set(pid, false)
      return
    }
    dlog(`前置检查通过 sid=${sessionId} question=${normalizedInput.slice(0, 30)}`)

    const question = normalizedInput

    // 重试判定：上一条消息是相同内容的 user 消息（中断后重问），重试时跳过积分门槛
    const lastMsg = messages.length > 0 ? messages[messages.length - 1] : null
    const isRetryOfUnanswered = !!(
      lastMsg
      && lastMsg.role === 'user'
      && lastMsg.content.replace(/\s+/g, ' ').trim() === question
      && question.length > 0
    )

    if (!isRetryOfUnanswered && (user?.points ?? 0) < 40) {
      logger.warn(`[${callId}] 积分不足`, { points: user?.points })
      setIsRechargeOpen(true)
      isSendingMapRef.current.set(pid, false)
      return
    }

    setInputValue('')

    // 拦截重复发送：仅拦截短时间内（3秒内）的重复提交
    const now = Date.now()
    const isRecentDuplicate =
      lastSentContentRef.current === question && now - lastSentTimeRef.current < 3000
    if (isRecentDuplicate) {
      logger.warn(`[${callId}] 短时间重复发送被拦截`, {
        lastContent: lastSentContentRef.current.slice(0, 30),
        diffMs: now - lastSentTimeRef.current,
      })
      isSendingMapRef.current.set(pid, false)
      return
    }
    lastSentContentRef.current = question
    lastSentTimeRef.current = now

    // 该人物正在生成时拒绝新请求（后端任务化，旧任务需完成或超时后才能发新问题）
    if (isPersonGenerating(pid)) {
      dlog(`被isPersonGenerating拦截（前端状态卡在生成中），退出`)
      logger.warn(`[${callId}] 该人物正在生成，拒绝新请求`, { pid })
      alert('正在生成中，请稍候完成后再发送新问题')
      isSendingMapRef.current.set(pid, false)
      return
    }
    dlog(`生成状态检查通过，准备发请求`)

    // 生成代际：防止同人物重发时旧 finally 误清新状态
    const myGen = (genCounterRef.current.get(pid) ?? 0) + 1
    genCounterRef.current.set(pid, myGen)

    const controller = new AbortController()
    abortControllersRef.current.set(pid, controller)

    // 立即显示进度条 + optimistic 问题（重试也显示，让用户看到刚发的问题）
    setPersonGenerating(pid, true)
    setCurrentMessage('')
    startProgress(pid)
    setPendingUserMsg(question)
    setPendingUserMsgPid(pid)
    scrollToBottom({ force: true })

    // 问题验证已移至后端 sendMessageStream 统一处理：拦截时后端落库 user+assistant(拦截文案)，
    // 通过 SSE 返回拦截文案 + __SAVED__，前端走和正常完成一样的 fetchMessages 流程，无需预检

    try {
      dlog(`调用sendMessageStream sid=${sessionId} isRetry=${isRetryOfUnanswered}`)
      logger.info(`[${callId}] 请求初始化完成，调用 sendMessageStream`, { sessionId, questionLen: question.length, isRetry: isRetryOfUnanswered })

      // 使用 sendMessageStream：后端扣积分 + 存用户消息 + 流式返回 + 存 AI 回复
      let acc = ''
      let saved = false
      const response = await chatApi.sendMessageStream(sessionId, question, controller.signal)
      dlog(`sendMessageStream响应 status=${response.status} ok=${response.ok}`)
      // 后端任务化：若该 session 正在生成（前端状态未同步时后端兜底），回滚并提示
      if (response.status === 409) {
        logger.warn(`[${callId}] 后端返回409：正在生成中`, { pid })
        setPersonGenerating(pid, false)
        stopProgress(pid)
        setPendingUserMsg(null)
        setPendingUserMsgPid(null)
        isSendingMapRef.current.set(pid, false)
        abortControllersRef.current.delete(pid)
        alert('正在生成中，请稍候完成后再发送新问题')
        return
      }
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      logger.info(`[${callId}] SSE连接建立，开始接收chunks`)
      let sseError: string | null = null
      await parseSSEStream(response, (chunk) => {
        acc += chunk
        const errorIdx = acc.indexOf('__ERROR__:')
        if (errorIdx >= 0) {
          // 后端任务异常：提取错误信息，显示提示
          sseError = acc.slice(errorIdx + '__ERROR__:'.length).split('\n')[0].trim()
          logger.error(`[${callId}] SSE 收到任务异常标记`, { sseError })
          return
        }
        const savedIdx = acc.indexOf('__SAVED__')
        if (savedIdx >= 0) {
          saved = true
          const display = acc.slice(0, savedIdx).replace(/\n+$/, '')
          setCurrentMessage(display, pid)
        } else {
          setCurrentMessage(acc, pid)
        }
      })
      logger.success(`[${callId}] SSE流完成`, { totalLen: acc.length, saved, sseError })
      dlog(`SSE流完成 totalLen=${acc.length} saved=${saved} sseError=${sseError}`)

      if (sseError) {
        // 任务异常：显示错误提示（积分已在重试场景免扣，正常场景不退）
        setPendingUserMsg(null)
        setPendingUserMsgPid(null)
        dlog(`任务异常，显示alert: ${sseError}`)
        alert(`生成失败(${sseError})，请稍后重试`)
      } else if (saved) {
        dlog(`存库完成，拉取消息`)
        setCurrentMessage('')
        await fetchMessages(pid, sessionId)
        setPendingUserMsg(null)
        setPendingUserMsgPid(null)
        setShowSuggested(true)  // 追问回答完成，显示推荐Chip
        await fetchUserInfo() // 刷新积分显示
      }
    } catch (err: any) {
      dlog(`catch异常: name=${err?.name} message=${err?.message} stack=${err?.stack?.slice(0, 200)}`)
      const personExists = usePersonStore.getState().persons.some(p => p.id === parseInt(personId || '0'))
      if (err?.name === 'AbortError' || !personExists) {
        dlog(`请求被中断或person已删除`)
        logger.info(`[${callId}] 请求被中断或person已删除`)
      } else {
        dlog(`发送失败: ${String(err)}`)
        logger.error(`[${callId}] 发送失败`, { error: String(err) })
        alert(`发送失败: ${err?.name || 'Error'} - ${err?.message || String(err)}`)
      }
      await fetchUserInfo()
    } finally {
      // 仅当代际匹配才清状态，避免旧 finally 误清新生成
      if (genCounterRef.current.get(pid) === myGen) {
        setPersonGenerating(pid, false)
        setPendingUserMsg(null)
        setPendingUserMsgPid(null)
        isSendingMapRef.current.set(pid, false)
        abortControllersRef.current.delete(pid)
        stopProgress(pid)
        logger.info(`[${callId}] 完成，锁已释放`, { pid })
      } else {
        logger.info(`[${callId}] 旧代际完成，跳过清状态`, { pid, myGen, current: genCounterRef.current.get(pid) })
      }
    }
  }

  if (!person) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#f2f0ed' }}>
        <div className="text-primary-600">加载中...</div>
      </div>
    )
  }

  const hasGenerated = hasFirstReading(person.id)

  // 乐观问题去重：fetchMessages 落库后 messages 已含真实问题，而 pendingUserMsg 尚未清除，
  // 中间态会同时渲染两个相同问题。真实问题一旦进 messages，乐观气泡立即隐藏，与时序无关。
  const normText = (s: string) => (s || '').replace(/\s+/g, ' ').trim()
  const optimisticDup = !!(
    pendingUserMsg
    && pendingUserMsgPid === person.id
    && safeMessages.some(m => m.role === 'user' && normText(m.content) === normText(pendingUserMsg))
  )
  // 重试判定：上一条消息是相同内容的 user 消息（中断后重问），用于按钮分支、文案、跳过积分门槛
  const lastMsgForRetry = messages.length > 0 ? messages[messages.length - 1] : null
  const isRetryOfUnanswered = !!(
    lastMsgForRetry
    && lastMsgForRetry.role === 'user'
    && lastMsgForRetry.content.replace(/\s+/g, ' ').trim()
      === inputValue.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim()
    && inputValue.trim().length > 0
  )

  return (
    <div style={{ position: 'fixed', top: `${viewportOffsetTop}px`, left: '50%', transform: 'translateX(-50%)', width: '100%', maxWidth: '820px', height: `${viewportHeight}px`, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* 页面标题栏 */}
      <div className="bg-white/80 backdrop-blur-sm border-b border-brand-inputBorder/40 flex-shrink-0 z-30">
        <div className="px-4 py-2.5">
        <div className="flex items-start gap-3">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="text-brand-brown/60 hover:text-brand-brown text-xl w-9 h-9 flex items-center justify-center rounded-lg hover:bg-brand-bgCard transition-all shrink-0 mt-0.5"
          >
            ←
          </button>
          <div className="flex-1 min-w-0 py-0.5">
            <h1 className="text-base font-bold text-brand-brownStrong truncate">
              {person.name || '命盘'}
            </h1>
            {(cardPhase === 'done' || hasGenerated) && baziResult?.命格箴言 && (
              <p className="text-[11px] text-brand-brown/50 truncate mt-0.5 tracking-wide">
                {baziResult.命格箴言}
              </p>
            )}
          </div>
        </div>
        </div>
      </div>

      {/* 内容区域 */}
      <div
        ref={scrollContainerRef}
        className="px-4 py-4 overflow-y-auto"
        style={{ flex: 1, minHeight: 0 }}
      >
        {cardPhase === 'ready' && baziResult && (
          <div className="bg-white rounded-2xl shadow-sm p-6 text-center">
            {/* 命格箴言 */}
            {baziResult.命格箴言 && (
              <div className="pb-5 border-b border-primary-100">
                <p className="text-primary-500/70 text-xs mb-2 tracking-wider">命格箴言</p>
                <p className="text-[22px] font-bold text-primary-800 tracking-[0.12em] mb-2 leading-relaxed">
                  {baziResult.命格箴言}
                </p>
                {baziResult.命格箴言标签 && (
                  <p className="text-xs text-primary-500/80">
                    {baziResult.命格箴言标签.调候标签} · {baziResult.命格箴言标签.十神做功标签}
                  </p>
                )}
              </div>
            )}

            {/* 命格概括 */}
            <div className={baziResult.命格箴言 ? 'pt-5' : ''}>
              <p className="text-primary-500/70 text-xs mb-3 tracking-wider">命格概括</p>
            <p className="text-xl font-bold text-gray-800 tracking-[0.2em] mb-4">
              {buildGejuSummary(baziResult)}
            </p>
            <div className="grid grid-cols-3 gap-2 mb-5">
              <div className="bg-primary-50 rounded-lg py-2">
                <p className="text-[10px] text-primary-500/70 mb-0.5">旺衰</p>
                <p className="text-sm font-semibold text-primary-800">{baziResult.旺衰结论}</p>
              </div>
              <div className="bg-primary-50 rounded-lg py-2">
                <p className="text-[10px] text-primary-500/70 mb-0.5">格局</p>
                <p className="text-sm font-semibold text-primary-800">{baziResult.格局}</p>
              </div>
              <div className="bg-primary-50 rounded-lg py-2">
                <p className="text-[10px] text-primary-500/70 mb-0.5">用神</p>
                <p className="text-sm font-semibold text-primary-800">{baziResult.用神}</p>
              </div>
            </div>
            </div>

            <button
              type="button"
              onClick={() => {
                setCardPhase('done')
                handleGenerateFirstReading()
              }}
              className="w-full py-3 rounded-xl text-sm font-medium shadow-md active:scale-[0.98] transition-all"
              style={{ backgroundColor: '#a7876f', color: '#f4f2f0' }}
            >
              查看完整解读
            </button>
          </div>
        )}

        {/* 排盘加载动画 */}
        {cardPhase === 'loading' && (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="bazi-loading-mystic">☯</div>
            <p className="text-brand-button text-sm mt-4 animate-pulse">正在排盘分析...</p>
          </div>
        )}

        {/* 排盘失败提示 */}
        {cardPhase === 'error' && (
          <div className="bg-white rounded-2xl shadow-sm p-8 text-center">
            <div className="text-4xl mb-3">⚠️</div>
            <p className="text-gray-600 mb-2">排盘分析失败</p>
            <p className="text-gray-400 text-xs mb-4">请检查网络连接或稍后重试</p>
            <button
              type="button"
              onClick={() => {
                setCardPhase('loading')
                analyzeBazi({
                  birth_date: person.birth_date,
                  birth_time: person.birth_time,
                  longitude: person.longitude || 116.4,
                  latitude: person.latitude || 39.9,
                  gender: person.gender,
                  location: person.birth_place || '',
                })
                  .then((result) => {
                    setBaziResult(result)
                    setCardPhase('ready')
                  })
                  .catch(() => setCardPhase('error'))
              }}
              className="bg-primary-600 text-white px-6 py-2 rounded-xl text-sm"
            >
              重新排盘
            </button>
          </div>
        )}

        {/* 对话消息区域 */}
        {(cardPhase === 'done' || hasGenerated) && (
          <div className="space-y-3">
            {messages.filter(Boolean).map((msg) => (
              <div key={msg.id} data-role={msg.role} className="flex items-start gap-2">
                {/* 左侧头像 */}
                <div className="flex-shrink-0 mt-1" style={{ width: '36px' }}>
                  {msg.role === 'assistant' ? (
                    <Logo dark className="logo-sm" showText={false} />
                  ) : null}
                </div>
                {/* 气泡 - flex-1 占满头像之间的空间，所有气泡左右边缘严格对齐 */}
                <div className="flex-1">
                  <div
                    className={`px-4 py-3 rounded-2xl ${
                      msg.role === 'user'
                        ? 'rounded-br-sm bg-[#8b6f5a] text-[#f4f2f0] ml-auto w-fit'
                        : 'bg-white text-brand-brown rounded-bl-sm shadow-sm'
                    }`}
                  >
                    {msg.role === 'user' ? (
                      <div className="whitespace-pre-wrap">{msg.content}</div>
                    ) : (
                      <HtmlContent content={msg.content || ''} />
                    )}
                  </div>
                </div>
                {/* 右侧头像 */}
                <div className="flex-shrink-0 mt-1" style={{ width: '36px' }}>
                  {msg.role === 'user' ? (
                    <div
                      className="flex items-center justify-center rounded-full text-white font-bold"
                      style={{ backgroundColor: '#8b6f5a', width: 36, height: 36, fontSize: 14 }}
                    >
                      {user?.name?.[0] || '?'}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}

            {/* optimistic用户消息（真实问题已落库则隐藏，避免重复渲染） */}
            {pendingUserMsg && pendingUserMsgPid === person.id && !optimisticDup && (
              <div className="flex items-start gap-2">
                <div className="flex-shrink-0 mt-1" style={{ width: '36px' }} />
                <div className="flex-1">
                  <div className="px-4 py-3 rounded-2xl rounded-br-sm bg-[#8b6f5a] text-[#f4f2f0] ml-auto w-fit">
                    <div className="whitespace-pre-wrap">{pendingUserMsg}</div>
                  </div>
                </div>
                <div className="flex-shrink-0 mt-1" style={{ width: '36px' }}>
                  <div className="flex items-center justify-center rounded-full text-white font-bold" style={{ backgroundColor: '#8b6f5a', width: 36, height: 36, fontSize: 14 }}>
                    {user?.name?.[0] || '?'}
                  </div>
                </div>
              </div>
            )}

            {/* 正在生成提示 */}
            {isPersonGenerating(person.id) && (() => {
              const p = progressMap[person.id]
              const percent = p?.percent ?? 0
              const time = p?.time ?? '预计1-2分钟'
              return (
              <div className="flex items-start gap-2">
                <div className="flex-shrink-0 mt-1" style={{ width: '36px' }}>
                  <Logo dark className="logo-sm" showText={false} />
                </div>
                <div className="flex-1">
                  <div className="px-6 py-5 rounded-2xl bg-white/90 backdrop-blur-sm rounded-bl-sm shadow-sm border border-brand-gold/20">
                    <div className="flex items-center gap-2 mb-4">
                      <span className="text-brand-button text-sm animate-pulse">正在分析中，请稍后…</span>
                    </div>
                    <div className="w-full h-3 bg-brand-bgCard rounded-full overflow-hidden mb-3">
                      <div className="h-full rounded-full transition-all duration-500 ease-out" style={{ width: `${percent}%`, backgroundColor: '#a7876f' }} />
                    </div>
                    <div className="flex justify-between items-center">
                      <p className="text-brand-button text-sm">{percent}%</p>
                      <p className="text-brand-brown/50 text-sm">{time}</p>
                    </div>
                  </div>
                </div>
                <div className="flex-shrink-0 mt-1" style={{ width: '36px' }} />
              </div>
              )
            })()}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* 智能悬浮翻页按钮（在 flex 容器内，fixed 定位） */}
      {(showScrollUp || showScrollDown) && (
        <div className="fixed z-50 flex flex-col gap-3" style={{ right: '16px', bottom: '180px' }}>
          {showScrollUp && (
            <button
              type="button"
              onClick={scrollToTop}
              className="bg-white/95 text-brand-brown w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold hover:bg-white transition-all backdrop-blur-sm shadow-lg border border-gray-200 active:scale-95"
              title="回到顶部"
            >
              ↑
            </button>
          )}
          {showScrollDown && (
            <button
              type="button"
              onClick={() => {
                // 点击后立即隐藏按钮，不等待 scroll 事件回调，避免视觉延迟
                setShowScrollDown(false)
                scrollToBottom({ force: true })
              }}
              className="bg-white/95 text-brand-brown w-10 h-10 rounded-full flex items-center justify-center text-lg font-bold hover:bg-white transition-all backdrop-blur-sm shadow-lg border border-gray-200 active:scale-95"
              title="回到底部"
            >
              ↓
            </button>
          )}
        </div>
      )}

      {/* 底部输入栏 */}
      {(hasGenerated || cardPhase === 'done') && (
        <div className="bg-white/90 backdrop-blur-sm border-t border-brand-inputBorder/40 flex-shrink-0" style={{ paddingBottom: 'env(safe-area-inset-bottom, 12px)' }}>

          {/* 推荐追问 Chip 条：浅金背景独立块 + 上滑淡入动画 */}
          {(() => {
            if (!showSuggested) return null
            const lastAssistant = [...messages].reverse().find(m => m.role === 'assistant')
            if (!lastAssistant || isPersonGenerating(person.id) || inputValue) return null
            const raw = extractSuggestedQuestions(lastAssistant.content)
            if (!raw) return null
            const filtered = filterAsked(raw, messages)
            if (filtered.length === 0) return null
            return (
              <div className="mx-3 mt-3 mb-2 bg-amber-50/70 rounded-xl border border-amber-200/60 p-3 shadow-[0_1px_3px_rgba(160,128,114,0.08)] chip-slide-up">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1 text-sm font-semibold text-amber-700/80">
                    <span className="text-base">✨</span>
                    <span>试试追问</span>
                    <span className="font-normal text-xs text-brand-muted/80 ml-1">（点击直接发送）</span>
                  </div>
                  <span className="text-[11px] text-brand-muted/60 flex-shrink-0">
                    {isRetryOfUnanswered
                      ? <>重新生成·不扣积分</>
                      : <>40积分/次</>
                    }
                  </span>
                </div>
                <div className="flex gap-2 overflow-x-auto" style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}>
                  {filtered.map((q, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => handleSend(q)}
                      className="flex-shrink-0 flex items-center gap-1.5 pl-3.5 pr-2.5 py-2 rounded-full border border-amber-300/50 bg-white text-brand-brown text-sm whitespace-nowrap active:scale-95 transition-all hover:border-amber-500/60 hover:bg-amber-50"
                    >
                      <span>{q}</span>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-amber-600 flex-shrink-0"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg>
                    </button>
                  ))}
                </div>
              </div>
            )
          })()}

          {/* 输入行 */}
          <div className="flex items-center space-x-2 px-4 py-2">
            <input
              type="text"
              value={inputValue}
              disabled={!!person && isPersonGenerating(person.id)}
              onChange={(e) => {
                // 实时移除换行符，防止长文本中间的换行导致内容被截断
                const cleanVal = e.target.value.replace(/[\r\n]+/g, ' ')
                if (cleanVal !== e.target.value) {
                  setInputValue(cleanVal)
                } else {
                  setInputValue(e.target.value)
                }
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  logger.info('[Input] Enter键触发', { isComposing: e.nativeEvent.isComposing, keyCode: e.keyCode, timeStamp: e.timeStamp })
                  e.preventDefault()
                  e.stopPropagation()
                  if (e.nativeEvent.isComposing) return
                  handleSend()
                }
              }}
              placeholder="追问，如：算一下今日运势/工作/财运/子女等"
              className="flex-1 px-4 py-2.5 border border-brand-inputBorder rounded-full focus:ring-2 focus:ring-brand-gold/50 focus:border-brand-gold outline-none transition-all bg-brand-bgInput text-sm disabled:bg-gray-100 disabled:cursor-not-allowed"
            />
            {(user?.points ?? 0) < 40 && !isRetryOfUnanswered ? (
              <button
                type="button"
                onClick={() => setIsRechargeOpen(true)}
                className="px-5 h-10 rounded-full text-sm font-medium transition-all whitespace-nowrap"
                style={{ backgroundColor: '#a7876f', color: '#f4f2f0' }}
              >
                去充值
              </button>
            ) : (
              <button
                type="button"
                disabled={!!person && isPersonGenerating(person.id)}
                onClick={(e) => {
                  logger.info('[Button] 追问按钮点击', { timeStamp: e.timeStamp, inputLen: inputValue.trim().length })
                  handleSend()
                }}
                className="px-5 h-10 rounded-full text-sm font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
                style={{ backgroundColor: '#a7876f', color: '#f4f2f0' }}
              >
                追问
              </button>
            )}
          </div>

          {/* 免责声明 */}
          <div className="text-center text-brand-muted/40 text-[10px] py-1">
            AI存在幻觉，仅供传统文化体验与娱乐参考，不具有科学预测能力
          </div>
        </div>
      )}

      {/* 充值弹层 */}
      <RechargeModal
        isOpen={isRechargeOpen}
        onClose={() => setIsRechargeOpen(false)}
      />
    </div>
  )
}

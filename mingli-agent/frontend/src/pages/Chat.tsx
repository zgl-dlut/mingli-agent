import React, { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useChatStore } from '../store/chatStore'
import { usePersonStore } from '../store/personStore'
import { useUserStore } from '../store/userStore'
import { chatApi } from '../api/chat'
import RechargeModal from '../components/RechargeModal'
import type { Person } from '../types'
import { analyzeBazi, AnalyzeResult } from '../api/bazi'
import Logo from '../components/Logo'
import { FollowupReportView, isStructuredReport } from '../components/FollowupReportView'
import { normalizeReportContent } from '../utils/reportFormat'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { createLogger, traceId } from '../utils/logger'

const logger = createLogger('ChatPage')
const sseLogger = createLogger('SSE')

/** 报告内容渲染组件
 * 架构：
 * 1. 结构化 JSON 报告（追问）→ FollowupReportView 直渲染 React 组件（不走 Markdown）
 * 2. Markdown 报告（首次报告）→ normalizeReportContent 归一化 → react-markdown 解析
 *
 * 追问报告用 JSON 结构化，格式 100% 由组件控制，不依赖 Markdown 解析。
 * 首次报告仍用 Markdown + react-markdown，两条链路隔离互不影响。
 */
const HtmlContent = React.memo(({ content }: { content: string }) => {
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
    isGenerating,
    fetchMessages,
    addMessage,
    setCurrentMessage,
    setIsGenerating,
    hasFirstReading,
    setFirstReadingGenerated,
  } = useChatStore()
  const { user, fetchUserInfo } = useUserStore()

  const [person, setPerson] = useState<Person | null>(null)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [inputValue, setInputValue] = useState('')
  const [baziResult, setBaziResult] = useState<AnalyzeResult | null>(null)
  const [cardPhase, setCardPhase] = useState<'loading' | 'ready' | 'done' | 'error'>('loading')
  const [isRechargeOpen, setIsRechargeOpen] = useState(false)
  // 生成进度相关状态
  const [progressPercent, setProgressPercent] = useState(0)
  const [estimatedTime, setEstimatedTime] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  // 滚动控制状态
  const [scrollButton, setScrollButton] = useState<'up' | 'down' | null>(null)
  // optimistic用户消息：发送追问时立即显示，fetchMessages后自动清除
  const [pendingUserMsg, setPendingUserMsg] = useState<string | null>(null)
  
  // 同步锁，防止快速重复发送（解决 setState 异步导致的竞态问题）
  const isSendingRef = useRef(false)

  // 请求ID追踪，防止重复发送
  const lastRequestIdRef = useRef<string>('')

  // 最后发送内容与时间戳，用于拦截重复提交（点击/回车二次触发、移动端双击等）
  const lastSentContentRef = useRef<string>('')
  const lastSentTimeRef = useRef<number>(0)

  // 🛡️ 第二层：requestAnimationFrame 级别防抖，防止同一帧内 click + touchend 双重触发
  const sendPendingRef = useRef(false)

  // AbortController，用于取消之前的请求
  const abortControllerRef = useRef<AbortController | null>(null)
  
  // 防抖滚动引用
  const debounceScrollRef = useRef<number | null>(null)
  
  // 进度条定时器引用
  const progressTimerRef = useRef<number | null>(null)
  
  // 上一次滚动位置
  const lastScrollTopRef = useRef(0)
  // 滚动防抖定时器
  const scrollTimerRef = useRef<number | null>(null)

  // 滚动监听，智能显示翻页按钮
  useEffect(() => {
    const container = scrollContainerRef.current
    if (!container) return

    const handleScroll = () => {
      const scrollTop = container.scrollTop
      const scrollHeight = container.scrollHeight
      const clientHeight = container.clientHeight
      const scrollDirection = scrollTop > lastScrollTopRef.current ? 'down' : 'up'
      
      lastScrollTopRef.current = scrollTop

      // 清除之前的定时器
      if (scrollTimerRef.current) {
        clearTimeout(scrollTimerRef.current)
      }

      // 判断是否显示按钮
      // 只要滚动了就显示按钮，不再限制在中间区域
      if (scrollTop > 50) {
        // 滚动距离顶部超过50px，显示向上按钮（回到顶部）
        setScrollButton('up')
      }
      
      if (scrollTop < scrollHeight - clientHeight - 50) {
        // 滚动距离底部超过50px，显示向下按钮（回到底部）
        setScrollButton('down')
      }
      
      // 如果既不在顶部也不在底部，根据滚动方向决定显示哪个按钮
      if (scrollTop > 50 && scrollTop < scrollHeight - clientHeight - 50) {
        setScrollButton(scrollDirection === 'down' ? 'down' : 'up')
      }
      
      // 已经在顶部，不显示向上按钮
      if (scrollTop <= 50) {
        // 如果还没到最底部，显示向下按钮
        if (scrollTop < scrollHeight - clientHeight - 50) {
          setScrollButton('down')
        } else {
          setScrollButton(null)
        }
      }
      
      // 已经在底部，不显示向下按钮
      if (scrollTop >= scrollHeight - clientHeight - 50) {
        // 如果还没到最顶部，显示向上按钮
        if (scrollTop > 50) {
          setScrollButton('up')
        } else {
          setScrollButton(null)
        }
      }

      // 3秒后自动隐藏
      scrollTimerRef.current = window.setTimeout(() => {
        setScrollButton(null)
      }, 3000)
    }

    container.addEventListener('scroll', handleScroll, { passive: true })
    return () => {
      container.removeEventListener('scroll', handleScroll)
      if (scrollTimerRef.current) {
        clearTimeout(scrollTimerRef.current)
      }
    }
  }, [])

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
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
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
    scrollContainerRef.current?.scrollTo({
      top: 0,
      behavior: 'smooth'
    })
  }

  // 启动进度条和预计时间更新
  const startProgress = () => {
    // 立即显示初始进度10%，避免用户等待
    setProgressPercent(10)
    setEstimatedTime('约3分钟')
    let elapsed = 0
    
    if (progressTimerRef.current) {
      clearInterval(progressTimerRef.current)
    }
    
    progressTimerRef.current = window.setInterval(() => {
      elapsed += 1
      // 模拟进度：前60秒到30%，中间60秒到70%，最后60秒到95%
      let percent = 10 // 初始10%
      if (elapsed <= 60) {
        percent = 10 + Math.min(20, (elapsed / 60) * 20)
      } else if (elapsed <= 120) {
        percent = 30 + Math.min(40, ((elapsed - 60) / 60) * 40)
      } else {
        percent = 70 + Math.min(25, ((elapsed - 120) / 60) * 25)
      }
      setProgressPercent(Math.round(percent))
      
      // 固定显示预计时间，不实时计算
      if (elapsed < 60) {
        setEstimatedTime('约3分钟')
      } else if (elapsed < 120) {
        setEstimatedTime('约2分钟')
      } else {
        setEstimatedTime('即将完成...')
      }
    }, 1000)
  }

  // 停止进度条
  const stopProgress = () => {
    if (progressTimerRef.current) {
      clearInterval(progressTimerRef.current)
      progressTimerRef.current = null
    }
    setProgressPercent(0)
    setEstimatedTime('')
  }

  // 消息或流式内容变化时：只在用户已经接近底部，或正在生成回复时自动滚动
  // 这样用户手动上翻看历史消息时不会被强制拉回底部
  useEffect(() => {
    scrollToBottom({ force: false })
  }, [messages, currentMessage, pendingUserMsg])

  useEffect(() => {
    if (!personId) return
    logger.info(`[Lifecycle] Chat组件挂载`, { personId })
    const id = parseInt(personId)
    const p = getPerson(id)
    if (!p) {
      logger.warn(`[Lifecycle] person未找到，跳转首页`, { personId })
      navigate('/')
      return
    }
    setPerson(p)
    // 获取 session_id 并从后端拉取消息
    chatApi.getSessions().then(sessions => {
      const s = sessions.find(s => s.person_id === id)
      if (s) {
        setSessionId(s.id)
        fetchMessages(id, s.id)
      }
    }).catch(err => {
      logger.error(`获取sessions失败`, String(err))
    })

    // 切换对话框时取消未完成的流式请求
    return () => {
      logger.info(`[Lifecycle] Chat组件卸载`, { personId })
      abortControllerRef.current?.abort()
      abortControllerRef.current = null
    }
  }, [personId])

  // person 删除后的跳转由 HistoryPanel 的 navigate 负责，避免双重 navigate 冲突
  // SSE 流未中断的部分由 catch 里的 personExists 检查静默处理

  // 加载命理分析数据
  useEffect(() => {
    if (!person) return
    setCardPhase(hasFirstReading(person.id) ? 'done' : 'loading')
    // 无论是否有历史，都要拿到 baziResult 用于后续追问！
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
      .finally(() => {})
  }, [person?.id])

  const handleGenerateFirstReading = async () => {
    const callId = traceId()
    logger.info(`[${callId}] handleGenerateFirstReading 入口`, {
      isSending: isSendingRef.current,
      hasPerson: !!person,
      isGenerating,
      hasBaziResult: !!baziResult,
      userPoints: user?.points ?? 'unknown',
    })
    if (isSendingRef.current) {
      logger.warn(`[${callId}] 被ref锁拦截`)
      return
    }
    isSendingRef.current = true

    if (!person || isGenerating) {
      logger.warn(`[${callId}] 前置条件不满足`, { hasPerson: !!person, isGenerating })
      isSendingRef.current = false
      return
    }
    if (!baziResult) {
      logger.warn(`[${callId}] baziResult为null`)
      alert('命理分析数据未就绪，请稍后重试')
      isSendingRef.current = false
      return
    }
    if (!sessionId) {
      logger.warn(`[${callId}] sessionId未就绪`)
      alert('会话未就绪，请稍后重试')
      isSendingRef.current = false
      return
    }
    // 注意：首次解读费用在创建 person 时已扣除（后端 person.py 扣 POINTS_FIRST_READING），
    // first-reading 接口不再扣分，此处无需积分检查与本地扣分

    // 生成唯一请求ID，防止重复发送
    const requestId = `first-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    
    // 如果当前正在发送相同内容的请求，直接返回
    if (lastRequestIdRef.current === requestId) {
      isSendingRef.current = false
      return
    }
    
    // 取消之前的请求
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()

    lastRequestIdRef.current = requestId
    setIsGenerating(true, Number(person.id))
    setCurrentMessage('')
    // 启动进度条和预计时间
    startProgress()

    try {
      scrollToBottom({ force: true })
      logger.info(`[${callId}] 调用 getFirstReadingStream`, { sessionId })

      // 使用 getFirstReadingStream：后端生成 + 存 AI 回复（不扣积分，积分在创建 person 时已扣）
      const response = await chatApi.getFirstReadingStream(sessionId)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const contentType = response.headers.get('content-type') || ''
      // 后端可能返回 JSON（已有首次解读）或 SSE 流（新生成）
      if (contentType.includes('application/json')) {
        // 已有首次解读，直接拉取消息
        logger.info(`[${callId}] 首次解读已存在（JSON响应），拉取消息`)
        await fetchMessages(person.id, sessionId)
        setFirstReadingGenerated(person.id)
      } else {
        // 流式响应
        let acc = ''
        let saved = false
        logger.info(`[${callId}] SSE连接建立，开始接收首次解读chunks`)
        await parseSSEStream(response, (chunk) => {
          acc += chunk
          // 过滤 __SAVED__ 标记
          const savedIdx = acc.indexOf('__SAVED__')
          if (savedIdx >= 0) {
            saved = true
            const display = acc.slice(0, savedIdx).replace(/\n+$/, '')
            setCurrentMessage(display, person.id)
          } else {
            setCurrentMessage(acc, person.id)
          }
        })
        logger.success(`[${callId}] SSE流完成`, { accLen: acc.length, saved })

        if (saved) {
          setCurrentMessage('')
          await fetchMessages(person.id, sessionId)
          setFirstReadingGenerated(person.id)
          await fetchUserInfo() // 同步积分显示
        }
      }
    } catch (err: any) {
      // abort 中断（如删除人物、切换页面）不算失败，静默处理
      const personExists = usePersonStore.getState().persons.some(p => p.id === parseInt(personId || '0'))
      if (err?.name === 'AbortError' || !personExists) {
        logger.info(`[${callId}] 请求被中断或person已删除`)
      } else {
        logger.error(`[${callId}] 生成失败`, { error: String(err) })
        alert(`生成失败: ${String(err).replace('Error: ', '')}`)
      }
      await fetchUserInfo() // 失败时同步积分（恢复本地误扣）
    } finally {
      setIsGenerating(false)
      isSendingRef.current = false
      lastRequestIdRef.current = ''
      abortControllerRef.current = null
      stopProgress()
      logger.info(`[${callId}] 完成，锁已释放`)
    }
  }

  const handleSend = async () => {
    const callId = traceId()
    logger.info(`[${callId}] handleSend 入口`, {
      isSending: isSendingRef.current,
      sendPending: sendPendingRef.current,
      inputLen: inputValue.length,
      isGenerating,
      hasPerson: !!person,
      hasBaziResult: !!baziResult,
      userPoints: user?.points ?? 'unknown',
    })

    // 🛡️ 第一层：ref 锁，同 tick 内防重
    if (isSendingRef.current) {
      logger.warn(`[${callId}] 被ref锁拦截`, { isSending: true })
      return
    }
    // 🛡️ 第二层：rAF 帧级防抖，解决移动端 click + touchend 双重触发
    if (sendPendingRef.current) {
      logger.warn(`[${callId}] 被rAF帧防抖拦截`, { sendPending: true })
      return
    }
    sendPendingRef.current = true
    requestAnimationFrame(() => { sendPendingRef.current = false })

    isSendingRef.current = true
    logger.info(`[${callId}] 锁已获取，进入主流程`)

    // 预处理输入：移除换行符和多余空白字符，防止文字被截断
    const normalizedInput = inputValue.replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim()
    
    // 检查基本条件
    if (!normalizedInput) {
      logger.warn(`[${callId}] 输入为空，退出`)
      isSendingRef.current = false
      return
    }
    if (!person) {
      logger.warn(`[${callId}] person为null，退出`)
      isSendingRef.current = false
      return
    }
    if (isGenerating) {
      logger.warn(`[${callId}] 正在生成中，退出`)
      isSendingRef.current = false
      return
    }
    if (!baziResult) {
      logger.warn(`[${callId}] baziResult未就绪，退出`)
      alert('命理数据未就绪，请稍等或刷新页面重试')
      isSendingRef.current = false
      return
    }
    if (!sessionId) {
      logger.warn(`[${callId}] sessionId未就绪，退出`)
      alert('会话未就绪，请稍后重试')
      isSendingRef.current = false
      return
    }
    if ((user?.points ?? 0) < 40) {
      logger.warn(`[${callId}] 积分不足`, { points: user?.points })
      setIsRechargeOpen(true)
      isSendingRef.current = false
      return
    }

    const question = normalizedInput
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
      isSendingRef.current = false
      return
    }
    lastSentContentRef.current = question
    lastSentTimeRef.current = now

    // ========== 关键：先验证问题有效性，不通过则不扣积分 ==========
    try {
      const validation = await chatApi.validateQuestion(question)
      if (!validation.valid) {
        addMessage(person.id, 'assistant', validation.message)
        setCurrentMessage('')
        isSendingRef.current = false
        logger.info(`[${callId}] 问题验证未通过`, { msg: validation.message })
        return
      }
    } catch (err) {
      logger.warn(`[${callId}] 验证接口调用失败，降级处理`, String(err))
      if (!question.trim() || question.length < 2) {
        addMessage(person.id, 'assistant', '请输入您想咨询的问题，本次不扣除积分～')
        isSendingRef.current = false
        return
      }
    }

    // 立即设置生成状态并启动进度条
    setIsGenerating(true, person.id)
    setCurrentMessage('')
    startProgress()

    try {
      // 取消之前的请求
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
        logger.info(`[${callId}] 取消之前的请求`)
      }
      abortControllerRef.current = new AbortController()

      logger.info(`[${callId}] 请求初始化完成，调用 sendMessageStream`, { sessionId, questionLen: question.length })
      // optimistic UI：立即显示用户问题，fetchMessages后自动清除
      setPendingUserMsg(question)
      scrollToBottom({ force: true })

      // 使用 sendMessageStream：后端扣积分 + 存用户消息 + 流式返回 + 存 AI 回复
      let acc = ''
      let saved = false
      const response = await chatApi.sendMessageStream(sessionId, question)
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      logger.info(`[${callId}] SSE连接建立，开始接收chunks`)
      await parseSSEStream(response, (chunk) => {
        acc += chunk
        // 过滤 __SAVED__ 标记，不显示给用户
        const savedIdx = acc.indexOf('__SAVED__')
        if (savedIdx >= 0) {
          saved = true
          const display = acc.slice(0, savedIdx).replace(/\n+$/, '')
          setCurrentMessage(display, person.id)
        } else {
          setCurrentMessage(acc, person.id)
        }
      })
      logger.success(`[${callId}] SSE流完成`, { totalLen: acc.length, saved })

      // 收到 __SAVED__：后端已存库，从后端拉取最新消息（以 DB 为准）
      if (saved) {
        setCurrentMessage('')
        await fetchMessages(person.id, sessionId)
        setPendingUserMsg(null) // fetchMessages已拉取到用户消息，清除optimistic
        await fetchUserInfo() // 刷新积分显示（后端已扣 40 积分）
      }
    } catch (err: any) {
      // abort 中断（如删除人物、切换页面）不算失败，静默处理
      const personExists = usePersonStore.getState().persons.some(p => p.id === parseInt(personId || '0'))
      if (err?.name === 'AbortError' || !personExists) {
        logger.info(`[${callId}] 请求被中断或person已删除`)
      } else {
        logger.error(`[${callId}] 发送失败`, { error: String(err) })
      }
      // 后端可能已扣积分但流中断，刷新积分获取真实值
      await fetchUserInfo()
    } finally {
      setIsGenerating(false)
      setPendingUserMsg(null)
      isSendingRef.current = false
      abortControllerRef.current = null
      stopProgress()
      logger.info(`[${callId}] 完成，锁已释放`)
    }
  }

  if (!person) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-50 to-primary-100">
        <div className="text-primary-600">加载中...</div>
      </div>
    )
  }

  const hasGenerated = hasFirstReading(person.id)

  return (
    <div style={{ maxWidth: '768px', margin: '0 auto', minHeight: '100vh' }}>
      {/* 页面标题栏 */}
      <div className="bg-white border-b border-gray-100 sticky top-0 z-30">
        <div className="px-4 py-3">
        <div className="flex items-start gap-3">
          <button
            type="button"
            onClick={() => navigate('/')}
            className="text-gray-600 hover:text-gray-800 text-xl w-10 h-10 flex items-center justify-center rounded-lg hover:bg-gray-100 transition-all shrink-0 mt-0.5"
          >
            ←
          </button>
          <div className="flex-1 min-w-0 py-0.5">
            <h1 className="text-lg font-bold text-gray-800 truncate">
              {person.name || '命盘'}
            </h1>
            {(cardPhase === 'done' || hasGenerated) && baziResult?.命格箴言 && (
              <p className="text-xs text-primary-600/70 truncate mt-0.5 tracking-wide">
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
        className="px-4 py-4 pb-36 overflow-y-auto"
        style={{ maxHeight: 'calc(100vh - 200px)' }}
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
              className="w-full bg-gradient-to-r from-primary-600 to-primary-700 text-white py-3 rounded-xl text-sm font-medium shadow-md active:scale-[0.98] transition-all"
            >
              查看完整解读
            </button>
          </div>
        )}

        {/* 排盘加载动画 */}
        {cardPhase === 'loading' && (
          <div className="flex flex-col items-center justify-center py-20">
            <div className="bazi-loading-mystic">☯</div>
            <p className="text-indigo-400 text-sm mt-4 animate-pulse">正在排盘分析...</p>
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
          <div className="space-y-4">
            {messages.filter(Boolean).map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} items-start gap-2`}
              >
                {msg.role === 'assistant' && (
                  <div className="flex-shrink-0 mt-1">
                    <Logo size={32} dark />
                  </div>
                )}
                <div
                  className={`max-w-[80%] px-4 py-3 rounded-2xl ${
                    msg.role === 'user'
                      ? 'bg-gradient-to-r from-primary-600 to-primary-700 text-white rounded-br-sm'
                      : 'bg-white text-gray-800 rounded-bl-sm shadow-sm'
                  }`}
                >
                  {msg.role === 'user' ? (
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  ) : (
                    <HtmlContent content={msg.content || ''} />
                  )}
                </div>
              </div>
            ))}

            {/* optimistic用户消息：发送追问时立即显示，fetchMessages后清除 */}
            {pendingUserMsg && (
              <div className="flex justify-end items-start gap-2">
                <div className="max-w-[80%] px-4 py-3 rounded-2xl bg-gradient-to-r from-primary-600 to-primary-700 text-white rounded-br-sm">
                  <div className="whitespace-pre-wrap">{pendingUserMsg}</div>
                </div>
              </div>
            )}

            {/* 正在生成提示 - 始终显示进度条 */}
            {isGenerating && (
              <div className="flex justify-start items-start gap-2">
                <div className="flex-shrink-0 mt-1">
                  <Logo size={32} dark />
                </div>
                <div className="max-w-[80%] px-5 py-4 rounded-2xl bg-white/80 backdrop-blur-sm rounded-bl-sm shadow-sm border border-indigo-100/50">
                  {/* 加载动画 */}
                  <div className="flex items-center gap-2 mb-3">
                    <div className="bazi-loading-mystic text-indigo-400" style={{ fontSize: '1.5rem' }}>☯</div>
                    <span className="text-indigo-400 text-sm animate-pulse">正在生成命理报告，请稍候...</span>
                  </div>
                  
                  {/* 动态进度条 */}
                  <div className="w-full h-2 bg-indigo-100 rounded-full overflow-hidden mb-2">
                    <div 
                      className="h-full bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 rounded-full transition-all duration-500 ease-out"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                  {/* 进度百分比和预计时间 */}
                  <div className="flex justify-between items-center">
                    <p className="text-indigo-400 text-xs">{progressPercent}%</p>
                    <p className="text-indigo-300 text-xs">{estimatedTime}</p>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
        
        {/* 智能悬浮翻页按钮 */}
        {scrollButton && (
          <button
            type="button"
            onClick={scrollButton === 'up' ? scrollToTop : () => scrollToBottom({ force: true })}
            className="fixed right-4 z-20 bg-gray-200/80 text-gray-500 w-6 h-6 rounded-full flex items-center justify-center text-xs hover:bg-gray-300 transition-all backdrop-blur-sm"
            style={{ top: '50%', transform: 'translateY(-50%)' }}
          >
            {scrollButton === 'up' ? '↑' : '↓'}
          </button>
        )}
      </div>

      {/* 底部输入栏 */}
      {(hasGenerated || cardPhase === 'done') && (
        <div className="fixed bottom-0 bg-white border-t border-gray-100" style={{ left: 0, right: 0, maxWidth: '768px', margin: '0 auto', paddingBottom: 'env(safe-area-inset-bottom, 12px)' }}>
          <div>
          {/* 积分提示 */}
          <div className="text-center text-gray-400 text-xs pt-2">
            本次分析消耗 <span className="text-primary-600 font-medium">40</span> 积分，当前余额 <span className="text-primary-600 font-medium">{user?.points ?? 0}</span> 积分
          </div>

          {/* 输入行 */}
          <div className="flex items-center space-x-2 px-4 py-2">
            <input
              type="text"
              value={inputValue}
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
              className="flex-1 px-4 py-2.5 border border-gray-200 rounded-full focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all bg-gray-50 text-sm"
              disabled={isGenerating}
            />
            {(user?.points ?? 0) < 40 ? (
              <button
                type="button"
                onClick={() => setIsRechargeOpen(true)}
                className="bg-gradient-to-r from-primary-600 to-primary-700 text-white px-5 h-10 rounded-full text-sm font-medium hover:from-primary-700 hover:to-primary-800 transition-all whitespace-nowrap"
              >
                去充值
              </button>
            ) : (
              <button
                type="button"
                onClick={(e) => {
                  logger.info('[Button] 追问按钮点击', { timeStamp: e.timeStamp, inputLen: inputValue.trim().length, isGenerating, disabled: !inputValue.trim() || isGenerating })
                  handleSend()
                }}
                className="bg-gradient-to-r from-primary-600 to-primary-700 text-white px-5 h-10 rounded-full text-sm font-medium hover:from-primary-700 hover:to-primary-800 transition-all disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
              >
                追问
              </button>
            )}
          </div>

          {/* 免责声明 */}
          <div className="text-center text-gray-300 text-[10px] py-1">
            AI存在幻觉，仅供传统文化体验与娱乐参考，不具有科学预测能力
          </div>
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

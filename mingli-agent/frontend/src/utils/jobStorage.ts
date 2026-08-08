/**
 * 管理异步分析任务的 job_id 本地持久化
 * 用于页面关闭后重新进入时拉取已生成的报告
 */
import { createLogger } from './logger'

const logger = createLogger('jobStorage')
const PENDING_JOBS_KEY = 'mingli_pending_jobs'

interface PendingJobs {
  [personId: number]: string[]
}

function loadPendingJobs(): PendingJobs {
  try {
    const raw = localStorage.getItem(PENDING_JOBS_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

function savePendingJobs(jobs: PendingJobs) {
  localStorage.setItem(PENDING_JOBS_KEY, JSON.stringify(jobs))
}

export function getPendingJobs(personId: number): string[] {
  const jobs = loadPendingJobs()
  return jobs[personId] || []
}

export function addPendingJob(personId: number, jobId: string) {
  logger.info(`addPendingJob`, { personId, jobId })
  const jobs = loadPendingJobs()
  if (!jobs[personId]) jobs[personId] = []
  if (!jobs[personId].includes(jobId)) {
    jobs[personId].push(jobId)
    savePendingJobs(jobs)
  }
}

export function removePendingJob(personId: number, jobId: string) {
  logger.info(`removePendingJob`, { personId, jobId })
  const jobs = loadPendingJobs()
  if (!jobs[personId]) return
  jobs[personId] = jobs[personId].filter((id) => id !== jobId)
  if (jobs[personId].length === 0) delete jobs[personId]
  savePendingJobs(jobs)
}

export function generateJobId(personId: number, isFirstReading: boolean, question?: string): string {
  const ts = Date.now()
  const type = isFirstReading ? 'first' : 'followup'
  const questionHash = question
    ? question.slice(0, 20).replace(/[^\u4e00-\u9fa5a-zA-Z0-9]/g, '')
    : 'none'
  return `p${personId}-${type}-${questionHash}-${ts}`
}

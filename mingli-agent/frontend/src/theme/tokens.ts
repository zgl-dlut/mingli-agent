/**
 * 设计系统 token —— 单一事实来源
 *
 * 全部取自 `.trae/documents/ui-design/01-today.html` 的 `:root`（14 份设计稿取值一致）。
 * 页面禁止再硬编码十六进制色值，一律从这里取；新增页面同样复用。
 *
 * 与旧的棕色体系（#4A4E8F / #4A4E8F）的关系：旧值是历史遗留，设计稿统一为黛蓝紫，
 * 本文件即迁移目标，由 index.css 同步声明为 CSS 变量。
 */

/** 主色板 */
export const color = {
  /** 宣纸暖白，页面底 */
  bg: '#F7F5F0',
  /** 卡片底 */
  card: '#FFFFFF',
  /** 黛蓝紫，主色 / Tab 选中 / 主 CTA */
  brand: '#4A4E8F',
  /** 主色浅底 */
  brandSoft: '#EEEFF9',
  /** 金色点缀：会员 / 吉 / 高亮边框 */
  gold: '#C9A86A',
  /** 主文字 */
  ink: '#2B2B33',
  /** 次文字 */
  ink2: '#8A8A93',
  /** 宜 / 吉 */
  success: '#2E9E6B',
  /** 忌 / 凶 */
  danger: '#D9534F',
  /** 警示档（fi-tag.warn） */
  warn: '#D9772B',
  /** 宜标签底 */
  successSoft: '#E7F4EE',
  /** 忌标签底 */
  dangerSoft: '#FBEAE9',
  /** 警示标签底 */
  warnSoft: '#FBEEDD',
  /** 进度条轨道 */
  track: '#EFEDE6',
  /** 分隔线 */
  divider: '#F0EEE7',
  /** 分段控件底 */
  segBg: '#ECEAE3',
  /** Tab 栏上边框 */
  tabBorder: '#ECEAE4',
} as const

/** 人生五维专属色（01-today 人生面板 / 六维同源） */
export const dimensionColor = {
  love: '#F4B8C4',
  marry: '#5DB8E8',
  wealth: '#E8B547',
  career: '#9B8FD4',
  study: '#4A90E2',
} as const

/** 圆角 */
export const radius = {
  card: '16px',
  pill: '999px',
} as const

/**
 * 梯度色（设计稿里的渐变底，收敛在此避免散落）
 */
export const gradient = {
  /** 年运 banner：90deg #FBF7EF → #F6EDDA */
  banner: 'linear-gradient(90deg, #FBF7EF, #F6EDDA)',
  /** 解锁通栏：90deg #F3EFFA → #EEEFF9 */
  unlock: 'linear-gradient(90deg, #F3EFFA, #EEEFF9)',
  /** 本年 hero：160deg #3E4278 → brand → #5A5FA8 */
  yearHero: 'linear-gradient(160deg, #3E4278 0%, #4A4E8F 60%, #5A5FA8 100%)',
} as const

/** 阴影 */
export const shadow = {
  card: '0 1px 4px rgba(43,43,51,.04)',
} as const

/** 字体族（PingFang SC 优先） */
export const fontFamily = '-apple-system, "PingFang SC", sans-serif'

/**
 * 性别归一化展示工具。
 *
 * 后端 DB 统一存英文 male/female，但历史监控数据/外部数据源（微信）可能存中文"男/女"
 * 或数字 1/2/0。前端展示/回显统一用本工具转中文，避免裸显示英文或判断失效。
 *
 * 用途：页面展示与回显（非数据提交；提交走 bazi.ts 的 normalizeGender 转英文）。
 */

/** 性别转中文展示文本，兼容 male/female/男/女/m/f/1/2/0 */
export function genderToText(gender: string | undefined | null): string {
  if (!gender) return ''
  const g = String(gender).trim().toLowerCase()
  if (g === 'male' || g === '男' || g === 'm' || g === '1') return '男'
  if (g === 'female' || g === '女' || g === 'f' || g === '2' || g === '0') return '女'
  return String(gender) // 未知值原样返回，便于排查
}

/** 性别对应图标符号，兼容多格式 */
export function genderIcon(gender: string | undefined | null): string {
  const t = genderToText(gender)
  return t === '男' ? '♂' : t === '女' ? '♀' : ''
}

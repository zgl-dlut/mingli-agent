/**
 * 农历转公历工具（基于 lunar-typescript 库）
 *
 * lunar-typescript API 说明：
 * - Lunar.fromYmd(year, month, day)：创建农历对象，闰月 month 传负数（如闰二月传 -2）
 * - lunar.getSolar()：转换为公历对象
 * - LunarYear.fromYear(year).getLeapMonth()：获取某年闰月月份（0 表示无闰月）
 */
import { Lunar, LunarYear, Solar } from 'lunar-typescript'

interface SolarDate {
  year: number
  month: number
  day: number
}

/**
 * 农历日期转公历日期
 * @param year 农历年
 * @param month 农历月（1-12）
 * @param day 农历日
 * @param isLeap 是否闰月
 */
export function lunarToSolar(year: number, month: number, day: number, isLeap: boolean): SolarDate {
  // lunar-typescript 约定：闰月用负数表示（闰二月 = -2）
  const lunarMonth = isLeap ? -month : month
  const lunar = Lunar.fromYmd(year, lunarMonth, day)
  const solar = lunar.getSolar()
  return {
    year: solar.getYear(),
    month: solar.getMonth(),
    day: solar.getDay(),
  }
}

/**
 * 获取某农历年的闰月月份
 * @param year 农历年
 * @returns 闰月月份（1-12），0 表示该年无闰月
 */
export function getLeapMonth(year: number): number {
  return LunarYear.fromYear(year).getLeapMonth()
}

/**
 * 判断某农历年某月是否为闰月
 * @param year 农历年
 * @param month 农历月（1-12）
 */
export function isLeapMonthOf(year: number, month: number): boolean {
  return getLeapMonth(year) === month
}

/**
 * 公历日期转农历日期（用于展示层：把数据库存的公历日期还原为用户原始农历日期）
 * @param year 公历年
 * @param month 公历月（1-12）
 * @param day 公历日
 */
export function solarToLunar(year: number, month: number, day: number): SolarDate & { isLeap: boolean } {
  const solar = Solar.fromYmd(year, month, day)
  const lunar = solar.getLunar()
  return {
    year: lunar.getYear(),
    month: Math.abs(lunar.getMonth()),
    day: lunar.getDay(),
    isLeap: lunar.getMonth() < 0,
  }
}

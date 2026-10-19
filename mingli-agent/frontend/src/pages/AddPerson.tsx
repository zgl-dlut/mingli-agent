import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePersonStore } from '../store/personStore'
import { useUserStore } from '../store/userStore'
import RechargeModal from '../components/RechargeModal'
import { chinaAreas } from '../data/chinaAreas'
import { getCityCoord } from '../utils/cityCoords'
import { lunarToSolar, isLeapMonthOf } from '../utils/lunarConvert'

// 出生年份范围（1930 - 当前年份）
const currentYear = new Date().getFullYear()
const yearOptions: number[] = []
for (let y = currentYear; y >= 1930; y--) yearOptions.push(y)

const hourOptions = Array.from({ length: 24 }, (_, i) => i)
const minuteOptions = Array.from({ length: 60 }, (_, i) => i)

function getMonthDays(year: number, month: number): number {
  if (!year || !month) return 31
  return new Date(year, month, 0).getDate()
}

export default function AddPerson() {
  const { createPerson, persons } = usePersonStore()
  const { user, fetchUserInfo } = useUserStore()
  const navigate = useNavigate()

  const [gender, setGender] = useState<'male' | 'female'>('male')
  const [calendarType, setCalendarType] = useState<'solar' | 'lunar'>('solar')
  const [birthYear, setBirthYear] = useState<number>(0)
  const [birthMonth, setBirthMonth] = useState<number>(0)
  const [birthDay, setBirthDay] = useState<number>(0)
  const [birthHour, setBirthHour] = useState<number>(-1)
  const [birthMinute, setBirthMinute] = useState<number>(-1)
  const [province, setProvince] = useState('')
  const [city, setCity] = useState('')
  const [isLeapMonth, setIsLeapMonth] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')

  // 弹层状态
  const [isRechargeOpen, setIsRechargeOpen] = useState(false)

  // 当前省份下的城市列表
  const cityList = useMemo(() => {
    const provinceNode = chinaAreas.find((p) => p.name === province)
    return provinceNode?.children || []
  }, [province])

  // 根据年份月份计算可选天数
  const dayOptions = useMemo(() => {
    const max = getMonthDays(birthYear, birthMonth)
    return Array.from({ length: max }, (_, i) => i + 1)
  }, [birthYear, birthMonth])

  // 农历模式下，判断当前选中年月是否为闰月
  const isCurrentMonthLeap = useMemo(() => {
    if (calendarType !== 'lunar' || !birthYear || !birthMonth) return false
    return isLeapMonthOf(birthYear, birthMonth)
  }, [calendarType, birthYear, birthMonth])

  // 年份/月份变化时，若当前月不是闰月则重置闰月勾选
  useEffect(() => {
    if (!isCurrentMonthLeap) {
      setIsLeapMonth(false)
    }
  }, [isCurrentMonthLeap])

  const handleProvinceChange = (name: string) => {
    setProvince(name)
    setCity('')
  }

  // 表单是否填写完整
  const isFormValid = birthYear && birthMonth && birthDay && birthHour >= 0 && birthMinute >= 0 && province && city

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!birthYear || !birthMonth || !birthDay) {
      setError('请选择完整的出生日期')
      return
    }
    if (birthHour < 0 || birthMinute < 0) {
      setError('请选择完整的出生时间')
      return
    }
    if (!province || !city) {
      setError('请选择出生地省市')
      return
    }

    // 农历转公历
    let solarYear = birthYear
    let solarMonth = birthMonth
    let solarDay = birthDay
    if (calendarType === 'lunar') {
      try {
        const solar = lunarToSolar(birthYear, birthMonth, birthDay, isLeapMonth)
        solarYear = solar.year
        solarMonth = solar.month
        solarDay = solar.day
      } catch {
        setError('农历日期无效，请检查日期')
        return
      }
    }
    const birthDate = `${solarYear}-${String(solarMonth).padStart(2, '0')}-${String(solarDay).padStart(2, '0')}`
    const birthTime = `${String(birthHour).padStart(2, '0')}:${String(birthMinute).padStart(2, '0')}`
    const birthPlace = `${province} ${city}`

    // 去重检查（用转换后的公历日期）
    const duplicate = persons.find(
      (p) => p.gender === gender && p.birth_date === birthDate && p.birth_time === birthTime && p.birth_location === birthPlace
    )
    if (duplicate) {
      setError('该生辰已存在')
      goChat(duplicate.id)
      return
    }

    setIsLoading(true)
    try {
      // 查询城市经纬度
      const coord = getCityCoord(province, city)

      // 自动名用用户原始历法日期：农历用户显示农历日期（与后端 lunar_utils 展示格式对齐，闰月加"闰"）
      const displayDateForName =
        calendarType === 'lunar'
          ? `${birthYear}-${isLeapMonth ? '闰' : ''}${String(birthMonth).padStart(2, '0')}-${String(birthDay).padStart(2, '0')}`
          : birthDate
      const autoName = `${displayDateForName} ${birthTime}`
      const person = await createPerson({
        name: autoName,
        gender,
        birth_date: birthDate,
        birth_time: birthTime,
        birth_location: birthPlace,
        province,
        city,
        calendar_type: calendarType,
        birth_lat: coord.lat,
        birth_lng: coord.lng,
      })
      await fetchUserInfo()
      navigate(`/chat/${person.id}`)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setError(detail || '创建失败，请稍后重试')
    } finally {
      setIsLoading(false)
    }
  }

  const goChat = (personId: number) => {
    navigate(`/chat/${personId}`)
  }

  return (
    <div className="px-4 py-3 pb-6" style={{ maxWidth: '768px', margin: '0 auto' }}>
      {/* 页面标题 */}
      <div className="text-center mb-3">
        <h1 className="text-lg font-bold text-gray-800">命理分析</h1>
        <p className="text-gray-500 text-xs mt-0.5">输入生辰信息开始推算</p>
      </div>

      {/* 表单区域 */}
      <div>
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl shadow-sm p-4">
          {/* 性别 */}
          <div className="mb-3">
            <label className="block text-gray-700 text-xs font-medium mb-1.5">性别</label>
            <div className="flex space-x-3">
              <button
                type="button"
                onClick={() => setGender('male')}
                className={`flex-1 py-2 rounded-xl border-2 transition-all text-sm ${
                  gender === 'male'
                    ? 'border-primary-600 bg-primary-50 text-primary-700'
                    : 'border-gray-200 text-gray-500'
                }`}
              >
                👨 男
              </button>
              <button
                type="button"
                onClick={() => setGender('female')}
                className={`flex-1 py-2 rounded-xl border-2 transition-all text-sm ${
                  gender === 'female'
                    ? 'border-primary-600 bg-primary-50 text-primary-700'
                    : 'border-gray-200 text-gray-500'
                }`}
              >
                👩 女
              </button>
            </div>
          </div>

          {/* 历法类型 */}
          <div className="mb-3">
            <label className="block text-gray-700 text-xs font-medium mb-1.5">历法</label>
            <div className="flex space-x-3">
              <button
                type="button"
                onClick={() => setCalendarType('solar')}
                className={`flex-1 py-2 rounded-xl border-2 transition-all text-sm ${
                  calendarType === 'solar'
                    ? 'border-primary-600 bg-primary-50 text-primary-700'
                    : 'border-gray-200 text-gray-500'
                }`}
              >
                🌞 公历
              </button>
              <button
                type="button"
                onClick={() => setCalendarType('lunar')}
                className={`flex-1 py-2 rounded-xl border-2 transition-all text-sm ${
                  calendarType === 'lunar'
                    ? 'border-primary-600 bg-primary-50 text-primary-700'
                    : 'border-gray-200 text-gray-500'
                }`}
              >
                🌙 农历
              </button>
            </div>
          </div>

          {/* 闰月选择（仅农历模式且当前月为闰月时显示） */}
          {calendarType === 'lunar' && isCurrentMonthLeap && (
            <div className="mb-3 flex items-center gap-2">
              <input
                type="checkbox"
                id="isLeapMonth"
                checked={isLeapMonth}
                onChange={(e) => setIsLeapMonth(e.target.checked)}
                className="w-4 h-4 accent-primary-600"
              />
              <label htmlFor="isLeapMonth" className="text-xs text-gray-600">
                该月为闰月，按闰月计算
              </label>
            </div>
          )}

          {/* 出生时间 */}
          <div className="mb-3">
            <label className="block text-gray-700 text-xs font-medium mb-1.5">出生时间</label>
            <div className="grid grid-cols-5 gap-1.5">
              <select value={birthYear} onChange={(e) => setBirthYear(Number(e.target.value))}
                className="w-full px-1.5 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all appearance-none bg-white text-center">
                <option value={0}>年</option>
                {yearOptions.map((y) => (
                  <option key={y} value={y}>{y}</option>
                ))}
              </select>
              <select value={birthMonth} onChange={(e) => setBirthMonth(Number(e.target.value))}
                className="w-full px-1.5 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all appearance-none bg-white text-center">
                <option value={0}>月</option>
                {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
              <select value={birthDay} onChange={(e) => setBirthDay(Number(e.target.value))}
                className="w-full px-1.5 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all appearance-none bg-white text-center">
                <option value={0}>日</option>
                {dayOptions.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
              <select value={birthHour} onChange={(e) => setBirthHour(Number(e.target.value))}
                className="w-full px-1.5 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all appearance-none bg-white text-center">
                <option value={-1}>时</option>
                {hourOptions.map((h) => (
                  <option key={h} value={h}>{String(h).padStart(2, '0')}</option>
                ))}
              </select>
              <select value={birthMinute} onChange={(e) => setBirthMinute(Number(e.target.value))}
                className="w-full px-1.5 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all appearance-none bg-white text-center"
                disabled={birthHour < 0}>
                <option value={-1}>分</option>
                {minuteOptions.map((m) => (
                  <option key={m} value={m}>{String(m).padStart(2, '0')}</option>
                ))}
              </select>
            </div>
          </div>

          {/* 出生地 */}
          <div className="mb-3">
            <label className="block text-gray-700 text-xs font-medium mb-1.5">出生地</label>
            <div className="grid grid-cols-2 gap-2">
              <select value={province} onChange={(e) => handleProvinceChange(e.target.value)}
                className="w-full px-2 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all appearance-none bg-white">
                <option value="">省</option>
                {chinaAreas.map((p) => (
                  <option key={p.code} value={p.name}>{p.name}</option>
                ))}
              </select>
              <select value={city} onChange={(e) => setCity(e.target.value)}
                className="w-full px-2 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent outline-none transition-all appearance-none bg-white"
                disabled={!province}>
                <option value="">市</option>
                {cityList.map((c) => (
                  <option key={c.code} value={c.name}>{c.name}</option>
                ))}
              </select>
            </div>
          </div>

          {error && <div className="mb-4 text-red-500 text-sm text-center">{error}</div>}
        </form>
      </div>

      {/* 报告内容提示 */}
      <div className="mt-3 bg-white rounded-2xl shadow-sm p-4">
        <p className="text-xs font-medium text-gray-700 mb-2">提交后将为你生成：</p>
        <div className="grid grid-cols-2 gap-x-3 gap-y-2">
          {[
            { num: '1', label: '命盘解码：五行能量格局' },
            { num: '2', label: '性格密码：天赋与潜能' },
            { num: '3', label: '事业指南：财富与方向' },
            { num: '4', label: '姻缘洞察：感情与婚姻' },
            { num: '5', label: '运势推演：大运与流年' },
            { num: '6', label: '养生开运：健康与能量' },
          ].map((item) => (
            <div key={item.num} className="flex items-center gap-2">
              <span className="w-5 h-5 rounded-full bg-primary-50 text-primary-700 flex items-center justify-center text-[10px] font-bold shrink-0">
                {item.num}
              </span>
              <span className="text-xs text-gray-600">{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 提交按钮 */}
      <div className="mt-4 px-1">
        {/* 积分提示 */}
        <div className="text-center text-gray-400 text-[11px] mb-2">
          本次分析消耗 <span className="text-primary-600 font-bold">160</span> 积分，当前余额 <span className="text-primary-600 font-bold">{user?.points ?? 0}</span> 积分
        </div>

        {(user?.points ?? 0) < 160 ? (
          <button
            type="button"
            onClick={() => setIsRechargeOpen(true)}
            className="w-full py-2.5 rounded-xl font-medium text-sm transition-all"
            style={{ backgroundColor: '#a7876f', color: '#f4f2f0' }}
          >
            去充值
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={isLoading || !isFormValid}
            className="w-full py-2.5 rounded-xl font-medium text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ backgroundColor: '#a7876f', color: '#f4f2f0' }}
          >
            {isLoading ? '正在创建...' : '确认分析'}
          </button>
        )}
      </div>

      {/* 充值弹层 */}
      <RechargeModal
        isOpen={isRechargeOpen}
        onClose={() => setIsRechargeOpen(false)}
      />
    </div>
  )
}

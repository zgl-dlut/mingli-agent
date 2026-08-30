export interface User {
  id: number
  phone: string
  email?: string
  name: string
  avatar: string | null
  points: number
  created_at: string
}

export interface Person {
  id: number
  name: string
  gender: 'male' | 'female'
  birth_date: string
  birth_time: string
  birth_place: string
  province: string
  city: string
  calendar_type: 'solar' | 'lunar'
  longitude?: number
  latitude?: number
  bazi: BaziResult | null
  astrology: AstrologyResult | null
  bazi_data?: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface BaziResult {
  year_gan: string
  year_zhi: string
  month_gan: string
  month_zhi: string
  day_gan: string
  day_zhi: string
  hour_gan: string
  hour_zhi: string
  gan_zhi_str: string
  wuxing: {
    metal: number
    wood: number
    water: number
    fire: number
    earth: number
  }
  shishen: {
    year: { ten_god: string; gan: string; zhi: string }
    month: { ten_god: string; gan: string; zhi: string }
    day: { ten_god: string; gan: string; zhi: string }
    hour: { ten_god: string; gan: string; zhi: string }
  }
  zonghe_analysis: string
}

export interface AstrologyResult {
  sun_sign: string
  moon_sign: string
  rising_sign: string
  planets: {
    name: string
    sign: string
    degree: number
    house: number
  }[]
  houses: {
    house: number
    sign: string
    cusp: number
    ruler: string
  }[]
  aspects: {
    planet1: string
    planet2: string
    aspect: string
    orb: number
  }[]
  element_analysis: string
  modality_analysis: string
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface ChatSession {
  id: number
  person_id: number
  status: 'pending' | 'generating' | 'completed'
  messages: ChatMessage[]
  created_at: string
  updated_at: string
}

export interface Order {
  id: number
  points: number
  amount: number
  pay_method: string
  status: 'pending' | 'paid' | 'failed'
  trade_no: string | null
  created_at: string
  paid_at: string | null
}

export interface Transaction {
  id: number
  type: 'recharge' | 'consume' | 'refund'
  points: number
  order_id: number | null
  description: string
  created_at: string
}

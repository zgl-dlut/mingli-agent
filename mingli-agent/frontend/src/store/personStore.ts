import { create } from 'zustand'
import type { Person } from '../types'
import { personApi } from '../api/person'

const STORAGE_KEY = 'mingli_persons'

function loadPersons(): Person[] {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) {
    try {
      return JSON.parse(stored)
    } catch {
      return []
    }
  }
  return []
}

function savePersons(persons: Person[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(persons))
}

export interface CreatePersonInput {
  name: string
  gender: 'male' | 'female'
  birth_date: string
  birth_time: string
  birth_place: string
  province: string
  city: string
  calendar_type: 'solar' | 'lunar'
  birth_lat: number
  birth_lng: number
}

interface PersonStore {
  persons: Person[]
  isLoading: boolean
  error: string | null
  fetchPersons: () => Promise<void>
  createPerson: (data: CreatePersonInput) => Promise<Person>
  deletePerson: (id: number) => Promise<void>
  renamePerson: (id: number, name: string) => void
  getPerson: (id: number) => Person | undefined
  setPersons: (persons: Person[]) => void
  clearPersons: () => void
}

export const usePersonStore = create<PersonStore>((set, get) => ({
  persons: loadPersons(),
  isLoading: false,
  error: null,
  fetchPersons: async () => {
    try {
      const response = await personApi.list()
      const persons: Person[] = response.data.map((sp) => ({
        id: sp.id,
        name: sp.name,
        gender: (sp.gender === 'male' || sp.gender === 'female' ? sp.gender : 'male') as 'male' | 'female',
        birth_date: sp.birth_date,
        birth_time: sp.birth_time,
        birth_place: sp.birth_location,
        province: sp.province || '',
        city: sp.city || '',
        calendar_type: (sp.calendar_type === 'lunar' ? 'lunar' : 'solar') as 'solar' | 'lunar',
        longitude: sp.birth_lng,
        latitude: sp.birth_lat,
        bazi: null,
        astrology: null,
        bazi_data: sp.bazi_data,
        created_at: sp.created_at,
        updated_at: sp.created_at,
      }))
      savePersons(persons)
      set({ persons })
    } catch (err) {
      console.error('获取person列表失败:', err)
      set({ persons: loadPersons() })
    }
  },
  createPerson: async (data) => {
    const birthLocation = `${data.province} ${data.city}`
    const response = await personApi.create({
      name: data.name,
      gender: data.gender,
      birth_date: data.birth_date,
      birth_time: data.birth_time,
      birth_location: birthLocation,
      birth_lat: data.birth_lat,
      birth_lng: data.birth_lng,
      calendar_type: data.calendar_type,
      province: data.province,
      city: data.city,
    })
    const sp = response.data.person
    const person: Person = {
      id: sp.id,
      name: sp.name,
      gender: data.gender,
      birth_date: sp.birth_date,
      birth_time: sp.birth_time,
      birth_place: sp.birth_location,
      province: data.province,
      city: data.city,
      calendar_type: data.calendar_type,
      longitude: sp.birth_lng,
      latitude: sp.birth_lat,
      bazi: null,
      astrology: null,
      bazi_data: response.data.bazi_data,
      created_at: sp.created_at,
      updated_at: sp.created_at,
    }
    const persons = [person, ...get().persons]
    savePersons(persons)
    set({ persons })
    return person
  },
  deletePerson: async (id) => {
    try {
      await personApi.delete(id)
    } catch (err: any) {
      const status = err?.response?.status
      const detail = err?.response?.data?.detail || err?.message || String(err)
      console.error('[deletePerson] 失败:', { id, status, detail, err })
      throw new Error(`[${status || 'ERR'}] ${detail}`)
    }
    const persons = get().persons.filter((p) => p.id !== id)
    savePersons(persons)
    set({ persons })
  },
  renamePerson: (id, name) => {
    const persons = get().persons.map((p) =>
      p.id === id ? { ...p, name, updated_at: new Date().toISOString() } : p
    )
    savePersons(persons)
    set({ persons })
  },
  getPerson: (id) => get().persons.find((p) => p.id === id),
  setPersons: (persons) => {
    savePersons(persons)
    set({ persons })
  },
  clearPersons: () => {
    savePersons([])
    set({ persons: [] })
  },
}))

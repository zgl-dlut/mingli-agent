import { create } from 'zustand'
import type { Person, CreatePersonInput } from '../types'
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
      const persons = response.data
      savePersons(persons)
      set({ persons })
    } catch (err) {
      console.error('获取person列表失败:', err)
      set({ persons: loadPersons() })
    }
  },
  createPerson: async (data) => {
    const response = await personApi.create(data)
    const person: Person = {
      ...response.data.person,
      session_id: response.data.session_id,
      bazi_data: response.data.bazi_data,
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
      p.id === id ? { ...p, name } : p
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

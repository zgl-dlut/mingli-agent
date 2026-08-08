/**
 * 人物 API
 */
import apiClient from './client'

export interface PersonResponse {
  id: number
  user_id: number
  name: string
  gender: string
  birth_date: string
  birth_time: string
  birth_location: string
  birth_lat: number
  birth_lng: number
  calendar_type?: string
  province?: string
  city?: string
  created_at: string
}

export interface CreatePersonRequest {
  name: string
  gender: string
  birth_date: string
  birth_time: string
  birth_location: string
  birth_lat: number
  birth_lng: number
  calendar_type: 'solar' | 'lunar'
  province: string
  city: string
}

export interface CreatePersonResult {
  person: PersonResponse
  session_id: number
  bazi_data: Record<string, unknown>
  astro_data: Record<string, unknown>
}

export const personApi = {
  create: (data: CreatePersonRequest) =>
    apiClient.post<CreatePersonResult>('/persons', data),

  list: () =>
    apiClient.get<PersonResponse[]>('/persons'),

  get: (id: number) =>
    apiClient.get<PersonResponse>(`/persons/${id}`),

  update: (id: number, data: Partial<CreatePersonRequest>) =>
    apiClient.put<PersonResponse>(`/persons/${id}`, data),

  delete: (id: number) =>
    apiClient.delete(`/persons/${id}`),
}

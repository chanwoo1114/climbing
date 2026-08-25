import { api } from '@/api/client'

export interface TokenPair {
  access: string
  refresh: string
}

export interface Me {
  id: number
  email: string
  nickname: string
  bio: string
  image: string
  createdAt: string
}

export async function login(email: string, password: string): Promise<TokenPair> {
  const { data } = await api.post<TokenPair>('/auth/login/', { email, password })
  return data
}

export async function register(email: string, nickname: string, password: string) {
  const { data } = await api.post('/auth/register/', { email, nickname, password })
  return data
}

export async function logout(refresh: string) {
  await api.post('/auth/logout/', { refresh })
}

export async function fetchMe(): Promise<Me> {
  const { data } = await api.get<Me>('/users/me/')
  return data
}

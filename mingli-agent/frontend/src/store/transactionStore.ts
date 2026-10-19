import { create } from 'zustand'
import type { Transaction } from '../types'

const STORAGE_KEY = 'mingli_transactions'

function loadTransactions(): Transaction[] {
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

function saveTransactions(transactions: Transaction[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(transactions))
}

interface TransactionStore {
  transactions: Transaction[]
  addTransaction: (type: Transaction['type'], points: number, description: string) => void
  clearTransactions: () => void
}

let nextId = 1

export const useTransactionStore = create<TransactionStore>((set, get) => ({
  transactions: loadTransactions(),
  addTransaction: (type, points, description) => {
    const transaction: Transaction = {
      id: Date.now() + nextId++,
      type,
      points,
      biz_type: null,
      order_id: null,
      description,
      created_at: new Date().toISOString(),
    }
    const transactions = [transaction, ...get().transactions]
    saveTransactions(transactions)
    set({ transactions })
  },
  clearTransactions: () => {
    localStorage.removeItem(STORAGE_KEY)
    set({ transactions: [] })
  },
}))

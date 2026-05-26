export type Grade = "A" | "B" | "C" | "D" | "F"

export interface Company {
  id: string
  title: string
  logo: string
}

export interface ProbPoint {
  date: string
  prob: number
}

export interface Market {
  id: string
  title: string
  description: string
  grade: Grade
  price: number
  payout: number
  end_date: string
  status: "open" | "won" | "expired"
  bet_count: number
  company: Company
  probability_history: ProbPoint[]
}

export interface MarketEvent {
  date: string
  label: string
  note: string
  delta: number
}

export interface SpotlightMarket extends Market {
  events: MarketEvent[]
}

export interface NewsItem {
  id: string
  title: string
  source: string
  url: string
  published_at: string
  summary: string
  tags: string[]
  company_id: string | null
}

export interface BalancePoint {
  date: string
  balance: number
}

export interface User {
  id: string
  username: string
  schmeckles: number
  schmeckle_history: BalancePoint[]
}

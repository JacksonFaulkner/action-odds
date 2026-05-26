import { SchmeckleIcon } from "./SchmeckleIcon"
import type { User } from "@/types"

const SECTORS = ["All", "Tech", "Finance", "Crypto", "Healthcare", "Gov", "Infra"] as const
type Sector = typeof SECTORS[number]

interface NavbarProps {
  user: User
  activeSector: Sector
  onSectorChange: (s: Sector) => void
}

export function Navbar({ user, activeSector, onSectorChange }: NavbarProps) {
  return (
    <header className="sticky top-0 z-50 border-b border-zinc-800 backdrop-blur" style={{ backgroundColor: "#15191Dcc" }}>
      <div className="mx-auto flex max-w-7xl items-center gap-6 px-4 py-1">
        <div className="flex items-center gap-2">
          <img src="/logo.png" alt="Action Odds" className="h-14 object-contain" />
          <span className="text-lg font-bold tracking-tight text-white">Action Odds</span>
        </div>

        <nav className="flex gap-1">
          {SECTORS.map((s) => (
            <button
              key={s}
              onClick={() => onSectorChange(s)}
              className={`rounded px-3 py-1 text-sm font-medium transition-colors ${
                activeSector === s
                  ? "text-white border-b-2 border-[#C00000]"
                  : "text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {s}
            </button>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2 rounded-full border border-zinc-700 bg-zinc-900 px-4 py-1.5">
          <span className="font-bold text-white">{user.schmeckles.toLocaleString()}</span>
          <SchmeckleIcon className="h-8 w-8" />
        </div>
      </div>
    </header>
  )
}

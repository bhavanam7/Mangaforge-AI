export function LoadingState() {
  return <div className="studio-card flex items-center justify-center gap-3 py-20 text-sm text-slate-400"><span className="h-2 w-2 animate-pulse rounded-full bg-violet-400" /> Loading your workspace...</div>
}

export function ErrorState({ message }) {
  return <p className="rounded-xl border border-rose-400/30 bg-rose-950/30 p-4 text-sm text-rose-200">{message}</p>
}

export function EmptyState({ message }) {
  return <div className="studio-card border-dashed p-14 text-center"><div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-2xl bg-violet-400/10 text-xl text-violet-300">✦</div><p className="text-sm text-slate-400">{message}</p></div>
}

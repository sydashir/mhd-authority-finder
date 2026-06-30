import { AlertCircle, CheckCircle2, ExternalLink, X } from 'lucide-react'
import { useEffect } from 'react'

export interface ToastData {
  message: string
  href?: string
  tone?: 'success' | 'error'
}

export function Toast({ toast, onClose }: { toast: ToastData | null; onClose: () => void }) {
  useEffect(() => {
    if (!toast) return
    const t = setTimeout(onClose, 8000)
    return () => clearTimeout(t)
  }, [toast, onClose])

  if (!toast) return null
  const error = toast.tone === 'error'

  return (
    <div className="fixed bottom-5 right-5 z-50 flex max-w-sm items-start gap-3 rounded-lg border border-border bg-surface px-4 py-3 shadow-2xl">
      <span className={error ? 'text-red-500' : 'text-emerald-500'}>
        {error ? <AlertCircle size={18} /> : <CheckCircle2 size={18} />}
      </span>
      <div className="min-w-0 flex-1">
        <div className="text-[13px] text-fg">{toast.message}</div>
        {toast.href && (
          <a
            href={toast.href}
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-flex items-center gap-1 text-[12px] font-medium text-brand hover:underline"
          >
            Open sheet <ExternalLink size={12} />
          </a>
        )}
      </div>
      <button type="button" onClick={onClose} className="text-fg-subtle hover:text-fg" aria-label="Dismiss">
        <X size={15} />
      </button>
    </div>
  )
}

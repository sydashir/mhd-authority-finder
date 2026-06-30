import { Download, FileSpreadsheet, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { exportSheet, getAllProspects, type ProspectFilters } from '../api/client'
import { downloadCsv, prospectsToCsv } from '../lib/csv'
import type { ToastData } from './Toast'

const BTN =
  'inline-flex items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1.5 text-[12px] font-medium text-fg-muted hover:bg-raised disabled:cursor-not-allowed disabled:opacity-50'

export function ExportActions({
  filters,
  notify,
}: {
  filters: ProspectFilters
  notify: (toast: ToastData) => void
}) {
  const [csvBusy, setCsvBusy] = useState(false)
  const [sheetBusy, setSheetBusy] = useState(false)

  async function onCsv() {
    setCsvBusy(true)
    try {
      // Export every matching row (not just the visible page).
      const rows = await getAllProspects(filters)
      downloadCsv(`authorityscout-prospects-${rows.length}.csv`, prospectsToCsv(rows))
      notify({ message: `Exported ${rows.length} prospects to CSV.`, tone: 'success' })
    } catch {
      notify({ message: 'CSV export failed — is the backend running?', tone: 'error' })
    } finally {
      setCsvBusy(false)
    }
  }

  async function onSheet() {
    setSheetBusy(true)
    try {
      const result = await exportSheet(filters)
      notify({
        message: `Exported ${result.row_count} prospects to a new Google Sheet.`,
        href: result.url,
        tone: 'success',
      })
    } catch {
      notify({ message: 'Sheet export failed — check the service account.', tone: 'error' })
    } finally {
      setSheetBusy(false)
    }
  }

  return (
    <>
      <button type="button" onClick={onCsv} disabled={csvBusy} className={BTN}>
        {csvBusy ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
        Export CSV
      </button>
      <button
        type="button"
        onClick={onSheet}
        disabled={sheetBusy}
        className={`${BTN} border-brand/40 bg-brand/10 text-brand hover:bg-brand/15`}
      >
        {sheetBusy ? <Loader2 size={13} className="animate-spin" /> : <FileSpreadsheet size={13} />}
        Export Sheet
      </button>
    </>
  )
}

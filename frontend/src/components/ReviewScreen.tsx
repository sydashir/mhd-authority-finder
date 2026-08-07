// The review queue — what the learning layer PROPOSES, for a human to accept or reject.
//
// The screen's whole job is to make one judgement fast and well-informed, so every card
// leads with the evidence a reviewer actually needs: how the domain was labelled in the
// wild (anchor text), how many independent pages linked it, and which pages those were.
// The model's reasoning is shown last and framed as a suggestion, because it is the
// weakest evidence here and should not anchor the decision.

import { useState } from 'react'
import { Check, ExternalLink, Loader2, ListChecks, X } from 'lucide-react'
import { useDomainStats, useReviewDomain, useReviewQueue } from '../api/hooks'
import type { LinkDomain } from '../api/types'
import { ErrorState, TableSkeleton } from './states'
import type { ToastData } from './Toast'

const BUCKET_LABEL: Record<string, string> = {
  addiction_directory: 'Addiction directory',
  mental_health_directory: 'Mental health directory',
  support_group: 'Support group',
}

function Evidence({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="mb-1 text-[11px] uppercase tracking-wide text-fg-subtle">{label}</div>
      {children}
    </div>
  )
}

function DomainCard({
  domain,
  notify,
}: {
  domain: LinkDomain
  notify: (toast: ToastData) => void
}) {
  const review = useReviewDomain()
  const [bucket, setBucket] = useState(domain.bucket ?? 'support_group')
  const anchors = domain.anchor_texts.split('\n').filter(Boolean)
  const pages = domain.example_pages.split('\n').filter(Boolean)

  const decide = (approve: boolean) => {
    review.mutate(
      { id: domain.id, approve, bucket: approve ? bucket : null },
      {
        onSuccess: () =>
          notify({
            tone: 'success',
            message: approve
              ? `${domain.domain} approved as ${BUCKET_LABEL[bucket] ?? bucket}`
              : `${domain.domain} rejected — it will not be proposed again`,
          }),
        onError: () => notify({ tone: 'error', message: `Could not save ${domain.domain}` }),
      },
    )
  }

  return (
    <li className="rounded-xl border border-border bg-surface p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <a
            href={`https://${domain.domain}`}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-[15px] font-semibold text-fg hover:text-brand hover:underline"
          >
            {domain.domain} <ExternalLink size={12} />
          </a>
          <div className="mt-0.5 text-[12px] text-fg-muted">
            seen on <span className="tnum font-medium text-fg">{domain.page_count}</span> pages
            {domain.confidence !== null && (
              <> · model confidence {(domain.confidence * 100).toFixed(0)}%</>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="sr-only" htmlFor={`bucket-${domain.id}`}>
            Bucket for {domain.domain}
          </label>
          <select
            id={`bucket-${domain.id}`}
            value={bucket}
            onChange={(e) => setBucket(e.target.value)}
            className="rounded-lg border border-border bg-raised px-2.5 py-1.5 text-[12px] text-fg"
          >
            {Object.entries(BUCKET_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => decide(true)}
            disabled={review.isPending}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-[12px] font-medium text-white transition-colors hover:bg-brand-strong disabled:opacity-50"
          >
            {review.isPending ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
            Approve
          </button>
          <button
            type="button"
            onClick={() => decide(false)}
            disabled={review.isPending}
            className="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-[12px] font-medium text-fg-muted transition-colors hover:bg-raised hover:text-fg disabled:opacity-50"
          >
            <X size={13} /> Reject
          </button>
        </div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Evidence label="Labelled in the wild as">
          {anchors.length === 0 ? (
            <div className="text-[12px] italic text-fg-subtle">no anchor text captured</div>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {anchors.slice(0, 6).map((text) => (
                <li key={text} className="badge badge-neutral">
                  {text}
                </li>
              ))}
            </ul>
          )}
        </Evidence>
        <Evidence label="Found on">
          <ul className="space-y-0.5">
            {pages.slice(0, 3).map((url) => (
              <li key={url} className="truncate">
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[12px] text-brand hover:underline"
                >
                  {url}
                </a>
              </li>
            ))}
          </ul>
        </Evidence>
      </div>

      {domain.reasoning && (
        <p className="mt-3 border-t border-border pt-2.5 text-[12px] leading-relaxed text-fg-subtle">
          <span className="font-medium">Suggested:</span> {domain.reasoning}
        </p>
      )}
    </li>
  )
}

export function ReviewScreen({ notify }: { notify: (toast: ToastData) => void }) {
  const [offset, setOffset] = useState(0)
  const limit = 25
  const queue = useReviewQueue({ limit, offset })
  const stats = useDomainStats()

  if (queue.isPending) return <TableSkeleton />
  if (queue.isError) {
    return (
      <ErrorState
        message="Could not load the review queue"
        onRetry={() => void queue.refetch()}
      />
    )
  }

  const { items, total } = queue.data

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-[18px] font-semibold text-fg">Domain review</h1>
        <p className="mt-1 max-w-2xl text-[13px] leading-relaxed text-fg-muted">
          Domains the tool found but has not been told about. Nothing here reaches the
          deliverable until you approve it — rejections are remembered and never proposed again.
        </p>
        {stats.data && (
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1 text-[12px] text-fg-muted">
            <span>
              <span className="tnum font-medium text-fg">{stats.data.awaiting_review}</span>{' '}
              awaiting review
            </span>
            <span>
              <span className="tnum font-medium text-fg">{stats.data.approved}</span> approved
            </span>
            <span>
              <span className="tnum font-medium text-fg">{stats.data.rejected}</span> rejected
            </span>
            <span>
              <span className="tnum font-medium text-fg">
                {stats.data.observed.toLocaleString()}
              </span>{' '}
              domains observed
            </span>
          </div>
        )}
      </header>

      {items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border border-border bg-surface px-6 py-12 text-center">
          <ListChecks size={22} className="text-fg-subtle" />
          <div className="text-[14px] font-medium text-fg">Nothing waiting</div>
          <p className="max-w-sm text-[12px] text-fg-muted">
            Every proposed domain has been decided. New ones appear here after the next run.
          </p>
        </div>
      ) : (
        <>
          <ul className="space-y-2.5">
            {items.map((domain) => (
              <DomainCard key={domain.id} domain={domain} notify={notify} />
            ))}
          </ul>
          {total > limit && (
            <div className="flex items-center justify-between text-[12px] text-fg-muted">
              <span>
                Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
              </span>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                  className="cursor-pointer rounded-lg border border-border px-2.5 py-1 hover:bg-raised disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={offset + limit >= total}
                  onClick={() => setOffset(offset + limit)}
                  className="cursor-pointer rounded-lg border border-border px-2.5 py-1 hover:bg-raised disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

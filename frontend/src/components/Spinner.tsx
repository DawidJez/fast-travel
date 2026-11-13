/** Small spinning circle; decorative (screen readers get the text next to it). */
export default function Spinner({ className = 'h-4 w-4' }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z" />
    </svg>
  )
}

/** Spinner + text for a whole area that is loading. */
export function Loading({ text }: { text: string }) {
  return (
    <p role="status" className="flex items-center gap-2 py-6 text-slate-500">
      <Spinner className="h-5 w-5 text-blue-600" />
      {text}
    </p>
  )
}

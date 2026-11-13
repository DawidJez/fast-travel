/** Shared Tailwind class sets, so buttons, cards and alerts look the same everywhere. */

export const card = 'rounded-xl border border-slate-200 bg-white shadow-sm'

export const button = {
  primary:
    'inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm ' +
    'hover:bg-blue-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-60',
  secondary:
    'inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 ' +
    'hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:cursor-not-allowed disabled:opacity-60',
  small:
    'rounded-md px-2 py-1 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-blue-600',
}

export const alert = 'rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800'

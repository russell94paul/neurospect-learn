import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { format, parseISO } from 'date-fns';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  try {
    // Handle both "YYYY-MM-DD" and full ISO strings
    const date = dateStr.includes('T') ? parseISO(dateStr) : parseISO(dateStr + 'T00:00:00');
    return format(date, 'MMM d, yyyy');
  } catch {
    return dateStr;
  }
}

export function formatDecimal(value: number | null | undefined, decimals = 2): string {
  if (value == null) return '—';
  return value.toFixed(decimals);
}

export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value == null) return '—';
  return `${(value * 100).toFixed(decimals)}%`;
}

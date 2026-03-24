import { format, formatDistanceToNow, parseISO, isToday, isYesterday } from 'date-fns';

function toDate(date: string | Date): Date {
  return typeof date === 'string' ? parseISO(date) : date;
}

export function formatReceiptDate(date: string | Date): string {
  return format(toDate(date), 'dd MMM yyyy');
}

export function formatRelativeDate(date: string | Date): string {
  const d = toDate(date);
  if (isToday(d)) return 'Today';
  if (isYesterday(d)) return 'Yesterday';
  return formatDistanceToNow(d, { addSuffix: true });
}

export function formatMonthYear(date: string | Date): string {
  return format(toDate(date), 'MMMM yyyy');
}

export function formatShortDate(date: string | Date): string {
  return format(toDate(date), 'dd/MM');
}

import { Session } from './types';

export function formatPrice(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

export function formatCompact(value: number): string {
  if (value >= 1e9) return `${(value / 1e9).toFixed(2)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(2)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}K`;
  return value.toFixed(0);
}

export function formatFunding(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${(value * 100).toFixed(4)}%`;
}

export function getSession(): Session {
  const hour = new Date().getUTCHours();
  if (hour >= 0 && hour < 7) return 'ASIA';
  if (hour >= 7 && hour < 12) return 'LONDON';
  if (hour >= 12 && hour < 16) return 'OVERLAP';
  return 'NEW_YORK';
}

export function getSessionEmoji(session?: Session): string {
  const s = session || getSession();
  switch (s) {
    case 'ASIA': return '🌏';
    case 'LONDON': return '🇬🇧';
    case 'NEW_YORK': return '🇺🇸';
    case 'OVERLAP': return '🔄';
    default: return '🌐';
  }
}

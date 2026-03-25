export function formatPercent(val) {
  if (val === null || val === undefined || isNaN(val)) return '--';
  const pct = typeof val === 'number' && Math.abs(val) < 1 ? val * 100 : val;
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}%`;
}

export function formatCurrency(val) {
  if (val === null || val === undefined || isNaN(val)) return '--';
  return '$' + Number(val).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatNumber(val) {
  if (val === null || val === undefined || isNaN(val)) return '--';
  return Number(val).toLocaleString('en-US');
}

export function formatDate(str) {
  if (!str) return '--';
  try {
    return new Date(str).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  } catch { return str; }
}

export function truncateId(uuid) {
  if (!uuid) return '--';
  return String(uuid).substring(0, 8);
}

export function cn(...classes) {
  return classes.filter(Boolean).join(' ');
}

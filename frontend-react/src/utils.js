export function formatPercent(val) {
  if (val === null || val === undefined || isNaN(val)) return '--';
  const num = Number(val);
  if (isNaN(num)) return '--';
  const pct = Math.abs(num) < 1 ? num * 100 : num;
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}%`;
}

export function formatCurrency(val) {
  const num = Number(val);
  if (val === null || val === undefined || isNaN(num)) return '--';
  return '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatNumber(val) {
  const num = Number(val);
  if (val === null || val === undefined || isNaN(num)) return '--';
  return num.toLocaleString('en-US');
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

export function formatCurrency(amount: number): string {
  return `€${amount.toFixed(2)}`;
}

export function formatCurrencyChange(amount: number): string {
  const sign = amount >= 0 ? '+' : '';
  return `${sign}€${Math.abs(amount).toFixed(2)}`;
}

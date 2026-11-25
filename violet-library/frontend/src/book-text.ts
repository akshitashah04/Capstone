const MISSING_DESCRIPTIONS = new Set(['', 'undefined', 'null', 'none', 'nan', 'n/a']);

export function cleanDescription(value: unknown): string {
  if (typeof value !== 'string') return '';
  const description = value.replace(/\s+/g, ' ').trim();
  return MISSING_DESCRIPTIONS.has(description.toLowerCase()) ? '' : description;
}

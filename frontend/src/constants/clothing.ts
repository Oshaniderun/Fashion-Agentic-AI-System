/** Shared clothing attribute options (must stay aligned with backend ontology). */
export const CLOTHING_CATEGORIES = [
  'top',
  'bottom',
  'dress',
  'outerwear',
  'shoes',
  'bag',
  'accessory',
] as const;

export const CLOTHING_PATTERNS = [
  'solid',
  'striped',
  'checked',
  'floral',
  'printed',
  'polka_dot',
  'textured',
  'unknown',
] as const;

export const CLOTHING_STYLES = [
  'casual',
  'smart_casual',
  'formal',
  'semi_formal',
  'elegant',
  'streetwear',
  'minimalist',
] as const;

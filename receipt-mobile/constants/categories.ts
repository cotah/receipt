export const CATEGORIES = [
  { key: 'fruit-veg', label: 'Fruit & Veg', icon: 'shopping-bag' },
  { key: 'dairy', label: 'Dairy', icon: 'droplet' },
  { key: 'meat-fish', label: 'Meat & Fish', icon: 'thermometer' },
  { key: 'bakery', label: 'Bakery', icon: 'coffee' },
  { key: 'frozen', label: 'Frozen', icon: 'cloud-snow' },
  { key: 'drinks', label: 'Drinks', icon: 'cup' },
  { key: 'snacks', label: 'Snacks & Confectionery', icon: 'gift' },
  { key: 'household', label: 'Household', icon: 'home' },
  { key: 'personal-care', label: 'Personal Care', icon: 'heart' },
  { key: 'baby-kids', label: 'Baby & Kids', icon: 'smile' },
  { key: 'other', label: 'Other', icon: 'more-horizontal' },
] as const;

export type CategoryKey = (typeof CATEGORIES)[number]['key'];

export const getCategoryByLabel = (label: string) =>
  CATEGORIES.find((c) => c.label === label) ?? CATEGORIES[CATEGORIES.length - 1];

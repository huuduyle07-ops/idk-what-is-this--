const PRODUCTS: Record<string, number> = {
  widget: 50,
  gadget: 100,
  sprocket: 200,
};

export function getMaxCapacity(productName: string): number {
  const cap = PRODUCTS[productName];
  if (cap === undefined) {
    throw new Error(`unknown product: ${productName}`);
  }
  return cap;
}

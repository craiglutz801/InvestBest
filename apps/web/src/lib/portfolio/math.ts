export function toNum(d: { toString(): string } | number | null | undefined): number {
  if (d == null) return 0;
  if (typeof d === "number") return d;
  return Number(d.toString());
}

/** Whole shares (floor) per spec */
export function wholeShares(dollars: number, price: number): number {
  if (price <= 0) return 0;
  return Math.floor(dollars / price);
}

/** Position market value */
export function marketValue(quantity: number, price: number): number {
  return quantity * price;
}

/** Unrealized P&L */
export function unrealizedPnl(quantity: number, avgCost: number, price: number): number {
  return quantity * (price - avgCost);
}

/** Mark-to-market contribution to portfolio equity (shorts subtract liability). */
export function signedExposureMarketValue(quantity: number, price: number, isShort: boolean): number {
  const v = quantity * price;
  return isShort ? -v : v;
}

/** Unrealized P&L for long or short (avgCost for short is entry sell price). */
export function unrealizedPnlPosition(quantity: number, avgCost: number, price: number, isShort: boolean): number {
  return isShort ? quantity * (avgCost - price) : quantity * (price - avgCost);
}

/** Realized P&L closing a short (buy-to-cover). */
export function realizedPnlCoverShort(quantity: number, avgCostShort: number, coverPrice: number): number {
  return quantity * (avgCostShort - coverPrice);
}

/** Gross notional |qty × price| for exposure reporting. */
export function grossNotional(quantity: number, price: number): number {
  return quantity * price;
}

/** New average cost after buy */
export function avgCostAfterBuy(
  prevQty: number,
  prevAvg: number,
  buyQty: number,
  buyPrice: number,
): number {
  const totalQty = prevQty + buyQty;
  if (totalQty <= 0) return buyPrice;
  return (prevQty * prevAvg + buyQty * buyPrice) / totalQty;
}

/** Realized P&L for full exit */
export function realizedPnlSell(quantity: number, avgCost: number, sellPrice: number): number {
  return quantity * (sellPrice - avgCost);
}

/** Apply slippage: buy pays more, sell receives less (spec: default 0.05%) */
export function applySlippage(price: number, side: "BUY" | "SELL", slippagePct: number): number {
  const factor = slippagePct / 100;
  return side === "BUY" ? price * (1 + factor) : price * (1 - factor);
}

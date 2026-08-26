/**
 * Active-app live-broker isolation.
 *
 * The Next.js paper engine (`apps/web`) must not import a broker SDK or place
 * live orders. Legacy Alpaca fields live only under `config/` + `backend/`
 * (unused by this runtime) and are documented as isolated.
 */

export const ACTIVE_APP_BROKER_POLICY = {
  liveOrdersAllowed: false,
  brokerSdkAllowed: false,
  supportedExecutionMode: "paper",
  legacyBrokerConfigLocation: "config/settings.py (legacy FastAPI stack only)",
} as const;

/** Import / identifier patterns that must not appear in the active web runtime. */
export const FORBIDDEN_ACTIVE_APP_BROKER_PATTERNS: readonly string[] = [
  "@alpacahq/alpaca-trade-api",
  "alpaca-trade-api",
  "from alpaca",
  "ib_insync",
  "ibkr",
  "interactivebrokers",
  "place_order",
  "submitOrder",
  "createOrder",
];

export function scanForForbiddenBrokerUsage(source: string): string[] {
  const lower = source.toLowerCase();
  return FORBIDDEN_ACTIVE_APP_BROKER_PATTERNS.filter((p) => lower.includes(p.toLowerCase()));
}

export function assertNoLiveBrokerCapability(): void {
  if (ACTIVE_APP_BROKER_POLICY.liveOrdersAllowed || ACTIVE_APP_BROKER_POLICY.brokerSdkAllowed) {
    throw new Error("Active paper runtime must not enable live broker orders.");
  }
}

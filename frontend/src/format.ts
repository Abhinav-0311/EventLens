import type { Signal } from "./types";

export function moneyCents(value: string): bigint {
  const match = /^([+-]?)(\d+)(?:\.(\d{1,2}))?$/.exec(value);
  if (!match) throw new Error("Invalid decimal financial value");
  return (
    (match[1] === "-" ? -1n : 1n) *
    (BigInt(match[2]) * 100n + BigInt((match[3] ?? "").padEnd(2, "0")))
  );
}
export function decimalFromCents(value: bigint): string {
  const absolute = value < 0n ? -value : value;
  return `${value < 0n ? "-" : ""}${absolute / 100n}.${String(absolute % 100n).padStart(2, "0")}`;
}
export function money(value: string, signed = false): string {
  const cents = moneyCents(value);
  const absolute = cents < 0n ? -cents : cents;
  const dollars = String(absolute / 100n).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${cents < 0n ? "−" : signed && cents > 0n ? "+" : ""}$${dollars}.${String(absolute % 100n).padStart(2, "0")}`;
}
export function signedDecimal(value: string): string {
  return value.startsWith("-")
    ? `−${value.slice(1)}`
    : Number(value) > 0
      ? `+${value}`
      : value;
}
export function utc(value: string | null): string {
  if (!value || Number.isNaN(new Date(value).getTime())) return "Not available";
  return (
    new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "UTC",
    }).format(new Date(value)) + " UTC"
  );
}
const titles: Record<string, string> = {
  rate_hike: "Policy rate increase",
  rate_cut: "Policy rate decrease",
  credit_deterioration: "Corporate credit deterioration",
  supply_disruption: "Supply disruption",
  acquisition: "Merger or acquisition",
  product_launch: "Product launch",
  macro_announcement: "Macro announcement",
  geopolitical_event: "Geopolitical event",
  ambiguous: "Conflicting event signals",
  unknown: "Unclassified announcement",
};
export function title(
  signal: Pick<Signal, "event_subtype" | "assertion_status">,
): string {
  return `${signal.assertion_status === "speculative" ? "Possible " : signal.assertion_status === "negated" ? "Negated: " : ""}${titles[signal.event_subtype] ?? "Unclassified announcement"}`;
}
const reasons: Record<string, string> = {
  source_not_verified: "Publisher is not verified.",
  non_live_mode: "This is not live-source evidence.",
  language_requires_review: "English-language evidence has not been confirmed.",
  impact_not_above_threshold:
    "Impact does not exceed the automatic threshold of 7.",
  scenario_unsupported: "No supported banking scenario matches this event.",
  event_not_asserted: "The event is speculative, negated or unclear.",
  cross_source_conflict:
    "Saved evidence disagrees about the event or direction.",
  stale_event: "Publication is outside the 72-hour freshness window.",
  future_publication:
    "Publication is in the future relative to the evaluation clock.",
  no_matching_exposure: "No eligible portfolio exposure was identified.",
  supply_exposure_unresolved:
    "An affected energy or transport exposure has not been resolved.",
  non_us_policy_requires_review:
    "This policy event is not linked to US rate exposure.",
  exposure_entity_unresolved:
    "The affected corporate issuer or sector is unresolved.",
  sentiment_truncated: "The model could not process all source tokens.",
  source_text_truncated: "The source text was truncated.",
  release_expansion_failed: "The full official release could not be fetched.",
  potential_text_duplicate:
    "The same text appears under another event identity; review it before running.",
  speculative_event:
    "The text describes a possible event, not an asserted decision.",
  multiple_event_clauses: "Multiple current event clauses require review.",
  magnitude_unspecified: "A policy change amount could not be extracted.",
  historical_context_ignored:
    "Historical context was excluded from the current-event rule.",
  geopolitical_cause_unclear: "A geopolitical cause has not been established.",
  conflicting_events:
    "The text contains conflicting event types or directions.",
  unsupported_event: "No supported current event phrase was found.",
};
export function reasonLabel(reason: string): string {
  return reasons[reason] ?? `${reason.replaceAll("_", " ")}.`;
}
export function safeSourceUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" &&
      !url.username &&
      !url.password &&
      (!url.port || url.port === "443") &&
      ["www.federalreserve.gov", "bsky.app"].includes(url.hostname)
      ? url.href
      : null;
  } catch {
    return null;
  }
}
export const modeLabel = (mode: string) =>
  ({
    automatic_live: "Live-source stress",
    automatic_simulation: "Automatic simulation",
    manual_comparison: "Manual comparison",
    synthetic: "Fictional sample",
    live: "Live source",
    user: "Supplied text",
    replay: "Saved replay",
  })[mode] ?? mode;
export function sentimentLabel(value: number) {
  return `${value > 0.05 ? "Positive" : value < -0.05 ? "Negative" : "Neutral"} ${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(3)}`;
}

export interface Signal {
  id: string;
  event_id: string;
  source_record_id: string;
  event_class: string;
  event_subtype: string;
  assertion_status: "asserted" | "speculative" | "negated" | "unclear";
  impact_score: number;
  impact_components: {
    magnitude_points: number;
    scope_points: number;
    rationale: string;
    rubric_version: string;
  };
  sentiment_score: number;
  sentiment_model_id: string;
  model_revision: string;
  sentiment_probabilities: Record<string, number>;
  engine_version: string;
  created_at: string;
  simulation_clock: string | null;
  review_reasons: string[];
  evidence_spans: { start: number; end: number; text: string }[];
  affected_issuers: string[];
  affected_sectors: string[];
  affected_regions: string[];
}
export interface Source {
  id: string;
  publisher: string;
  source_family: string;
  source_id: string;
  canonical_uri: string;
  text: string;
  text_kind: string;
  published_at: string;
  retrieved_at: string;
  provenance_mode: string;
  verified_publisher: boolean;
}
export interface Eligibility {
  state:
    "informational" | "needs_review" | "eligible_live" | "eligible_simulation";
  scenario_id: string | null;
  reasons: string[];
  rate_position_ids: string[];
  spread_position_ids: string[];
  reference_clock: string;
  evaluated_at: string;
}
export interface EventSummary {
  id: string;
  primary_signal: Signal;
  source_record_ids: string[];
  source_families: string[];
  provenance_modes: string[];
  verified_publisher_count: number;
  evidence_independent: boolean;
  eligibility: Eligibility | null;
}
export interface EventDetail {
  event: EventSummary;
  evidence: Source[];
  signals: Signal[];
  eligibility: Eligibility;
  stress_run_ids: string[];
}
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
export interface Position {
  id: string;
  asset_type: "loan" | "bond" | "swap";
  instrument_type: string;
  issuer: string;
  sector: string;
  currency: string;
  region: string;
  base_market_value_usd: string;
  notional_usd: string;
  rate_duration: string;
  spread_duration: string;
  signed_rate_pnl_per_bp: string;
}
export interface Portfolio {
  name: string;
  version: string;
  provenance: "synthetic";
  currency: string;
  assumptions: string[];
  positions: Position[];
  base_total_usd: string;
  notional_total_usd: string;
}
export interface Scenario {
  id: string;
  version: string;
  name: string;
  event_subtype: string;
  rate_shock_bp: string;
  spread_shock_bp: string;
  reference_impact: number;
  assumption: string;
}
export interface PositionResult {
  position_id: string;
  base_market_value_usd: string;
  rate_applied: boolean;
  spread_applied: boolean;
  rate_pnl_usd: string;
  spread_pnl_usd: string;
  total_pnl_usd: string;
  stressed_market_value_usd: string;
  explanation: string;
}
export interface Run {
  id: string;
  status: "completed";
  event_id: string;
  signal_id: string;
  mode: "automatic_live" | "automatic_simulation" | "manual_comparison";
  created_at: string;
  scenario_id: string;
  scenario_version: string;
  portfolio_version: string;
  actual_rate_shock_bp: string;
  actual_spread_shock_bp: string;
  impact_score: number;
  base_total_usd: string;
  stressed_total_usd: string;
  total_pnl_usd: string;
  simulation_clock: string | null;
  override_reason: string | null;
  portfolio_snapshot: Portfolio;
  scenario_snapshot: Scenario;
  signal_snapshot: Signal;
  source_snapshot: Source[];
  eligibility_snapshot: Eligibility;
  position_results: PositionResult[];
  calculation_version: string;
}
export interface Health {
  status: string;
  model_ready: boolean;
  portfolio_available: boolean;
  model_revision: string;
  model_error_code: string | null;
  sources: {
    source_id: string;
    stale: boolean;
    error_code: string | null;
    last_success_at: string | null;
    next_allowed_at: string | null;
  }[];
}
export interface Operation {
  id: string;
  status: "queued" | "running" | "completed" | "failed" | "interrupted";
  kind: string;
  result_counts: Record<string, number>;
  error_code: string | null;
}

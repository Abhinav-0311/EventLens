import { useState } from "react";
import type { Api } from "./api";
import { useResource } from "./hooks";
import type { Page, Run } from "./types";
import {
  decimalFromCents,
  modeLabel,
  money,
  moneyCents,
  reasonLabel,
  signedDecimal,
  utc,
} from "./format";
import { Badge, Download, Empty, ErrorPanel, Loading, Pagination } from "./ui";

function Result({ api, run }: { api: Api; run: Run }) {
  const sign =
    moneyCents(run.total_pnl_usd) < 0n
      ? "loss"
      : moneyCents(run.total_pnl_usd) > 0n
        ? "gain"
        : "unchanged";
  const groups = ["loan", "bond", "swap"].map((asset) => ({
    asset,
    cents: run.position_results
      .filter(
        (result) =>
          run.portfolio_snapshot.positions.find(
            (position) => position.id === result.position_id,
          )?.asset_type === asset,
      )
      .reduce((sum, result) => sum + moneyCents(result.total_pnl_usd), 0n),
  }));
  const max = Math.max(
    1,
    ...groups.map((group) => Math.abs(Number(group.cents))),
  );
  const positions = new Map(
    run.portfolio_snapshot.positions.map((position) => [position.id, position]),
  );
  const reconciles =
    run.position_results.reduce(
      (sum, result) => sum + moneyCents(result.total_pnl_usd),
      0n,
    ) === moneyCents(run.total_pnl_usd) &&
    moneyCents(run.base_total_usd) + moneyCents(run.total_pnl_usd) ===
      moneyCents(run.stressed_total_usd);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">{run.scenario_snapshot.name}</p>
          <h1>Stress result</h1>
        </div>
        <div className="actions">
          <Download
            api={api}
            path={`/api/exports/stress-runs/${run.id}?format=csv`}
            name={`eventlens-stress-${run.id}.csv`}
            primary
          >
            Export CSV
          </Download>
          <Download
            api={api}
            path={`/api/exports/stress-runs/${run.id}`}
            name={`eventlens-stress-${run.id}.json`}
          >
            Export JSON
          </Download>
        </div>
      </div>
      <div className="result-meta">
        <Badge tone={run.mode === "automatic_simulation" ? "amber" : "neutral"}>
          {modeLabel(run.mode)}
        </Badge>
        <span className="small muted">Saved {utc(run.created_at)}</span>
        <a className="text-link" href={`#events/${run.event_id}`}>
          View event evidence ↗
        </a>
        <a className="text-link" href="#runs">
          All runs
        </a>
      </div>
      <p className="result-disclaimer">
        Conditional result for a fictional portfolio. Not a forecast of actual
        losses.
      </p>
      {!reconciles && (
        <ErrorPanel message="This saved response does not reconcile. Do not interpret the totals; inspect the JSON and contact the project owner." />
      )}
      <dl className="totals">
        <div>
          <dt>Original base · USD</dt>
          <dd>{money(run.base_total_usd)}</dd>
        </div>
        <div className={sign}>
          <dt>Scenario {sign === "unchanged" ? "P&L" : sign} · USD</dt>
          <dd>{money(run.total_pnl_usd, true)}</dd>
        </div>
        <div>
          <dt>Stressed fair value · USD</dt>
          <dd>{money(run.stressed_total_usd)}</dd>
        </div>
      </dl>
      <div className="shock-line">
        <span>
          Impact <strong>{run.impact_score} / 10</strong>
        </span>
        <span>
          USD rate <strong>{signedDecimal(run.actual_rate_shock_bp)} bp</strong>
        </span>
        <span>
          Matched credit spread{" "}
          <strong>{signedDecimal(run.actual_spread_shock_bp)} bp</strong>
        </span>
        <span>
          {reconciles ? "Totals reconcile to cents" : "Reconciliation failed"}
        </span>
      </div>
      <section
        className="contribution-section"
        aria-labelledby="contribution-heading"
      >
        <h2 id="contribution-heading">Where the change comes from</h2>
        <div className="contributions">
          {groups.map((group) => (
            <div className="contribution" key={group.asset}>
              <span>
                {group.asset === "swap"
                  ? "Rate swaps"
                  : `${group.asset.charAt(0).toUpperCase()}${group.asset.slice(1)}s`}
              </span>
              <div className="contribution-track" aria-hidden="true">
                <span
                  className={group.cents < 0n ? "loss-bar" : "gain-bar"}
                  style={{
                    width: `${(Math.abs(Number(group.cents)) / max) * 100}%`,
                  }}
                />
              </div>
              <strong className={group.cents < 0n ? "loss" : "gain"}>
                {money(decimalFromCents(group.cents), true)}
              </strong>
            </div>
          ))}
        </div>
      </section>
      <section className="section-block">
        <div className="section-heading">
          <h2>Position contributions</h2>
          <span className="small muted">
            Independent calculation · same base
          </span>
        </div>
        <div
          className="table-scroll"
          tabIndex={0}
          role="region"
          aria-label="Scrollable position contributions"
        >
          <table aria-label="Stress position results">
            <thead>
              <tr>
                <th scope="col">Position / issuer</th>
                <th scope="col">Exposure applied</th>
                <th scope="col" className="numeric">
                  Base · USD
                </th>
                <th scope="col" className="numeric">
                  Rate P&L · USD
                </th>
                <th scope="col" className="numeric">
                  Spread P&L · USD
                </th>
                <th scope="col" className="numeric">
                  Total P&L · USD
                </th>
                <th scope="col" className="numeric">
                  Stressed · USD
                </th>
              </tr>
            </thead>
            <tbody>
              {run.position_results.map((result) => (
                <tr key={result.position_id}>
                  <th scope="row">
                    {result.position_id}
                    <small>
                      {positions.get(result.position_id)?.issuer ??
                        "Unknown position"}
                    </small>
                  </th>
                  <td>
                    {result.rate_applied ? "Rate" : ""}
                    {result.rate_applied && result.spread_applied ? " + " : ""}
                    {result.spread_applied ? "Credit spread" : ""}
                    {!result.rate_applied && !result.spread_applied
                      ? "Unaffected"
                      : ""}
                    <small>
                      {positions.get(result.position_id)?.asset_type}
                    </small>
                  </td>
                  <td className="numeric">
                    {money(result.base_market_value_usd)}
                  </td>
                  <td className="numeric">
                    {money(result.rate_pnl_usd, true)}
                  </td>
                  <td className="numeric">
                    {money(result.spread_pnl_usd, true)}
                  </td>
                  <td
                    className={`numeric ${moneyCents(result.total_pnl_usd) < 0n ? "loss" : moneyCents(result.total_pnl_usd) > 0n ? "gain" : ""}`}
                  >
                    {money(result.total_pnl_usd, true)}
                  </td>
                  <td className="numeric">
                    {money(result.stressed_market_value_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <details className="section-block">
        <summary>Scenario assumptions & audit trail</summary>
        <p>{run.scenario_snapshot.assumption}</p>
        {run.override_reason && (
          <p>
            <strong>Manual comparison reason:</strong> {run.override_reason}
          </p>
        )}
        {run.simulation_clock && (
          <p>Fictional simulation clock: {utc(run.simulation_clock)}.</p>
        )}
        <p className="small muted">
          Reference at impact {run.scenario_snapshot.reference_impact}: rate{" "}
          {signedDecimal(run.scenario_snapshot.rate_shock_bp)} bp, spread{" "}
          {signedDecimal(run.scenario_snapshot.spread_shock_bp)} bp. Applied
          scale = min(impact / 8, 1.25).
        </p>
        <ul className="assumptions">
          {run.portfolio_snapshot.assumptions.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
        {run.eligibility_snapshot.reasons.length > 0 && (
          <>
            <h3>Eligibility at comparison time</h3>
            <ul className="review-reasons">
              {run.eligibility_snapshot.reasons.map((reason) => (
                <li key={reason}>{reasonLabel(reason)}</li>
              ))}
            </ul>
          </>
        )}
        <dl className="audit-grid">
          <div>
            <dt>Portfolio version</dt>
            <dd>{run.portfolio_version}</dd>
          </div>
          <div>
            <dt>Scenario version</dt>
            <dd>{run.scenario_version}</dd>
          </div>
          <div>
            <dt>Calculation</dt>
            <dd>{run.calculation_version}</dd>
          </div>
          <div>
            <dt>Run ID</dt>
            <dd>
              <code>{run.id}</code>
            </dd>
          </div>
          <div>
            <dt>Signal ID</dt>
            <dd>
              <code>{run.signal_id}</code>
            </dd>
          </div>
        </dl>
        <p className="small muted">
          Saved evidence and input snapshots are preserved even when later
          evidence or current eligibility changes. The base is never
          overwritten.
        </p>
      </details>
    </>
  );
}
export function RunView({
  api,
  selectedId,
  revision,
}: {
  api: Api;
  selectedId: string | null;
  revision: number;
}) {
  const [offset, setOffset] = useState(0);
  const resource = useResource<Page<Run>>(
    api,
    selectedId ? null : `/api/stress-runs?limit=25&offset=${offset}`,
    revision,
  );
  const selected = useResource<Run>(
    api,
    selectedId ? `/api/stress-runs/${encodeURIComponent(selectedId)}` : null,
    revision,
  );
  if (selectedId)
    return selected.loading ? (
      <Loading label="Loading saved stress result…" />
    ) : selected.error ? (
      <ErrorPanel message={selected.error} retry={selected.retry} />
    ) : selected.data ? (
      <Result api={api} run={selected.data} />
    ) : null;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Saved, independent calculations</p>
          <h1>Runs</h1>
        </div>
        <div className="actions">
          <a className="button primary" href="#events">
            Browse events
          </a>
          <button
            className="button secondary"
            onClick={resource.retry}
            disabled={resource.loading}
          >
            Reload history
          </button>
        </div>
      </div>
      {resource.loading ? (
        <Loading label="Loading run history…" />
      ) : resource.error ? (
        <ErrorPanel message={resource.error} retry={resource.retry} />
      ) : resource.data?.items.length === 0 ? (
        <Empty title="No saved runs">
          Eligible events run after successful ingestion. You can also record a
          reasoned manual comparison from an event.
        </Empty>
      ) : (
        <div className="history-list">
          {resource.data?.items.map((run) => (
            <button
              key={run.id}
              className="history-row"
              onClick={() => {
                window.location.hash = `runs/${run.id}`;
              }}
            >
              <span>
                <strong>{run.scenario_snapshot.name}</strong>
                <small>
                  {modeLabel(run.mode)} · {utc(run.created_at)}
                </small>
              </span>
              <span
                className={moneyCents(run.total_pnl_usd) < 0n ? "loss" : "gain"}
              >
                {money(run.total_pnl_usd, true)}
              </span>
              <span className="small muted">View result ↗</span>
            </button>
          ))}
        </div>
      )}
      {resource.data && (
        <Pagination
          page={resource.data}
          offset={offset}
          setOffset={setOffset}
        />
      )}
    </>
  );
}

import type { Api } from "./api";
import type { Portfolio, Scenario } from "./types";
import { money, signedDecimal } from "./format";
import { Badge, Download } from "./ui";

export function PortfolioView({
  api,
  portfolio,
  scenarios,
}: {
  api: Api;
  portfolio: Portfolio;
  scenarios: Scenario[];
}) {
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">Original base · {portfolio.version}</p>
          <h1>Portfolio</h1>
        </div>
        <div className="actions">
          <a className="button primary" href="#events">
            Browse events
          </a>
          <Download
            api={api}
            path="/api/portfolio"
            name="eventlens-portfolio.json"
          >
            Export portfolio JSON
          </Download>
        </div>
      </div>
      <div className="portfolio-intro">
        <Badge tone="amber">Entirely synthetic</Badge>
        <p>
          {portfolio.positions.length} fictional positions. Fair value and
          principal/notional are different quantities.
        </p>
      </div>
      <dl className="totals two">
        <div>
          <dt>Base fair value · USD</dt>
          <dd>{money(portfolio.base_total_usd)}</dd>
        </div>
        <div>
          <dt>Principal / notional · USD</dt>
          <dd className="secondary-number">
            {money(portfolio.notional_total_usd)}
          </dd>
        </div>
      </dl>
      <div
        className="table-scroll"
        tabIndex={0}
        role="region"
        aria-label="Scrollable base portfolio"
      >
        <table aria-label="Base portfolio positions">
          <thead>
            <tr>
              <th scope="col">Position</th>
              <th scope="col">Issuer / type</th>
              <th scope="col">Sector</th>
              <th scope="col" className="numeric">
                Fair value · USD
              </th>
              <th scope="col" className="numeric">
                Notional · USD
              </th>
              <th scope="col" className="numeric">
                Rate duration · years
              </th>
              <th scope="col" className="numeric">
                Spread duration · years
              </th>
              <th scope="col" className="numeric">
                Swap USD / bp
              </th>
            </tr>
          </thead>
          <tbody>
            {portfolio.positions.map((position) => (
              <tr key={position.id}>
                <th scope="row">{position.id}</th>
                <td>
                  <strong>{position.issuer}</strong>
                  <small>
                    {position.asset_type} ·{" "}
                    {position.instrument_type.replaceAll("_", " ")}
                  </small>
                </td>
                <td>{position.sector}</td>
                <td className="numeric">
                  {money(position.base_market_value_usd)}
                </td>
                <td className="numeric">{money(position.notional_usd)}</td>
                <td className="numeric">
                  {position.asset_type === "swap"
                    ? "—"
                    : position.rate_duration}
                </td>
                <td className="numeric">
                  {position.asset_type === "swap"
                    ? "—"
                    : position.spread_duration}
                </td>
                <td className="numeric">
                  {position.asset_type === "swap"
                    ? signedDecimal(position.signed_rate_pnl_per_bp)
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <section className="section-block">
        <h2>Assumptions & scenario profiles</h2>
        <details>
          <summary>Portfolio assumptions</summary>
          <ul className="assumptions">
            {portfolio.assumptions.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </details>
        {scenarios.map((scenario) => (
          <details key={scenario.id}>
            <summary>
              {scenario.name}
              <span className="small muted">
                Reference impact 8 · rate{" "}
                {signedDecimal(scenario.rate_shock_bp)} bp · spread{" "}
                {signedDecimal(scenario.spread_shock_bp)} bp
              </span>
            </summary>
            <p>{scenario.assumption}</p>
            <p className="small muted">
              Applied shocks scale by impact / 8, capped at 1.25. Version:{" "}
              {scenario.version}. Every run starts from the original base.
            </p>
          </details>
        ))}
      </section>
    </>
  );
}

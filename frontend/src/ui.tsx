import { Component, type ReactNode } from "react";
import type { Api } from "./api";
import { useAction } from "./hooks";
import type { Health, Page } from "./types";
import { utc } from "./format";

export function ErrorPanel({
  message,
  retry,
  label = "Retry",
}: {
  message: string;
  retry?: () => void;
  label?: string;
}) {
  return (
    <div className="error-panel">
      <p role="alert">{message}</p>
      {retry && (
        <button className="button secondary" onClick={retry}>
          {label}
        </button>
      )}
    </div>
  );
}
export function Loading({ label = "Loading workspace…" }: { label?: string }) {
  return (
    <div className="loading" role="status">
      <span className="loading-line" aria-hidden="true" />
      {label}
    </div>
  );
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-mark" aria-hidden="true">
        ↗
      </span>
      <h2>{title}</h2>
      <p>{children}</p>
      {action && <div className="actions">{action}</div>}
    </div>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "green" | "amber";
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Download({
  api,
  path,
  name,
  children,
  primary = false,
}: {
  api: Api;
  path: string;
  name: string;
  children: ReactNode;
  primary?: boolean;
}) {
  const action = useAction();
  return (
    <div className="download">
      <button
        className={`button ${primary ? "primary" : "secondary"}`}
        disabled={action.busy}
        onClick={() => void action.run(() => api.download(path, name))}
      >
        {action.busy ? "Preparing export…" : children}
      </button>
      {action.error && (
        <p role="alert" className="inline-error">
          {action.error}
        </p>
      )}
    </div>
  );
}
export function Pagination<T>({
  page,
  offset,
  setOffset,
}: {
  page: Page<T>;
  offset: number;
  setOffset: (value: number) => void;
}) {
  if (page.total <= page.limit) return null;
  return (
    <nav className="pagination" aria-label="Results pages">
      <button
        className="button quiet"
        disabled={offset === 0}
        onClick={() => setOffset(Math.max(0, offset - page.limit))}
      >
        Previous
      </button>
      <span>
        {offset + 1}–{Math.min(offset + page.items.length, page.total)} of{" "}
        {page.total}
      </span>
      <button
        className="button quiet"
        disabled={offset + page.limit >= page.total}
        onClick={() => setOffset(offset + page.limit)}
      >
        Next
      </button>
    </nav>
  );
}
export function SourceStatus({ health }: { health: Health }) {
  const refreshed = health.sources.some((source) => source.last_success_at);
  return (
    <details className="source-status">
      <summary>
        <span
          className={`dot ${health.model_ready ? "ready" : ""}`}
          aria-hidden="true"
        />
        {health.model_ready
          ? "FinBERT local · ready"
          : "Local model unavailable"}
        <span className="status-separator">/</span>
        <span className="freshness-label">
          {health.sources.every((source) => !source.stale)
            ? "Live sources fresh"
            : refreshed
              ? "Live sources need attention"
              : "Live sources not refreshed"}
        </span>
        <span className="summary-link">Source status</span>
      </summary>
      <div className="source-body">
        <p>
          RSS and social are two channels from the same publisher, not
          independent confirmation.
        </p>
        {health.sources.map((source) => (
          <div className="source-row" key={source.source_id}>
            <strong>
              {source.source_id === "fed_rss"
                ? "Federal Reserve RSS"
                : "Federal Reserve social"}
            </strong>
            <span>
              {source.error_code
                ? source.error_code.replaceAll("_", " ")
                : source.stale
                  ? "Not fresh"
                  : "Fresh"}
            </span>
            <small>
              Last successful refresh: {utc(source.last_success_at)}
            </small>
            {source.next_allowed_at && (
              <small>Next refresh allowed: {utc(source.next_allowed_at)}</small>
            )}
          </div>
        ))}
        <p className="muted">
          Pinned model revision <code>{health.model_revision}</code>
        </p>
      </div>
    </details>
  );
}
export class RenderBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="content">
        <ErrorPanel
          message="The dashboard could not render this response. Reload the workspace; do not interpret an incomplete financial result."
          retry={() => window.location.reload()}
          label="Reload workspace"
        />
      </main>
    ) : (
      this.props.children
    );
  }
}

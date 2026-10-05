import { useCallback, useEffect, useRef, useState } from "react";
import type { Api } from "./api";
import { errorMessage } from "./api";

export function useResource<T>(api: Api, path: string | null, revision = 0) {
  const [state, setState] = useState<{
    path: string | null;
    data: T | null;
    loading: boolean;
    error: string | null;
  }>({ path: null, data: null, loading: true, error: null });
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    // Different IDs/filters must not briefly display the previous event's result.
    setState({ path, data: null, loading: !!path, error: null });
    if (path)
      api
        .get<T>(path, controller.signal)
        .then((data) => {
          if (!controller.signal.aborted)
            setState({ path, data, loading: false, error: null });
        })
        .catch((error) => {
          if (!controller.signal.aborted)
            setState({
              path,
              data: null,
              loading: false,
              error: errorMessage(error),
            });
        });
    return () => controller.abort();
  }, [api, path, revision, retry]);
  return {
    data: state.path === path ? state.data : null,
    loading: state.path !== path ? !!path : state.loading,
    error: state.path === path ? state.error : null,
    retry: useCallback(() => setRetry((value) => value + 1), []),
  };
}
export interface Route {
  view: "events" | "portfolio" | "runs";
  id: string | null;
}
export function parseRoute(hash: string): Route {
  const [view, id] = hash.replace(/^#\/?/, "").split("/");
  return {
    view: view === "portfolio" || view === "runs" ? view : "events",
    id: id && /^[A-Za-z0-9_-]{1,64}$/.test(id) ? id : null,
  };
}
export function useRoute() {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  useEffect(() => {
    const changed = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  return route;
}
export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const active = useRef(false);
  const run = async (action: () => Promise<void>) => {
    if (active.current) return;
    active.current = true;
    setBusy(true);
    setError(null);
    try {
      await action();
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      active.current = false;
      setBusy(false);
    }
  };
  return { busy, error, run, clear: () => setError(null) };
}

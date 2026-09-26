import { useCallback, useEffect, useState } from "react";
import { api, ApiError, type Providers, type Stats } from "../api/client";
import { Badge } from "../components/Badge";

function Bars({ title, counts }: { title: string; counts: Record<string, number> }) {
  const max = Math.max(1, ...Object.values(counts));
  return (
    <div className="bars">
      <h3>{title}</h3>
      {Object.entries(counts).map(([key, value]) => (
        <div className="bar-row" key={key}>
          <span className="bar-label">{key.replace("_", " ")}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${(value / max) * 100}%` }} />
          </span>
          <span className="bar-value" data-testid={`count-${key}`}>{value}</span>
        </div>
      ))}
    </div>
  );
}

export function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [cacheHit, setCacheHit] = useState<boolean | null>(null);
  const [providers, setProviders] = useState<Providers | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.getStats();
      setStats(result.stats);
      setCacheHit(result.cacheHit);
      setProviders(await api.getProviders());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="card">
      <div className="row">
        <h2>Statistics</h2>
        {cacheHit !== null && (
          <span title="From the X-Cache response header">
            <Badge kind={cacheHit ? "cache-hit" : "cache-miss"}>{cacheHit ? "Cache: HIT" : "Cache: MISS"}</Badge>
          </span>
        )}
        <button className="secondary" onClick={() => void load()}>Reload</button>
      </div>
      <p className="meta">
        Reload within 30 s to see a cache HIT. Submitting a complaint invalidates the cache, so the next load is a MISS.
      </p>
      {error && <p className="error" role="alert">{error}</p>}
      {stats && (
        <>
          <p className="total">
            <strong data-testid="total">{stats.total}</strong> complaints in total
          </p>
          <div className="grid">
            <Bars title="By category" counts={stats.by_category} />
            <Bars title="By priority" counts={stats.by_priority} />
            <Bars title="By status" counts={stats.by_status} />
          </div>
        </>
      )}
      {providers && (
        <div className="providers">
          <h3>AI triage</h3>
          <p>
            Active provider: <strong>{providers.active_provider}</strong> · fallback: {providers.fallback_provider} ·
            triage cache hit rate: <strong>{Math.round(providers.triage_cache.hit_rate * 100)}%</strong> (
            {providers.triage_cache.hits} hits / {providers.triage_cache.misses} misses)
          </p>
          <table>
            <thead>
              <tr><th>When</th><th>Provider</th><th>Latency</th><th>Fallback</th><th>Cache</th></tr>
            </thead>
            <tbody>
              {providers.recent.map((o) => (
                <tr key={`${o.complaint_id}-${o.at}`}>
                  <td className="meta">{new Date(o.at).toLocaleTimeString()}</td>
                  <td>{o.provider}</td>
                  <td>{o.latency_ms} ms</td>
                  <td>{o.fallback ? "yes" : "no"}</td>
                  <td>{o.cache_hit ? "hit" : "miss"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

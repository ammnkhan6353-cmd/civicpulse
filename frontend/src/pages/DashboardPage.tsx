import { useCallback, useEffect, useState } from "react";
import {
  api,
  ApiError,
  CATEGORIES,
  PRIORITIES,
  STATUSES,
  type Category,
  type Complaint,
  type ComplaintPage,
  type Priority,
  type Status,
} from "../api/client";
import { Badge } from "../components/Badge";

const PAGE_SIZE = 10;

/**
 * The operator can request ANY status. The frontend does not know the transition
 * rules - the backend does. Allowed next steps come from `allowed_transitions`
 * in the API response (rendered as quick buttons), and an invalid request made via
 * the "Set status" dropdown shows the server's 409 message verbatim.
 */
function StatusControls({ complaint, onChanged }: { complaint: Complaint; onChanged: () => void }) {
  const [target, setTarget] = useState<Status>(complaint.status);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function change(status: Status) {
    setBusy(true);
    setError(null);
    try {
      await api.updateStatus(complaint.id, status);
      onChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="status-controls">
      {(complaint.allowed_transitions ?? []).map((next) => (
        <button key={next} disabled={busy} onClick={() => change(next)} className="small">
          → {next.replace("_", " ")}
        </button>
      ))}
      <select
        aria-label={`Set status for ${complaint.id}`}
        value={target}
        onChange={(e) => setTarget(e.target.value as Status)}
      >
        {STATUSES.map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
      <button className="small secondary" disabled={busy} onClick={() => change(target)}>
        Set status
      </button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function DashboardPage() {
  const [category, setCategory] = useState<Category | "">("");
  const [priority, setPriority] = useState<Priority | "">("");
  const [status, setStatus] = useState<Status | "">("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ComplaintPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.listComplaints({ category, priority, status, page, pageSize: PAGE_SIZE }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server.");
    } finally {
      setLoading(false);
    }
  }, [category, priority, status, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <section className="card">
      <h2>Operations dashboard</h2>
      <div className="filters">
        <select aria-label="Category filter" value={category} onChange={(e) => { setPage(1); setCategory(e.target.value as Category | ""); }}>
          <option value="">All categories</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select aria-label="Priority filter" value={priority} onChange={(e) => { setPage(1); setPriority(e.target.value as Priority | ""); }}>
          <option value="">All priorities</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select aria-label="Status filter" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value as Status | ""); }}>
          <option value="">All statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <button className="secondary" onClick={() => void load()}>Refresh</button>
      </div>

      {loading && <p role="status">Loading complaints…</p>}
      {error && <p className="error" role="alert">{error}</p>}

      {data && !loading && (
        <>
          <p className="meta">{data.total} complaint(s)</p>
          <table>
            <thead>
              <tr>
                <th>Complaint</th>
                <th>Category</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Triaged by</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((c) => (
                <tr key={c.id}>
                  <td>
                    <div className="summary">{c.ai_summary ?? c.text}</div>
                    <div className="meta">{c.location} · {new Date(c.created_at).toLocaleString()}</div>
                  </td>
                  <td><Badge kind={c.category}>{c.category}</Badge></td>
                  <td><Badge kind={`priority-${c.priority}`}>{c.priority}</Badge></td>
                  <td><Badge kind={`status-${c.status}`}>{c.status}</Badge></td>
                  <td className="meta">{c.triaged_by}<br />{c.triage_latency_ms} ms</td>
                  <td><StatusControls complaint={c} onChanged={() => void load()} /></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pager">
            <button className="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Previous</button>
            <span>Page {page} of {totalPages}</span>
            <button className="secondary" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>Next →</button>
          </div>
        </>
      )}
    </section>
  );
}

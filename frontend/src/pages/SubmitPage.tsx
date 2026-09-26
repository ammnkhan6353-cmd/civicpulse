import { useState, type FormEvent } from "react";
import { api, ApiError, type Complaint } from "../api/client";
import { Badge } from "../components/Badge";

// These MIRROR the server's rules for instant feedback - they do not replace them.
// The server re-validates everything and its 400 field errors are shown too.
const TEXT_MIN = 10;
const TEXT_MAX = 2000;
const LOCATION_MIN = 3;
const LOCATION_MAX = 200;

export function validate(text: string, location: string): Record<string, string> {
  const errors: Record<string, string> = {};
  const t = text.trim();
  const l = location.trim();
  if (t.length < TEXT_MIN) errors.text = `Please describe the problem in at least ${TEXT_MIN} characters.`;
  if (t.length > TEXT_MAX) errors.text = `Please keep it under ${TEXT_MAX} characters.`;
  if (l.length < LOCATION_MIN) errors.location = `Location must be at least ${LOCATION_MIN} characters.`;
  if (l.length > LOCATION_MAX) errors.location = `Location must be under ${LOCATION_MAX} characters.`;
  return errors;
}

export function SubmitPage() {
  const [text, setText] = useState("");
  const [location, setLocation] = useState("");
  const [contact, setContact] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<Complaint | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setServerError(null);
    setResult(null);
    const clientErrors = validate(text, location);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length > 0) return;

    setSubmitting(true);
    try {
      const created = await api.createComplaint({
        text: text.trim(),
        location: location.trim(),
        reporter_contact: contact.trim() || null,
      });
      setResult(created);
      setText("");
      setLocation("");
      setContact("");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.fieldErrors.length > 0) {
          setErrors(Object.fromEntries(err.fieldErrors.map((e) => [e.field, e.message])));
        }
        const retry = err.retryAfterSeconds ? ` (try again in ${err.retryAfterSeconds} s)` : "";
        setServerError(`${err.message}${retry}`);
      } else {
        setServerError("Could not reach the server. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="card">
      <h2>Report a problem</h2>
      <form onSubmit={onSubmit} noValidate>
        <label htmlFor="text">What is the problem?</label>
        <textarea
          id="text"
          rows={5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. Burst water main flooding Street 12 since fajr, water entering ground floors"
          aria-invalid={Boolean(errors.text)}
        />
        <div className="hint">{text.trim().length} / {TEXT_MAX}</div>
        {errors.text && <p className="field-error">{errors.text}</p>}

        <label htmlFor="location">Where?</label>
        <input id="location" value={location} onChange={(e) => setLocation(e.target.value)} aria-invalid={Boolean(errors.location)} />
        {errors.location && <p className="field-error">{errors.location}</p>}

        <label htmlFor="contact">Phone or email (optional)</label>
        <input id="contact" value={contact} onChange={(e) => setContact(e.target.value)} />
        {errors.reporter_contact && <p className="field-error">{errors.reporter_contact}</p>}

        <button type="submit" disabled={submitting}>
          {submitting ? "Submitting…" : "Submit complaint"}
        </button>
      </form>

      {submitting && (
        <p className="loading" role="status">
          <span className="spinner" aria-hidden="true" /> Triaging with AI… this can take a few seconds.
        </p>
      )}
      {serverError && (
        <p className="error" role="alert">
          {serverError}
        </p>
      )}

      {result && (
        <div className="result" data-testid="triage-result">
          <h3>Thank you - your complaint was received.</h3>
          <p>
            <Badge kind={result.category}>{result.category}</Badge>{" "}
            <Badge kind={`priority-${result.priority}`}>{`${result.priority} priority`}</Badge>
          </p>
          <p className="summary">{result.ai_summary}</p>
          <p className="meta">
            Triaged by <strong>{result.triaged_by}</strong> in {result.triage_latency_ms} ms
            {result.triaged_by === "rules:fallback" && " (AI was unavailable - keyword rules were used)"}
          </p>
        </div>
      )}
    </section>
  );
}

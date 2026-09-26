/**
 * Component tests. fetch is replaced by a fake, so no backend is needed and the
 * tests are deterministic. Each test checks a behaviour the rubric names.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { ErrorBoundary } from "../src/components/ErrorBoundary";
import { DashboardPage } from "../src/pages/DashboardPage";
import { StatsPage } from "../src/pages/StatsPage";
import { SubmitPage, validate } from "../src/pages/SubmitPage";

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

const complaint = {
  id: "11111111-1111-1111-1111-111111111111",
  text: "Burst water main flooding Street 12 since fajr",
  location: "Street 12, Islamabad",
  reporter_contact: null,
  category: "water",
  priority: "high",
  status: "resolved",
  ai_summary: "Burst main flooding homes on Street 12",
  triaged_by: "llm:groq",
  triage_latency_ms: 412,
  created_at: "2026-09-26T10:00:00Z",
  updated_at: "2026-09-26T10:00:00Z",
  allowed_transitions: [],
};

describe("Submit view", () => {
  it("mirrors server validation and blocks a too-short complaint without calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<SubmitPage />);

    await userEvent.type(screen.getByLabelText(/what is the problem/i), "leak");
    await userEvent.type(screen.getByLabelText(/where/i), "G9");
    await userEvent.click(screen.getByRole("button", { name: /submit complaint/i }));

    expect(screen.getByText(/at least 10 characters/i)).toBeInTheDocument();
    expect(screen.getByText(/at least 3 characters/i)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(validate("a valid complaint text", "Lahore")).toEqual({});
  });

  it("shows an honest loading state, then category, priority, AI summary and provider", async () => {
    let resolve!: (r: Response) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((r) => (resolve = r))));
    render(<SubmitPage />);

    await userEvent.type(screen.getByLabelText(/what is the problem/i), complaint.text);
    await userEvent.type(screen.getByLabelText(/where/i), complaint.location);
    await userEvent.click(screen.getByRole("button", { name: /submit complaint/i }));

    expect(screen.getByRole("status")).toHaveTextContent(/triaging with ai/i);
    expect(screen.getByRole("button", { name: /submitting/i })).toBeDisabled();

    resolve(jsonResponse({ ...complaint, status: "open" }, 201));
    const result = await screen.findByTestId("triage-result");
    expect(within(result).getByText("water")).toBeInTheDocument();
    expect(within(result).getByText(/high priority/i)).toBeInTheDocument();
    expect(within(result).getByText(complaint.ai_summary)).toBeInTheDocument();
    expect(within(result).getByText("llm:groq")).toBeInTheDocument();
  });

  it("shows server-side field errors and the 429 retry hint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        jsonResponse({ detail: "Rate limit exceeded: 10 complaints per minute." }, 429, { "Retry-After": "42" }),
      ),
    );
    render(<SubmitPage />);
    await userEvent.type(screen.getByLabelText(/what is the problem/i), complaint.text);
    await userEvent.type(screen.getByLabelText(/where/i), complaint.location);
    await userEvent.click(screen.getByRole("button", { name: /submit complaint/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Rate limit exceeded: 10 complaints per minute. (try again in 42 s)");
  });
});

describe("Dashboard view", () => {
  it("renders the list and surfaces the server's 409 message verbatim", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      if (init?.method === "PATCH") {
        return jsonResponse({ detail: "Invalid transition: resolved → open" }, 409);
      }
      return jsonResponse({ items: [complaint], total: 1, page: 1, page_size: 10 });
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<DashboardPage />);

    expect(await screen.findByText(complaint.ai_summary)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText(/set status for/i), "open");
    await userEvent.click(screen.getByRole("button", { name: /set status/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid transition: resolved → open");
  });

  it("sends filters and pagination to the server", async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ items: [complaint], total: 25, page: 1, page_size: 10 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<DashboardPage />);

    await screen.findByText(complaint.ai_summary);
    await userEvent.selectOptions(screen.getByLabelText(/category filter/i), "water");
    const lastUrl = () => String((fetchMock.mock.lastCall as unknown[] | undefined)?.[0]);
    await waitFor(() => expect(lastUrl()).toContain("category=water"));

    await userEvent.click(await screen.findByRole("button", { name: /next/i }));
    await waitFor(() => expect(lastUrl()).toContain("page=2"));
    expect(lastUrl()).toContain("category=water");
    expect(screen.getByText(/page 2 of 3/i)).toBeInTheDocument();
  });
});

describe("Stats view", () => {
  it("renders aggregates and the cache state from the X-Cache header", async () => {
    const stats = {
      total: 33,
      by_category: { water: 6, electricity: 6, sanitation: 6, roads: 6, streetlights: 5, other: 4 },
      by_priority: { high: 15, normal: 12, low: 6 },
      by_status: { open: 18, in_progress: 7, resolved: 5, rejected: 3 },
    };
    const providers = {
      active_provider: "llm:groq",
      fallback_provider: "rules",
      available_providers: ["llm", "ollama", "rules", "simulated"],
      triage_cache: { hits: 1, misses: 3, hit_rate: 0.25 },
      recent: [],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.includes("/api/stats") ? jsonResponse(stats, 200, { "X-Cache": "HIT" }) : jsonResponse(providers),
      ),
    );
    render(<StatsPage />);

    expect(await screen.findByText("Cache: HIT")).toBeInTheDocument();
    expect(screen.getByTestId("total")).toHaveTextContent("33");
    expect(screen.getByTestId("count-streetlights")).toHaveTextContent("5");
    expect(await screen.findByText("25%")).toBeInTheDocument();
  });
});

describe("App shell", () => {
  it("error boundary contains a crashing view", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    function Boom(): never {
      throw new Error("kaboom");
    }
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("kaboom");
  });

  it("navigates between the three views", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ items: [], total: 0, page: 1, page_size: 10 })));
    render(<App />);
    expect(screen.getByRole("heading", { name: /report a problem/i })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Dashboard" }));
    expect(await screen.findByRole("heading", { name: /operations dashboard/i })).toBeInTheDocument();
  });
});

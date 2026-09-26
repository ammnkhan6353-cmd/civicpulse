import { useState } from "react";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { DashboardPage } from "./pages/DashboardPage";
import { StatsPage } from "./pages/StatsPage";
import { SubmitPage } from "./pages/SubmitPage";

const VIEWS = {
  submit: { label: "Submit", Page: SubmitPage },
  dashboard: { label: "Dashboard", Page: DashboardPage },
  stats: { label: "Stats", Page: StatsPage },
} as const;
type View = keyof typeof VIEWS;

function initialView(): View {
  const hash = window.location.hash.replace("#", "");
  return hash in VIEWS ? (hash as View) : "submit";
}

export default function App() {
  const [view, setView] = useState<View>(initialView);
  const { Page } = VIEWS[view];

  function go(next: View) {
    window.location.hash = next;
    setView(next);
  }

  return (
    <div className="app">
      <header>
        <h1>CivicPulse</h1>
        <nav>
          {(Object.keys(VIEWS) as View[]).map((key) => (
            <button key={key} className={key === view ? "tab active" : "tab"} onClick={() => go(key)}>
              {VIEWS[key].label}
            </button>
          ))}
        </nav>
      </header>
      <main>
        {/* key={view}: switching views also resets a crashed boundary */}
        <ErrorBoundary key={view}>
          <Page />
        </ErrorBoundary>
      </main>
    </div>
  );
}

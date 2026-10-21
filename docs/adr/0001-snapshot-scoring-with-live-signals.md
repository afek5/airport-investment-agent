# Scores run on a dated Snapshot; live public APIs only add Live Signals

The brief asks the agent to "use public APIs" and to include deterministic scoring. Only about half the KPIs we need have a live public API: route distances (T-100), delays (On-Time), forecasts (TAF) and enplanements exist only as bulk downloads, and some of those take minutes to download. We therefore build a dated Snapshot by script from public endpoints and run all scoring on it, so the same question always gives the same score. Three keyless APIs (BTS airport traffic, DOT Airfare Report, FAA NAS Status) are agent tools that run at question time. They add freshness and evidence to explanations but never change a score.

## Considered Options

- Fully live: rejected, because most metrics have no API, rate limits would put the demo at risk, and results would not be reproducible.
- Snapshot only: rejected, because it gives up the brief's explicit public-API requirement and live freshness.

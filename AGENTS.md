# Airport Investment Intelligence Agent

A take-home build: a chat agent that ranks US airports for terminal-modernisation investment using deterministic scoring over public aviation data.

- **The assignment itself:** `docs/brief/TASK.md` (a transcription of the original PDF next to it). Every requirement there must stay met.
- **Building or changing anything:** start with `docs/HANDOFF.md`, which covers phases, package ownership, contracts and completion criteria. `docs/SPEC.md` is the source of truth for behaviour.
- **Domain words** (Investment Opportunity Score, Capacity Pressure, Spill, Long-haul Flight, Snapshot, Live Signal…) mean exactly what `GLOSSARY.md` says. Use them in code names, prompts and docs.
- **Why it's built this way:** `docs/adr/`. Read the relevant ADR before reversing a decision. Write a new ADR when you make a hard-to-reverse trade-off.
- **Data source facts, endpoints and gotchas:** `docs/research/data-sources.md`.
- **UI work:** use the `ui-taste` skill. The visual target is `docs/UI-STYLE.md`.
- **GitHub:** account `afek5` only, via `GH_TOKEN=$(gh auth token -u afek5)`.
- **Scores:** every score and number the agent shows comes from a deterministic tool result. The LLM selects tools and explains, and it never computes.

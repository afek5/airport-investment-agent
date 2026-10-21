# Glossary

The shared language of the Airport Investment Intelligence Agent. Terms only — no implementation.

## Investment framing

**Investment Thesis**
A terminal/airside renovation is most profitable where passenger and flight demand is growing, the existing infrastructure is already strained by that demand, and the market is large enough for added capacity to be monetised.
_Avoid_: "best airport", "top airport" (without saying by which thesis)

**Investment Opportunity Score**
A single deterministic number per airport that expresses how strongly that airport fits the Investment Thesis. Computed from the three Pillars; never produced by the language model. It is a **screening** signal: it identifies airports worth investigating, and it does not establish that a renovation would be profitable. It has no knowledge of project cost, terminal utilisation, commercial revenue or expansion feasibility.
_Avoid_: "AI score", "rating", "rank" (a Ranking is an ordering of scores, not the score itself), "profitability score"

**Coverage**
How many of the score's input metrics are actually measured for an airport, e.g. "6 of 7".

**Provisional Score**
An Investment Opportunity Score computed with incomplete Coverage. Missing metrics are assumed to sit at the median of all airports, an assumption that pulls the score toward the middle and can raise or lower it. It is always shown with its Coverage and the metrics that were assumed, and labelled provisional. An airport missing a whole Pillar is "not ranked: insufficient data".

**Pillar**
One of the three independent dimensions of the Investment Thesis: Demand Momentum, Capacity Pressure, Market Scale. Each Pillar is itself a deterministic score.

**Demand Momentum**
How fast passenger and flight demand at an airport is growing, observed and forecast.
_Avoid_: "growth" alone (ambiguous between passengers, flights, seats)

**Capacity Pressure**
How close an airport's current infrastructure is to being unable to serve the demand placed on it — e.g. full aircraft, congestion, delays.
_Avoid_: "congestion" as a synonym (congestion is one symptom of Capacity Pressure, not the whole of it)

**Market Scale**
The size of the demand base an airport serves, which bounds how much value added capacity can capture.

**Ranking**
An ordering of airports by Investment Opportunity Score (or by a single Pillar), within an explicitly stated scope such as a region or hub size.

**Pillar Weights**
The relative importance of the three Pillars in the Investment Opportunity Score. They have stated defaults, and an analyst may override them for a single conversation.

**Percentile Score**
A metric expressed as the share of Primary Airports that the airport outranks (0–100). All Pillar inputs are Percentile Scores, so airports of very different size are comparable.

## Demand and capacity signals

**Load Factor**
Passengers carried divided by seats offered, over a stated period. A high Load Factor means aircraft are full.

**Spill Scenario**
A sensitivity scenario: how many passengers *might* have been turned away by full flights under stated assumptions (a load-factor threshold and spill rates). It is never presented as observed evidence or as the answer itself. Full aircraft alone do not prove passengers were turned away.
_Avoid_: "spill" stated as a fact, "lost passengers"

**Constraint Evidence**
Observable signs that infrastructure, not airline choice, limits an airport's throughput, such as departure delays, long taxi-out times, and a gap between good-weather and bad-weather runway capacity. It answers the "why" of Unmet Demand.

**Forecast Gap**
How much demand the official FAA forecast expects an airport to add over a stated horizon, relative to today.

**Unmet Demand**
Demand an airport appears unable to serve. It is argued from observed Constraint Evidence and the Forecast Gap. A Spill Scenario may accompany it, kept clearly separate. Every Unmet Demand answer also states what the data cannot determine.
_Avoid_: "lost passengers", "demand gap" (unqualified)

**Congestion**
How strained an airport's day-to-day operations are, seen in delays, taxi-out times, cancellations and live disruptions. Congestion is a symptom inside Capacity Pressure.

**Long-haul Flight**
A flight segment of 3,000 statute miles or more. Unless the scope says otherwise, it means scheduled passenger flights. Cargo-inclusive and passenger-weighted shares are separate, explicitly labelled variants.
_Avoid_: "international flight" (many international flights are short; some domestic flights, e.g. to Hawaii, are long-haul)

## Evidence and trust

**Snapshot**
The fixed, dated body of public aviation data that all scoring runs on. The same question against the same Snapshot always gives the same scores.

**Live Signal**
A figure fetched from a public API at question time, such as current delays or the latest monthly traffic. It informs explanations but never changes a score.

**As-of Date**
The latest period a figure describes, such as "T-100 through Jul 2026". Every figure an answer cites carries one.

**Data Confidence**
A stated level (High / Medium / Low) on an answer, derived from how complete and how recent the underlying data is, never from the language model's own judgement. It describes the evidence, not the likelihood that an investment succeeds.
_Avoid_: "confidence" unqualified

**Assumption**
An interpretation the agent made to answer a question, stated openly in the answer, such as "LA = LAX" or "long-haul = 3,000 mi or more".

## Airports

**Primary Airport**
A US commercial-service airport with more than 10,000 passenger boardings per year, as classified by the FAA. The universe of airports the agent scores.
_Avoid_: "major airport", "commercial airport" (both are fuzzier)

**Hub Size**
The FAA classification of a Primary Airport by its share of national boardings: large hub, medium hub, small hub, nonhub. Used as a filter, not as a score input.
_Avoid_: "airline hub" (an airline's connecting hub is a different concept)

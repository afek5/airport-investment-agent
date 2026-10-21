# Investment Opportunity Score = weighted geometric mean of percentile Pillars, median imputation (disclosed) for gaps

The Investment Thesis is a conjunction: growing demand AND strained infrastructure AND enough market scale. Every input metric becomes a percentile across all Primary Airports, so a 2M-passenger airport can be compared with a 40M one and outliers such as ANC cargo or ATL volume don't distort the scale. The final score is a weighted *geometric* mean of the Pillars (default weights Momentum 35 / Pressure 40 / Scale 25, with a floor of 1), so an airport that is weak on any one Pillar is penalised instead of being carried by the other two.

Missing metrics (common for small airports that lack On-Time coverage) are imputed at the median (50th percentile) and the score is marked Provisional with its Coverage and the imputed metrics named. This is not neutral: it pulls the Pillar toward the middle and can raise or lower an airport relative to its unknown true value (Pressure 80/20/20 → 44, but 80/missing/missing → 62). An airport missing a whole Pillar is not ranked. We chose median imputation over renormalising across available metrics, because renormalising silently substitutes the airport's own other strengths for the gap. Median imputation has a known direction (toward the middle) and is always disclosed.

The score is a screening signal, not a profitability estimate. The language model never computes or adjusts scores; it can only re-run scoring with different weights through a tool.

## Considered Options

- Weighted arithmetic mean: easier to explain, but a huge, stagnant airport ranks high, which contradicts the thesis.
- Z-scores: sensitive to the extreme outliers present in aviation data.
- Renormalising over available metrics: rejected, because it substitutes an airport's other strengths for the gap invisibly.

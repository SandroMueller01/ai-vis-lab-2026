# Open questions for Phase II (why does the model behave like this?)

## 1. Why do the last 1–2 hours of each 32-hour block (counted back from the forecast start) change the forecast ~2x more than an average hour? (Exp 10)
- Bright cells in the occlusion heatmap repeat every 32 h (diagonal, shifting 8 h per day), in normal days and before
  fronts. Hiding the newest 1-2 h of each 32-h block (counted back from the forecast start) changes the forecast ~2x the
  average (2.0x for random forecasts without the last day, above 1x in 97 % of cases); the oldest hour of a block
  ~0.6x.
- The 32-h blocks explain WHERE (input split into 32-hour blocks). WHY they are brighter is open: do those hours weigh
  more, or does the model handle a gap at a block edge badly? (We measured the effect of hiding, not weight.)

## 2. Why do extra inputs (pressure, a warning flag, neighbours) not help the model see a front coming? (Exp 3, 4, 5)
- **Pressure:** it falls ~7 hPa over the day before the drop (Exp 5, average front in all variables). Given as levels
  (Exp 3 setup D) and as 3-hour changes (Exp 4 setup G): no improvement in the drop captured. Hypotheses: the model
  must learn the pressure -> temperature link from the 10-week history alone (few fronts in it); pressure also falls
  without a front. Untested.
- **A perfect warning flag:** a flag marking exactly when the front comes (12 h ahead, as past and as future
  covariate, Exp 3 B and F) did not help either. So the problem is not signal quality: the model does not learn
  "signal -> drop" from the context. How does TiRex-2 use covariates at all, and how many examples in the context
  would it need?
- **Neighbours and other combinations (Exp 4):** none of 6 input combinations (levels, 3 h changes, upstream
  points, unusual part) beat temperature only (all ~21 % of the drop captured). Is it the nature of temperature, are
  the features not rich enough, or can the model not learn this kind of link?

## 3. Once the front is in the history: why does the model adopt the new level fast, but never extend the fall? (Exp 3 section 6, Exp 5)
- **Adopts fast:** forecasts started after the drop follow the new cold level and keep it (+6 to +48 h), instead of
  returning to the usual daily pattern of the weeks before. What in the model makes it adopt the new level so quickly?
- **No momentum:** once it has seen part of the drop it adopts the new level, but never extends the ongoing fall.
  In the data falls do continue for hours, so a trend-following forecaster would extend them.

## 4. Why does the band shrink again for the largest inserted drops? (Exp 6)
- Inserting cold drops into the history widens the band (unchanged: 6.1 °C). With 8-12 drops it is widest at
  6-9 °C drops and shrinks again towards 15 °C drops; with 16 drops it keeps growing (up to 9.7 °C).
- Checked on 2026-11-11 with faded drop ends (269 cases): the band falling *below* the unchanged one, seen in Exp 6,
  came from the drops ending abruptly. The shrinking towards the largest drops remains.

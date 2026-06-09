# Skill: run-geographical-detector

---

## [DEV ONLY]
> For Claude Code development use only. Skipped at runtime.

Implementation: backend/tools/geodetector.py
Tool name: run_geographical_detector

---

## [PRE_EXECUTION]

**Uploaded files**: Extract paths from uploaded files first. Only ask for genuinely missing inputs.

**Required parameters**:
- input_csv: path to the input CSV (or xlsx) containing the dependent variable and the factor columns
- y_variable: column name of the continuous dependent variable Y (e.g. incidence, yield, price)
- x_variables: comma-separated list of CATEGORICAL factor column names (X)

**Optional parameters**:
- alpha: significance level, default 0.05

**Key notes**:
- The Geographical Detector (Geodetector, Wang Jinfeng) measures spatial stratified heterogeneity and detects driving factors.
- X factors MUST be categorical / stratified (e.g. soil type, climate zone, elevation class). If the user has continuous factors, tell them to discretize into zones/classes first (the tool does not auto-discretize).
- Y must be continuous.
- Trigger words: geodetector, geographical detector, spatial stratified heterogeneity, q-statistic, q value, driving factors, factor detector, interaction detector, risk detector, ecological detector.

---

## [POST_EXECUTION]

### Output files

| File | Type | Description |
|------|------|-------------|
| geodetector_factor.csv | CSV | Per-factor q-statistic (0..1 explanatory power), p-value, number of strata, significance — sorted strongest first |
| geodetector_interaction.csv | CSV | For each factor pair: combined q vs individual q, and interaction type (Enhance_bi-, Enhance_nonlinear, Weaken_uni-, Weaken_nonlinear, Independent) |
| geodetector_risk.csv | CSV | Mean of Y within each stratum of each factor (long format) |
| geodetector_ecological.csv | CSV | Whether two factors differ significantly in their influence on Y |

### Suggested next steps
- Rank factors by q in geodetector_factor.csv — the highest q is the strongest driver of Y.
- Check geodetector_interaction.csv: pairs that "Enhance_bi-" or "Enhance_nonlinear" indicate factors that jointly explain more than alone.
- Use geodetector_risk.csv to see which strata (zones) have the highest/lowest mean Y.

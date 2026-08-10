# ML-OOS-02 — outcome-blind policy-confirmation methodology vet (2026-08-10)

**Status: VETTED DIRECTION / OPEN NUMERICAL DECISIONS**

This study evaluates the statistical design that a future policy-confirmation
contract would need. It does not select thresholds, inspect the current live
cohort's outcomes, register `POLICY_CONFIRMATION_CONTRACTS`, or make Task 06
promotion-eligible.

Executable synthetic calibration follow-up:
[`ml_oos_02_synthetic_calibration_2026-08-10.md`](./ml_oos_02_synthetic_calibration_2026-08-10.md).

## Evidence boundary

- Executable truth: `accum_path_v1`, `time_purged_folds`, the ML-OOS-02 geometry
  simulator, current verdict law, and the empty confirmation-contract registry.
- Data unit for inference: ordered trading session. Ticker/session rows are
  cross-sectional observations within a session, not independent time samples.
- Outcome boundary: no live IC, fold metric, challenger ranking, or outcome
  distribution was used to choose this direction.
- Production boundary: `ai-saham` remains the production/data owner;
  `ml-saham` remains read-only and non-authoritative.

## Objective findings

### 1. Structural fold validity is not statistical adequacy

The shipped splitter can first form two post-embargo folds with 44 eligible
sessions, but the shallowest training fold then contains only two sessions.
It can first form all three scheduled folds with 84 sessions, but the
shallowest training fold contains only one session. Those calendars are valid
geometry tests, not policy-grade sample floors.

Selected outcome-free geometry facts:

| Total eligible sessions | Untouched tail | Folds | Shallowest train | Shallowest test |
|---:|---:|---:|---:|---:|
| 44 | 0 | 2 | 2 | 11 |
| 84 | 0 | 3 | 1 | 21 |
| 100 | 20 | 2 | 20 | 20 |
| 120 | 20 | 3 | 5 | 25 |
| 180 | 20 | 3 | 20 | 40 |
| 252 | 20 | 3 | 38 | 58 |

None of these rows is a recommendation. They expose the interaction among the
20-session embargo, outer folds, a final tail, and train/test depth.

### 2. Session-native inference is required

Pooled ticker/session rank IC treats a large cross-section as if it created
independent time evidence. The primary inferential series should instead be
one predeclared metric difference per session, with unweighted sessions as the
default candidate. Pooled rank IC, row counts, median session IC, and the
fraction of positive sessions may remain descriptive secondary output.

The future contract must also set a minimum valid-name count per session and
define what happens when score or target ranks are constant. Missing or
undefined sessions must not be silently removed from the denominator.

### 3. Fixed and learned challengers need different adequacy gates

A fixed challenger has no training fit, but still needs enough independent
sessions for stable OOS comparison, dependence-aware uncertainty, and regime
coverage. A learned challenger additionally needs enough training history for
the complete fitting and selection algorithm.

For learned challengers, every scaler, imputer, feature choice, hyperparameter,
threshold, calibration step, and model selection step must be repeated inside
the training side of an inner ordered/purged loop. Reusing the outer OOS folds
for tuning and evaluation would make the reported error optimistic. Linear and
tree challengers must not share a floor merely because both implement the same
interface.

### 4. The 20-session embargo should not be weakened in this study

`accum_path_v1` reports H3/H10/H20 and currently uses a 20-session embargo. It
therefore protects the longest reported forward path, not only primary H10.
Reducing it to make folds appear earlier would change the protocol and could
reintroduce overlapping-label leakage. No outcome-blind evidence found in this
vet supports reducing it.

### 5. IID confidence intervals are not suitable

Session metric differences can be serially dependent and heteroskedastic.
Newey-West HAC and dependent bootstraps are established candidate families,
but both require tuning choices and enough time observations. A stationary
bootstrap also requires a block-length rule; choosing the block length after
looking for a favorable interval would itself be researcher freedom.

The short current geometry is inadequate for claiming that either asymptotic
HAC or a dependent bootstrap has calibrated coverage. Coverage must be checked
prospectively under plausible dependence before either becomes product law.
A stationary bootstrap assumes a weakly stationary dependence structure; it
must not be used to turn an evident regime break into a precise-looking
interval. A failed stationarity/regime-coverage gate remains inconclusive.

### 6. Search and confirmation must be separate products

Selecting the best challenger, threshold, feature set, or uncertainty setting
on an OOS history and then using that history as confirmation is data snooping.
Recording the search is necessary but not sufficient.

The cleanest confirmation path is one frozen primary challenger per contract.
If a named family must be assessed together, the future contract must choose a
single multiplicity procedure appropriate to its claim. Hansen's SPA targets
whether the best candidate has superior predictive ability versus a benchmark;
Romano-Wolf stepdown targets simultaneous candidate-level claims. They are not
interchangeable defaults.

### 7. A final holdout is consumable, not reusable

The final holdout should be one contiguous future tail opened only after the
challenger, fit procedure, metric, uncertainty method, correction, and success
law are frozen. Once inspected, it becomes historical evidence; later redesign
requires a newly accumulated untouched tail. A fixed percentage or convenient
5/10/20-session tail is not justified without a prospective precision and
regime-coverage target.

## Candidate methodology requiring further vetting

This is the recommended direction to evaluate, **not an adopted contract**:

1. **Primary estimand:** the unweighted mean of a predeclared session-level
   challenger-minus-production metric; use pooled row IC only as descriptive
   output.
2. **Outer evaluation:** retain chronological expanding folds and the
   20-session embargo. Vet requiring all three scheduled outer folds for
   policy-grade evidence; keep the shipped two-fold rule as an exploratory
   minimum until that decision is accepted.
3. **Fixed challengers:** freeze the challenger before outer evaluation. Select
   train/test session floors through prospective precision/coverage simulation,
   not parameter-count heuristics.
4. **Learned challengers:** use nested ordered/purged tuning wholly inside each
   outer training block. Version the complete fitting algorithm and select a
   separate floor for each capacity class. Treat tree models as a distinct
   contract from regularized linear reweights.
5. **Uncertainty:** evaluate stationary block bootstrap with an automatic,
   predeclared block-length rule and sensitivity band as the primary candidate;
   evaluate HAC as a secondary robustness check. Adopt neither until simulation
   shows acceptable coverage and false-positive behavior at the chosen floor.
6. **Multiplicity:** prefer one preregistered primary challenger. If the product
   needs best-of-family selection, vet SPA; if it needs simultaneous claims for
   several challengers, vet Romano-Wolf stepdown. Exploratory searches remain
   permanently ineligible for confirmation.
7. **Final holdout:** reserve one contiguous tail for a single confirmatory use.
   Derive its length from a written minimum-effect/precision target and regime
   requirement, then add that length on top of the fold-region requirement.
8. **Decision rule:** define the smallest policy-relevant effect, acceptable
   uncertainty width, false-positive tolerance, fold agreement, and tail-risk
   non-inferiority before generating any confirmation result.

## How numerical floors should be selected

Do not infer floors from the current cohort's observed effect. Before contract
registration:

1. Define the policy question and smallest effect that would justify human
   review, separately for score, gate, and learned-model decisions.
2. Define acceptable false-positive probability, interval coverage, and
   precision for the session-level estimand.
3. Build outcome-independent null and alternative simulations with plausible
   cross-sectional width, serial dependence, heteroskedasticity, missingness,
   and regime shifts. Parameters may come from synthetic conservative bounds or
   explicitly exploratory historical material that can never become the
   confirmation cohort.
4. Reproduce the exact splitter, embargo, fitting pipeline, search breadth,
   uncertainty method, and final-holdout rule in simulation.
5. Select the smallest calendar whose operating characteristics meet the
   predeclared targets across adverse scenarios—not merely on average.
6. Freeze those values in a versioned contract and mutation-test every material
   identity field before collecting/opening confirmatory outcomes.

## Decisions still open

- Exact session-level primary metric for each decision type; IC must not become
  a universal gate metric.
- Minimum valid names per session and undefined-session denominator law.
- Minimum train/test sessions for fixed, linear-learned, and tree-learned
  challengers.
- Whether policy-grade evidence requires all three scheduled outer folds.
- Bootstrap family, automatic block-length rule, resample count, seed, interval
  construction, and sensitivity acceptance.
- Whether HAC is diagnostic-only or part of a joint acceptance rule.
- One-primary-challenger discipline versus SPA or Romano-Wolf for named search
  families.
- Smallest relevant effect, uncertainty width, error tolerance, tail-risk gate,
  and regime-coverage definition.
- Final untouched-tail length and the governance rule after it is opened.

Until these are accepted, `POLICY_CONFIRMATION_CONTRACTS` must remain empty and
Task 06 must remain blocked even after raw fold geometry becomes available.

## Primary references

- Newey and West, “A Simple, Positive Semi-Definite, Heteroskedasticity and
  Autocorrelation Consistent Covariance Matrix”
  ([NBER working paper and Econometrica reference](https://www.nber.org/papers/t0055)).
- Politis and Romano, “The Stationary Bootstrap”
  ([JASA](https://doi.org/10.1080/01621459.1994.10476870)).
- Politis and White, “Automatic Block-Length Selection for the Dependent
  Bootstrap”
  ([Econometric Reviews](https://doi.org/10.1081/ETC-120028836)).
- White, “A Reality Check for Data Snooping”
  ([Econometrica](https://doi.org/10.1111/1468-0262.00152)).
- Hansen, “A Test for Superior Predictive Ability”
  ([working-paper record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=264569)).
- Romano and Wolf, “Stepwise Multiple Testing as Formalized Data Snooping”
  ([Econometrica](https://doi.org/10.1111/j.1468-0262.2005.00615.x)).
- Varma and Simon, “Bias in error estimation when using cross-validation for
  model selection”
  ([BMC Bioinformatics](https://doi.org/10.1186/1471-2105-7-91)).
- Bergmeir, Hyndman, and Koo, “A Note on the Validity of Cross-Validation for
  Evaluating Autoregressive Time Series Prediction”
  ([Computational Statistics & Data Analysis](https://doi.org/10.1016/j.csda.2017.11.003)).
- Bailey, Borwein, López de Prado, and Zhu, “The Effects of Backtest
  Overfitting on Out-of-Sample Performance”
  ([SSRN record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659)).

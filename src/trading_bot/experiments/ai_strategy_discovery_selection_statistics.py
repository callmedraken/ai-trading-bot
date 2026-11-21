"""Deterministic Sharpe, PSR, and campaign selection-bias statistics.

The DSR uses Bailey and López de Prado (2014), Eq. (2), with daily Sharpe
ratios, raw Pearson kurtosis, and the campaign's frozen zero-centered
22-trial benchmark.  Decimal arithmetic uses a private 60-digit context.  The
standard-normal CDF uses an erf power series through |z| <= 8 and a Mills-ratio
continued fraction above that range; inverse upper-tail quantiles use Decimal
bisection over that same CDF.  No platform math library or ambient Decimal
context affects the results.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from uuid import UUID

from trading_bot.experiments.filtered_trend_campaign import (
    decimal_text,
    semantic_identity,
)

G1_SEARCH_TRIAL_COUNT = 22
CAMPAIGN_EVALUATED_TRIAL_COUNT = 28
ANNUALIZATION_DAYS = 252
_ARITHMETIC_CONTEXT = Context(
    prec=60,
    rounding=ROUND_HALF_EVEN,
    Emin=-999_999_999,
    Emax=999_999_999,
)
with localcontext(_ARITHMETIC_CONTEXT):
    DSR_PASS_THRESHOLD = Decimal("0.95")
    CAMPAIGN_FAMILYWISE_ALPHA = Decimal("0.05") / Decimal(
        CAMPAIGN_EVALUATED_TRIAL_COUNT
    )
_ZERO = Decimal(0)
_ONE = Decimal(1)
_TWO = Decimal(2)
_FOUR = Decimal(4)
_PI = Decimal("3.1415926535897932384626433832795028841971693993751058209749445923")
_SQRT_TWO = Decimal("1.414213562373095048801688724209698078569671875376948073176679738")
_EULER_MASCHERONI = Decimal(
    "0.5772156649015328606065120900824024310421593359399235988057672349"
)
_SERIES_EPSILON = Decimal("1e-58")
_ERF_SERIES_LIMIT = Decimal(8)
_MILLS_FRACTION_DEPTH = 120
_NORMAL_INVERSE_UPPER_BOUND = Decimal(10)
_NORMAL_INVERSE_ITERATIONS = 240


class SelectionStatisticsError(ValueError):
    """Invalid or degenerate daily-return or G1-search statistics."""


@dataclass(frozen=True, slots=True)
class SharpeStatistics:
    """Summary of one exact daily simple-return sequence."""

    observation_count: int
    mean_daily_return: Decimal
    sample_std_daily_return: Decimal
    sharpe_daily: Decimal
    sharpe_annualized: Decimal
    skewness: Decimal
    raw_pearson_kurtosis: Decimal
    daily_returns_identity: str
    identity: str

    def __post_init__(self) -> None:
        if type(self.observation_count) is not int or self.observation_count < 3:
            raise SelectionStatisticsError("observation count must be at least three")
        _require_finite_decimal(self.mean_daily_return, "mean daily return")
        _require_finite_decimal(
            self.sample_std_daily_return, "sample standard deviation"
        )
        _require_finite_decimal(self.sharpe_daily, "daily Sharpe")
        _require_finite_decimal(self.sharpe_annualized, "annualized Sharpe")
        _require_finite_decimal(self.skewness, "skewness")
        _require_finite_decimal(self.raw_pearson_kurtosis, "raw Pearson kurtosis")
        if self.sample_std_daily_return <= 0:
            raise SelectionStatisticsError("daily return variance must be positive")
        if not _is_uuid5(self.daily_returns_identity) or not _is_uuid5(self.identity):
            raise SelectionStatisticsError(
                "statistics identities must be canonical UUID5 values"
            )
        expected = _sharpe_statistics_identity(
            self.observation_count,
            self.mean_daily_return,
            self.sample_std_daily_return,
            self.sharpe_daily,
            self.sharpe_annualized,
            self.skewness,
            self.raw_pearson_kurtosis,
            self.daily_returns_identity,
        )
        if self.identity != expected:
            raise SelectionStatisticsError("Sharpe statistics identity mismatch")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "ai-strategy-discovery-sharpe-statistics/v1",
            "observation_count": self.observation_count,
            "mean_daily_return": decimal_text(self.mean_daily_return),
            "sample_std_daily_return": decimal_text(self.sample_std_daily_return),
            "sharpe_daily": decimal_text(self.sharpe_daily),
            "sharpe_annualized": decimal_text(self.sharpe_annualized),
            "annualization_days": ANNUALIZATION_DAYS,
            "skewness": decimal_text(self.skewness),
            "kurtosis_convention": "raw_pearson_central_moment_m4_over_m2_squared",
            "raw_pearson_kurtosis": decimal_text(self.raw_pearson_kurtosis),
            "moment_convention": "central_moments_divided_by_observation_count",
            "daily_returns_identity": self.daily_returns_identity,
            "identity": self.identity,
        }


@dataclass(frozen=True, slots=True)
class SearchBenchmark:
    """The frozen 22-trial zero-centered expected-maximum Sharpe benchmark."""

    trial_count: int
    population_daily_sharpes: tuple[Decimal, ...]
    population_statistics_identities: tuple[str, ...]
    population_mean_daily_sharpe: Decimal
    sharpe_dispersion_variance: Decimal
    sharpe_dispersion_std: Decimal
    normal_quantile_one_over_n: Decimal
    normal_quantile_one_over_ne: Decimal
    expected_max_daily_sharpe: Decimal
    population_identity: str
    identity: str

    def __post_init__(self) -> None:
        if (
            type(self.trial_count) is not int
            or self.trial_count != G1_SEARCH_TRIAL_COUNT
        ):
            raise SelectionStatisticsError(
                "G1 search benchmark requires exactly 22 trials"
            )
        if (
            type(self.population_daily_sharpes) is not tuple
            or len(self.population_daily_sharpes) != G1_SEARCH_TRIAL_COUNT
        ):
            raise SelectionStatisticsError(
                "G1 search population must contain exactly 22 Sharpe values"
            )
        if (
            type(self.population_statistics_identities) is not tuple
            or len(self.population_statistics_identities) != G1_SEARCH_TRIAL_COUNT
        ):
            raise SelectionStatisticsError(
                "G1 search population must contain exactly 22 identities"
            )
        if any(not _is_uuid5(value) for value in self.population_statistics_identities):
            raise SelectionStatisticsError(
                "population statistics identities must be canonical UUID5 values"
            )
        for value in self.population_daily_sharpes:
            _require_finite_decimal(value, "population daily Sharpe")
        for value, label in (
            (self.population_mean_daily_sharpe, "population mean daily Sharpe"),
            (self.sharpe_dispersion_variance, "Sharpe dispersion variance"),
            (self.sharpe_dispersion_std, "Sharpe dispersion standard deviation"),
            (self.normal_quantile_one_over_n, "1 - 1/N normal quantile"),
            (self.normal_quantile_one_over_ne, "1 - 1/(N e) normal quantile"),
            (self.expected_max_daily_sharpe, "expected maximum daily Sharpe"),
        ):
            _require_finite_decimal(value, label)
        if self.sharpe_dispersion_variance <= 0 or self.sharpe_dispersion_std <= 0:
            raise SelectionStatisticsError(
                "G1 Sharpe search dispersion must be positive"
            )
        if not _is_uuid5(self.population_identity) or not _is_uuid5(self.identity):
            raise SelectionStatisticsError(
                "benchmark identities must be canonical UUID5 values"
            )
        expected_population = semantic_identity(
            "ai-strategy-discovery-g1-sharpe-population/v1",
            tuple(
                zip(
                    self.population_statistics_identities,
                    self.population_daily_sharpes,
                    strict=True,
                )
            ),
        )
        if self.population_identity != expected_population:
            raise SelectionStatisticsError("Sharpe population identity mismatch")
        expected_identity = _search_benchmark_identity(
            self.trial_count,
            self.population_daily_sharpes,
            self.population_statistics_identities,
            self.population_mean_daily_sharpe,
            self.sharpe_dispersion_variance,
            self.sharpe_dispersion_std,
            self.normal_quantile_one_over_n,
            self.normal_quantile_one_over_ne,
            self.expected_max_daily_sharpe,
            self.population_identity,
        )
        if self.identity != expected_identity:
            raise SelectionStatisticsError("search benchmark identity mismatch")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "ai-strategy-discovery-g1-search-benchmark/v1",
            "trial_count": self.trial_count,
            "population_daily_sharpes": [
                decimal_text(value) for value in self.population_daily_sharpes
            ],
            "population_statistics_identities": list(
                self.population_statistics_identities
            ),
            "population_mean_daily_sharpe": decimal_text(
                self.population_mean_daily_sharpe
            ),
            "sharpe_dispersion_variance": decimal_text(self.sharpe_dispersion_variance),
            "sharpe_dispersion_variance_convention": "sample_variance_ddof_1",
            "sharpe_dispersion_std": decimal_text(self.sharpe_dispersion_std),
            "normal_quantile_one_over_n": decimal_text(self.normal_quantile_one_over_n),
            "normal_quantile_one_over_ne": decimal_text(
                self.normal_quantile_one_over_ne
            ),
            "euler_mascheroni_constant": decimal_text(_EULER_MASCHERONI),
            "expected_max_daily_sharpe": decimal_text(self.expected_max_daily_sharpe),
            "null_convention": "zero_centered_no_empirical_mean_added",
            "trial_independence_assumption": (
                "The 22 frozen G1 programs are treated as independent trials for the "
                "expected-maximum approximation; actual strategies may be dependent."
            ),
            "expected_max_method": "Bailey_Lopez_de_Prado_2014_equation_2",
            "normal_distribution_method": _NORMAL_DISTRIBUTION_METHOD,
            "population_identity": self.population_identity,
            "identity": self.identity,
        }


@dataclass(frozen=True, slots=True)
class SelectionInference:
    """DSR and separate campaign-wide zero-benchmark PSR sensitivity."""

    statistics_identity: str
    benchmark_identity: str
    observation_count: int
    search_trial_count: int
    campaign_trial_count: int
    non_normality_variance_term: Decimal
    dsr_statistic: Decimal
    dsr_probability: Decimal
    zero_benchmark_psr_statistic: Decimal
    zero_benchmark_psr_probability: Decimal
    campaign_psr_p_value: Decimal
    campaign_alpha: Decimal
    dsr_threshold: Decimal
    passed: bool
    identity: str

    def __post_init__(self) -> None:
        if self.search_trial_count != G1_SEARCH_TRIAL_COUNT:
            raise SelectionStatisticsError("selection inference must use 22 G1 trials")
        if (
            type(self.search_trial_count) is not int
            or type(self.campaign_trial_count) is not int
            or self.campaign_trial_count != CAMPAIGN_EVALUATED_TRIAL_COUNT
        ):
            raise SelectionStatisticsError("campaign sensitivity must use 28 trials")
        if type(self.observation_count) is not int or self.observation_count < 3:
            raise SelectionStatisticsError("observation count must be at least three")
        if type(self.passed) is not bool:
            raise SelectionStatisticsError("passed must be a bool")
        for value, label in (
            (self.non_normality_variance_term, "non-normality variance term"),
            (self.dsr_statistic, "DSR statistic"),
            (self.dsr_probability, "DSR probability"),
            (self.zero_benchmark_psr_statistic, "zero-benchmark PSR statistic"),
            (self.zero_benchmark_psr_probability, "zero-benchmark PSR probability"),
            (self.campaign_psr_p_value, "campaign PSR p-value"),
            (self.campaign_alpha, "campaign alpha"),
            (self.dsr_threshold, "DSR threshold"),
        ):
            _require_finite_decimal(value, label)
        if not (
            _ZERO <= self.dsr_probability <= _ONE
            and _ZERO <= self.zero_benchmark_psr_probability <= _ONE
            and _ZERO <= self.campaign_psr_p_value <= _ONE
        ):
            raise SelectionStatisticsError("inference probabilities must be in [0, 1]")
        if self.non_normality_variance_term <= 0:
            raise SelectionStatisticsError(
                "non-normality variance term must be positive"
            )
        if (
            not _is_uuid5(self.statistics_identity)
            or not _is_uuid5(self.benchmark_identity)
            or not _is_uuid5(self.identity)
        ):
            raise SelectionStatisticsError(
                "inference identities must be canonical UUID5 values"
            )
        expected_alpha = CAMPAIGN_FAMILYWISE_ALPHA
        if (
            self.campaign_alpha != expected_alpha
            or self.dsr_threshold != DSR_PASS_THRESHOLD
        ):
            raise SelectionStatisticsError(
                "selection thresholds do not match the frozen contract"
            )
        expected_passed = _passes_thresholds(
            self.dsr_probability,
            self.campaign_psr_p_value,
            self.campaign_alpha,
            self.dsr_threshold,
        )
        if self.passed != expected_passed:
            raise SelectionStatisticsError(
                "selection pass field does not match its thresholds"
            )
        expected_identity = _selection_inference_identity(
            self.statistics_identity,
            self.benchmark_identity,
            self.observation_count,
            self.search_trial_count,
            self.campaign_trial_count,
            self.non_normality_variance_term,
            self.dsr_statistic,
            self.dsr_probability,
            self.zero_benchmark_psr_statistic,
            self.zero_benchmark_psr_probability,
            self.campaign_psr_p_value,
            self.campaign_alpha,
            self.dsr_threshold,
            self.passed,
        )
        if self.identity != expected_identity:
            raise SelectionStatisticsError("selection inference identity mismatch")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "ai-strategy-discovery-selection-inference/v1",
            "statistics_identity": self.statistics_identity,
            "benchmark_identity": self.benchmark_identity,
            "observation_count": self.observation_count,
            "search_trial_count": self.search_trial_count,
            "campaign_trial_count": self.campaign_trial_count,
            "non_normality_variance_term": decimal_text(
                self.non_normality_variance_term
            ),
            "dsr_statistic": decimal_text(self.dsr_statistic),
            "dsr_probability": decimal_text(self.dsr_probability),
            "dsr_threshold": decimal_text(self.dsr_threshold),
            "zero_benchmark_psr_statistic": decimal_text(
                self.zero_benchmark_psr_statistic
            ),
            "zero_benchmark_psr_probability": decimal_text(
                self.zero_benchmark_psr_probability
            ),
            "campaign_psr_p_value": decimal_text(self.campaign_psr_p_value),
            "campaign_alpha": decimal_text(self.campaign_alpha),
            "campaign_sensitivity_method": "one_sided_PSR_Bonferroni_0.05_over_28",
            "passed": self.passed,
            "identity": self.identity,
        }


_NORMAL_DISTRIBUTION_METHOD = (
    "Decimal erf alternating power series for |z|<=8; Decimal Mills-ratio "
    "continued fraction for upper tails above 8; inverse upper tail by bisection"
)


def summarize_daily_returns(returns: tuple[Decimal, ...]) -> SharpeStatistics:
    """Summarize finite daily simple returns using fixed Decimal conventions."""
    if type(returns) is not tuple or len(returns) < 3:
        raise SelectionStatisticsError(
            "returns must be a tuple with at least three values"
        )
    for value in returns:
        if type(value) is not Decimal or not value.is_finite():
            raise SelectionStatisticsError("returns must contain finite Decimal values")

    with localcontext(_ARITHMETIC_CONTEXT):
        count = len(returns)
        n = Decimal(count)
        mean = sum(returns, _ZERO) / n
        centered = tuple(value - mean for value in returns)
        sum_squares = sum((value * value for value in centered), _ZERO)
        if sum_squares == 0:
            raise SelectionStatisticsError("daily return variance must be positive")
        sample_std = (sum_squares / Decimal(count - 1)).sqrt()
        second_moment = sum_squares / n
        third_moment = sum((value**3 for value in centered), _ZERO) / n
        fourth_moment = sum((value**4 for value in centered), _ZERO) / n
        sharpe_daily = mean / sample_std
        sharpe_annualized = sharpe_daily * Decimal(ANNUALIZATION_DAYS).sqrt()
        skewness = third_moment / (second_moment * second_moment.sqrt())
        raw_pearson_kurtosis = fourth_moment / (second_moment * second_moment)
        returns_identity = semantic_identity(
            "ai-strategy-discovery-daily-return-series/v1",
            returns,
        )
        identity = _sharpe_statistics_identity(
            count,
            mean,
            sample_std,
            sharpe_daily,
            sharpe_annualized,
            skewness,
            raw_pearson_kurtosis,
            returns_identity,
        )
        return SharpeStatistics(
            observation_count=count,
            mean_daily_return=mean,
            sample_std_daily_return=sample_std,
            sharpe_daily=sharpe_daily,
            sharpe_annualized=sharpe_annualized,
            skewness=skewness,
            raw_pearson_kurtosis=raw_pearson_kurtosis,
            daily_returns_identity=returns_identity,
            identity=identity,
        )


def g1_search_benchmark(
    population: tuple[SharpeStatistics, ...],
) -> SearchBenchmark:
    """Build the expected-maximum benchmark from the complete 22-program G1 set."""
    if type(population) is not tuple or len(population) != G1_SEARCH_TRIAL_COUNT:
        raise SelectionStatisticsError(
            "G1 search population must contain exactly 22 programs"
        )
    for item in population:
        if type(item) is not SharpeStatistics:
            raise SelectionStatisticsError(
                "G1 search population must contain SharpeStatistics values"
            )
        _validate_sharpe_statistics(item)

    with localcontext(_ARITHMETIC_CONTEXT):
        sharpes = tuple(item.sharpe_daily for item in population)
        count = Decimal(G1_SEARCH_TRIAL_COUNT)
        mean = sum(sharpes, _ZERO) / count
        squared_differences = tuple((value - mean) ** 2 for value in sharpes)
        variance = sum(squared_differences, _ZERO) / Decimal(G1_SEARCH_TRIAL_COUNT - 1)
        if variance <= 0:
            raise SelectionStatisticsError(
                "G1 Sharpe search dispersion must be positive"
            )
        dispersion_std = variance.sqrt()
        (
            quantile_one_over_n,
            quantile_one_over_ne,
            expected_max_multiplier,
        ) = _expected_max_quantile_multiplier(G1_SEARCH_TRIAL_COUNT)
        expected_max = dispersion_std * expected_max_multiplier
        statistics_identities = tuple(item.identity for item in population)
        population_identity = semantic_identity(
            "ai-strategy-discovery-g1-sharpe-population/v1",
            tuple(zip(statistics_identities, sharpes, strict=True)),
        )
        identity = _search_benchmark_identity(
            G1_SEARCH_TRIAL_COUNT,
            sharpes,
            statistics_identities,
            mean,
            variance,
            dispersion_std,
            quantile_one_over_n,
            quantile_one_over_ne,
            expected_max,
            population_identity,
        )
        return SearchBenchmark(
            trial_count=G1_SEARCH_TRIAL_COUNT,
            population_daily_sharpes=sharpes,
            population_statistics_identities=statistics_identities,
            population_mean_daily_sharpe=mean,
            sharpe_dispersion_variance=variance,
            sharpe_dispersion_std=dispersion_std,
            normal_quantile_one_over_n=quantile_one_over_n,
            normal_quantile_one_over_ne=quantile_one_over_ne,
            expected_max_daily_sharpe=expected_max,
            population_identity=population_identity,
            identity=identity,
        )


def assess_selection_bias(
    stats: SharpeStatistics,
    benchmark: SearchBenchmark,
) -> SelectionInference:
    """Compute 22-trial DSR and separate one-sided Bonferroni PSR sensitivity."""
    if type(stats) is not SharpeStatistics:
        raise SelectionStatisticsError("stats must be SharpeStatistics")
    if type(benchmark) is not SearchBenchmark:
        raise SelectionStatisticsError("benchmark must be SearchBenchmark")
    _validate_sharpe_statistics(stats)
    _validate_search_benchmark(benchmark)
    if stats.identity not in benchmark.population_statistics_identities:
        raise SelectionStatisticsError(
            "candidate statistics must be a member of the complete G1 search population"
        )

    with localcontext(_ARITHMETIC_CONTEXT):
        sharpe = stats.sharpe_daily
        non_normality_variance = (
            _ONE
            - stats.skewness * sharpe
            + (stats.raw_pearson_kurtosis - _ONE) * sharpe * sharpe / _FOUR
        )
        if non_normality_variance <= 0:
            raise SelectionStatisticsError(
                "non-normality variance term must be positive"
            )
        scale = non_normality_variance.sqrt()
        track_record_scale = Decimal(stats.observation_count - 1).sqrt()
        dsr_statistic = (
            (sharpe - benchmark.expected_max_daily_sharpe) * track_record_scale / scale
        )
        zero_psr_statistic = sharpe * track_record_scale / scale
        dsr_probability = _normal_cdf(dsr_statistic)
        zero_psr_probability = _normal_cdf(zero_psr_statistic)
        campaign_psr_p_value = _normal_survival(zero_psr_statistic)
        campaign_alpha = Decimal("0.05") / Decimal(CAMPAIGN_EVALUATED_TRIAL_COUNT)
        passed = _passes_thresholds(
            dsr_probability,
            campaign_psr_p_value,
            campaign_alpha,
            DSR_PASS_THRESHOLD,
        )
        identity = _selection_inference_identity(
            stats.identity,
            benchmark.identity,
            stats.observation_count,
            G1_SEARCH_TRIAL_COUNT,
            CAMPAIGN_EVALUATED_TRIAL_COUNT,
            non_normality_variance,
            dsr_statistic,
            dsr_probability,
            zero_psr_statistic,
            zero_psr_probability,
            campaign_psr_p_value,
            campaign_alpha,
            DSR_PASS_THRESHOLD,
            passed,
        )
        return SelectionInference(
            statistics_identity=stats.identity,
            benchmark_identity=benchmark.identity,
            observation_count=stats.observation_count,
            search_trial_count=G1_SEARCH_TRIAL_COUNT,
            campaign_trial_count=CAMPAIGN_EVALUATED_TRIAL_COUNT,
            non_normality_variance_term=non_normality_variance,
            dsr_statistic=dsr_statistic,
            dsr_probability=dsr_probability,
            zero_benchmark_psr_statistic=zero_psr_statistic,
            zero_benchmark_psr_probability=zero_psr_probability,
            campaign_psr_p_value=campaign_psr_p_value,
            campaign_alpha=campaign_alpha,
            dsr_threshold=DSR_PASS_THRESHOLD,
            passed=passed,
            identity=identity,
        )


def _normal_upper_quantile(upper_tail_probability: Decimal) -> Decimal:
    if (
        type(upper_tail_probability) is not Decimal
        or not upper_tail_probability.is_finite()
        or not _ZERO < upper_tail_probability < Decimal("0.5")
    ):
        raise SelectionStatisticsError(
            "normal upper-tail probability must be in (0, 0.5)"
        )
    with localcontext(_ARITHMETIC_CONTEXT):
        low = _ZERO
        high = _NORMAL_INVERSE_UPPER_BOUND
        if _normal_survival_positive(high) >= upper_tail_probability:
            raise SelectionStatisticsError(
                "normal quantile exceeds the supported bound"
            )
        for _ in range(_NORMAL_INVERSE_ITERATIONS):
            midpoint = (low + high) / _TWO
            if midpoint == low or midpoint == high:
                break
            if _normal_survival_positive(midpoint) > upper_tail_probability:
                low = midpoint
            else:
                high = midpoint
        return (low + high) / _TWO


def _expected_max_quantile_multiplier(
    trial_count: int,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return the Eq. (2) Gaussian maximum quantiles and their weighted factor."""
    if type(trial_count) is not int or trial_count < 2:
        raise SelectionStatisticsError(
            "normal expected maximum needs at least two trials"
        )
    with localcontext(_ARITHMETIC_CONTEXT):
        count = Decimal(trial_count)
        euler_number = _ONE.exp()
        quantile_one_over_n = _normal_upper_quantile(_ONE / count)
        quantile_one_over_ne = _normal_upper_quantile(_ONE / (count * euler_number))
        multiplier = (
            _ONE - _EULER_MASCHERONI
        ) * quantile_one_over_n + _EULER_MASCHERONI * quantile_one_over_ne
        return quantile_one_over_n, quantile_one_over_ne, multiplier


def _normal_cdf(value: Decimal) -> Decimal:
    with localcontext(_ARITHMETIC_CONTEXT):
        if value >= _ZERO:
            return _ONE - _normal_survival_positive(value)
        return _normal_survival_positive(-value)


def _normal_survival(value: Decimal) -> Decimal:
    with localcontext(_ARITHMETIC_CONTEXT):
        if value >= _ZERO:
            return _normal_survival_positive(value)
        return _ONE - _normal_survival_positive(-value)


def _normal_survival_positive(value: Decimal) -> Decimal:
    if value == _ZERO:
        return Decimal("0.5")
    with localcontext(_ARITHMETIC_CONTEXT):
        if value <= _ERF_SERIES_LIMIT:
            standard_argument = value / _SQRT_TWO
            argument_squared = standard_argument * standard_argument
            term = standard_argument
            series = term
            index = 0
            while True:
                next_index = index + 1
                term = (
                    -term
                    * argument_squared
                    * Decimal(2 * index + 1)
                    / (Decimal(next_index) * Decimal(2 * index + 3))
                )
                series += term
                index = next_index
                if abs(term) <= _SERIES_EPSILON:
                    break
                if index > 2_000:
                    raise SelectionStatisticsError(
                        "normal CDF power series did not converge"
                    )
            erf = (_TWO / _PI.sqrt()) * series
            return (_ONE - erf) / _TWO

        denominator = value
        for numerator in range(_MILLS_FRACTION_DEPTH, 0, -1):
            denominator = value + Decimal(numerator) / denominator
        mills_ratio = _ONE / denominator
        density = (-value * value / _TWO).exp() / (_TWO * _PI).sqrt()
        return density * mills_ratio


def _passes_thresholds(
    dsr_probability: Decimal,
    campaign_psr_p_value: Decimal,
    campaign_alpha: Decimal,
    dsr_threshold: Decimal,
) -> bool:
    return dsr_probability >= dsr_threshold and campaign_psr_p_value <= campaign_alpha


def _validate_sharpe_statistics(value: SharpeStatistics) -> None:
    if type(value) is not SharpeStatistics:
        raise SelectionStatisticsError("expected SharpeStatistics")
    try:
        value.__post_init__()
    except SelectionStatisticsError:
        raise
    except (TypeError, ValueError, ArithmeticError):
        raise SelectionStatisticsError("invalid SharpeStatistics value") from None


def _validate_search_benchmark(value: SearchBenchmark) -> None:
    if type(value) is not SearchBenchmark:
        raise SelectionStatisticsError("expected SearchBenchmark")
    try:
        value.__post_init__()
    except SelectionStatisticsError:
        raise
    except (TypeError, ValueError, ArithmeticError):
        raise SelectionStatisticsError("invalid SearchBenchmark value") from None


def _sharpe_statistics_identity(
    observation_count: int,
    mean_daily_return: Decimal,
    sample_std_daily_return: Decimal,
    sharpe_daily: Decimal,
    sharpe_annualized: Decimal,
    skewness: Decimal,
    raw_pearson_kurtosis: Decimal,
    daily_returns_identity: str,
) -> str:
    return semantic_identity(
        "ai-strategy-discovery-sharpe-statistics/v1",
        (
            observation_count,
            mean_daily_return,
            sample_std_daily_return,
            sharpe_daily,
            sharpe_annualized,
            skewness,
            raw_pearson_kurtosis,
            daily_returns_identity,
            ANNUALIZATION_DAYS,
            "sample_std_ddof_1",
            "central_moments_divisor_T",
            "raw_pearson_kurtosis",
        ),
    )


def _search_benchmark_identity(
    trial_count: int,
    population_daily_sharpes: tuple[Decimal, ...],
    population_statistics_identities: tuple[str, ...],
    population_mean_daily_sharpe: Decimal,
    sharpe_dispersion_variance: Decimal,
    sharpe_dispersion_std: Decimal,
    normal_quantile_one_over_n: Decimal,
    normal_quantile_one_over_ne: Decimal,
    expected_max_daily_sharpe: Decimal,
    population_identity: str,
) -> str:
    return semantic_identity(
        "ai-strategy-discovery-g1-search-benchmark/v1",
        (
            trial_count,
            population_daily_sharpes,
            population_statistics_identities,
            population_mean_daily_sharpe,
            sharpe_dispersion_variance,
            sharpe_dispersion_std,
            normal_quantile_one_over_n,
            normal_quantile_one_over_ne,
            _EULER_MASCHERONI,
            expected_max_daily_sharpe,
            population_identity,
            "zero_centered_no_empirical_mean_added",
            "sample_variance_ddof_1",
            "bailey_lopez_de_prado_2014_equation_2",
        ),
    )


def _selection_inference_identity(
    statistics_identity: str,
    benchmark_identity: str,
    observation_count: int,
    search_trial_count: int,
    campaign_trial_count: int,
    non_normality_variance_term: Decimal,
    dsr_statistic: Decimal,
    dsr_probability: Decimal,
    zero_benchmark_psr_statistic: Decimal,
    zero_benchmark_psr_probability: Decimal,
    campaign_psr_p_value: Decimal,
    campaign_alpha: Decimal,
    dsr_threshold: Decimal,
    passed: bool,
) -> str:
    return semantic_identity(
        "ai-strategy-discovery-selection-inference/v1",
        (
            statistics_identity,
            benchmark_identity,
            observation_count,
            search_trial_count,
            campaign_trial_count,
            non_normality_variance_term,
            dsr_statistic,
            dsr_probability,
            zero_benchmark_psr_statistic,
            zero_benchmark_psr_probability,
            campaign_psr_p_value,
            campaign_alpha,
            dsr_threshold,
            passed,
        ),
    )


def _require_finite_decimal(value: object, label: str) -> None:
    if type(value) is not Decimal or not value.is_finite():
        raise SelectionStatisticsError(f"{label} must be a finite Decimal")


def _is_uuid5(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError):
        return False
    return parsed.version == 5 and str(parsed) == value

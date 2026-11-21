from __future__ import annotations

import math
from decimal import ROUND_DOWN, Context, Decimal, localcontext
from statistics import NormalDist

import pytest

from trading_bot.experiments.ai_strategy_discovery_selection_statistics import (
    CAMPAIGN_EVALUATED_TRIAL_COUNT,
    CAMPAIGN_FAMILYWISE_ALPHA,
    DSR_PASS_THRESHOLD,
    G1_SEARCH_TRIAL_COUNT,
    SearchBenchmark,
    SelectionStatisticsError,
    SharpeStatistics,
    _expected_max_quantile_multiplier,
    _normal_cdf,
    _normal_survival,
    _passes_thresholds,
    assess_selection_bias,
    g1_search_benchmark,
    summarize_daily_returns,
)


def _stats_with_daily_sharpe(sharpe: Decimal) -> SharpeStatistics:
    spread = Decimal("0.0001")
    mean = sharpe * spread
    return summarize_daily_returns((mean - spread, mean, mean + spread))


def _standard_library_benchmark(sharpes: tuple[Decimal, ...]) -> tuple[float, float]:
    values = tuple(float(value) for value in sharpes)
    mean = sum(values) / len(values)
    sample_variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    dispersion = math.sqrt(sample_variance)
    normal = NormalDist()
    euler_mascheroni = 0.5772156649015329
    trials = len(values)
    multiplier = (1 - euler_mascheroni) * normal.inv_cdf(1 - 1 / trials)
    multiplier += euler_mascheroni * normal.inv_cdf(1 - 1 / (trials * math.e))
    return sample_variance, dispersion * multiplier


def test_summary_uses_sample_sharpe_and_raw_central_moments() -> None:
    returns = (Decimal("0.01"), Decimal("0.02"), Decimal("0.03"))

    stats = summarize_daily_returns(returns)

    assert stats.observation_count == 3
    assert stats.mean_daily_return == Decimal("0.02")
    assert stats.sample_std_daily_return == Decimal("0.01")
    assert stats.sharpe_daily == Decimal("2")
    assert stats.skewness == Decimal("0")
    assert stats.raw_pearson_kurtosis == Decimal("1.5")
    with localcontext(Context(prec=60)):
        assert stats.sharpe_annualized == Decimal(2) * Decimal(252).sqrt()
    assert stats.identity == summarize_daily_returns(returns).identity
    assert (
        stats.daily_returns_identity
        != summarize_daily_returns(
            (Decimal("0.01"), Decimal("0.02"), Decimal("0.04"))
        ).daily_returns_identity
    )

    payload = stats.to_dict()
    assert payload["annualization_days"] == 252
    assert (
        payload["kurtosis_convention"]
        == "raw_pearson_central_moment_m4_over_m2_squared"
    )
    assert payload["raw_pearson_kurtosis"] == "1.5"


def test_moments_use_t_divisors_without_bias_correction() -> None:
    stats = summarize_daily_returns((Decimal("0"), Decimal("0"), Decimal("1")))

    with localcontext(Context(prec=60)):
        assert abs(stats.skewness - Decimal(1) / Decimal(2).sqrt()) < Decimal("1e-58")
        assert stats.raw_pearson_kurtosis == Decimal("1.5")


@pytest.mark.parametrize(
    "returns",
    (
        (Decimal("1"), Decimal("1"), Decimal("1")),
        (Decimal("1"), Decimal("2")),
        [Decimal("1"), Decimal("2"), Decimal("3")],
        (Decimal("1"), Decimal("2"), 3),
        (Decimal("1"), Decimal("2"), Decimal("NaN")),
    ),
)
def test_invalid_or_zero_variance_daily_returns_fail_closed(returns: object) -> None:
    with pytest.raises(SelectionStatisticsError):
        summarize_daily_returns(returns)  # type: ignore[arg-type]


def test_statistics_are_independent_of_ambient_decimal_context() -> None:
    returns = (
        Decimal("0.001"),
        Decimal("-0.002"),
        Decimal("0.004"),
        Decimal("0.003"),
        Decimal("0.012"),
    )
    baseline = summarize_daily_returns(returns)

    with localcontext(Context(prec=6, rounding=ROUND_DOWN)):
        constrained = summarize_daily_returns(returns)

    assert constrained == baseline
    assert constrained.to_dict() == baseline.to_dict()

    population = tuple(
        _stats_with_daily_sharpe(Decimal(index - 10) / Decimal(100))
        for index in range(22)
    )
    baseline_benchmark = g1_search_benchmark(population)
    baseline_inference = assess_selection_bias(population[-1], baseline_benchmark)
    with localcontext(Context(prec=6, rounding=ROUND_DOWN)):
        constrained_benchmark = g1_search_benchmark(population)
        constrained_inference = assess_selection_bias(
            population[-1], constrained_benchmark
        )

    assert constrained_benchmark == baseline_benchmark
    assert constrained_inference == baseline_inference


def test_g1_benchmark_uses_complete_22_population_and_ddof_one() -> None:
    population = tuple(
        _stats_with_daily_sharpe(Decimal(index - 11) / Decimal(100))
        for index in range(G1_SEARCH_TRIAL_COUNT)
    )
    benchmark = g1_search_benchmark(population)

    expected_variance, expected_maximum = _standard_library_benchmark(
        tuple(Decimal(index - 11) / Decimal(100) for index in range(22))
    )
    assert benchmark.trial_count == 22
    assert benchmark.population_mean_daily_sharpe == Decimal("-0.005")
    assert len(benchmark.population_daily_sharpes) == 22
    assert len(benchmark.population_statistics_identities) == 22
    assert benchmark.population_daily_sharpes[0] == Decimal("-0.11")
    assert benchmark.population_daily_sharpes[-1] == Decimal("0.1")
    assert math.isclose(
        float(benchmark.sharpe_dispersion_variance), expected_variance, rel_tol=1e-14
    )
    assert math.isclose(
        float(benchmark.expected_max_daily_sharpe), expected_maximum, rel_tol=1e-14
    )
    assert benchmark.to_dict()["trial_independence_assumption"]
    assert (
        benchmark.to_dict()["null_convention"]
        == "zero_centered_no_empirical_mean_added"
    )


def test_g1_benchmark_rejects_shortlist_only_and_degenerate_population() -> None:
    full_population = tuple(
        _stats_with_daily_sharpe(Decimal(index - 10) / Decimal(100))
        for index in range(22)
    )
    with pytest.raises(SelectionStatisticsError, match="exactly 22"):
        g1_search_benchmark(full_population[:12])
    with pytest.raises(SelectionStatisticsError, match="exactly 22"):
        g1_search_benchmark(full_population[:21])

    identical_population = tuple(
        _stats_with_daily_sharpe(Decimal("0.1")) for _ in range(22)
    )
    with pytest.raises(SelectionStatisticsError, match="dispersion must be positive"):
        g1_search_benchmark(identical_population)


def test_expected_maximum_increases_with_trial_count() -> None:
    multiplier_22 = _expected_max_quantile_multiplier(22)[2]
    multiplier_28 = _expected_max_quantile_multiplier(28)[2]

    assert multiplier_28 > multiplier_22


def test_normal_distribution_approximation_matches_independent_tail_values() -> None:
    for z_value in ("-6", "-2.5", "0", "1.6448536269514722", "8", "8.0001", "10"):
        z = Decimal(z_value)
        expected_cdf = 0.5 * math.erfc(-float(z) / math.sqrt(2))
        expected_survival = 0.5 * math.erfc(float(z) / math.sqrt(2))
        assert math.isclose(
            float(_normal_cdf(z)), expected_cdf, rel_tol=2e-13, abs_tol=1e-30
        )
        assert math.isclose(
            float(_normal_survival(z)), expected_survival, rel_tol=2e-13, abs_tol=1e-30
        )


def test_bailey_numeric_example_reproduces_published_dsr_values() -> None:
    # Bailey and López de Prado (2014), numerical example: T=1250, annualized
    # SR=2.5 on a 250-day convention, variance(SR trials)=0.5/250, skew=-3,
    # raw kurtosis=10. The paper reports DSR≈0.90 for N=100 and 0.9505 for N=46.
    with localcontext(Context(prec=60)):
        observed_daily_sharpe = Decimal("2.5") / Decimal(250).sqrt()
        trial_dispersion = (Decimal("0.5") / Decimal(250)).sqrt()
        variance_term = (
            Decimal(1)
            - Decimal("-3") * observed_daily_sharpe
            + (Decimal(10) - Decimal(1)) * observed_daily_sharpe**2 / Decimal(4)
        )

        probabilities: dict[int, Decimal] = {}
        for trial_count in (100, 46):
            expected_max_multiplier = _expected_max_quantile_multiplier(trial_count)[2]
            expected_max = trial_dispersion * expected_max_multiplier
            statistic = (
                (observed_daily_sharpe - expected_max)
                * Decimal(1249).sqrt()
                / variance_term.sqrt()
            )
            probabilities[trial_count] = _normal_cdf(statistic)

    assert math.isclose(float(probabilities[100]), 0.9003968344493904, abs_tol=2e-12)
    assert math.isclose(float(probabilities[46]), 0.9505017068755786, abs_tol=2e-12)


def test_selection_inference_matches_independent_psr_and_dsr_formulas() -> None:
    candidate = summarize_daily_returns(
        (
            Decimal("-0.02"),
            Decimal("-0.01"),
            Decimal("0"),
            Decimal("0.015"),
            Decimal("0.025"),
            Decimal("0.05"),
        )
    )
    population = (candidate,) + tuple(
        _stats_with_daily_sharpe(Decimal(index - 10) / Decimal(100))
        for index in range(21)
    )
    benchmark = g1_search_benchmark(population)
    inference = assess_selection_bias(candidate, benchmark)

    candidate_sharpe = float(candidate.sharpe_daily)
    skew = float(candidate.skewness)
    raw_kurtosis = float(candidate.raw_pearson_kurtosis)
    variance_term = (
        1 - skew * candidate_sharpe + (raw_kurtosis - 1) * candidate_sharpe**2 / 4
    )
    standard_error_scale = math.sqrt(variance_term)
    track_record_scale = math.sqrt(candidate.observation_count - 1)
    independent_maximum = _standard_library_benchmark(
        benchmark.population_daily_sharpes
    )[1]
    expected_dsr_statistic = (
        (candidate_sharpe - independent_maximum)
        * track_record_scale
        / standard_error_scale
    )
    expected_psr_statistic = (
        candidate_sharpe * track_record_scale / standard_error_scale
    )
    expected_psr_p_value = 0.5 * math.erfc(expected_psr_statistic / math.sqrt(2))
    normal = NormalDist()

    assert float(inference.non_normality_variance_term) == pytest.approx(
        variance_term, rel=1e-13
    )
    assert float(inference.dsr_statistic) == pytest.approx(
        expected_dsr_statistic, rel=1e-13
    )
    assert float(inference.dsr_probability) == pytest.approx(
        normal.cdf(expected_dsr_statistic), rel=1e-13
    )
    assert float(inference.zero_benchmark_psr_statistic) == pytest.approx(
        expected_psr_statistic, rel=1e-13
    )
    assert float(inference.campaign_psr_p_value) == pytest.approx(
        expected_psr_p_value, rel=1e-13
    )
    assert float(
        inference.zero_benchmark_psr_probability + inference.campaign_psr_p_value
    ) == pytest.approx(1, abs=1e-15)
    assert inference.campaign_trial_count == CAMPAIGN_EVALUATED_TRIAL_COUNT == 28
    assert inference.campaign_alpha == CAMPAIGN_FAMILYWISE_ALPHA
    assert inference.dsr_threshold == DSR_PASS_THRESHOLD
    assert inference.passed is (
        inference.dsr_probability >= Decimal("0.95")
        and inference.campaign_psr_p_value <= inference.campaign_alpha
    )
    assert (
        inference.to_dict()["campaign_sensitivity_method"]
        == "one_sided_PSR_Bonferroni_0.05_over_28"
    )


def test_assessment_rejects_candidate_outside_full_population() -> None:
    population = tuple(
        _stats_with_daily_sharpe(Decimal(index - 10) / Decimal(100))
        for index in range(22)
    )
    benchmark = g1_search_benchmark(population)
    outside_candidate = summarize_daily_returns(
        (Decimal("0"), Decimal("0.1"), Decimal("0.2"))
    )

    with pytest.raises(SelectionStatisticsError, match="member"):
        assess_selection_bias(outside_candidate, benchmark)


def test_selection_gate_uses_inclusive_frozen_boundaries() -> None:
    assert _passes_thresholds(
        Decimal("0.95"),
        CAMPAIGN_FAMILYWISE_ALPHA,
        CAMPAIGN_FAMILYWISE_ALPHA,
        DSR_PASS_THRESHOLD,
    )
    assert not _passes_thresholds(
        Decimal("0.949999999999999999"),
        CAMPAIGN_FAMILYWISE_ALPHA,
        CAMPAIGN_FAMILYWISE_ALPHA,
        DSR_PASS_THRESHOLD,
    )
    assert not _passes_thresholds(
        DSR_PASS_THRESHOLD,
        CAMPAIGN_FAMILYWISE_ALPHA + Decimal("1e-20"),
        CAMPAIGN_FAMILYWISE_ALPHA,
        DSR_PASS_THRESHOLD,
    )


def test_search_benchmark_rejects_non_sharpe_inputs() -> None:
    invalid = tuple(object() for _ in range(22))

    with pytest.raises(SelectionStatisticsError, match="SharpeStatistics"):
        g1_search_benchmark(invalid)  # type: ignore[arg-type]

    assert SearchBenchmark.__dataclass_params__.frozen

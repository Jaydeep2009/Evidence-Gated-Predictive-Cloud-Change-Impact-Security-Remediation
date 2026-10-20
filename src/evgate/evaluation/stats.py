"""
P4-12: Statistical Analysis
Bootstrap confidence intervals, significance tests.
"""

from typing import List, Dict, Any, Tuple
import numpy as np
from scipy import stats as scipy_stats


class StatisticalAnalyzer:
    """
    Performs statistical analysis on evaluation results.
    
    Features:
    - Bootstrap confidence intervals
    - McNemar's test for paired comparisons
    - Wilcoxon signed-rank test
    """
    
    def __init__(self, n_bootstrap: int = 1000, confidence_level: float = 0.95, seed: int = 42):
        self.n_bootstrap = n_bootstrap
        self.confidence_level = confidence_level
        self.rng = np.random.RandomState(seed)
    
    def bootstrap_confidence_interval(
        self,
        data: List[float],
        statistic_fn=np.mean
    ) -> Tuple[float, float, float]:
        """
        Compute bootstrap confidence interval.
        
        Args:
            data: Sample data
            statistic_fn: Function to compute statistic (default: np.mean)
        
        Returns:
            Tuple of (point_estimate, lower_bound, upper_bound)
        """
        
        data = np.array(data)
        n = len(data)
        
        # Compute point estimate
        point_estimate = statistic_fn(data)
        
        # Bootstrap resampling
        bootstrap_estimates = []
        for _ in range(self.n_bootstrap):
            sample = self.rng.choice(data, size=n, replace=True)
            bootstrap_estimates.append(statistic_fn(sample))
        
        # Compute confidence interval
        alpha = 1 - self.confidence_level
        lower_percentile = (alpha / 2) * 100
        upper_percentile = (1 - alpha / 2) * 100
        
        lower_bound = np.percentile(bootstrap_estimates, lower_percentile)
        upper_bound = np.percentile(bootstrap_estimates, upper_percentile)
        
        return (
            round(float(point_estimate), 4),
            round(float(lower_bound), 4),
            round(float(upper_bound), 4)
        )
    
    def mcnemar_test(
        self,
        method1_correct: List[bool],
        method2_correct: List[bool]
    ) -> Dict[str, Any]:
        """
        McNemar's test for comparing two paired classifiers.
        
        Tests whether two methods have significantly different error rates.
        
        Args:
            method1_correct: Binary correctness for method 1
            method2_correct: Binary correctness for method 2
        
        Returns:
            Dict with test statistic, p-value, and interpretation
        """
        
        if len(method1_correct) != len(method2_correct):
            raise ValueError("Methods must have same number of predictions")
        
        # Build contingency table
        # n00: both wrong, n01: m1 wrong m2 correct, n10: m1 correct m2 wrong, n11: both correct
        n01 = sum(1 for m1, m2 in zip(method1_correct, method2_correct) if not m1 and m2)
        n10 = sum(1 for m1, m2 in zip(method1_correct, method2_correct) if m1 and not m2)
        
        # McNemar statistic (with continuity correction)
        if n01 + n10 == 0:
            return {
                "statistic": 0.0,
                "p_value": 1.0,
                "significant": False,
                "interpretation": "Both methods have identical performance (no discordant pairs)"
            }
        
        statistic = ((abs(n01 - n10) - 1) ** 2) / (n01 + n10)
        p_value = 1 - scipy_stats.chi2.cdf(statistic, df=1)
        
        significant = p_value < 0.05
        
        if significant:
            winner = "method1" if n10 > n01 else "method2"
            interpretation = f"Significant difference (p={p_value:.4f}): {winner} performs better"
        else:
            interpretation = f"No significant difference (p={p_value:.4f})"
        
        return {
            "statistic": round(statistic, 4),
            "p_value": round(p_value, 4),
            "significant": significant,
            "n01": n01,  # m1 wrong, m2 correct
            "n10": n10,  # m1 correct, m2 wrong
            "interpretation": interpretation
        }
    
    def wilcoxon_signed_rank_test(
        self,
        method1_scores: List[float],
        method2_scores: List[float]
    ) -> Dict[str, Any]:
        """
        Wilcoxon signed-rank test for paired samples.
        
        Non-parametric test for comparing two related samples.
        
        Args:
            method1_scores: Performance scores for method 1
            method2_scores: Performance scores for method 2
        
        Returns:
            Dict with test statistic, p-value, and interpretation
        """
        
        if len(method1_scores) != len(method2_scores):
            raise ValueError("Methods must have same number of scores")
        
        statistic, p_value = scipy_stats.wilcoxon(method1_scores, method2_scores)
        
        significant = p_value < 0.05
        
        mean_diff = np.mean(np.array(method1_scores) - np.array(method2_scores))
        
        if significant:
            winner = "method1" if mean_diff > 0 else "method2"
            interpretation = f"Significant difference (p={p_value:.4f}): {winner} has higher scores"
        else:
            interpretation = f"No significant difference (p={p_value:.4f})"
        
        return {
            "statistic": round(float(statistic), 4),
            "p_value": round(float(p_value), 4),
            "significant": significant,
            "mean_difference": round(float(mean_diff), 4),
            "interpretation": interpretation
        }
    
    def effect_size_cohen_d(
        self,
        group1: List[float],
        group2: List[float]
    ) -> float:
        """
        Compute Cohen's d effect size.
        
        Measures standardized difference between two groups.
        
        Args:
            group1: Scores for group 1
            group2: Scores for group 2
        
        Returns:
            Cohen's d effect size
        """
        
        group1 = np.array(group1)
        group2 = np.array(group2)
        
        n1 = len(group1)
        n2 = len(group2)
        
        mean1 = np.mean(group1)
        mean2 = np.mean(group2)
        
        var1 = np.var(group1, ddof=1)
        var2 = np.var(group2, ddof=1)
        
        # Pooled standard deviation
        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
        
        # Cohen's d
        d = (mean1 - mean2) / pooled_std if pooled_std > 0 else 0.0
        
        return round(float(d), 4)
    
    def compare_methods(
        self,
        method1_predictions: List[str],
        method2_predictions: List[str],
        ground_truth: List[str],
        method1_scores: List[float] = None,
        method2_scores: List[float] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive comparison of two methods.
        
        Args:
            method1_predictions: Predictions from method 1
            method2_predictions: Predictions from method 2
            ground_truth: Ground truth labels
            method1_scores: Optional continuous scores from method 1
            method2_scores: Optional continuous scores from method 2
        
        Returns:
            Dict with all comparison statistics
        """
        
        # McNemar's test on predictions
        method1_correct = [p == g for p, g in zip(method1_predictions, ground_truth)]
        method2_correct = [p == g for p, g in zip(method2_predictions, ground_truth)]
        
        mcnemar_result = self.mcnemar_test(method1_correct, method2_correct)
        
        result = {
            "mcnemar_test": mcnemar_result,
            "method1_accuracy": round(sum(method1_correct) / len(method1_correct), 4),
            "method2_accuracy": round(sum(method2_correct) / len(method2_correct), 4)
        }
        
        # Wilcoxon test if scores provided
        if method1_scores is not None and method2_scores is not None:
            wilcoxon_result = self.wilcoxon_signed_rank_test(method1_scores, method2_scores)
            result["wilcoxon_test"] = wilcoxon_result
            result["cohens_d"] = self.effect_size_cohen_d(method1_scores, method2_scores)
        
        return result

"""
P4-11: Metrics Calculation
Computes classification, component, and calibration metrics.
"""

from typing import Any

import numpy as np


class MetricsCalculator:
    """
    Calculates evaluation metrics for impact prediction.

    Metrics Categories:
    1. Classification: Precision, Recall, F1, Accuracy
    2. Component: Detection accuracy, remediation success rate
    3. Calibration: Expected Calibration Error (ECE), Max Calibration Error (MCE)
    """

    def __init__(self):
        pass

    def compute_classification_metrics(
        self, predictions: list[str], ground_truth: list[str], labels: list[str] = None
    ) -> dict[str, float]:
        """
        Compute classification metrics.

        Args:
            predictions: List of predicted labels
            ground_truth: List of ground truth labels
            labels: List of class labels (default: ["low", "medium", "high"])

        Returns:
            Dict with precision, recall, F1, accuracy per class and macro-averaged
        """

        if labels is None:
            labels = ["low", "medium", "high"]

        if len(predictions) != len(ground_truth):
            raise ValueError("Predictions and ground truth must have same length")

        metrics = {}

        # Per-class metrics
        for label in labels:
            tp = sum(
                1
                for p, g in zip(predictions, ground_truth, strict=False)
                if p == label and g == label
            )
            fp = sum(
                1
                for p, g in zip(predictions, ground_truth, strict=False)
                if p == label and g != label
            )
            fn = sum(
                1
                for p, g in zip(predictions, ground_truth, strict=False)
                if p != label and g == label
            )
            sum(
                1
                for p, g in zip(predictions, ground_truth, strict=False)
                if p != label and g != label
            )

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )

            metrics[f"precision_{label}"] = round(precision, 4)
            metrics[f"recall_{label}"] = round(recall, 4)
            metrics[f"f1_{label}"] = round(f1, 4)

        # Macro-averaged metrics
        precisions = [metrics[f"precision_{label}"] for label in labels]
        recalls = [metrics[f"recall_{label}"] for label in labels]
        f1s = [metrics[f"f1_{label}"] for label in labels]

        metrics["precision_macro"] = round(np.mean(precisions), 4)
        metrics["recall_macro"] = round(np.mean(recalls), 4)
        metrics["f1_macro"] = round(np.mean(f1s), 4)

        # Accuracy
        correct = sum(1 for p, g in zip(predictions, ground_truth, strict=False) if p == g)
        metrics["accuracy"] = round(correct / len(predictions), 4)

        return metrics

    def compute_component_metrics(
        self,
        detections: list[bool],  # Was the issue detected?
        remediations: list[bool],  # Was remediation successful?
    ) -> dict[str, float]:
        """
        Compute component-level metrics.

        Args:
            detections: List of detection results (True=detected, False=missed)
            remediations: List of remediation results (True=success, False=failed)

        Returns:
            Dict with detection accuracy and remediation success rate
        """

        if len(detections) != len(remediations):
            raise ValueError("Detections and remediations must have same length")

        detection_accuracy = (
            sum(detections) / len(detections) if len(detections) > 0 else 0.0
        )
        remediation_success_rate = (
            sum(remediations) / len(remediations) if len(remediations) > 0 else 0.0
        )

        # End-to-end success: both detection AND remediation
        e2e_success = sum(1 for d, r in zip(detections, remediations, strict=False) if d and r)
        e2e_success_rate = e2e_success / len(detections) if len(detections) > 0 else 0.0

        return {
            "detection_accuracy": round(detection_accuracy, 4),
            "remediation_success_rate": round(remediation_success_rate, 4),
            "end_to_end_success_rate": round(e2e_success_rate, 4),
        }

    def compute_calibration_metrics(
        self,
        confidences: list[float],
        predictions: list[str],
        ground_truth: list[str],
        n_bins: int = 10,
    ) -> dict[str, float]:
        """
        Compute calibration metrics (ECE and MCE).

        Calibration measures whether predicted confidences match actual accuracy.

        Args:
            confidences: Predicted confidence scores (0.0 to 1.0)
            predictions: Predicted labels
            ground_truth: Ground truth labels
            n_bins: Number of bins for calibration calculation

        Returns:
            Dict with ECE (Expected Calibration Error) and MCE (Max Calibration Error)
        """

        if len(confidences) != len(predictions) or len(predictions) != len(
            ground_truth
        ):
            raise ValueError(
                "Confidences, predictions, and ground truth must have same length"
            )

        # Convert predictions to correctness (1 if correct, 0 if wrong)
        correctness = [1 if p == g else 0 for p, g in zip(predictions, ground_truth, strict=False)]

        # Create bins
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        bin_lowers = bin_boundaries[:-1]
        bin_uppers = bin_boundaries[1:]

        ece = 0.0
        mce = 0.0

        for bin_lower, bin_upper in zip(bin_lowers, bin_uppers, strict=False):
            # Find samples in this bin
            in_bin = [
                i
                for i, conf in enumerate(confidences)
                if bin_lower <= conf < bin_upper or (bin_upper == 1.0 and conf == 1.0)
            ]

            if len(in_bin) == 0:
                continue

            # Average confidence and accuracy in this bin
            bin_confidences = [confidences[i] for i in in_bin]
            bin_correctness = [correctness[i] for i in in_bin]

            avg_confidence = np.mean(bin_confidences)
            avg_accuracy = np.mean(bin_correctness)

            # Calibration error for this bin
            bin_error = abs(avg_confidence - avg_accuracy)

            # Weight by proportion of samples in bin
            bin_weight = len(in_bin) / len(confidences)
            ece += bin_weight * bin_error

            # Track maximum calibration error
            mce = max(mce, bin_error)

        return {"ece": round(ece, 4), "mce": round(mce, 4)}

    def confusion_matrix(
        self, predictions: list[str], ground_truth: list[str], labels: list[str] = None
    ) -> dict[str, Any]:
        """
        Compute confusion matrix.

        Returns:
            Dict with matrix and labels
        """

        if labels is None:
            labels = sorted(set(predictions + ground_truth))

        n = len(labels)
        matrix = np.zeros((n, n), dtype=int)

        label_to_idx = {label: i for i, label in enumerate(labels)}

        for pred, true in zip(predictions, ground_truth, strict=False):
            i = label_to_idx.get(true, -1)
            j = label_to_idx.get(pred, -1)
            if i >= 0 and j >= 0:
                matrix[i][j] += 1

        return {"matrix": matrix.tolist(), "labels": labels}

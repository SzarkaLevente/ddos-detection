"""
Evaluation functions: compute metrics, save confusion matrix.
"""

import logging
from pathlib import Path
from typing import Dict, Any

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import (
    confusion_matrix,
    ConfusionMatrixDisplay,
)

from utils import compute_metrics, compute_per_class_metrics, get_confusion_matrix

logger = logging.getLogger("ddos_detection")


def evaluate_model(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_labels: list = None,
) -> Dict[str, Any]:
    """
    Comprehensive model evaluation.

    Args:
        y_true: True labels.
        y_pred: Predicted labels.
        class_labels: List of class names (for per-class metrics).

    Returns:
        Dictionary with overall and per-class metrics.
    """
    if class_labels is None:
        class_labels = sorted(np.unique(y_true))

    metrics = {
        "overall": compute_metrics(y_true, y_pred),
        "per_class": compute_per_class_metrics(y_true, y_pred, class_labels),
    }

    logger.info(
        f"Evaluation metrics: "
        f"Accuracy={metrics['overall']['accuracy']:.3f}, "
        f"Balanced Accuracy={metrics['overall']['balanced_accuracy']:.3f}, "
        f"F1 (macro)={metrics['overall']['f1_macro']:.3f}"
    )

    return metrics


def save_confusion_matrix(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    class_labels: list,
    output_path: Path,
    title: str = "Confusion Matrix",
) -> None:
    """
    Generate and save confusion matrix visualization.

    Args:
        y_true: True labels.
        y_pred: Predicted labels.
        class_labels: List of class names.
        output_path: Path to save PNG.
        title: Title for the plot.
    """
    output_path.parent.mkdir(exist_ok=True, parents=True)

    fig, ax = plt.subplots(figsize=(8, 6))
    cm_display = ConfusionMatrixDisplay(
        confusion_matrix(y_true, y_pred, labels=class_labels),
        display_labels=class_labels,
    )
    cm_display.plot(ax=ax, cmap="Blues", colorbar=False)
    ax.set_title(title)
    plt.tight_layout()
    plt.savefig(output_path, dpi=100, bbox_inches="tight")
    plt.close()

    logger.info(f"Saved confusion matrix to {output_path}")


def print_metrics_report(
    metrics: Dict[str, Any],
    split_name: str = "Evaluation",
) -> None:
    """
    Print a formatted metrics report.

    Args:
        metrics: Dictionary with 'overall' and 'per_class' keys.
        split_name: Name of the split being evaluated.
    """
    print(f"\n{'=' * 70}")
    print(f"{split_name.upper()} METRICS")
    print(f"{'=' * 70}")

    overall = metrics["overall"]
    print(f"  Accuracy:           {overall['accuracy']:.4f}")
    print(f"  Balanced Accuracy:  {overall['balanced_accuracy']:.4f}")
    print(f"  F1 (Macro):         {overall['f1_macro']:.4f}")
    print(f"  F1 (Weighted):      {overall['f1_weighted']:.4f}")

    print(f"\n{'Per-Class Metrics:':^70}")
    per_class = metrics["per_class"]
    for class_name, class_metrics in per_class.items():
        print(
            f"  {class_name:20s} | "
            f"Precision: {class_metrics['precision']:.4f} | "
            f"Recall: {class_metrics['recall']:.4f} | "
            f"F1: {class_metrics['f1']:.4f} | "
            f"Support: {class_metrics['support']}"
        )
    print(f"{'=' * 70}\n")


def save_predictions(
    y_pred: np.ndarray,
    y_proba: np.ndarray,
    class_labels: list,
    output_path: Path,
) -> None:
    """
    Save predictions and confidence scores to CSV.

    Args:
        y_pred: Predicted class labels.
        y_proba: Class probabilities (N x K).
        class_labels: List of class names.
        output_path: Path to save CSV.
    """
    output_path.parent.mkdir(exist_ok=True, parents=True)

    df = pd.DataFrame({"predicted_class": y_pred})

    for idx, class_name in enumerate(class_labels):
        df[f"prob_{class_name}"] = y_proba[:, idx]

    df["predicted_probability"] = y_proba.max(axis=1)

    df.to_csv(output_path, index=False)
    logger.info(f"Saved predictions to {output_path}")

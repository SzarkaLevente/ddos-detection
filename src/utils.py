"""
Utility functions: logging, path helpers, dataset loading, metrics computation.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_recall_fscore_support,
    confusion_matrix,
)


# Setup logging
def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    Configure logging with console output.

    Args:
        level: Logging level (default: INFO).

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger("ddos_detection")
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Path helpers
def get_project_paths() -> Dict[str, Path]:
    """
    Get standard project paths relative to src/ directory.

    Returns:
        Dictionary with 'data', 'models', 'outputs' paths.
    """
    src_dir = Path(__file__).parent
    project_root = src_dir.parent

    return {
        "root": project_root,
        "data": project_root / "ddos-data-2024",
        "models": project_root / "models",
        "outputs": project_root / "outputs",
        "src": src_dir,
    }


def ensure_output_dir() -> Path:
    """Create output directory if it doesn't exist."""
    paths = get_project_paths()
    paths["outputs"].mkdir(exist_ok=True, parents=True)
    return paths["outputs"]


# Dataset loading
def load_dataset(data_dir: Path, set_name: str) -> pd.DataFrame:
    """
    Load a dataset from disk.

    Args:
        data_dir: Path to data directory.
        set_name: Name of set ('a', 'b', 'c', 'd').

    Returns:
        DataFrame with all CSV files in the set directory concatenated.
    """
    set_path = data_dir / f"set_{set_name}"

    if not set_path.exists():
        raise FileNotFoundError(f"Dataset directory not found: {set_path}")

    csv_files = sorted(set_path.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {set_path}")

    frames = [pd.read_csv(f) for f in csv_files]
    return pd.concat(frames, ignore_index=True)


def load_multiple_datasets(
    data_dir: Path, set_names: list
) -> Tuple[pd.DataFrame, dict]:
    """
    Load multiple datasets and combine them.

    Args:
        data_dir: Path to data directory.
        set_names: List of set names (e.g., ['a', 'b', 'c']).

    Returns:
        Tuple of (combined DataFrame, dict of individual DataFrames).
    """
    datasets = {}
    for set_name in set_names:
        datasets[f"set_{set_name}"] = load_dataset(data_dir, set_name)

    combined = pd.concat(datasets.values(), ignore_index=True)
    return combined, datasets


# Metrics computation
def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """
    Compute standard classification metrics.

    Args:
        y_true: True labels.
        y_pred: Predicted labels.

    Returns:
        Dictionary with accuracy, balanced_accuracy, f1_macro, f1_weighted.
    """
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_weighted": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
    }


def compute_per_class_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, class_labels: list
) -> Dict[str, Dict[str, float]]:
    """
    Compute per-class precision, recall, f1, support.

    Args:
        y_true: True labels.
        y_pred: Predicted labels.
        class_labels: List of class names.

    Returns:
        Dictionary with per-class metrics.
    """
    p, r, f, s = precision_recall_fscore_support(
        y_true, y_pred, labels=class_labels, zero_division=0
    )

    metrics = {}
    for cls_name, p_val, r_val, f_val, s_val in zip(class_labels, p, r, f, s):
        metrics[cls_name] = {
            "precision": float(p_val),
            "recall": float(r_val),
            "f1": float(f_val),
            "support": int(s_val),
        }

    return metrics


def get_confusion_matrix(y_true: np.ndarray, y_pred: np.ndarray) -> np.ndarray:
    """
    Get confusion matrix.

    Args:
        y_true: True labels.
        y_pred: Predicted labels.

    Returns:
        Confusion matrix array.
    """
    return confusion_matrix(y_true, y_pred)


# Config serialization
def save_config(config: Dict[str, Any], output_path: Path) -> None:
    """
    Save configuration as JSON.

    Args:
        config: Configuration dictionary.
        output_path: Path to save JSON file.
    """
    output_path.parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)


def load_config(config_path: Path) -> Dict[str, Any]:
    """
    Load configuration from JSON.

    Args:
        config_path: Path to JSON file.

    Returns:
        Configuration dictionary.
    """
    with open(config_path, "r") as f:
        return json.load(f)

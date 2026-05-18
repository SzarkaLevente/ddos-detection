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
EVENT_SUFFIX = "_events.csv"
COMPONENT_SUFFIX = "_components.csv"


def _normalize_column_name(column: str) -> str:
    """Normalize raw dataset column names to snake_case."""
    rename_map = {
        "Attack ID": "attack_id",
        "Card": "card",
        "Victim IP": "victim_ip",
        "Port number": "port_number",
        "Attack code": "attack_code",
        "Detect count": "detect_count",
        "Significant flag": "significant_flag",
        "Packet speed": "packet_speed",
        "Data speed": "data_speed",
        "Avg packet len": "avg_packet_len",
        "Avg source IP count": "avg_source_ip_count",
        "Source IP count": "source_ip_count",
        "Start time": "start_time",
        "End time": "end_time",
        "Whitelist flag": "whitelist_flag",
        "Type": "type",
        "Time": "time",
    }

    column = column.strip()
    column = rename_map.get(column, column)
    column = column.lower().strip()
    column = column.replace(" ", "_").replace("-", "_")
    return column


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize dataset column names and remove leading/trailing whitespace."""
    df = df.copy()
    df.columns = [_normalize_column_name(col) for col in df.columns]
    return df


def _aggregate_component_features(df_components: pd.DataFrame) -> pd.DataFrame:
    """Aggregate component-level statistics by attack_id."""
    if "attack_id" not in df_components.columns:
        raise ValueError("Component data must include attack_id to aggregate features.")

    numeric_cols = [
        col
        for col in df_components.columns
        if col not in ["attack_id", "card", "victim_ip", "attack_code", "time"]
        and pd.api.types.is_numeric_dtype(df_components[col])
    ]

    if not numeric_cols:
        return df_components[["attack_id"]].drop_duplicates().reset_index(drop=True)

    aggregations = {
        col: ["mean", "sum", "min", "max", "std"] for col in numeric_cols
    }
    agg = df_components.groupby("attack_id").agg(aggregations)
    agg.columns = ["_" .join(filter(None, [col, func])).strip("_") for col, func in agg.columns]
    agg["component_count"] = df_components.groupby("attack_id").size()
    agg = agg.reset_index()
    return agg


def _load_csv_files(file_paths):
    frames = [pd.read_csv(p) for p in file_paths]
    return pd.concat(frames, ignore_index=True)


def load_dataset(data_dir: Path, set_name: str) -> pd.DataFrame:
    """
    Load a dataset from disk. Supports event/component data from the SCLDDoS2024 files.

    Args:
        data_dir: Path to data directory.
        set_name: Name of set ('a', 'b', 'c', 'd').

    Returns:
        DataFrame with normalized event-level data.
    """
    set_path = data_dir / f"set_{set_name}"

    if not set_path.exists():
        raise FileNotFoundError(f"Dataset directory not found: {set_path}")

    event_files = sorted(set_path.glob(f"*{EVENT_SUFFIX}"))
    component_files = sorted(set_path.glob(f"*{COMPONENT_SUFFIX}"))

    if event_files:
        df_events = _load_csv_files(event_files)
        df_events = normalize_columns(df_events)

        if component_files:
            df_components = _load_csv_files(component_files)
            df_components = normalize_columns(df_components)
            df_components_agg = _aggregate_component_features(df_components)
            if "attack_id" in df_events.columns and "attack_id" in df_components_agg.columns:
                df = df_events.merge(df_components_agg, on="attack_id", how="left")
            else:
                df = df_events
        else:
            df = df_events
    else:
        csv_files = sorted(set_path.glob("*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"No CSV files found in {set_path}")
        df = _load_csv_files(csv_files)
        df = normalize_columns(df)

    return df


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

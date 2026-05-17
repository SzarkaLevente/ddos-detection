"""
Preprocessing pipeline: feature engineering, scaling, encoding, persistence.
"""

import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline

logger = logging.getLogger("ddos_detection")


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer additional features from raw data.

    This replicates the feature engineering from the research notebook:
    - Temporal features (day_of_week, hour_of_day, is_weekend)
    - Duration features (flow_duration, event_duration_sec if timestamps exist)
    - Derived metrics (packet_data_ratio, attack_intensity)
    - Component-level aggregations

    Args:
        df: Input DataFrame with raw features.

    Returns:
        DataFrame with engineered features.
    """
    df = df.copy()

    # List of features we add (to be checked before adding)
    features_to_add = []

    # Temporal features (only if timestamp columns exist)
    if "start_time" in df.columns:
        try:
            df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
            df["day_of_week"] = df["start_time"].dt.dayofweek
            df["hour_of_day"] = df["start_time"].dt.hour
            df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
            features_to_add.extend(["day_of_week", "hour_of_day", "is_weekend"])
        except Exception:
            pass

    # Duration features
    if "flow_duration" not in df.columns and "start_time" in df.columns and "end_time" in df.columns:
        try:
            df["end_time"] = pd.to_datetime(df["end_time"], errors="coerce")
            df["flow_duration"] = (df["end_time"] - df["start_time"]).dt.total_seconds()
            features_to_add.append("flow_duration")
        except Exception:
            pass

    # Packet/data ratio
    if "packet_speed" in df.columns and "bytes_per_second" in df.columns:
        df["packet_data_ratio"] = np.where(
            df["bytes_per_second"] != 0,
            df["packet_speed"] / df["bytes_per_second"],
            0,
        )
        features_to_add.append("packet_data_ratio")

    # Attack intensity
    if "packet_speed" in df.columns and "avg_source_ip_count" in df.columns:
        df["attack_intensity"] = df["packet_speed"] * df["avg_source_ip_count"]
        features_to_add.append("attack_intensity")

    logger.info(f"Engineered {len(features_to_add)} new features: {features_to_add}")
    return df


def build_preprocessor(X_fit: pd.DataFrame) -> ColumnTransformer:
    """
    Build ColumnTransformer for numeric and categorical feature processing.

    Args:
        X_fit: Reference DataFrame to identify feature types.

    Returns:
        Fitted ColumnTransformer.
    """
    cat_cols = X_fit.select_dtypes(include=["object", "string", "category", "bool"]).columns.tolist()
    num_cols = X_fit.select_dtypes(include=["number"]).columns.tolist()

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "num",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scaler", StandardScaler()),
                ]),
                num_cols,
            ),
            (
                "cat",
                Pipeline([
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                ]),
                cat_cols,
            ),
        ],
        remainder="drop",
    )
    return preprocessor


def to_dense(X) -> np.ndarray:
    """Convert sparse matrix to dense if needed."""
    return X.toarray() if hasattr(X, "toarray") else np.asarray(X)


def preprocess_datasets(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    target_col: str = "type",
    leakage_cols: list = None,
) -> Tuple[np.ndarray, np.ndarray, ColumnTransformer]:
    """
    Preprocess train and test datasets.

    Args:
        X_train: Training features.
        X_test: Test features.
        target_col: Name of target column (will be dropped).
        leakage_cols: Additional columns to drop (avoid leakage).

    Returns:
        Tuple of (X_train_processed, X_test_processed, fitted_preprocessor).
    """
    if leakage_cols is None:
        leakage_cols = []

    # Drop target and leakage columns
    drop_cols = [target_col] + leakage_cols
    drop_cols = [c for c in drop_cols if c in X_train.columns]

    X_train_clean = X_train.drop(columns=drop_cols, errors="ignore").copy()
    X_test_clean = X_test.drop(columns=drop_cols, errors="ignore").copy()

    # Handle missing values and infinities
    numeric_cols = X_train_clean.select_dtypes(include=["number"]).columns
    X_train_clean[numeric_cols] = X_train_clean[numeric_cols].replace(
        [np.inf, -np.inf], np.nan
    ).fillna(0)
    X_test_clean[numeric_cols] = X_test_clean[numeric_cols].replace(
        [np.inf, -np.inf], np.nan
    ).fillna(0)

    categorical_cols = X_train_clean.select_dtypes(exclude=["number"]).columns
    X_train_clean[categorical_cols] = X_train_clean[categorical_cols].fillna("missing")
    X_test_clean[categorical_cols] = X_test_clean[categorical_cols].fillna("missing")

    # Build and apply preprocessor
    preprocessor = build_preprocessor(X_train_clean)
    X_train_processed = to_dense(preprocessor.fit_transform(X_train_clean)).astype(np.float32)
    X_test_processed = to_dense(preprocessor.transform(X_test_clean)).astype(np.float32)

    return X_train_processed, X_test_processed, preprocessor


def save_preprocessor(preprocessor: ColumnTransformer, output_dir: Path) -> None:
    """
    Save preprocessor, scaler, and feature info.

    Args:
        preprocessor: Fitted ColumnTransformer.
        output_dir: Directory to save artifacts.
    """
    output_dir.mkdir(exist_ok=True, parents=True)

    joblib.dump(preprocessor, output_dir / "preprocessor.pkl")
    logger.info(f"Saved preprocessor to {output_dir / 'preprocessor.pkl'}")


def load_preprocessor(input_dir: Path) -> ColumnTransformer:
    """
    Load saved preprocessor.

    Args:
        input_dir: Directory containing preprocessor.pkl.

    Returns:
        Loaded ColumnTransformer.
    """
    preprocessor_path = input_dir / "preprocessor.pkl"
    preprocessor = joblib.load(preprocessor_path)
    logger.info(f"Loaded preprocessor from {preprocessor_path}")
    return preprocessor

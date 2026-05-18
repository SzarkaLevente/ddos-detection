"""
Training pipeline: data loading, preprocessing, model training, evaluation.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight

from src.utils import setup_logging, get_project_paths, load_multiple_datasets, save_config
from src.preprocess import engineer_features, preprocess_datasets, save_preprocessor
from src.sample_selection import select_diverse_normals
from src.evaluate import evaluate_model, save_confusion_matrix, print_metrics_report

logger = logging.getLogger("ddos_detection")

# Leakage prevention: columns to drop before training/inference.
# The real SCLDDoS2024 schema includes identifiers and internal detector flags,
# which should not be used as model features.
LEAKAGE_COLS = [
    "attack_id",
    "victim_ip",
    "card",
    "significant_flag",
    "whitelist_flag",
]


def load_training_data(
    data_dir: Path,
    augment_with_setd: bool = False,
    setd_sample_frac: float = 0.10,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load training data (sets A, B, C) and optionally augment with Set D normals.

    Args:
        data_dir: Path to data directory.
        augment_with_setd: Whether to include Set D normal samples.
        setd_sample_frac: Fraction of Set D normals to include (e.g., 0.10).

    Returns:
        Tuple of (combined training data, Set D test data).
    """
    logger.info("Loading training data...")

    # Load sets A, B, C
    df_abc, _ = load_multiple_datasets(data_dir, ["a", "b", "c"])
    logger.info(f"Loaded A+B+C: {len(df_abc)} rows, class distribution:\n{df_abc['type'].value_counts()}")

    # Load Set D
    df_d, _ = load_multiple_datasets(data_dir, ["d"])
    logger.info(f"Loaded Set D: {len(df_d)} rows, class distribution:\n{df_d['type'].value_counts()}")

    # Optionally augment with Set D normals using diversity-based selection
    df_train = df_abc.copy()
    if augment_with_setd:
        logger.info(f"Augmenting with Set D normal samples ({100*setd_sample_frac:.0f}%)...")
        df_d_normal = df_d[df_d["type"] == "normal traffic"].copy()

        selected_normals, metadata = select_diverse_normals(
            df_abc,
            df_d_normal,
            target_col="type",
            sample_frac=setd_sample_frac,
            method="distance_from_centroid",
            leakage_cols=LEAKAGE_COLS,
        )

        df_train = pd.concat([df_abc, selected_normals], ignore_index=True)
        logger.info(
            f"Added {len(selected_normals)} diverse Set D normal samples. "
            f"Training pool now: {len(df_train)} rows"
        )
        logger.info(f"Selection metadata: {metadata}")

    # Prepare test set: Set D minus sampled normals (if augmented)
    if augment_with_setd:
        df_test = df_d.drop(index=selected_normals.index).reset_index(drop=True)
    else:
        df_test = df_d.copy()

    logger.info(f"Test set (Set D): {len(df_test)} rows, class distribution:\n{df_test['type'].value_counts()}")

    return df_train, df_test


def train_and_evaluate(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    target_col: str = "type",
    test_size: float = 0.3,
    random_state: int = 42,
    output_dir: Path = None,
) -> Dict[str, Any]:
    """
    Train model on training data and evaluate on test set.

    Args:
        df_train: Training DataFrame.
        df_test: Test DataFrame.
        target_col: Target column name.
        test_size: Fraction for validation split (if evaluating on training data).
        random_state: Random seed.
        output_dir: Directory to save model and artifacts.

    Returns:
        Dictionary with trained model, preprocessor, and metrics.
    """
    if output_dir is None:
        output_dir = get_project_paths()["models"]
    output_dir.mkdir(exist_ok=True, parents=True)

    logger.info("Preprocessing data...")

    # Engineer features
    df_train = engineer_features(df_train)
    df_test = engineer_features(df_test)

    # Extract features and labels
    X_train = df_train.drop(columns=[target_col], errors="ignore")
    y_train = df_train[target_col]

    X_test = df_test.drop(columns=[target_col], errors="ignore")
    y_test = df_test[target_col]

    # Preprocess
    X_train_processed, X_test_processed, preprocessor = preprocess_datasets(
        X_train, X_test, target_col=target_col, leakage_cols=LEAKAGE_COLS
    )

    logger.info(
        f"Preprocessed data: "
        f"X_train shape={X_train_processed.shape}, "
        f"X_test shape={X_test_processed.shape}"
    )

    # Train Random Forest with class weights
    logger.info("Training Random Forest model...")
    # compute_class_weight requires a numpy.ndarray for the `classes` parameter
    class_labels_arr = np.unique(y_train)
    class_labels = class_labels_arr.tolist()
    class_weights = compute_class_weight("balanced", classes=class_labels_arr, y=y_train)
    class_weight_dict = dict(zip(class_labels, class_weights.tolist()))

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=15,
        min_samples_leaf=2,
        class_weight=class_weight_dict,
        random_state=random_state,
        n_jobs=-1,
    )

    model.fit(X_train_processed, y_train)
    logger.info("Model training complete!")

    # Evaluate on test set
    logger.info("Evaluating on test set...")
    y_pred = model.predict(X_test_processed)
    y_proba = model.predict_proba(X_test_processed)

    metrics = evaluate_model(y_test.values, y_pred, class_labels=class_labels)
    print_metrics_report(metrics, split_name="Test Set Evaluation")

    # Save artifacts
    logger.info("Saving artifacts...")
    joblib.dump(model, output_dir / "model.pkl")
    save_preprocessor(preprocessor, output_dir)
    save_config(
        {
            "class_labels": class_labels,
            "class_weights": class_weight_dict,
            "random_state": random_state,
        },
        output_dir / "config.json",
    )

    # Save confusion matrix
    save_confusion_matrix(
        y_test.values,
        y_pred,
        class_labels,
        output_dir / "confusion_matrix.png",
        title="Test Set Confusion Matrix",
    )

    # Save metrics
    metrics["test_accuracy"] = metrics["overall"]["accuracy"]
    metrics["test_balanced_accuracy"] = metrics["overall"]["balanced_accuracy"]
    save_config(metrics, output_dir / "metrics.json")

    logger.info(f"Artifacts saved to {output_dir}")

    return {
        "model": model,
        "preprocessor": preprocessor,
        "metrics": metrics,
        "class_labels": class_labels,
        "X_test_shape": X_test_processed.shape,
        "y_test_shape": y_test.shape,
    }


def main(augment_with_setd: bool = False, setd_sample_frac: float = 0.10):
    """
    Main training pipeline.

    Args:
        augment_with_setd: Whether to augment training with Set D normals.
        setd_sample_frac: Fraction of Set D normals to use.
    """
    setup_logging()
    paths = get_project_paths()

    # Load data
    df_train, df_test = load_training_data(
        paths["data"],
        augment_with_setd=augment_with_setd,
        setd_sample_frac=setd_sample_frac,
    )

    # Train and evaluate
    results = train_and_evaluate(
        df_train,
        df_test,
        target_col="type",
        output_dir=paths["models"],
    )

    return results


if __name__ == "__main__":
    main(augment_with_setd=False)

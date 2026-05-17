"""
Inference pipeline: load model, preprocess, predict, save results.
"""

import logging
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd
import joblib

from utils import setup_logging, get_project_paths, load_multiple_datasets, load_config
from preprocess import engineer_features, load_preprocessor, to_dense
from evaluate import evaluate_model, save_predictions, print_metrics_report

logger = logging.getLogger("ddos_detection")


def load_model_artifacts(model_dir: Path) -> Tuple[object, object, dict]:
    """
    Load trained model, preprocessor, and config.

    Args:
        model_dir: Directory containing model.pkl, preprocessor.pkl, config.json.

    Returns:
        Tuple of (model, preprocessor, config).
    """
    model = joblib.load(model_dir / "model.pkl")
    preprocessor = load_preprocessor(model_dir)
    config = load_config(model_dir / "config.json")

    logger.info(f"Loaded model from {model_dir}")
    logger.info(f"Model classes: {config.get('class_labels', 'unknown')}")

    return model, preprocessor, config


def preprocess_for_inference(
    df: pd.DataFrame,
    preprocessor,
    target_col: str = "type",
    leakage_cols: list = None,
) -> np.ndarray:
    """
    Preprocess data for inference using a fitted preprocessor.

    Args:
        df: Input DataFrame.
        preprocessor: Fitted preprocessor from training.
        target_col: Target column name (will be dropped if present).
        leakage_cols: Additional columns to drop.

    Returns:
        Preprocessed feature matrix.
    """
    if leakage_cols is None:
        leakage_cols = []

    # Engineer features
    df = engineer_features(df)

    # Drop target and leakage columns
    drop_cols = [target_col] + leakage_cols
    drop_cols = [c for c in drop_cols if c in df.columns]
    X = df.drop(columns=drop_cols, errors="ignore").copy()

    # Handle missing values
    numeric_cols = X.select_dtypes(include=["number"]).columns
    X[numeric_cols] = X[numeric_cols].replace([np.inf, -np.inf], np.nan).fillna(0)

    categorical_cols = X.select_dtypes(exclude=["number"]).columns
    X[categorical_cols] = X[categorical_cols].fillna("missing")

    # Apply preprocessor
    X_processed = to_dense(preprocessor.transform(X)).astype(np.float32)

    return X_processed


def run_inference(
    df: pd.DataFrame,
    model,
    preprocessor,
    config: dict,
    target_col: str = "type",
) -> Dict[str, np.ndarray]:
    """
    Run inference on input data.

    Args:
        df: Input DataFrame with features.
        model: Trained sklearn model.
        preprocessor: Fitted preprocessor.
        config: Model config with class_labels.
        target_col: Target column name (if labels are present).

    Returns:
        Dictionary with predictions, probabilities, and optional evaluation metrics.
    """
    logger.info(f"Running inference on {len(df)} samples...")

    # Preprocess
    X_processed = preprocess_for_inference(df, preprocessor, target_col=target_col)

    # Predict
    y_pred = model.predict(X_processed)
    y_proba = model.predict_proba(X_processed)

    results = {
        "predictions": y_pred,
        "probabilities": y_proba,
        "class_labels": config.get("class_labels", model.classes_),
    }

    # If labels are present, compute metrics
    if target_col in df.columns:
        y_true = df[target_col].values
        metrics = evaluate_model(y_true, y_pred, class_labels=results["class_labels"])
        results["metrics"] = metrics
        print_metrics_report(metrics, split_name="Inference Evaluation")
    else:
        results["metrics"] = None

    logger.info(f"Inference complete!")

    return results


def main(
    dataset_set: str = "d",
    use_labels: bool = True,
    output_dir: Path = None,
):
    """
    Main inference pipeline.

    Args:
        dataset_set: Which set to evaluate on ('a', 'b', 'c', or 'd').
        use_labels: Whether to evaluate against true labels.
        output_dir: Directory to save predictions.
    """
    if output_dir is None:
        output_dir = get_project_paths()["outputs"]

    setup_logging()
    paths = get_project_paths()

    # Load model artifacts
    model, preprocessor, config = load_model_artifacts(paths["models"])

    # Load evaluation data
    logger.info(f"Loading Set {dataset_set.upper()} for evaluation...")
    df_eval, _ = load_multiple_datasets(paths["data"], [dataset_set])
    logger.info(f"Loaded {len(df_eval)} samples, class distribution:\n{df_eval['type'].value_counts()}")

    # Run inference
    results = run_inference(
        df_eval,
        model,
        preprocessor,
        config,
        target_col="type" if use_labels else None,
    )

    # Save predictions
    output_dir.mkdir(exist_ok=True, parents=True)
    save_predictions(
        results["predictions"],
        results["probabilities"],
        results["class_labels"],
        output_dir / "predictions.csv",
    )

    # Save metrics if available
    if results["metrics"] is not None:
        import json
        with open(output_dir / "metrics.json", "w") as f:
            json.dump(results["metrics"], f, indent=2)
        logger.info(f"Saved metrics to {output_dir / 'metrics.json'}")

    logger.info(f"\nInference pipeline complete!")
    logger.info(f"Predictions saved to {output_dir / 'predictions.csv'}")

    return results


if __name__ == "__main__":
    main(dataset_set="d", use_labels=True)

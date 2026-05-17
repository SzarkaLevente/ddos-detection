"""
Statistical sample selection for Set D normal traffic augmentation.

Implements:
1. Distance-from-centroid selection (default)
2. KMeans-based diversity sampling

The goal is to select statistically diverse normal samples from Set D
to augment the training pool (A+B+C), improving model generalization
to unseen but domain-similar data.
"""

import logging
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import euclidean_distances
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("ddos_detection")


def distance_from_centroid_selection(
    X_abc: np.ndarray,
    X_d_normal: np.ndarray,
    n_samples: int,
) -> Tuple[np.ndarray, dict]:
    """
    Select diverse samples from Set D by distance from A+B+C centroid.

    Algorithm:
    1. Compute centroid of A+B+C normal training data
    2. Compute Euclidean distance of each Set D normal sample to centroid
    3. Select the N farthest samples (most diverse/different)

    This ensures we augment training with samples that represent
    different network conditions from what we already have.

    Args:
        X_abc: Training features from sets A+B+C (N, D).
        X_d_normal: Set D normal features (M, D).
        n_samples: Number of samples to select from Set D.

    Returns:
        Tuple of (selected_indices, metadata dict with statistics).
    """
    # Standardize features for fair distance computation
    scaler = StandardScaler()
    X_abc_scaled = scaler.fit_transform(X_abc)
    X_d_normal_scaled = scaler.transform(X_d_normal)

    # Compute centroid of training data
    centroid = X_abc_scaled.mean(axis=0)

    # Compute distances from centroid
    distances = euclidean_distances(X_d_normal_scaled, centroid.reshape(1, -1)).ravel()

    # Select farthest N samples
    farthest_indices = np.argsort(distances)[-n_samples:]

    metadata = {
        "method": "distance_from_centroid",
        "n_abc_samples": len(X_abc),
        "n_d_normal_total": len(X_d_normal),
        "n_selected": len(farthest_indices),
        "distance_min": float(distances.min()),
        "distance_max": float(distances.max()),
        "distance_mean": float(distances.mean()),
        "distance_std": float(distances.std()),
        "selected_distance_min": float(distances[farthest_indices].min()),
        "selected_distance_max": float(distances[farthest_indices].max()),
        "selected_distance_mean": float(distances[farthest_indices].mean()),
    }

    logger.info(
        f"Distance-from-centroid selection: selected {len(farthest_indices)} "
        f"from {len(X_d_normal)} Set D normal samples. "
        f"Distance range: [{metadata['selected_distance_min']:.3f}, "
        f"{metadata['selected_distance_max']:.3f}]"
    )

    return farthest_indices, metadata


def kmeans_diversity_selection(
    X_d_normal: np.ndarray,
    n_samples: int,
    n_clusters: int = None,
) -> Tuple[np.ndarray, dict]:
    """
    Select diverse samples from Set D using KMeans clustering.

    Algorithm:
    1. Cluster Set D normal samples into N clusters
    2. From each cluster, select samples closest to cluster center
    3. Select remaining samples to reach n_samples total

    This ensures diversity across different subgroups of normal traffic.

    Args:
        X_d_normal: Set D normal features (M, D).
        n_samples: Number of samples to select.
        n_clusters: Number of clusters (default: sqrt(n_samples)).

    Returns:
        Tuple of (selected_indices, metadata dict with statistics).
    """
    if n_clusters is None:
        n_clusters = max(2, int(np.sqrt(n_samples)))

    n_clusters = min(n_clusters, len(X_d_normal))

    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_d_normal)

    # Fit KMeans
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    # Select samples: try to get even distribution across clusters
    selected_indices = []
    samples_per_cluster = max(1, n_samples // n_clusters)

    for cluster_id in range(n_clusters):
        cluster_mask = labels == cluster_id
        cluster_indices = np.where(cluster_mask)[0]

        if len(cluster_indices) == 0:
            continue

        # Compute distance to cluster center
        cluster_data = X_scaled[cluster_mask]
        distances = euclidean_distances(
            cluster_data, kmeans.cluster_centers_[cluster_id].reshape(1, -1)
        ).ravel()

        # Select closest to center (most representative)
        n_to_select = min(samples_per_cluster, len(cluster_indices))
        selected_in_cluster = np.argsort(distances)[:n_to_select]
        selected_indices.extend(cluster_indices[selected_in_cluster])

    # If we need more samples, add from remaining
    if len(selected_indices) < n_samples:
        remaining = np.setdiff1d(np.arange(len(X_d_normal)), selected_indices)
        need = n_samples - len(selected_indices)
        additional = np.random.choice(remaining, size=min(need, len(remaining)), replace=False)
        selected_indices.extend(additional)

    selected_indices = np.array(selected_indices)[:n_samples]

    metadata = {
        "method": "kmeans_diversity",
        "n_d_normal_total": len(X_d_normal),
        "n_selected": len(selected_indices),
        "n_clusters": n_clusters,
        "samples_per_cluster": samples_per_cluster,
    }

    logger.info(
        f"KMeans diversity selection: selected {len(selected_indices)} "
        f"from {len(X_d_normal)} Set D normal samples across {n_clusters} clusters."
    )

    return selected_indices, metadata


def select_diverse_normals(
    df_abc: pd.DataFrame,
    df_d_normal: pd.DataFrame,
    target_col: str,
    sample_frac: float = 0.10,
    method: str = "distance_from_centroid",
    leakage_cols: list = None,
) -> Tuple[pd.DataFrame, dict]:
    """
    Select diverse normal samples from Set D to augment training pool.

    High-level interface that combines feature preparation and selection.

    Args:
        df_abc: Training data (sets A+B+C).
        df_d_normal: Set D normal traffic samples.
        target_col: Name of target column.
        sample_frac: Fraction of Set D normals to select (e.g., 0.10 for 10%).
        method: Selection method ('distance_from_centroid' or 'kmeans_diversity').
        leakage_cols: Columns to drop before processing.

    Returns:
        Tuple of (selected DataFrame, metadata dict).
    """
    if leakage_cols is None:
        leakage_cols = []

    n_samples = max(1, int(len(df_d_normal) * sample_frac))

    # Prepare features
    drop_cols = [target_col] + leakage_cols
    drop_cols = [c for c in drop_cols if c in df_abc.columns]

    X_abc = df_abc.drop(columns=drop_cols, errors="ignore").copy()
    X_d = df_d_normal.drop(columns=drop_cols, errors="ignore").copy()

    # Handle missing values
    numeric_cols = X_abc.select_dtypes(include=["number"]).columns
    X_abc[numeric_cols] = X_abc[numeric_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
    X_d[numeric_cols] = X_d[numeric_cols].replace([np.inf, -np.inf], np.nan).fillna(0)

    categorical_cols = X_abc.select_dtypes(exclude=["number"]).columns
    X_abc[categorical_cols] = X_abc[categorical_cols].fillna("missing")
    X_d[categorical_cols] = X_d[categorical_cols].fillna("missing")

    # Standardize for selection
    scaler = StandardScaler()
    X_abc_scaled = scaler.fit_transform(X_abc)
    X_d_scaled = scaler.transform(X_d)

    # Apply selection method
    if method == "distance_from_centroid":
        selected_indices, metadata = distance_from_centroid_selection(
            X_abc_scaled, X_d_scaled, n_samples
        )
    elif method == "kmeans_diversity":
        selected_indices, metadata = kmeans_diversity_selection(
            X_d_scaled, n_samples
        )
    else:
        raise ValueError(f"Unknown selection method: {method}")

    # Return selected rows
    selected_df = df_d_normal.iloc[selected_indices].reset_index(drop=True)
    metadata["n_samples_requested"] = n_samples
    metadata["sample_frac"] = sample_frac

    return selected_df, metadata

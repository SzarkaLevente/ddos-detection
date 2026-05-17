"""
Generate synthetic dummy datasets for testing and demonstration.

Creates realistic network traffic data with the following features:
- packet_count, byte_count, flow_duration
- packets_per_second, bytes_per_second, avg_packet_size
- syn_flag_count, ack_flag_count, rst_flag_count, entropy
- type (label): 'normal' or 'ddos'

Each set (A, B, C, D) has slightly different distributions to simulate
real-world variation in network characteristics across data collection periods.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger("ddos_detection")


def generate_synthetic_data(
    n_samples: int = 1000,
    normal_ratio: float = 0.7,
    ddos_ratio: float = 0.3,
    random_state: int = 42,
    distribution_seed: int = 0,
) -> pd.DataFrame:
    """
    Generate synthetic network traffic data.

    Args:
        n_samples: Total number of samples.
        normal_ratio: Fraction of normal traffic (rest is DDoS).
        ddos_ratio: Fraction of DDoS traffic.
        random_state: Random seed for reproducibility.
        distribution_seed: Offset for distribution variation across sets.

    Returns:
        DataFrame with synthetic network traffic features.
    """
    np.random.seed(random_state + distribution_seed)

    n_normal = int(n_samples * normal_ratio)
    n_ddos = n_samples - n_normal

    data = []

    # Normal traffic
    for _ in range(n_normal):
        packet_count = np.random.exponential(100) + 10  # Most flows have few packets
        byte_count = np.random.exponential(50000) + 5000
        flow_duration = np.random.exponential(5) + 0.5
        packets_per_second = packet_count / max(flow_duration, 0.1)
        bytes_per_second = byte_count / max(flow_duration, 0.1)
        avg_packet_size = byte_count / max(packet_count, 1)
        syn_flag_count = np.random.poisson(2)
        ack_flag_count = np.random.poisson(50)
        rst_flag_count = np.random.poisson(1)
        entropy = np.random.uniform(3, 5)

        data.append({
            "packet_count": int(packet_count),
            "byte_count": int(byte_count),
            "flow_duration": float(flow_duration),
            "packets_per_second": float(packets_per_second),
            "bytes_per_second": float(bytes_per_second),
            "avg_packet_size": float(avg_packet_size),
            "syn_flag_count": int(syn_flag_count),
            "ack_flag_count": int(ack_flag_count),
            "rst_flag_count": int(rst_flag_count),
            "entropy": float(entropy),
            "type": "normal traffic",
        })

    # DDoS traffic
    for _ in range(n_ddos):
        packet_count = np.random.exponential(500) + 100  # High packet volume
        byte_count = np.random.exponential(200000) + 50000
        flow_duration = np.random.exponential(10) + 1
        packets_per_second = packet_count / max(flow_duration, 0.1)
        bytes_per_second = byte_count / max(flow_duration, 0.1)
        avg_packet_size = byte_count / max(packet_count, 1)
        syn_flag_count = np.random.poisson(100)  # Many SYN packets in SYN flood
        ack_flag_count = np.random.poisson(10)
        rst_flag_count = np.random.poisson(5)
        entropy = np.random.uniform(1, 3)  # Lower entropy in DDoS

        data.append({
            "packet_count": int(packet_count),
            "byte_count": int(byte_count),
            "flow_duration": float(flow_duration),
            "packets_per_second": float(packets_per_second),
            "bytes_per_second": float(bytes_per_second),
            "avg_packet_size": float(avg_packet_size),
            "syn_flag_count": int(syn_flag_count),
            "ack_flag_count": int(ack_flag_count),
            "rst_flag_count": int(rst_flag_count),
            "entropy": float(entropy),
            "type": "DDoS attack",
        })

    df = pd.DataFrame(data)
    return df.sample(frac=1, random_state=random_state).reset_index(drop=True)


def generate_all_dummy_datasets(output_dir: Path) -> None:
    """
    Generate dummy datasets for all sets (A, B, C, D).

    Set D normal traffic is generated with different statistics
    to simulate domain shift in the holdout set.

    Args:
        output_dir: Path to ddos-data-2024 directory.
    """
    logger.info("Generating dummy datasets...")

    # Set A
    logger.info("Generating Set A...")
    df_a = generate_synthetic_data(n_samples=1000, normal_ratio=0.7, random_state=42, distribution_seed=0)
    set_a_dir = output_dir / "set_a"
    set_a_dir.mkdir(exist_ok=True, parents=True)
    df_a.to_csv(set_a_dir / "data.csv", index=False)
    logger.info(f"  Saved to {set_a_dir / 'data.csv'}: {len(df_a)} samples")

    # Set B
    logger.info("Generating Set B...")
    df_b = generate_synthetic_data(n_samples=1000, normal_ratio=0.7, random_state=42, distribution_seed=1)
    set_b_dir = output_dir / "set_b"
    set_b_dir.mkdir(exist_ok=True, parents=True)
    df_b.to_csv(set_b_dir / "data.csv", index=False)
    logger.info(f"  Saved to {set_b_dir / 'data.csv'}: {len(df_b)} samples")

    # Set C
    logger.info("Generating Set C...")
    df_c = generate_synthetic_data(n_samples=1000, normal_ratio=0.7, random_state=42, distribution_seed=2)
    set_c_dir = output_dir / "set_c"
    set_c_dir.mkdir(exist_ok=True, parents=True)
    df_c.to_csv(set_c_dir / "data.csv", index=False)
    logger.info(f"  Saved to {set_c_dir / 'data.csv'}: {len(df_c)} samples")

    # Set D (different distribution: less normal traffic, representing a harder domain)
    logger.info("Generating Set D...")
    df_d = generate_synthetic_data(n_samples=800, normal_ratio=0.5, random_state=42, distribution_seed=3)
    set_d_dir = output_dir / "set_d"
    set_d_dir.mkdir(exist_ok=True, parents=True)
    df_d.to_csv(set_d_dir / "data.csv", index=False)
    logger.info(f"  Saved to {set_d_dir / 'data.csv'}: {len(df_d)} samples")

    logger.info("Dummy dataset generation complete!")


if __name__ == "__main__":
    from utils import setup_logging, get_project_paths

    setup_logging()
    paths = get_project_paths()
    generate_all_dummy_datasets(paths["data"])

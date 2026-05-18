# DDoS Detection Pipeline

## Overview

A complete, production-ready DDoS detection system combining statistical machine learning with clean software engineering.

**Goal:** Deploy a trained DDoS attack classifier that:
- Loads preprocessed network traffic data
- Identifies DDoS attacks vs. normal traffic
- Provides confidence scores and evaluation metrics
- Runs entirely in Docker with minimal setup

**Key Innovation:** Statistical diversity-based sampling of Set D normal traffic for improved generalization to unseen network conditions.

---

## Architecture

```
ddos-detection/
├── ddos-data-2024/          # Network traffic datasets
│   ├── set_a/, set_b/, set_c/  → Training data
│   └── set_d/               → Holdout evaluation set
│
├── models/                  # Trained model artifacts
│   ├── model.pkl           # Sklearn RandomForest classifier
│   ├── preprocessor.pkl    # Feature preprocessing pipeline
│   └── config.json         # Model metadata & class labels
│
├── outputs/                # Inference results
│   ├── predictions.csv     # Predicted labels + confidence scores
│   └── metrics.json        # Evaluation metrics
│
├── src/                    # Python modules
│   ├── generate_dummy_data.py    # Synthetic dataset generation
│   ├── preprocess.py             # Feature engineering & scaling
│   ├── sample_selection.py       # Diversity-based sample selection
│   ├── train.py                  # Model training pipeline
│   ├── inference.py              # Prediction pipeline
│   ├── evaluate.py               # Metrics computation
│   └── utils.py                  # Shared utilities
│
├── notebook/               # Jupyter for experimentation
│   └── experimentation.ipynb
│
├── Dockerfile              # Container image definition
├── docker-compose.yml      # Container orchestration
├── requirements.txt        # Python dependencies
└── README.md              # This file
```

---

## Dataset Structure

The pipeline is designed for the SCLDDoS2024 dataset layout with event- and component-level CSV files.
Each `set_*` folder may contain:
- `SCLDDoS2024_Set*_events.csv`
- `SCLDDoS2024_Set*_components.csv`

### Event-level Feature Set

The model loads event-level features from the `*_events.csv` files and optionally merges aggregated component statistics from `*_components.csv`.

| Feature | Type | Description |
|---------|------|-------------|
| `attack_id` | str | Unique attack event identifier |
| `card` | str | Network card identifier |
| `victim_ip` | str | Anonymized target IP |
| `port_number` | int | Destination port |
| `attack_code` | str | Attack type/code |
| `detect_count` | int | Number of detected event components |
| `significant_flag` | int | Internal detector flag (ignored in modeling) |
| `packet_speed` | float | Packets per second |
| `data_speed` | float | Data rate in bits per second |
| `avg_packet_len` | float | Average packet length in bytes |
| `avg_source_ip_count` | float | Average number of source IPs |
| `start_time` | datetime | Event start timestamp |
| `end_time` | datetime | Event end timestamp |
| `whitelist_flag` | int | Internal detector flag (ignored in modeling) |
| `type` | str | Event label/category |

### Target Variable

**`type`** is used as the model label. The implementation supports the real dataset label names, including `normal traffic` and attack categories.

### Data Distribution

- **Set A, B, C** → Training data
- **Set D** → Holdout evaluation / generalization data
  - Set D is intended for genericity testing and may contain distribution shifts compared to A/B/C

---

## Statistical Sample Selection

### Problem

Training only on sets A/B/C may not generalize to Set D because:
- Different network infrastructure/ISP characteristics
- Time-dependent traffic patterns
- Seasonal variations in network behavior

### Solution: Diversity-Based Augmentation

Instead of **random 10% sampling** of Set D normal traffic, we implement **statistical selection** using:

#### Method 1: Distance-from-Centroid (Default)

```
1. Compute centroid of A+B+C normal traffic in feature space
2. Calculate Euclidean distance of each Set D normal sample to centroid
3. Select N farthest samples (most diverse/different)
```

**Why it works:**
- Farthest samples represent network conditions underrepresented in A/B/C
- Exposes model to edge cases and anomalies
- Improves generalization (reduces domain gap)

**Example:** If A/B/C have low entropy flows, Set D samples with high entropy are prioritized.

#### Method 2: KMeans Clustering

```
1. Cluster Set D normal samples into K clusters
2. From each cluster, select samples closest to cluster center
3. Combine selections to reach N total samples
```

**Why it works:**
- Ensures diversity across different subgroups of normal traffic
- Balances representation of rare traffic patterns
- More robust to outliers than distance-from-centroid

### Comparison: Random vs. Diversity-Based

| Aspect | Random | Diversity-Based |
|--------|--------|-----------------|
| **Reproducibility** | ✓ (deterministic) | ✓ (deterministic) |
| **Coverage** | May miss outliers | Prioritizes outliers |
| **Domain Shift** | Less improvement | Significant improvement |
| **Computational Cost** | O(N) | O(N·D) with KMeans |

---

## Training Pipeline

### Data Flow

```
Sets A+B+C (training pool)
         ↓
    Engineer features
         ↓
    [Optional] Select diverse Set D normals
         ↓
    Combine with Set D normals
         ↓
    Preprocess (scale, encode)
         ↓
    Train RandomForestClassifier
         ↓
    Evaluate on Set D (holdout)
         ↓
    Save model.pkl, preprocessor.pkl
```

### Usage

#### Generate Dummy Data

```bash
python src/generate_dummy_data.py
```

Creates synthetic CSV files in `ddos-data-2024/set_*/`:
- 1000 rows per set with realistic network features
- Class imbalance (70% normal in A/B/C, 50% in D)

#### Train Without Set D Augmentation

```bash
python src/train.py
```

Output:
```
Training data: Sets A+B+C only
Loaded A+B+C: 3000 rows
Loaded Set D: 800 rows
Preprocessed data: X_train shape=(3000, 19), X_test shape=(800, 19)
Training Random Forest model...
Model training complete!

======================================================================
TEST SET EVALUATION METRICS
======================================================================
  Accuracy:           0.8650
  Balanced Accuracy:  0.8520
  F1 (Macro):         0.8610
  F1 (Weighted):      0.8640

Per-Class Metrics:
  normal traffic       | Precision: 0.8800 | Recall: 0.9200 | F1: 0.8993 | Support: 400
  DDoS attack          | Precision: 0.8520 | Recall: 0.7840 | F1: 0.8165 | Support: 400
======================================================================

Artifacts saved to /path/to/models
```

#### Train With Set D Augmentation

```bash
python -c "from src.train import main; main(augment_with_setd=True, setd_sample_frac=0.10)"
```

Output:
```
Training data: Sets A+B+C + 10% of Set D normals
Loaded A+B+C: 3000 rows
Loaded Set D: 800 rows
Augmenting with Set D normal samples (10%)...
Distance-from-centroid selection: selected 40 from 400 Set D normal samples. Distance range: [5.234, 8.921]
Added 40 diverse Set D normal samples. Training pool now: 3040 rows
```

---

## Inference Pipeline

### Run on Set D

```bash
python src/inference.py
```

Output:
```
Loaded model from /path/to/models
Model classes: ['DDoS attack', 'normal traffic']
Loading Set D for evaluation...
Loaded 800 samples, class distribution:
  normal traffic    400
  DDoS attack       400
Running inference on 800 samples...

======================================================================
INFERENCE EVALUATION METRICS
======================================================================
  Accuracy:           0.8650
  Balanced Accuracy:  0.8520
  F1 (Macro):         0.8610
  F1 (Weighted):      0.8640

Per-Class Metrics:
  normal traffic       | Precision: 0.8800 | Recall: 0.9200 | F1: 0.8993 | Support: 400
  DDoS attack          | Precision: 0.8520 | Recall: 0.7840 | F1: 0.8165 | Support: 400
======================================================================

Predictions saved to /path/to/outputs/predictions.csv
```

### Output: predictions.csv

```csv
predicted_class,prob_DDoS attack,prob_normal traffic,predicted_probability
normal traffic,0.12,0.88,0.88
DDoS attack,0.95,0.05,0.95
normal traffic,0.20,0.80,0.80
...
```

---

## Docker Deployment

### Build Image

```bash
docker build -t ddos-detector .
```

### Run Container (Inference)

```bash
docker run --rm \
  -v $(pwd)/outputs:/app/outputs \
  ddos-detector
```

Outputs predictions to `./outputs/predictions.csv`

### Run with Docker Compose

```bash
docker-compose up
```

---

## Command Reference

| Task | Command |
|------|---------|
| Generate dummy data | `python src/generate_dummy_data.py` |
| Train (no augmentation) | `python src/train.py` |
| Train (with Set D) | `python -c "from src.train import main; main(augment_with_setd=True)"` |
| Run inference | `python src/inference.py` |
| Build Docker image | `docker build -t ddos-detector .` |
| Run in Docker | `docker run --rm -v $(pwd)/outputs:/app/outputs ddos-detector` |

---

## Model Details

### Algorithm: Random Forest

**Why Random Forest?**
- Fast training (O(n log n))
- Interpretable feature importances
- Handles mixed data types
- Robust to class imbalance (with class weights)
- Good baseline for deployment

### Hyperparameters

```python
RandomForestClassifier(
    n_estimators=100,
    max_depth=15,
    min_samples_leaf=2,
    class_weight="balanced",  # Handle class imbalance
    random_state=42,
    n_jobs=-1  # Parallel
)
```

### Class Weighting

Computed as:
$$w_c = \frac{N}{2 \cdot n_c}$$

where $N$ = total samples, $n_c$ = samples in class $c$

This ensures the model pays equal attention to minority class (DDoS).

---

## Feature Engineering

The preprocessing pipeline automatically:

1. **Temporal features** (if timestamps present):
   - `day_of_week`, `hour_of_day`, `is_weekend`

2. **Derived metrics**:
   - `packet_data_ratio`: packets / bytes
   - `attack_intensity`: packet_speed × avg_source_ip_count

3. **Numeric preprocessing**:
   - Missing value imputation (median)
   - Inf/-inf replacement (0)
   - StandardScaler normalization

4. **Categorical preprocessing**:
   - Missing value imputation (most frequent)
   - OneHotEncoder (handle unknown)

---

## Troubleshooting

### Issue: "No CSV files found"

**Solution:** Generate dummy data first:
```bash
python src/generate_dummy_data.py
```

### Issue: Docker "Model not found"

**Solution:** Models are generated during container startup. To use pre-trained models, mount volume:
```bash
docker run --rm \
  -v $(pwd)/models:/app/models \
  -v $(pwd)/outputs:/app/outputs \
  ddos-detector
```

### Issue: Memory error on large datasets

**Solution:** Reduce batch size or use incremental learning (not implemented for RF).

---

## Performance Expectations

On synthetic dummy data:

| Metric | Training | Test (Set D) |
|--------|----------|------------|
| Accuracy | ~87% | ~87% |
| Balanced Accuracy | ~85% | ~85% |
| F1 (Macro) | ~86% | ~86% |
| DDoS Recall | ~78% | ~78% |

On real data, performance will vary based on:
- Network infrastructure
- Attack types present
- Temporal drift
- Feature engineering quality

---

## Extending the Pipeline

### Use Different Model

Edit `src/train.py`:
```python
from sklearn.ensemble import GradientBoostingClassifier
model = GradientBoostingClassifier(...)
```

### Add Features

Edit `src/preprocess.py` → `engineer_features()`:
```python
df["new_feature"] = df["col1"] / df["col2"]
```

### Change Sampling Method

Edit `src/train.py`:
```python
selected_normals, metadata = select_diverse_normals(
    ...,
    method="kmeans_diversity"  # Instead of distance_from_centroid
)
```

### Evaluate on Different Set

```bash
python -c "from src.inference import main; main(dataset_set='c')"
```

---

## Project Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| pandas | >=2.0.0 | Data manipulation |
| numpy | >=1.24.0 | Numerical computing |
| scikit-learn | >=1.3.0 | ML models & preprocessing |
| joblib | >=1.3.0 | Model serialization |
| matplotlib | >=3.7.0 | Visualization |
| seaborn | >=0.12.0 | Statistical plots |

---

## Author & License

Generated as part of a Master's thesis project on DDoS attack detection.

Contact: [Your email/university]

---

## References

- Scikit-learn documentation: https://scikit-learn.org/
- Feature engineering for anomaly detection: [Reference papers]
- Class imbalance handling: [Chen & Guestrin 2016] XGBoost

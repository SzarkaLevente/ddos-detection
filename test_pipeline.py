#!/usr/bin/env python3
"""
Quick test script to verify the entire pipeline works.
Run this to generate data, train, and infer.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils import setup_logging, get_project_paths
from src.generate_dummy_data import generate_all_dummy_datasets
from src.train import main as train_main
from src.inference import main as inference_main

def main():
    """Run complete pipeline."""
    setup_logging()
    paths = get_project_paths()
    
    print("\n" + "="*70)
    print("DDoS DETECTION PIPELINE - QUICK TEST")
    print("="*70)
    
    # Step 1: Generate dummy data
    print("\n[Step 1] Generating synthetic datasets...")
    try:
        generate_all_dummy_datasets(paths["data"])
        print("✓ Datasets generated successfully!")
    except Exception as e:
        print(f"✗ Error generating datasets: {e}")
        return False
    
    # Step 2: Train model
    print("\n[Step 2] Training model (sets A+B+C)...")
    try:
        results = train_main(augment_with_setd=False)
        print("✓ Model trained successfully!")
        print(f"  Test Accuracy: {results['metrics']['overall']['accuracy']:.4f}")
    except Exception as e:
        print(f"✗ Error training model: {e}")
        return False
    
    # Step 3: Run inference
    print("\n[Step 3] Running inference on Set D...")
    try:
        results = inference_main(dataset_set="d", use_labels=True)
        print("✓ Inference completed successfully!")
        print(f"  Predictions saved to outputs/predictions.csv")
    except Exception as e:
        print(f"✗ Error running inference: {e}")
        return False
    
    print("\n" + "="*70)
    print("✓ PIPELINE TEST COMPLETED SUCCESSFULLY!")
    print("="*70)
    print("\nNext steps:")
    print("1. Review outputs/predictions.csv")
    print("2. Check models/ directory for artifacts")
    print("3. Run: python -m notebook.experimentation")
    print("4. Build Docker: docker build -t ddos-detector .")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

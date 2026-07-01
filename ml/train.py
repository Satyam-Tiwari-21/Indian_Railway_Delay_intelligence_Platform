# ml/train.py
# CLI entry point for model training.
#
# Usage:
#   python ml/train.py                          # Train all models with MLflow
#   python ml/train.py --no-mlflow              # Train without MLflow tracking
#   python ml/train.py --model-dir ml/saved_models

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging_config import setup_logging, get_logger
from app.core.database import check_db_connection

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Train India Railways delay prediction models"
    )
    parser.add_argument(
        "--no-mlflow",
        action="store_true",
        help="Disable MLflow tracking (faster, no server needed)",
    )
    parser.add_argument(
        "--model-dir",
        default="ml/saved_models",
        help="Directory to save trained models (default: ml/saved_models)",
    )
    args = parser.parse_args()

    setup_logging()

    print("\n" + "="*60)
    print("  India Railways Delay Intelligence Platform")
    print("  Model Training Pipeline")
    print("="*60)

    # Pre-flight checks
    print("\nRunning pre-flight checks...")

    db_status = check_db_connection()
    if db_status["status"] != "healthy":
        print("❌ Database not reachable. Start it with: docker-compose up -d postgres")
        sys.exit(1)
    print("  ✅ Database connected")

    if not args.no_mlflow:
        try:
            import mlflow
            from app.core.config import settings
            mlflow.set_tracking_uri(settings.MLFLOW_TRACKING_URI)
            print(f"  ✅ MLflow at {settings.MLFLOW_TRACKING_URI}")
        except Exception as e:
            print(f"  ⚠️  MLflow not reachable ({e}) — running without tracking")
            args.no_mlflow = True

    try:
        import xgboost
        print("  ✅ XGBoost available")
    except ImportError:
        print("  ❌ XGBoost not installed. Run: pip install xgboost")
        sys.exit(1)

    print("\nStarting training...\n")

    from ml.pipelines.training_pipeline import run_training

    results = run_training(
        use_mlflow=not args.no_mlflow,
        model_dir=args.model_dir,
    )

    print("\n" + "="*60)
    print("✅  Training complete!")
    print("="*60)
    print(f"   Best model MAE: {results['xgb_metrics']['mae']:.2f} min")
    print(f"   Within 15 min:  {results['xgb_metrics']['within_15min_pct']:.1f}%")
    print(f"\n   Models saved to: {args.model_dir}/")
    print("\nNext steps:")
    print("   1. Run evaluation:  python ml/evaluate.py")
    print("   2. Restart API:     uvicorn app.main:app --reload --port 8000")
    print("   3. The API now uses the real XGBoost model instead of the mock predictor")
    if not args.no_mlflow:
        print("   4. View MLflow:     http://localhost:5000")


if __name__ == "__main__":
    main()
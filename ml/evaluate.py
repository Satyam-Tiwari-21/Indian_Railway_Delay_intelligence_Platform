# ml/evaluate.py
# CLI for model evaluation.
#
# Usage:
#   python ml/evaluate.py
#   python ml/evaluate.py --predictor ml/saved_models/xgboost_delay_predictor.pkl

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging_config import setup_logging


def main():
    parser = argparse.ArgumentParser(description="Evaluate trained delay prediction models")
    parser.add_argument(
        "--predictor",
        default="ml/saved_models/xgboost_delay_predictor.pkl",
        help="Path to trained predictor .pkl file",
    )
    parser.add_argument(
        "--classifier",
        default="ml/saved_models/delay_classifier.pkl",
        help="Path to trained classifier .pkl file",
    )
    args = parser.parse_args()

    setup_logging()

    print("\n" + "="*55)
    print("  Model Evaluation Report")
    print("="*55)

    if not Path(args.predictor).exists():
        print(f"❌ Model not found: {args.predictor}")
        print("   Run training first: python ml/train.py")
        sys.exit(1)

    from ml.pipelines.evaluation_pipeline import run_evaluation

    metrics = run_evaluation(
        predictor_path=args.predictor,
        classifier_path=args.classifier,
    )

    print("\n" + "="*55)
    print("✅  Evaluation complete!")
    print(f"   MAE:           {metrics['mae']:.2f} min")
    print(f"   RMSE:          {metrics['rmse']:.2f} min")
    print(f"   Within 15min:  {metrics['within_15min_pct']:.1f}%")
    print(f"   Plots saved:   ml/saved_models/evaluation/")


if __name__ == "__main__":
    main()
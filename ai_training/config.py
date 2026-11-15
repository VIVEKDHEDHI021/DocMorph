"""AI Training Configuration and Label Schema for DocMorph Universal Footer Detection."""

from pathlib import Path
from typing import Any

# Fixed random seed for complete reproducibility
RANDOM_SEED: int = 42

# 13-Class BIO Tagging Schema
LABEL_LIST: list[str] = [
    "O",
    "B-FOOTER",
    "I-FOOTER",
    "B-STUDENT_NAME",
    "I-STUDENT_NAME",
    "B-ENROLLMENT_ID",
    "I-ENROLLMENT_ID",
    "B-ROLL_NUMBER",
    "I-ROLL_NUMBER",
    "B-STUDENT_ID",
    "I-STUDENT_ID",
    "B-PAGE_NUMBER",
    "I-PAGE_NUMBER",
]

ID2LABEL: dict[int, str] = {idx: label for idx, label in enumerate(LABEL_LIST)}
LABEL2ID: dict[str, int] = {label: idx for idx, label in enumerate(LABEL_LIST)}

# Base paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
AI_TRAINING_DIR: Path = BASE_DIR / "ai_training"
DATA_DIR: Path = AI_TRAINING_DIR / "data"
CHECKPOINT_DIR: Path = AI_TRAINING_DIR / "checkpoints"
MODEL_OUTPUT_DIR: Path = AI_TRAINING_DIR / "trained_model"

# Training Hyperparameters
TRAINING_CONFIG: dict[str, Any] = {
    "model_name": "microsoft/layoutlmv3-base",
    "max_seq_length": 512,
    "batch_size": 4,
    "learning_rate": 3e-5,
    "weight_decay": 0.01,
    "num_train_epochs": 6,
    "warmup_ratio": 0.1,
    "logging_steps": 10,
    "save_total_limit": 2,
    "seed": RANDOM_SEED,
    "train_ratio": 0.70,
    "val_ratio": 0.15,
    "test_ratio": 0.15,
}


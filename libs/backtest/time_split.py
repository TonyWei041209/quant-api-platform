"""Walk-forward and time-split utilities for backtesting.

Rules:
- Research/training data must come BEFORE test data
- No look-ahead allowed
- Walk-forward: rolling windows of train + test
- Simple split: single train/test boundary
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class TimeSplit:
    """A single time split with train and test periods."""
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    fold: int = 0

    def __repr__(self) -> str:
        return (
            f"TimeSplit(fold={self.fold}, "
            f"train={self.train_start}..{self.train_end}, "
            f"test={self.test_start}..{self.test_end})"
        )


def simple_split(
    start_date: date,
    end_date: date,
    train_ratio: float = 0.7,
) -> TimeSplit:
    """Simple train/test split by date ratio."""
    total_days = (end_date - start_date).days
    train_days = int(total_days * train_ratio)
    train_end = start_date + timedelta(days=train_days)
    test_start = train_end + timedelta(days=1)

    return TimeSplit(
        train_start=start_date,
        train_end=train_end,
        test_start=test_start,
        test_end=end_date,
    )


def walk_forward_splits(
    start_date: date,
    end_date: date,
    train_days: int = 504,  # ~2 years
    test_days: int = 63,     # ~3 months
    step_days: int = 63,     # ~3 months
) -> list[TimeSplit]:
    """Generate walk-forward time splits.

    Each fold uses train_days for training and test_days for testing.
    Folds advance by step_days.
    """
    splits = []
    fold = 0
    current_train_start = start_date

    while True:
        train_end = current_train_start + timedelta(days=train_days)
        test_start = train_end + timedelta(days=1)
        test_end = test_start + timedelta(days=test_days)

        if test_end > end_date:
            break

        splits.append(TimeSplit(
            train_start=current_train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            fold=fold,
        ))

        current_train_start += timedelta(days=step_days)
        fold += 1

    return splits


def expanding_window_splits(
    start_date: date,
    end_date: date,
    min_train_days: int = 252,
    test_days: int = 63,
    step_days: int = 63,
) -> list[TimeSplit]:
    """Generate expanding window splits (train always starts from start_date)."""
    splits = []
    fold = 0
    current_test_start = start_date + timedelta(days=min_train_days + 1)

    while True:
        test_end = current_test_start + timedelta(days=test_days)
        if test_end > end_date:
            break

        splits.append(TimeSplit(
            train_start=start_date,
            train_end=current_test_start - timedelta(days=1),
            test_start=current_test_start,
            test_end=test_end,
            fold=fold,
        ))

        current_test_start += timedelta(days=step_days)
        fold += 1

    return splits

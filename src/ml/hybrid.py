"""Reusable residual ET predictor; inference does not require observed ET."""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from .fao56.baseline import WIND_HEIGHT_M, add_et0
from .train_ml import FEATURES

NDVI_FEATURES = ("ndvi_last", "ndvi_age_days")


def prepare_features(frame: pd.DataFrame, use_et0_feature: bool = False, extra_features=()):
    columns = FEATURES + (["et0_mm"] if use_et0_feature else [])
    numeric = frame[FEATURES].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("Hybrid inputs must be finite")
    physical = add_et0(numeric, wind_height_m=WIND_HEIGHT_M)
    if not np.isfinite(physical["et0_mm"]).all():
        raise ValueError("ET0 must be finite")
    features = physical[columns].copy()
    if tuple(extra_features) not in ((), NDVI_FEATURES):
        raise ValueError("Unsupported extra feature contract")
    if extra_features:
        ndvi = frame[list(extra_features)].apply(pd.to_numeric, errors="raise")
        if np.isinf(ndvi.to_numpy(dtype=float)).any():
            raise ValueError("NDVI inputs must not be infinite")
        if (ndvi.ndvi_last.dropna().abs() > 1).any():
            raise ValueError("NDVI must be in [-1, 1]")
        age = ndvi.ndvi_age_days.dropna()
        if ((age < 0) | (age % 1 != 0)).any():
            raise ValueError("NDVI age must be a nonnegative integer")
        if not ndvi.ndvi_last.isna().equals(ndvi.ndvi_age_days.isna()):
            raise ValueError("NDVI and age missingness must match")
        features[list(extra_features)] = ndvi
    return features, physical["et0_mm"]


class HybridPredictor:
    """Wrap a fitted residual estimator with its physical baseline contract."""

    def __init__(self, estimator, use_et0_feature: bool = False, extra_features=()):
        self.extra_features = tuple(extra_features)
        self.estimator = estimator
        self.use_et0_feature = use_et0_feature

    def predict_components(self, frame):
        features, et0 = prepare_features(frame, self.use_et0_feature, self.extra_features)
        residual = np.asarray(self.estimator.predict(features), dtype=float)
        if residual.shape != (len(frame),) or not np.isfinite(residual).all():
            raise ValueError("Invalid residual predictions")
        return pd.DataFrame({"et0_mm": et0.to_numpy(), "residual_pred_mm": residual,
                             "et_pred_mm": et0.to_numpy() + residual}, index=frame.index)

    def predict(self, frame):
        return self.predict_components(frame)["et_pred_mm"].to_numpy()

    def save(self, directory: Path, name: str):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"hybrid_{name}.json" if name == "xgb" and not self.extra_features else f"hybrid_{name}.joblib"
        if name == "xgb" and not self.extra_features:
            self.estimator.save_model(directory / filename)
        else:
            joblib.dump(self.estimator, directory / filename)
        metadata = {"schema_version": 2, "extra_features": list(self.extra_features),
                    "serialization": "joblib" if self.extra_features or name != "xgb" else "xgboost", "model_file": filename,
                    "use_et0_feature": self.use_et0_feature,
                    "features": FEATURES + (["et0_mm"] if self.use_et0_feature else []) + list(self.extra_features),
                    "wind_height_m": WIND_HEIGHT_M,
                    "target": "et_obs_mm - et0_mm", "prediction": "et0_mm + residual_pred_mm"}
        (directory / f"hybrid_{name}_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")

    @classmethod
    def load(cls, directory: Path, name: str):
        directory = Path(directory)
        metadata = json.loads((directory / f"hybrid_{name}_metadata.json").read_text())
        use_et0 = metadata["use_et0_feature"]
        extra = tuple(metadata.get("extra_features", ()))
        expected = FEATURES + (["et0_mm"] if use_et0 else []) + list(extra)
        if (metadata["schema_version"] not in (1, 2) or extra not in ((), NDVI_FEATURES) or metadata["features"] != expected
                or metadata["wind_height_m"] != WIND_HEIGHT_M):
            raise ValueError("Incompatible hybrid model metadata")
        path = directory / metadata["model_file"]
        if metadata.get("serialization", "xgboost" if name == "xgb" else "joblib") == "xgboost":
            estimator = XGBRegressor()
            estimator.load_model(path)
        else:
            estimator = joblib.load(path)
        return cls(estimator, use_et0, extra)

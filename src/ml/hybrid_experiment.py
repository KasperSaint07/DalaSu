"""Shared experiment identity and default artifact layout for Hybrid workflows."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HybridExperiment:
    use_ndvi: bool = False
    use_et0_feature: bool = False

    @property
    def name(self) -> str:
        base = 'hybrid_ndvi' if self.use_ndvi else 'hybrid'
        return base + ('_with_et0' if self.use_et0_feature else '')

    def models_dir(self, root: Path) -> Path:
        return root / 'models' / (self.name if self.use_ndvi or self.use_et0_feature else '')

    def reports_dir(self, root: Path) -> Path:
        return root / 'reports' / (self.name if self.use_et0_feature else '')

    def data_dir(self, root: Path) -> Path:
        return root / 'data/processed' / ('ndvi' if self.use_ndvi else '')

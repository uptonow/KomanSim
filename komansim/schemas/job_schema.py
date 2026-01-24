from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class PoseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    p: List[float] = Field(..., min_length=3, max_length=3)
    q: List[float] = Field(..., min_length=4, max_length=4)


class SceneModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usd_path: Optional[str] = None
    dome_light_intensity: float = 1500.0
    physics_dt: float = 1.0 / 60.0


class AssetModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    usd_path: str
    semantic_label: Optional[str] = None
    scale: float = 1.0


class SensorModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: str
    pose: PoseModel
    intrinsics: Dict[str, Any] = Field(default_factory=dict)


class RandomizationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    random_xy: float = 0.2
    random_yaw_deg: float = 180.0


class JobConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_name: str = "job"
    out_dir: str = "outputs/job"
    seed: int = 0
    num_frames: int = 100
    dt: float = 1.0 / 30.0
    headless: bool = True
    width: int = 1280
    height: int = 720
    backend: Optional[str] = Field(
        default=None, description="Backend name: dummy | isaac_sim | mujoco | pybullet"
    )

    scene: SceneModel = Field(default_factory=SceneModel)
    assets: List[AssetModel] = Field(default_factory=list)
    sensors: List[SensorModel] = Field(default_factory=list)
    randomization: RandomizationModel = Field(default_factory=RandomizationModel)

    # Resource limits (MVP)
    max_frames: Optional[int] = Field(default=None, description="Maximum number of frames allowed")
    max_resolution: Optional[int] = Field(
        default=None, description="Maximum resolution (width * height) allowed"
    )
    max_modalities: Optional[int] = Field(
        default=None, description="Maximum number of unique sensor types allowed"
    )
    max_total_size: Optional[int] = Field(
        default=None, description="Maximum estimated total size in bytes"
    )

    @field_validator("num_frames")
    @classmethod
    def _frames_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("num_frames must be > 0")
        return v

    @field_validator("dt")
    @classmethod
    def _dt_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("dt must be > 0")
        return v

    @field_validator("width", "height")
    @classmethod
    def _dimensions_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("width and height must be > 0")
        return v

    @field_validator("max_frames", "max_resolution", "max_modalities", "max_total_size")
    @classmethod
    def _limits_positive_if_set(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Resource limits must be > 0 if set")
        return v

    @field_validator("backend")
    @classmethod
    def _validate_backend(cls, v: Optional[str]) -> Optional[str]:
        """Validate backend name if provided."""
        if v is not None:
            valid_backends = {"dummy", "isaac_sim", "mujoco", "pybullet"}
            if v not in valid_backends:
                raise ValueError(
                    f"Invalid backend '{v}'. Must be one of: {', '.join(sorted(valid_backends))}"
                )
        return v

    @model_validator(mode="after")
    def _validate_resource_limits(self) -> "JobConfig":
        """Validate resource limits before running."""
        errors: List[str] = []

        # Check max_frames
        if self.max_frames is not None and self.num_frames > self.max_frames:
            errors.append(
                f"num_frames ({self.num_frames}) exceeds max_frames limit ({self.max_frames})"
            )

        # Check max_resolution
        resolution = self.width * self.height
        if self.max_resolution is not None and resolution > self.max_resolution:
            errors.append(
                f"Resolution ({self.width}x{self.height} = {resolution} pixels) exceeds "
                f"max_resolution limit ({self.max_resolution} pixels)"
            )

        # Check max_modalities (unique sensor types)
        unique_modalities = len(set(s.type for s in self.sensors))
        if self.max_modalities is not None and unique_modalities > self.max_modalities:
            errors.append(
                f"Number of unique sensor types ({unique_modalities}: {sorted(set(s.type for s in self.sensors))}) "
                f"exceeds max_modalities limit ({self.max_modalities})"
            )

        # Check max_total_size (estimate)
        if self.max_total_size is not None:
            # Estimate size per frame based on modalities present
            # RGB: width * height * 3 bytes (uint8)
            # Depth: width * height * 4 bytes (float32)
            # Segmentation: width * height * 4 bytes (int32)
            sensor_types = set(s.type for s in self.sensors)
            bytes_per_pixel = 0
            if any("rgb" in t.lower() or "color" in t.lower() for t in sensor_types):
                bytes_per_pixel += 3  # RGB uint8
            if any("depth" in t.lower() for t in sensor_types):
                bytes_per_pixel += 4  # Depth float32
            if any("seg" in t.lower() or "semantic" in t.lower() for t in sensor_types):
                bytes_per_pixel += 4  # Segmentation int32

            # If no specific modalities detected, assume at least RGB
            if bytes_per_pixel == 0:
                bytes_per_pixel = 3

            estimated_size = self.num_frames * resolution * bytes_per_pixel
            if estimated_size > self.max_total_size:
                errors.append(
                    f"Estimated total size ({estimated_size:,} bytes ≈ {estimated_size / (1024**2):.2f} MB) "
                    f"exceeds max_total_size limit ({self.max_total_size:,} bytes ≈ {self.max_total_size / (1024**2):.2f} MB). "
                    f"Estimation based on {self.num_frames} frames, {resolution} pixels/frame, "
                    f"~{bytes_per_pixel} bytes/pixel (modalities: {sorted(sensor_types)})"
                )

        if errors:
            raise ValueError("Resource limit validation failed:\n  " + "\n  ".join(errors))

        return self

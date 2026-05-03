from typing import Optional

from pydantic import BaseModel, Field


class DedrmRequest(BaseModel):
    acsm_file: str = Field(..., description="ACSM input path, relative to DATA_DIR")
    drm_file: str = Field(..., description="Intermediate DRM output path, relative to DATA_DIR")
    output_dir: str = Field(..., description="Final EPUB/PDF output directory, relative to DATA_DIR")
    output_file: str = Field(..., description="Final output filename (no slashes)")


class DedrmSuccessResponse(BaseModel):
    ok: bool = True
    output_path: str
    duration_ms: int


class DedrmErrorResponse(BaseModel):
    ok: bool = False
    stage: str
    exit_code: Optional[int] = None
    stderr: str = ""
    error: Optional[str] = None


class HealthResponse(BaseModel):
    ok: bool = True
    version: str

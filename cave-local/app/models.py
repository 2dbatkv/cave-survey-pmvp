from pydantic import BaseModel, Field, conlist, validator
from typing import List, Optional
from datetime import datetime

class Shot(BaseModel):
    from_station: str = Field(..., min_length=1, max_length=50)
    to_station: str = Field(..., min_length=1, max_length=50)
    slope_distance: float = Field(..., gt=0, le=1000)  # Max 1km per shot
    azimuth_deg: float = Field(..., ge=0, lt=360)
    inclination_deg: float = Field(..., ge=-90, le=90)
    
    @validator('from_station', 'to_station')
    def validate_station_names(cls, v):
        if not v.strip():
            raise ValueError('Station names cannot be empty or whitespace')
        return v.strip()
    
    @validator('slope_distance')
    def validate_distance(cls, v):
        if v <= 0:
            raise ValueError('Slope distance must be positive')
        return v

class TraverseIn(BaseModel):
    origin_x: float = Field(default=0, ge=-100000, le=100000)  # Reasonable coordinate bounds
    origin_y: float = Field(default=0, ge=-100000, le=100000)
    origin_z: float = Field(default=0, ge=-10000, le=10000)   # Cave depth bounds
    shots: conlist(Shot, min_items=1, max_items=1000)         # Max 1000 shots per request
    section: str = Field(default="default", min_length=1, max_length=100)
    close: Optional[str] = Field(default=None, max_length=50)
    
    @validator('section')
    def validate_section(cls, v):
        if not v.strip():
            raise ValueError('Section name cannot be empty')
        # Allow only alphanumeric, spaces, hyphens, underscores
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', v):
            raise ValueError('Section name contains invalid characters')
        return v.strip()

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=8, max_length=100)
    
    @validator('username')
    def validate_username(cls, v):
        import re
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers, and underscores')
        return v

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class StationResponse(BaseModel):
    name: str
    x: float
    y: float
    z: float

class ResidualResponse(BaseModel):
    from_station: str = Field(alias="from")
    to_station: str = Field(alias="to")
    dx: float
    dy: float
    dz: float

class MetaResponse(BaseModel):
    num_stations: int
    num_shots: int
    total_slope_distance: float
    total_horizontal_distance: float
    bbox: dict
    residuals: List[ResidualResponse]

class ReduceResponse(BaseModel):
    stations: List[StationResponse]
    meta: MetaResponse

class SaveResponse(BaseModel):
    saved: bool
    survey_id: Optional[int] = None
    s3_bucket: Optional[str] = None
    json_key: Optional[str] = None
    png_key: Optional[str] = None
    json_url: Optional[str] = None
    png_url: Optional[str] = None
    meta: MetaResponse
    error: Optional[str] = None

class HealthResponse(BaseModel):
    ok: bool
    service: str
    version: str = "1.0.0"
    timestamp: datetime
    database_connected: bool
    s3_configured: bool
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from collections import deque, defaultdict
import io, os, math, json
import logging
from typing import List

# Datadog APM
from ddtrace import patch_all, tracer
import datadog

# headless backend for matplotlib (avoids GUI/toolkit issues)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Local imports
from .config import get_settings
from .database import get_db, create_tables, User, Survey, Feedback
from .auth import (
    authenticate_user, create_access_token, get_current_active_user,
    get_password_hash, get_user_by_username
)
from .s3_service import s3_service
from .models import (
    Shot, TraverseIn, UserCreate, UserLogin, Token,
    ReduceResponse, SaveResponse, HealthResponse
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

# Initialize Datadog APM
if settings.datadog_api_key:
    # Patch all supported libraries (includes FastAPI automatically)
    patch_all()
    
    # Configure Datadog
    datadog.initialize(
        api_key=settings.datadog_api_key,
        app_key=settings.datadog_app_key,
        host_name="render-backend"
    )
    
    # Set service info
    tracer.set_tags({
        'service': settings.dd_service,
        'env': settings.dd_env,
        'version': settings.dd_version
    })

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Create database tables on startup
create_tables()

# ----- CORS -----
# Debug: log the allowed origins
logger.info(f"CORS allowed_origins: {settings.allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Temporary wildcard for debugging
    allow_credentials=False,  # Must be False when using wildcard
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Error handling middleware
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    logger.error(f"ValueError: {exc}")
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid input data", "detail": str(exc)}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "An unexpected error occurred"}
    )

# ---------- Geometry (cave conventions) ----------
def shot_to_deltas(slope_distance: float, azimuth_deg: float, inclination_deg: float):
    """
    0° azimuth = North, clockwise positive (N=0, E=90, S=180, W=270)
    Inclination +up / -down.
    """
    inc = math.radians(inclination_deg)
    az  = math.radians(azimuth_deg % 360.0)
    horiz = slope_distance * math.cos(inc)   # horizontal component
    dz    = slope_distance * math.sin(inc)   # vertical (+ up)
    dx    = horiz * math.sin(az)             # X = East
    dy    = horiz * math.cos(az)             # Y = North
    return dx, dy, dz, horiz

def build_graph(shots: list[Shot]):
    """Adjacency and directed edge vectors for both directions."""
    adj: dict[str, list[tuple[str, int]]] = defaultdict(list)   # node -> list[(nbr, edge_id)]
    vec: dict[int, tuple[str, str, tuple[float, float, float]]] = {}  # id -> (u, v, (dx,dy,dz))
    eid = 0
    for s in shots:
        u, v = s.from_station, s.to_station
        dx, dy, dz, _ = shot_to_deltas(s.slope_distance, s.azimuth_deg, s.inclination_deg)
        vec[eid] = (u, v, (dx, dy, dz))
        adj[u].append((v, eid))
        eid += 1
        # reverse edge (for traversal convenience)
        vec[eid] = (v, u, (-dx, -dy, -dz))
        adj[v].append((u, eid))
        eid += 1
    return adj, vec

def reduce_graph(shots: list[Shot], origin_name: str, ox: float, oy: float, oz: float):
    """
    BFS over the station graph starting from origin_name.
    Returns:
      pos:   station -> (x,y,z)
      edges: set of undirected edges { (a,b) } with a<b lexicographically
      meta:  stats + residuals (tie-in misclosures)
    """
    adj, vec = build_graph(shots)

    # choose a valid seed
    seed = origin_name if origin_name in adj else (next(iter(adj)) if adj else origin_name)

    pos: dict[str, tuple[float, float, float]] = {}
    visited_edges: set[int] = set()
    residuals: list[tuple[str, str, float, float, float]] = []

    # seed coordinates
    pos[seed] = (ox, oy, oz)

    # track per-shot lengths for totals
    total_slope = 0.0
    total_horiz = 0.0

    # Make a quick map of directed unit deltas to recover lengths
    shot_map = {}
    for s in shots:
        dx, dy, dz, horiz = shot_to_deltas(s.slope_distance, s.azimuth_deg, s.inclination_deg)
        shot_map[(s.from_station, s.to_station)] = (dx, dy, dz, s.slope_distance, horiz)

    q = deque([seed])
    while q:
        u = q.popleft()
        ux, uy, uz = pos[u]
        for v, eid in adj[u]:
            if eid in visited_edges:
                continue
            visited_edges.add(eid)
            _, _, (dx, dy, dz) = vec[eid]

            if v not in pos:
                # accumulate lengths for "forward" edges if original shot exists
                if (u, v) in shot_map:
                    _, _, _, s_len, h_len = shot_map[(u, v)]
                    total_slope += s_len
                    total_horiz += h_len
                pos[v] = (ux + dx, uy + dy, uz + dz)
                q.append(v)
            else:
                # tie-in / loop: record residual between predicted and existing
                px, py, pz = ux + dx, uy + dy, uz + dz
                vx, vy, vz = pos[v]
                residuals.append((u, v, px - vx, py - vy, pz - vz))

    # Undirected edge set for plotting (dedupe reverse)
    edges: set[tuple[str, str]] = set()
    for eid, (a, b, _) in vec.items():
        key = (a, b) if a < b else (b, a)
        edges.add(key)

    # Metadata
    if pos:
        xs, ys, zs = zip(*pos.values())
        bbox = {"min_x": min(xs), "max_x": max(xs), "min_y": min(ys), "max_y": max(ys),
                "min_z": min(zs), "max_z": max(zs)}
    else:
        bbox = {}

    meta = {
        "num_stations": len(pos),
        "num_shots": len(edges),
        "total_slope_distance": round(total_slope, 3),
        "total_horizontal_distance": round(total_horiz, 3),
        "bbox": bbox,
        "residuals": [
            {"from": u, "to": v, "dx": dx, "dy": dy, "dz": dz}
            for (u, v, dx, dy, dz) in residuals
        ],
    }
    return pos, edges, meta

# ---------- Plotting ----------
def plot_graph_png(pos: dict[str, tuple[float, float, float]], edges: set[tuple[str, str]]):
    fig, ax = plt.subplots(figsize=(6, 6))
    # draw edges
    for a, b in sorted(edges):
        if a in pos and b in pos:
            xa, ya, _ = pos[a]
            xb, yb, _ = pos[b]
            ax.plot([xa, xb], [ya, yb], linewidth=2)
    # annotate stations
    for name, (x, y, z) in pos.items():
        ax.plot(x, y, "o", markersize=3)
        ax.text(x, y, f" {name}", fontsize=8)
    ax.set_aspect("equal")
    ax.set_xlabel("X (East)")
    ax.set_ylabel("Y (North)")
    ax.grid(True, alpha=0.25)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf

# ---------- Routes ----------
@app.get("/", response_model=HealthResponse)
async def health(db: Session = Depends(get_db)):
    # Check database connection
    db_connected = True
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        db_connected = False
    
    # Check S3 configuration
    s3_configured = bool(settings.s3_bucket_name and settings.aws_access_key_id)
    
    return HealthResponse(
        ok=db_connected and s3_configured,
        service=settings.app_name,
        timestamp=datetime.utcnow(),
        database_connected=db_connected,
        s3_configured=s3_configured
    )

@app.post("/register", response_model=Token)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    if get_user_by_username(db, user.username):
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/reduce", response_model=ReduceResponse)
def reduce_endpoint(trav: TraverseIn):
    # pick origin station from the first shot's from_station
    origin_station = trav.shots[0].from_station
    pos, edges, meta = reduce_graph(
        shots=trav.shots,
        origin_name=origin_station,
        ox=trav.origin_x, oy=trav.origin_y, oz=trav.origin_z,
    )
    # Serialize stations in a stable order (by name)
    stations = [{"name": k, "x": v[0], "y": v[1], "z": v[2]} for k, v in sorted(pos.items())]
    return {"stations": stations, "meta": meta}

@app.post("/plot")
def plot_endpoint(trav: TraverseIn):
    origin_station = trav.shots[0].from_station
    pos, edges, meta = reduce_graph(
        shots=trav.shots,
        origin_name=origin_station,
        ox=trav.origin_x, oy=trav.origin_y, oz=trav.origin_z,
    )
    img = plot_graph_png(pos, edges)
    return StreamingResponse(img, media_type="image/png")

@app.post("/save", response_model=SaveResponse)
def save_endpoint(
    trav: TraverseIn, 
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    try:
        origin_station = trav.shots[0].from_station
        pos, edges, meta = reduce_graph(
            shots=trav.shots,
            origin_name=origin_station,
            ox=trav.origin_x, oy=trav.origin_y, oz=trav.origin_z,
        )
        
        day = datetime.utcnow().strftime("%Y-%m-%d")
        section = trav.section.lower().replace(" ", "_")
        
        # S3 object keys
        key_base = f"{section}/{day}/{day}-{current_user.username}"
        json_key = f"{key_base}.json"
        png_key = f"{key_base}.png"
        
        # JSON document
        json_doc = {
            "origin": {"station": origin_station, "x": trav.origin_x, "y": trav.origin_y, "z": trav.origin_z},
            "shots": [s.model_dump() for s in trav.shots],
            "stations": [{"name": k, "x": v[0], "y": v[1], "z": v[2]} for k, v in sorted(pos.items())],
            "meta": meta,
            "saved_at": datetime.utcnow().isoformat() + "Z",
            "user": current_user.username
        }
        
        # Generate PNG
        img = plot_graph_png(pos, edges)
        png_bytes = img.getvalue()
        
        # Upload to S3
        json_success, json_error = s3_service.upload_json(json_key, json_doc)
        png_success, png_error = s3_service.upload_png(png_key, png_bytes)
        
        if not json_success or not png_success:
            error_msg = f"S3 upload failed: {json_error or png_error}"
            logger.error(error_msg)
            return SaveResponse(
                saved=False,
                error=error_msg,
                meta=meta
            )
        
        # Get URLs
        json_url = s3_service.get_url(json_key)
        png_url = s3_service.get_url(png_key)
        
        # Save to database
        survey = Survey(
            title=f"{section} - {day}",
            section=trav.section,
            description=f"Survey with {len(pos)} stations and {len(edges)} shots",
            owner_id=current_user.id,
            s3_json_key=json_key,
            s3_png_key=png_key,
            json_url=json_url,
            png_url=png_url,
            num_stations=meta["num_stations"],
            num_shots=meta["num_shots"],
            total_slope_distance=meta["total_slope_distance"],
            total_horizontal_distance=meta["total_horizontal_distance"],
            min_x=meta["bbox"].get("min_x"),
            max_x=meta["bbox"].get("max_x"),
            min_y=meta["bbox"].get("min_y"),
            max_y=meta["bbox"].get("max_y"),
            min_z=meta["bbox"].get("min_z"),
            max_z=meta["bbox"].get("max_z")
        )
        
        db.add(survey)
        db.commit()
        db.refresh(survey)
        
        return SaveResponse(
            saved=True,
            survey_id=survey.id,
            s3_bucket=settings.s3_bucket_name,
            json_key=json_key,
            png_key=png_key,
            json_url=json_url,
            png_url=png_url,
            meta=meta
        )
        
    except Exception as e:
        logger.error(f"Save endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save survey data")

@app.post("/feedback")
def submit_feedback(
    feedback_data: dict,
    db: Session = Depends(get_db)
):
    try:
        feedback_text = feedback_data.get("feedback_text", "").strip()
        if not feedback_text:
            raise HTTPException(status_code=400, detail="Feedback text is required")
        
        feedback = Feedback(
            feedback_text=feedback_text,
            user_session=feedback_data.get("user_session", "anonymous"),
            category=feedback_data.get("category", "general"),
            priority=feedback_data.get("priority", "normal")
        )
        
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        
        return {
            "success": True,
            "feedback_id": feedback.id,
            "message": "Thank you for your feedback!"
        }
        
    except Exception as e:
        logger.error(f"Feedback endpoint error: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")

@app.get("/admin/feedback")
def view_feedback(db: Session = Depends(get_db)):
    try:
        feedback_items = db.query(Feedback).order_by(Feedback.submitted_at.desc()).all()
        
        return {
            "feedback_count": len(feedback_items),
            "feedback": [
                {
                    "id": item.id,
                    "feedback_text": item.feedback_text,
                    "submitted_at": item.submitted_at,
                    "user_session": item.user_session,
                    "category": item.category,
                    "priority": item.priority,
                    "status": item.status
                }
                for item in feedback_items
            ]
        }
        
    except Exception as e:
        logger.error(f"View feedback error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve feedback")

@app.get("/surveys")
def list_surveys(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100
):
    surveys = db.query(Survey).filter(
        Survey.owner_id == current_user.id
    ).offset(skip).limit(limit).all()
    
    return {
        "surveys": [
            {
                "id": s.id,
                "title": s.title,
                "section": s.section,
                "created_at": s.created_at,
                "num_stations": s.num_stations,
                "num_shots": s.num_shots,
                "png_url": s.png_url
            }
            for s in surveys
        ]
    }

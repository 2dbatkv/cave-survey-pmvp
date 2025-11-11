from fastapi import FastAPI, HTTPException, Depends, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from collections import deque, defaultdict
import io, os, math, json
import logging
from . import export_utils
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
from .database import get_db, create_tables, User, Survey, Feedback, SurveyDraft
from .auth import (
    authenticate_user, create_access_token, get_current_active_user,
    get_password_hash, get_user_by_username
)
from .s3_service import s3_service
from . import draft_utils
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
    
    # Check Datadog configuration
    datadog_configured = bool(settings.datadog_api_key)
    
    # Test Datadog connection by sending a custom metric
    if datadog_configured:
        try:
            from datadog import statsd
            statsd.increment('health_check', tags=['service:cave-survey-api'])
        except Exception as e:
            logger.error(f"Datadog metric failed: {e}")
    
    return HealthResponse(
        ok=db_connected and s3_configured,
        service=settings.app_name,
        timestamp=datetime.utcnow(),
        database_connected=db_connected,
        s3_configured=s3_configured,
        datadog_configured=datadog_configured
    )

@app.post("/register", response_model=Token)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    if get_user_by_username(db, user.username):
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )

    # Truncate password to 72 bytes before hashing (bcrypt limitation)
    password_to_hash = user.password
    password_bytes = password_to_hash.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
        password_to_hash = password_bytes.decode('utf-8', errors='ignore')

    # Create new user
    try:
        hashed_password = get_password_hash(password_to_hash)
    except ValueError as e:
        logger.error(f"Password hashing error: {e}")
        raise HTTPException(
            status_code=400,
            detail="Password format invalid. Please use a different password."
        )

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

# ============================================================
# DRAFT MANAGEMENT ENDPOINTS
# ============================================================

@app.post("/surveys/{survey_id}/drafts/upload-csv")
async def upload_csv_draft(
    survey_id: int,
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Upload a TopoDroid CSV file and create a draft for review
    """
    try:
        csv_file = data.get("csv_file", "")
        filename = data.get("filename", "survey.csv")

        # Verify survey exists and user has access, or create one
        survey = db.query(Survey).filter(
            Survey.id == survey_id,
            Survey.owner_id == current_user.id
        ).first()

        if not survey:
            # Create a default survey for this user
            survey = Survey(
                owner_id=current_user.id,
                title=f"{current_user.username}'s Survey",
                section="main",
                description="Auto-created survey for draft uploads"
            )
            db.add(survey)
            db.commit()
            db.refresh(survey)
            logger.info(f"Created survey {survey.id} for user {current_user.username}")

        # Parse CSV
        draft_data = draft_utils.parse_topodroid_csv(csv_file)

        # Validate data
        is_valid, issues = draft_utils.validate_draft_data(draft_data)

        # Create draft
        draft = SurveyDraft(
            survey_id=survey_id,
            uploaded_by=current_user.id,
            source_type='csv',
            original_filename=filename,
            draft_data=draft_data,
            status='draft',
            has_errors=not is_valid,
            error_count=len([i for i in issues if i["type"] == "shot"]),
            validation_notes=json.dumps(issues) if issues else None
        )

        db.add(draft)
        db.commit()
        db.refresh(draft)

        return {
            "success": True,
            "draft_id": draft.id,
            "survey_id": survey_id,
            "status": draft.status,
            "shot_count": len(draft_data.get("shots", [])),
            "has_errors": draft.has_errors,
            "error_count": draft.error_count,
            "issues": issues
        }

    except Exception as e:
        logger.error(f"CSV upload error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/surveys/{survey_id}/drafts/paste-data")
async def paste_data_draft(
    survey_id: int,
    data: dict,  # {"content": "csv_text", "format": "topodroid"}
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create a draft from pasted survey data
    """
    try:
        survey = db.query(Survey).filter(
            Survey.id == survey_id,
            Survey.owner_id == current_user.id
        ).first()

        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")

        content = data.get("content", "")
        format_type = data.get("format", "topodroid")

        # Parse based on format
        if format_type == "topodroid":
            draft_data = draft_utils.parse_topodroid_csv(content)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format_type}")

        # Validate
        is_valid, issues = draft_utils.validate_draft_data(draft_data)

        # Create draft
        draft = SurveyDraft(
            survey_id=survey_id,
            uploaded_by=current_user.id,
            source_type='paste',
            original_filename=f"pasted_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            draft_data=draft_data,
            status='draft',
            has_errors=not is_valid,
            error_count=len([i for i in issues if i["type"] == "shot"]),
            validation_notes=json.dumps(issues) if issues else None
        )

        db.add(draft)
        db.commit()
        db.refresh(draft)

        return {
            "success": True,
            "draft_id": draft.id,
            "survey_id": survey_id,
            "shot_count": len(draft_data.get("shots", [])),
            "has_errors": draft.has_errors,
            "issues": issues
        }

    except Exception as e:
        logger.error(f"Paste data error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/surveys/{survey_id}/drafts")
def list_drafts(
    survey_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List all drafts for a survey
    """
    try:
        survey = db.query(Survey).filter(
            Survey.id == survey_id,
            Survey.owner_id == current_user.id
        ).first()

        if not survey:
            # Create a default survey for this user
            survey = Survey(
                owner_id=current_user.id,
                title=f"{current_user.username}'s Survey",
                section="main",
                description="Auto-created survey"
            )
            db.add(survey)
            db.commit()
            db.refresh(survey)
            logger.info(f"Created survey {survey.id} for user {current_user.username}")

        drafts = db.query(SurveyDraft).filter(
            SurveyDraft.survey_id == survey_id
        ).order_by(SurveyDraft.created_at.desc()).all()

        return {
            "survey_id": survey_id,
            "drafts": [
                {
                    "id": d.id,
                    "source_type": d.source_type,
                    "filename": d.original_filename,
                    "status": d.status,
                    "shot_count": len(d.draft_data.get("shots", [])),
                    "has_errors": d.has_errors,
                    "error_count": d.error_count,
                    "created_at": d.created_at,
                    "updated_at": d.updated_at
                }
                for d in drafts
            ]
        }

    except Exception as e:
        logger.error(f"List drafts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/surveys/{survey_id}/drafts/{draft_id}")
def get_draft(
    survey_id: int,
    draft_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific draft with full data for editing
    """
    try:
        draft = db.query(SurveyDraft).filter(
            SurveyDraft.id == draft_id,
            SurveyDraft.survey_id == survey_id
        ).first()

        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")

        # Verify user has access to the survey
        survey = db.query(Survey).filter(
            Survey.id == survey_id,
            Survey.owner_id == current_user.id
        ).first()

        if not survey:
            raise HTTPException(status_code=403, detail="Access denied")

        # Parse validation notes
        validation_issues = []
        if draft.validation_notes:
            try:
                validation_issues = json.loads(draft.validation_notes)
            except:
                pass

        return {
            "id": draft.id,
            "survey_id": draft.survey_id,
            "source_type": draft.source_type,
            "filename": draft.original_filename,
            "status": draft.status,
            "draft_data": draft.draft_data,
            "has_errors": draft.has_errors,
            "error_count": draft.error_count,
            "validation_issues": validation_issues,
            "created_at": draft.created_at,
            "updated_at": draft.updated_at
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get draft error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/surveys/{survey_id}/drafts/{draft_id}")
def update_draft(
    survey_id: int,
    draft_id: int,
    data: dict,  # {"draft_data": {...}}
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update draft data (save edits from review screen)
    """
    try:
        draft = db.query(SurveyDraft).filter(
            SurveyDraft.id == draft_id,
            SurveyDraft.survey_id == survey_id
        ).first()

        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")

        # Verify access
        survey = db.query(Survey).filter(
            Survey.id == survey_id,
            Survey.owner_id == current_user.id
        ).first()

        if not survey:
            raise HTTPException(status_code=403, detail="Access denied")

        # Don't allow editing committed drafts
        if draft.status == 'committed':
            raise HTTPException(status_code=400, detail="Cannot edit committed draft")

        # Update draft data
        new_draft_data = data.get("draft_data")
        if new_draft_data:
            # Validate updated data
            is_valid, issues = draft_utils.validate_draft_data(new_draft_data)

            draft.draft_data = new_draft_data
            draft.has_errors = not is_valid
            draft.error_count = len([i for i in issues if i["type"] == "shot"])
            draft.validation_notes = json.dumps(issues) if issues else None
            draft.status = 'draft'  # Reset to draft if it was reviewing

            db.commit()
            db.refresh(draft)

            return {
                "success": True,
                "draft_id": draft.id,
                "has_errors": draft.has_errors,
                "error_count": draft.error_count,
                "validation_issues": issues
            }
        else:
            raise HTTPException(status_code=400, detail="No draft_data provided")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update draft error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/surveys/{survey_id}/drafts/{draft_id}/commit")
def commit_draft(
    survey_id: int,
    draft_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Commit a draft to the main survey (final step)
    """
    try:
        draft = db.query(SurveyDraft).filter(
            SurveyDraft.id == draft_id,
            SurveyDraft.survey_id == survey_id
        ).first()

        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")

        # Verify access
        survey = db.query(Survey).filter(
            Survey.id == survey_id,
            Survey.owner_id == current_user.id
        ).first()

        if not survey:
            raise HTTPException(status_code=403, detail="Access denied")

        # Check if already committed
        if draft.status == 'committed':
            raise HTTPException(status_code=400, detail="Draft already committed")

        # Validate before committing
        is_valid, issues = draft_utils.validate_draft_data(draft.draft_data)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot commit draft with {len(issues)} validation errors"
            )

        # Convert draft data to survey format
        survey_data = draft_utils.convert_draft_to_survey_data(draft.draft_data)

        # TODO: Merge survey_data into main survey
        # For now, just mark as committed
        draft.status = 'committed'
        draft.committed_at = datetime.now()

        db.commit()

        return {
            "success": True,
            "draft_id": draft.id,
            "survey_id": survey_id,
            "committed_at": draft.committed_at,
            "message": "Draft successfully committed to survey"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Commit draft error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/surveys/{survey_id}/drafts/{draft_id}")
def delete_draft(
    survey_id: int,
    draft_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete a draft
    """
    try:
        draft = db.query(SurveyDraft).filter(
            SurveyDraft.id == draft_id,
            SurveyDraft.survey_id == survey_id
        ).first()

        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")

        # Verify access
        survey = db.query(Survey).filter(
            Survey.id == survey_id,
            Survey.owner_id == current_user.id
        ).first()

        if not survey:
            raise HTTPException(status_code=403, detail="Access denied")

        # Don't allow deleting committed drafts
        if draft.status == 'committed':
            raise HTTPException(status_code=400, detail="Cannot delete committed draft")

        db.delete(draft)
        db.commit()

        return {
            "success": True,
            "message": "Draft deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete draft error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================
# SURVEY PROCESSING & EXPORT ENDPOINTS
# ============================================================

@app.get("/surveys/{survey_id}/data")
def get_survey_data(
    survey_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all committed survey shots for processing/export
    """
    try:
        # Verify survey access
        survey = db.query(Survey).filter(
            Survey.id == survey_id,
            Survey.owner_id == current_user.id
        ).first()

        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")

        # Get all committed drafts
        committed_drafts = db.query(SurveyDraft).filter(
            SurveyDraft.survey_id == survey_id,
            SurveyDraft.status == 'committed'
        ).order_by(SurveyDraft.committed_at).all()

        # Extract and combine all shots
        all_shots = export_utils.get_survey_shots_from_drafts(committed_drafts)

        # Separate survey shots and splays
        survey_shots = [s for s in all_shots if s.get('type') == 'survey']
        splays = [s for s in all_shots if s.get('type') == 'splay']

        return {
            "survey_id": survey_id,
            "survey_name": survey.title,
            "section": survey.section,
            "total_shots": len(all_shots),
            "survey_shots": len(survey_shots),
            "splays": len(splays),
            "committed_drafts": len(committed_drafts),
            "shots": all_shots,
            "metadata": {
                "created_at": survey.created_at,
                "updated_at": survey.updated_at,
                "num_stations": survey.num_stations,
                "num_shots": survey.num_shots
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get survey data error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/surveys/{survey_id}/reduce")
def reduce_survey(
    survey_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Reduce the survey: calculate 3D station positions from shots
    """
    try:
        # Get survey data
        survey = db.query(Survey).filter(
            Survey.id == survey_id,
            Survey.owner_id == current_user.id
        ).first()

        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")

        # Get all committed shots
        committed_drafts = db.query(SurveyDraft).filter(
            SurveyDraft.survey_id == survey_id,
            SurveyDraft.status == 'committed'
        ).all()

        all_shots = export_utils.get_survey_shots_from_drafts(committed_drafts)
        
        # Filter to survey shots only (not splays)
        survey_shots = [s for s in all_shots if s.get('type') == 'survey']

        if not survey_shots:
            raise HTTPException(status_code=400, detail="No survey shots to reduce")

        # Convert to format expected by reduce_graph
        from .models import Shot
        shot_objects = []
        for s in survey_shots:
            shot_obj = Shot(
                from_station=s['from'],
                to_station=s['to'],
                slope_distance=s['distance'],
                azimuth_deg=s['compass'],
                inclination_deg=s['clino']
            )
            shot_objects.append(shot_obj)

        # Run reduction
        origin_station = shot_objects[0].from_station
        positions, edges, meta = reduce_graph(
            shots=shot_objects,
            origin_name=origin_station,
            origin_x=0.0,
            origin_y=0.0,
            origin_z=0.0
        )

        # Update survey metadata
        survey.num_stations = len(positions)
        survey.num_shots = len(survey_shots)
        survey.total_slope_distance = sum(s['distance'] for s in survey_shots)
        db.commit()

        return {
            "success": True,
            "survey_id": survey_id,
            "num_stations": len(positions),
            "num_shots": len(survey_shots),
            "total_distance": survey.total_slope_distance,
            "stations": positions,
            "edges": edges,
            "metadata": meta
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reduce survey error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/surveys/{survey_id}/plot")
def plot_survey(
    survey_id: int,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate a line plot of the survey
    """
    try:
        # Get survey data
        survey = db.query(Survey).filter(
            Survey.id == survey_id,
            Survey.owner_id == current_user.id
        ).first()

        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")

        # Get all committed shots
        committed_drafts = db.query(SurveyDraft).filter(
            SurveyDraft.survey_id == survey_id,
            SurveyDraft.status == 'committed'
        ).all()

        all_shots = export_utils.get_survey_shots_from_drafts(committed_drafts)
        survey_shots = [s for s in all_shots if s.get('type') == 'survey']

        if not survey_shots:
            raise HTTPException(status_code=400, detail="No survey shots to plot")

        # Convert to format expected by plot_traverse
        from .models import Shot
        shot_objects = []
        for s in survey_shots:
            shot_obj = Shot(
                from_station=s['from'],
                to_station=s['to'],
                slope_distance=s['distance'],
                azimuth_deg=s['compass'],
                inclination_deg=s['clino']
            )
            shot_objects.append(shot_obj)

        # Run reduction first
        origin_station = shot_objects[0].from_station
        positions, edges, meta = reduce_graph(
            shots=shot_objects,
            origin_name=origin_station,
            origin_x=0.0,
            origin_y=0.0,
            origin_z=0.0
        )

        # Generate plot
        png_bytes = plot_traverse(positions, edges, survey.section)

        # Return as PNG image
        return StreamingResponse(
            io.BytesIO(png_bytes),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename=survey_{survey_id}_plot.png"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Plot survey error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/surveys/{survey_id}/export/{format}")
def export_survey(
    survey_id: int,
    format: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Export survey in various formats: srv, dat, svx, th, csv, json
    """
    try:
        # Verify survey access
        survey = db.query(Survey).filter(
            Survey.id == survey_id,
            Survey.owner_id == current_user.id
        ).first()

        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")

        # Get all committed shots
        committed_drafts = db.query(SurveyDraft).filter(
            SurveyDraft.survey_id == survey_id,
            SurveyDraft.status == 'committed'
        ).all()

        all_shots = export_utils.get_survey_shots_from_drafts(committed_drafts)

        if not all_shots:
            raise HTTPException(status_code=400, detail="No committed data to export")

        survey_name = survey.title or f"Survey_{survey_id}"

        # Generate export based on format
        if format == "srv":
            content = export_utils.convert_to_walls_srv(all_shots, survey_name)
            media_type = "text/plain"
            extension = "srv"
        elif format == "dat":
            content = export_utils.convert_to_compass_dat(all_shots, survey_name)
            media_type = "text/plain"
            extension = "dat"
        elif format == "svx":
            content = export_utils.convert_to_survex_svx(all_shots, survey_name)
            media_type = "text/plain"
            extension = "svx"
        elif format == "th":
            content = export_utils.convert_to_therion_th(all_shots, survey_name)
            media_type = "text/plain"
            extension = "th"
        elif format == "csv":
            content = export_utils.convert_to_csv(all_shots)
            media_type = "text/csv"
            extension = "csv"
        elif format == "json":
            metadata = {
                "survey_id": survey_id,
                "survey_name": survey_name,
                "section": survey.section,
                "total_shots": len(all_shots)
            }
            content = export_utils.convert_to_json(all_shots, metadata)
            media_type = "application/json"
            extension = "json"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

        # Generate filename
        filename = export_utils.format_export_filename(survey_name, extension)

        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(content.encode('utf-8')),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export survey error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

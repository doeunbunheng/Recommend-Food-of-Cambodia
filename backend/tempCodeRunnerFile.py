from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import sys, os

sys.path.insert(0, os.path.dirname(__file__))

from database import engine, get_db
from db_models import Base, UserSession
from models import UserInput, RecommendationResponse, BMIResult, FoodItem, SessionRecord
from services.recommendation import recommend, bmi_only, get_all_foods
from auth import require_api_key

# Create tables on startup (safe to run multiple times)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Cambodian Food Recommendation API",
    description="""
## 🍚 Budget-Aware Healthy Cambodian Food Recommendation System

**I4-AMS-A · Institute of Technology of Cambodia · 2025–2026**

### 🔐 Authentication
All data endpoints require an API key in the request header:
```
X-API-Key: your-secret-key
```

### Quick Start
1. `POST /recommend` — submit your health & budget data → get a meal plan
2. `GET /history` — view all past recommendation sessions stored in PostgreSQL
3. `GET /foods` — browse the full Cambodian food database
    """,
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── PUBLIC ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Public"])
def root():
    return {"message": "Cambodian Food Recommendation API 🍚", "docs": "/docs", "version": "2.0.0"}

@app.get("/health-check", tags=["Public"])
def health_check():
    return {"status": "ok"}


# ── RECOMMEND ─────────────────────────────────────────────────────────────────

@app.post(
    "/recommend",
    response_model=RecommendationResponse,
    tags=["Recommendation"],
    summary="Get personalised Cambodian meal recommendations",
    description="""
🔐 **Requires X-API-Key header.**

Submit your health and budget data to receive:
- BMI analysis and health classification
- Daily calorie and water estimates
- A personalised Breakfast / Lunch / Dinner plan from the Cambodian food database
- The session is **automatically saved to PostgreSQL**

**Activity levels:** `sedentary` | `light` | `moderate` | `active` | `very_active`

**Budget type:** `daily` (per day) or `monthly` (divided by 30)
    """,
)
def get_recommendation(
    user: UserInput,
    db:   Session = Depends(get_db),
    _key: str     = Depends(require_api_key),
):
    try:
        return recommend(user, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── BMI ───────────────────────────────────────────────────────────────────────

@app.get(
    "/bmi",
    response_model=BMIResult,
    tags=["Health Analysis"],
    summary="Quick BMI calculator",
    description="🔐 **Requires X-API-Key.** Calculate BMI and get health classification.",
)
def calculate_bmi_endpoint(
    weight_kg: float = Query(..., gt=10,  lt=300, description="Weight in kg"),
    height_m:  float = Query(..., gt=0.5, lt=3.0, description="Height in metres"),
    _key: str        = Depends(require_api_key),
):
    try:
        return bmi_only(weight_kg, height_m)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── FOODS ─────────────────────────────────────────────────────────────────────

@app.get(
    "/foods",
    response_model=List[FoodItem],
    tags=["Food Database"],
    summary="List all Cambodian foods",
    description="🔐 **Requires X-API-Key.** Returns all 100+ dishes from the PostgreSQL food table.",
)
def list_foods(
    db:   Session = Depends(get_db),
    _key: str     = Depends(require_api_key),
):
    return get_all_foods(db)


@app.get(
    "/foods/filter",
    response_model=List[FoodItem],
    tags=["Food Database"],
    summary="Filter foods by meal type or health label",
    description="""
🔐 **Requires X-API-Key.**

Filter foods using optional query parameters:
- `meal_type`: e.g. `breakfast`, `lunch`, `dinner`
- `health_label`: `Normal`, `Healthy`, or `High Calorie`
- `max_price`: maximum price in USD
    """,
)
def filter_foods(
    meal_type:    Optional[str]  = Query(None, description="breakfast | lunch | dinner"),
    health_label: Optional[str]  = Query(None, description="Normal | Healthy | High Calorie"),
    max_price:    Optional[float] = Query(None, description="Max price in USD"),
    db:   Session = Depends(get_db),
    _key: str     = Depends(require_api_key),
):
    from db_models import Food
    from sqlalchemy import or_
    q = db.query(Food)
    if meal_type:
        kws = meal_type.strip().lower()
        q = q.filter(Food.meal_type.ilike(f"%{kws}%"))
    if health_label:
        q = q.filter(Food.health_label.ilike(f"%{health_label.strip()}%"))
    if max_price is not None:
        q = q.filter(Food.price_usd <= max_price)
    rows = q.order_by(Food.food_id).all()
    return [FoodItem(food_id=r.food_id, food_name=r.food_name,
                     category=r.category.strip(), calories=r.calories,
                     price_usd=r.price_usd, meal_type=r.meal_type,
                     price_riel=r.price_riel, health_label=r.health_label)
            for r in rows]


# ── SESSION HISTORY ───────────────────────────────────────────────────────────

@app.get(
    "/history",
    response_model=List[SessionRecord],
    tags=["Session History"],
    summary="View all stored user sessions",
    description="""
🔐 **Requires X-API-Key.**

Returns every recommendation request saved in PostgreSQL,
ordered newest first. Use `limit` and `offset` for pagination.
    """,
)
def get_history(
    limit:  int = Query(50,  ge=1, le=200, description="Number of records to return"),
    offset: int = Query(0,   ge=0,         description="Number of records to skip"),
    db:   Session = Depends(get_db),
    _key: str     = Depends(require_api_key),
):
    rows = (
        db.query(UserSession)
        .order_by(UserSession.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return rows


@app.get(
    "/history/{session_id}",
    response_model=SessionRecord,
    tags=["Session History"],
    summary="Get one session by ID",
    description="🔐 **Requires X-API-Key.** Retrieve a single saved recommendation session.",
)
def get_session(
    session_id: int,
    db:   Session = Depends(get_db),
    _key: str     = Depends(require_api_key),
):
    row = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return row


@app.delete(
    "/history/{session_id}",
    tags=["Session History"],
    summary="Delete a session",
    description="🔐 **Requires X-API-Key.** Permanently delete a stored session.",
)
def delete_session(
    session_id: int,
    db:   Session = Depends(get_db),
    _key: str     = Depends(require_api_key),
):
    row = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    db.delete(row)
    db.commit()
    return {"message": f"Session {session_id} deleted."}

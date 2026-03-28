import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

"""
KhmerPlate API v3.0
"""
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional

from database import engine, get_db
from db_models import Base, UserSession, User, UserPreference, UserFavorite, FoodRating, Food
from models import (
    UserInput, RecommendationResponse, BMIResult, FoodItem,
    SessionRecord, RegisterInput, LoginInput, TokenResponse,
    UserOut, PreferenceInput, PreferenceOut,
    FavoriteToggle, FavoriteOut, RatingInput, RatingOut,
    WeeklyPlanResponse, AnalyticsResponse,
)
from recommendation import (
    recommend, bmi_only, get_all_foods, generate_weekly_plan, _row_to_food_item
)
from auth import (
    require_api_key, require_current_user, get_current_user_optional,
    hash_password, verify_password, create_access_token,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="KhmerPlate — Cambodian Food Recommendation API",
    description="""
## 🍚 KhmerPlate v3.0
**Budget-Aware Healthy Cambodian Food Recommendation System**
*Institute of Technology of Cambodia · I4-AMS-A · 2025–2026*

### 🔐 Auth
| Layer | How | Required for |
|-------|-----|---|
| API Key | `X-API-Key` header | All endpoints |
| JWT Bearer | `Authorization: Bearer <token>` | User endpoints |

### Quick start
1. `POST /register` → create account
2. `POST /login` → get JWT token
3. `PUT /user/preferences` → set dietary preferences
4. `POST /recommend` → get personalised meal plan
5. `POST /meal-plan/week` → generate 7-day plan
6. `POST /foods/{food_id}/rate` → rate a food
7. `POST /favorites` → save/remove a favourite
8. `GET /analytics/me` → your BMI trend & spending history
    """,
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Public ────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Public"])
def root():
    return {"message": "KhmerPlate Cambodian Food API 🍚", "docs": "/docs", "version": "3.0.0"}

@app.get("/health-check", tags=["Public"])
def health_check():
    return {"status": "ok"}


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/register", response_model=UserOut, tags=["Auth"])
def register(body: RegisterInput, db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(400, "Username already taken.")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(400, "Email already registered.")
    user = User(username=body.username, email=body.email, hashed_pw=hash_password(body.password))
    db.add(user); db.commit(); db.refresh(user)
    return user

@app.post("/login", response_model=TokenResponse, tags=["Auth"])
def login(body: LoginInput, db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_pw):
        raise HTTPException(401, "Invalid username or password.")
    if not user.is_active:
        raise HTTPException(403, "Account disabled.")
    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token, user_id=user.id, username=user.username)

@app.get("/user/me", response_model=UserOut, tags=["Auth"])
def get_me(current=Depends(require_current_user), db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    user = db.query(User).filter(User.id == current["user_id"]).first()
    if not user: raise HTTPException(404, "User not found.")
    return user


# ── Preferences ───────────────────────────────────────────────────────────────

@app.put("/user/preferences", response_model=PreferenceOut, tags=["User"])
def set_preferences(body: PreferenceInput, current=Depends(require_current_user),
                    db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    prefs = db.query(UserPreference).filter(UserPreference.user_id == current["user_id"]).first()
    allergen_str = ",".join(body.avoid_allergens) if body.avoid_allergens else ""
    if prefs:
        prefs.is_vegetarian = body.is_vegetarian
        prefs.avoid_allergens = allergen_str
        prefs.max_cal_per_meal = body.max_cal_per_meal
        prefs.preferred_budget = body.preferred_budget
    else:
        prefs = UserPreference(user_id=current["user_id"], is_vegetarian=body.is_vegetarian,
                               avoid_allergens=allergen_str, max_cal_per_meal=body.max_cal_per_meal,
                               preferred_budget=body.preferred_budget)
        db.add(prefs)
    db.commit(); db.refresh(prefs)
    return prefs

@app.get("/user/preferences", response_model=PreferenceOut, tags=["User"])
def get_preferences(current=Depends(require_current_user), db: Session = Depends(get_db),
                    _: str = Depends(require_api_key)):
    prefs = db.query(UserPreference).filter(UserPreference.user_id == current["user_id"]).first()
    if not prefs: raise HTTPException(404, "No preferences set yet.")
    return prefs


# ── Recommend ─────────────────────────────────────────────────────────────────

@app.post("/recommend", response_model=RecommendationResponse, tags=["Recommendation"])
def get_recommendation(user: UserInput, db: Session = Depends(get_db),
                       _: str = Depends(require_api_key),
                       current=Depends(get_current_user_optional)):
    if current:
        user.user_id = current["user_id"]
    try:
        return recommend(user, db)
    except Exception as e:
        raise HTTPException(500, str(e))

@app.post("/meal-plan/week", response_model=WeeklyPlanResponse, tags=["Recommendation"])
def get_weekly_plan(user: UserInput, db: Session = Depends(get_db),
                    _: str = Depends(require_api_key),
                    current=Depends(get_current_user_optional)):
    if current:
        user.user_id = current["user_id"]
    try:
        rec = recommend(user, db)
        return generate_weekly_plan(user, rec.session_id, db)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── BMI ───────────────────────────────────────────────────────────────────────

@app.get("/bmi", response_model=BMIResult, tags=["Health Analysis"])
def calculate_bmi_endpoint(weight_kg: float = Query(..., gt=10, lt=300),
                           height_m: float = Query(..., gt=0.5, lt=3.0),
                           _: str = Depends(require_api_key)):
    return bmi_only(weight_kg, height_m)


# ── Foods ─────────────────────────────────────────────────────────────────────

@app.get("/foods", response_model=List[FoodItem], tags=["Food Database"])
def list_foods(db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    return get_all_foods(db)

@app.get("/foods/search", response_model=List[FoodItem], tags=["Food Database"])
def search_foods(q: Optional[str] = Query(None),
                 meal_type: Optional[str] = Query(None),
                 health_label: Optional[str] = Query(None),
                 max_price: Optional[float] = Query(None),
                 vegetarian: Optional[bool] = Query(None),
                 max_calories: Optional[float] = Query(None),
                 db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    query = db.query(Food)
    if q:
        query = query.filter((Food.food_name.ilike(f"%{q}%")) | (Food.category.ilike(f"%{q}%")))
    if meal_type:
        query = query.filter(Food.meal_type.ilike(f"%{meal_type.strip()}%"))
    if health_label:
        query = query.filter(Food.health_label.ilike(f"%{health_label.strip()}%"))
    if max_price is not None:
        query = query.filter(Food.price_usd <= max_price)
    if vegetarian is not None:
        query = query.filter(Food.is_vegetarian == vegetarian)
    if max_calories is not None:
        query = query.filter(Food.calories <= max_calories)
    return [_row_to_food_item(r) for r in query.order_by(Food.food_id).all()]

@app.get("/foods/{food_id}", response_model=FoodItem, tags=["Food Database"])
def get_food(food_id: int, db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    row = db.query(Food).filter(Food.food_id == food_id).first()
    if not row: raise HTTPException(404, f"Food {food_id} not found.")
    return _row_to_food_item(row)


# ── Favorites ─────────────────────────────────────────────────────────────────

@app.post("/favorites", tags=["Favorites"])
def toggle_favorite(body: FavoriteToggle, current=Depends(require_current_user),
                    db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    food = db.query(Food).filter(Food.food_id == body.food_id).first()
    if not food: raise HTTPException(404, "Food not found.")
    existing = db.query(UserFavorite).filter(
        UserFavorite.user_id == current["user_id"],
        UserFavorite.food_id == body.food_id).first()
    if existing:
        db.delete(existing); db.commit()
        return {"action": "removed", "food_id": body.food_id}
    db.add(UserFavorite(user_id=current["user_id"], food_id=body.food_id))
    db.commit()
    return {"action": "added", "food_id": body.food_id, "food_name": food.food_name}

@app.get("/favorites", response_model=List[FavoriteOut], tags=["Favorites"])
def list_favorites(current=Depends(require_current_user), db: Session = Depends(get_db),
                   _: str = Depends(require_api_key)):
    rows = db.query(UserFavorite).filter(UserFavorite.user_id == current["user_id"]).all()
    result = []
    for r in rows:
        food = db.query(Food).filter(Food.food_id == r.food_id).first()
        result.append(FavoriteOut(id=r.id, food_id=r.food_id,
                                  food_name=food.food_name if food else "Unknown",
                                  created_at=r.created_at))
    return result


# ── Ratings ───────────────────────────────────────────────────────────────────

@app.post("/foods/{food_id}/rate", tags=["Ratings"])
def rate_food(food_id: int, body: RatingInput, current=Depends(require_current_user),
              db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    food = db.query(Food).filter(Food.food_id == food_id).first()
    if not food: raise HTTPException(404, "Food not found.")
    existing = db.query(FoodRating).filter(
        FoodRating.user_id == current["user_id"], FoodRating.food_id == food_id).first()
    if existing:
        existing.rating = body.rating; existing.comment = body.comment
    else:
        db.add(FoodRating(user_id=current["user_id"], food_id=food_id,
                          rating=body.rating, comment=body.comment))
    db.commit()
    from sqlalchemy import func as sqlfunc
    avg = db.query(sqlfunc.avg(FoodRating.rating)).filter(FoodRating.food_id == food_id).scalar()
    return {"food_id": food_id, "your_rating": body.rating, "avg_rating": round(avg or 0, 2)}

@app.get("/foods/{food_id}/ratings", tags=["Ratings"])
def get_food_ratings(food_id: int, db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    from sqlalchemy import func as sqlfunc
    avg = db.query(sqlfunc.avg(FoodRating.rating)).filter(FoodRating.food_id == food_id).scalar()
    count = db.query(FoodRating).filter(FoodRating.food_id == food_id).count()
    return {"food_id": food_id, "avg_rating": round(avg or 0, 2), "total_ratings": count}


# ── Analytics ─────────────────────────────────────────────────────────────────

@app.get("/analytics/me", response_model=AnalyticsResponse, tags=["Analytics"])
def my_analytics(current=Depends(require_current_user), db: Session = Depends(get_db),
                 _: str = Depends(require_api_key)):
    uid = current["user_id"]
    sessions = db.query(UserSession).filter(UserSession.user_id == uid).order_by(UserSession.created_at).all()
    total = len(sessions)
    avg_bmi   = round(sum(s.bmi for s in sessions if s.bmi) / total, 1) if total else None
    avg_spend = round(sum(s.total_meal_cost_usd for s in sessions if s.total_meal_cost_usd) / total, 2) if total else None
    bmi_trend   = [{"date": str(s.created_at.date()), "bmi": s.bmi} for s in sessions if s.bmi]
    spend_trend = [{"date": str(s.created_at.date()), "cost": s.total_meal_cost_usd} for s in sessions if s.total_meal_cost_usd]
    food_counts: dict = {}
    for s in sessions:
        for name in [s.breakfast_food_name, s.lunch_food_name, s.dinner_food_name]:
            if name: food_counts[name] = food_counts.get(name, 0) + 1
    top_foods = [{"food_name": k, "count": v} for k, v in sorted(food_counts.items(), key=lambda x: -x[1])[:10]]
    bmi_dist: dict = {}
    for s in sessions:
        if s.bmi_status: bmi_dist[s.bmi_status] = bmi_dist.get(s.bmi_status, 0) + 1
    return AnalyticsResponse(total_sessions=total, avg_bmi=avg_bmi, bmi_trend=bmi_trend,
                             avg_daily_spend_usd=avg_spend, spend_trend=spend_trend,
                             top_foods=top_foods, bmi_distribution=bmi_dist)

@app.get("/analytics/global", tags=["Analytics"])
def global_analytics(db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    from sqlalchemy import func as sqlfunc
    return {
        "total_sessions": db.query(UserSession).count(),
        "total_users":    db.query(User).count(),
        "avg_bmi":        round(db.query(sqlfunc.avg(UserSession.bmi)).scalar() or 0, 1),
    }


# ── History ───────────────────────────────────────────────────────────────────

@app.get("/history", response_model=List[SessionRecord], tags=["Session History"])
def get_history(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    return db.query(UserSession).order_by(UserSession.created_at.desc()).offset(offset).limit(limit).all()

@app.get("/history/me", response_model=List[SessionRecord], tags=["Session History"])
def my_history(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
               current=Depends(require_current_user), db: Session = Depends(get_db),
               _: str = Depends(require_api_key)):
    return (db.query(UserSession).filter(UserSession.user_id == current["user_id"])
            .order_by(UserSession.created_at.desc()).offset(offset).limit(limit).all())

@app.get("/history/{session_id}", response_model=SessionRecord, tags=["Session History"])
def get_session(session_id: int, db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    row = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not row: raise HTTPException(404, f"Session {session_id} not found.")
    return row

@app.delete("/history/{session_id}", tags=["Session History"])
def delete_session(session_id: int, db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    row = db.query(UserSession).filter(UserSession.id == session_id).first()
    if not row: raise HTTPException(404, f"Session {session_id} not found.")
    db.delete(row); db.commit()
    return {"message": f"Session {session_id} deleted."}

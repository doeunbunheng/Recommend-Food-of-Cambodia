import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

"""
Enhanced Recommendation Engine
- Calorie-gap-aware meal selection (picks meals closest to target calorie split)
- Snack slot support
- Vegetarian / allergen filtering
- Weekly 7-day plan generation
- Nutrition summary per recommendation
"""
import json
import random
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from db_models import Food, UserSession, UserPreference, WeeklyMealPlan
from models import (
    UserInput, BMIResult, MealSlot, MealPlan,
    RecommendationResponse, FoodItem, NutritionSummary,
    WeeklyPlanResponse, DayPlan,
)

# ── BMI & health calculations ─────────────────────────────────────────────────

def calculate_bmi(weight_kg: float, height_m: float) -> BMIResult:
    bmi = round(weight_kg / (height_m ** 2), 1)
    if bmi < 18.5:
        return BMIResult(bmi=bmi, status="Underweight",
            description="Your BMI is below the healthy range. Focus on nutrient-rich, higher-calorie Cambodian foods like Bai Sach Chrouk and Lok Lak.")
    elif bmi < 25:
        return BMIResult(bmi=bmi, status="Normal",
            description="Your BMI is within the healthy range. Maintain a balanced diet with a variety of Cambodian proteins, vegetables, and rice.")
    elif bmi < 30:
        return BMIResult(bmi=bmi, status="Overweight",
            description="Your BMI is above the healthy range. Choose lighter dishes like soups, grilled proteins, and steamed vegetables.")
    else:
        return BMIResult(bmi=bmi, status="Obese",
            description="Your BMI indicates obesity. Focus on Healthy-labelled, low-calorie Cambodian dishes and avoid High Calorie items.")

ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.0, "light": 1.1, "moderate": 1.2,
    "active": 1.35,   "very_active": 1.5,
}

def estimate_calories(weight_kg, gender, activity):
    base = weight_kg * 30 if gender == "male" else weight_kg * 28
    return int(base * ACTIVITY_MULTIPLIERS.get(activity, 1.0))

def estimate_water(weight_kg):
    return round(weight_kg * 0.033, 2)

DIET_TIPS = {
    "Underweight": "Eat calorie-dense Cambodian foods: Lok Lak, Bai Sach Chrouk, Samlar Kari, and Kaw Sach Chrouk to build healthy weight.",
    "Normal":      "Keep your balanced diet with Amok, Grilled Fish, vegetables, and rice. Stay hydrated with coconut water!",
    "Overweight":  "Choose lighter dishes: Samlar Proher, Grilled Fish, Cha Trakoun, and fruits. Limit High Calorie items like Lort Cha.",
    "Obese":       "Prioritise Healthy-labelled foods: soups, grilled proteins, fruits. Avoid High Calorie dishes and sugary drinks.",
}

# Meal type keyword mapping
MEAL_MATCH = {
    "breakfast": ["breakfast", "morning"],
    "lunch":     ["lunch", "morning/lunch", "breakfast/lunch"],
    "dinner":    ["dinner", "lunch/dinner"],
    "snack":     ["snack", "dessert", "drink", "fruit"],
}

# Target calorie split per meal (% of daily target)
CALORIE_SPLIT = {
    "breakfast": 0.25,
    "lunch":     0.35,
    "dinner":    0.30,
    "snack":     0.10,
}


def _apply_prefs(query, prefs: Optional[UserPreference], bmi_status: str):
    """Apply dietary filters to a SQLAlchemy query."""
    if prefs:
        if prefs.is_vegetarian:
            query = query.filter(Food.is_vegetarian == True)
        if prefs.avoid_allergens:
            for allergen in prefs.avoid_allergens.split(","):
                allergen = allergen.strip()
                if allergen:
                    query = query.filter(~Food.allergens.ilike(f"%{allergen}%"))
        if prefs.max_cal_per_meal:
            query = query.filter(Food.calories <= prefs.max_cal_per_meal)

    if bmi_status in ("Overweight", "Obese"):
        query = query.filter(Food.health_label != "High Calorie")

    return query


def _query_meal(
    db: Session,
    slot: str,
    bmi_status: str,
    max_price: float,
    exclude_ids: list,
    target_calories: float,
    prefs: Optional[UserPreference] = None,
) -> Optional[Food]:
    keywords = MEAL_MATCH[slot]
    meal_filter = or_(*[Food.meal_type.ilike(f"%{kw}%") for kw in keywords])

    query = (
        db.query(Food)
        .filter(meal_filter)
        .filter(Food.price_usd <= max_price)
        .filter(Food.food_id.notin_(exclude_ids))
    )
    query = _apply_prefs(query, prefs, bmi_status)
    candidates = query.all()

    if not candidates:
        # Relax price constraint
        query = (db.query(Food)
                   .filter(meal_filter)
                   .filter(Food.food_id.notin_(exclude_ids)))
        query = _apply_prefs(query, prefs, bmi_status)
        candidates = query.all()

    if not candidates:
        candidates = db.query(Food).filter(meal_filter).all()

    if not candidates:
        return None

    # Pick the food closest to the target calorie for this slot
    best = min(candidates, key=lambda f: abs((f.calories or 0) - target_calories))
    # Add light randomisation: randomly pick among the 3 closest options
    candidates_sorted = sorted(candidates, key=lambda f: abs((f.calories or 0) - target_calories))
    return random.choice(candidates_sorted[:min(3, len(candidates_sorted))])


def _food_to_slot(f: Food) -> MealSlot:
    return MealSlot(
        food_id=f.food_id, food_name=f.food_name,
        category=(f.category or "").strip(), calories=f.calories or 0,
        price_usd=f.price_usd or 0, price_riel=f.price_riel or 0,
        health_label=f.health_label or "",
        is_vegetarian=f.is_vegetarian or False,
        protein_g=f.protein_g or 0,
        carbs_g=f.carbs_g or 0,
        fat_g=f.fat_g or 0,
    )


def _fallback(db: Session, slot: str) -> Optional[Food]:
    kws = MEAL_MATCH[slot]
    rows = db.query(Food).filter(or_(*[Food.meal_type.ilike(f"%{k}%") for k in kws])).all()
    return random.choice(rows) if rows else db.query(Food).first()


# ── Main recommend ─────────────────────────────────────────────────────────────

def recommend(user: UserInput, db: Session) -> RecommendationResponse:
    daily_budget = round(user.budget / 30, 2) if user.budget_type == "monthly" else round(user.budget, 2)
    bmi_result   = calculate_bmi(user.weight_kg, user.height_m)
    target_cal   = estimate_calories(user.weight_kg, user.gender, user.activity)
    water        = estimate_water(user.weight_kg)

    # Load user preferences if available
    prefs = None
    if user.user_id:
        prefs = db.query(UserPreference).filter(UserPreference.user_id == user.user_id).first()

    # Budget splits
    snack_share = 0.10 if user.include_snack else 0.0
    b_budget = round(daily_budget * 0.25, 2)
    l_budget = round(daily_budget * (0.35 - snack_share / 2), 2)
    d_budget = round(daily_budget * (0.30 - snack_share / 2), 2)
    s_budget = round(daily_budget * snack_share, 2)

    # Calorie targets per slot
    b_cal = target_cal * CALORIE_SPLIT["breakfast"]
    l_cal = target_cal * CALORIE_SPLIT["lunch"]
    d_cal = target_cal * CALORIE_SPLIT["dinner"]
    s_cal = target_cal * CALORIE_SPLIT["snack"]

    used_ids = []

    bf_row = _query_meal(db, "breakfast", bmi_result.status, b_budget, used_ids, b_cal, prefs)
    if bf_row: used_ids.append(bf_row.food_id)

    ln_row = _query_meal(db, "lunch",     bmi_result.status, l_budget, used_ids, l_cal, prefs)
    if ln_row: used_ids.append(ln_row.food_id)

    dn_row = _query_meal(db, "dinner",    bmi_result.status, d_budget, used_ids, d_cal, prefs)
    if dn_row: used_ids.append(dn_row.food_id)

    sn_row = None
    if user.include_snack and s_budget > 0:
        sn_row = _query_meal(db, "snack", bmi_result.status, s_budget, used_ids, s_cal, prefs)

    bf = _food_to_slot(bf_row or _fallback(db, "breakfast"))
    ln = _food_to_slot(ln_row or _fallback(db, "lunch"))
    dn = _food_to_slot(dn_row or _fallback(db, "dinner"))
    sn = _food_to_slot(sn_row) if sn_row else None

    total_cal  = bf.calories + ln.calories + dn.calories + (sn.calories if sn else 0)
    total_cost = round(bf.price_usd + ln.price_usd + dn.price_usd + (sn.price_usd if sn else 0), 2)

    nutrition = NutritionSummary(
        total_protein_g  = round(bf.protein_g + ln.protein_g + dn.protein_g + (sn.protein_g if sn else 0), 1),
        total_carbs_g    = round(bf.carbs_g   + ln.carbs_g   + dn.carbs_g   + (sn.carbs_g   if sn else 0), 1),
        total_fat_g      = round(bf.fat_g     + ln.fat_g     + dn.fat_g     + (sn.fat_g     if sn else 0), 1),
        calorie_coverage = round((total_cal / target_cal) * 100, 1) if target_cal else 0,
    )

    session = UserSession(
        user_id=user.user_id,
        height_m=user.height_m, weight_kg=user.weight_kg,
        gender=user.gender,     activity=user.activity,
        budget_input=user.budget, budget_type=user.budget_type,
        daily_budget_usd=daily_budget,
        bmi=bmi_result.bmi,    bmi_status=bmi_result.status,
        daily_calories_kcal=target_cal, water_liters_per_day=water,
        breakfast_food_id=bf.food_id,   breakfast_food_name=bf.food_name,
        breakfast_calories=bf.calories, breakfast_price_usd=bf.price_usd,
        lunch_food_id=ln.food_id,       lunch_food_name=ln.food_name,
        lunch_calories=ln.calories,     lunch_price_usd=ln.price_usd,
        dinner_food_id=dn.food_id,      dinner_food_name=dn.food_name,
        dinner_calories=dn.calories,    dinner_price_usd=dn.price_usd,
        snack_food_id=sn.food_id       if sn else None,
        snack_food_name=sn.food_name   if sn else None,
        snack_calories=sn.calories     if sn else None,
        snack_price_usd=sn.price_usd   if sn else None,
        total_meal_calories=total_cal,
        total_meal_cost_usd=total_cost,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return RecommendationResponse(
        session_id=session.id,
        bmi=bmi_result.bmi, bmi_status=bmi_result.status,
        bmi_description=bmi_result.description,
        daily_calories_kcal=target_cal, water_liters_per_day=water,
        daily_budget_usd=daily_budget,
        meal_plan=MealPlan(breakfast=bf, lunch=ln, dinner=dn, snack=sn),
        total_meal_calories=total_cal,
        total_meal_cost_usd=total_cost,
        diet_tip=DIET_TIPS[bmi_result.status],
        nutrition=nutrition,
        budget_remaining_usd=round(daily_budget - total_cost, 2),
    )


# ── Weekly plan ───────────────────────────────────────────────────────────────

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

def generate_weekly_plan(user: UserInput, session_id: int, db: Session) -> WeeklyPlanResponse:
    days_out: List[DayPlan] = []
    total_cost = 0.0
    total_cal  = 0.0

    daily_budget = round(user.budget / 30, 2) if user.budget_type == "monthly" else round(user.budget, 2)
    bmi_result   = calculate_bmi(user.weight_kg, user.height_m)
    target_cal   = estimate_calories(user.weight_kg, user.gender, user.activity)

    prefs = None
    if user.user_id:
        prefs = db.query(UserPreference).filter(UserPreference.user_id == user.user_id).first()

    # Collect all eligible foods per slot once for efficiency
    def pool(slot):
        kws = MEAL_MATCH[slot]
        q = db.query(Food).filter(or_(*[Food.meal_type.ilike(f"%{k}%") for k in kws]))
        q = _apply_prefs(q, prefs, bmi_result.status)
        return q.all() or db.query(Food).filter(or_(*[Food.meal_type.ilike(f"%{k}%") for k in kws])).all()

    bf_pool = pool("breakfast")
    ln_pool = pool("lunch")
    dn_pool = pool("dinner")
    sn_pool = pool("snack") if user.include_snack else []

    for day_name in DAYS:
        # Pick without repetition within the same day, allow repetition across days
        used = []
        def pick(p, target_cal_slot, max_price):
            eligible = [f for f in p if f.food_id not in used and (f.price_usd or 0) <= max_price]
            if not eligible:
                eligible = p
            if not eligible:
                return None
            sorted_p = sorted(eligible, key=lambda f: abs((f.calories or 0) - target_cal_slot))
            chosen = random.choice(sorted_p[:min(3, len(sorted_p))])
            used.append(chosen.food_id)
            return chosen

        b_cal = target_cal * CALORIE_SPLIT["breakfast"]
        l_cal = target_cal * CALORIE_SPLIT["lunch"]
        d_cal = target_cal * CALORIE_SPLIT["dinner"]
        s_cal = target_cal * CALORIE_SPLIT["snack"]

        snack_share = 0.10 if user.include_snack else 0.0

        bf = _food_to_slot(pick(bf_pool, b_cal, daily_budget * 0.25) or bf_pool[0])
        ln = _food_to_slot(pick(ln_pool, l_cal, daily_budget * (0.35 - snack_share/2)) or ln_pool[0])
        dn = _food_to_slot(pick(dn_pool, d_cal, daily_budget * (0.30 - snack_share/2)) or dn_pool[0])
        sn_row = pick(sn_pool, s_cal, daily_budget * snack_share) if sn_pool and user.include_snack else None
        sn = _food_to_slot(sn_row) if sn_row else None

        day_cal  = bf.calories + ln.calories + dn.calories + (sn.calories if sn else 0)
        day_cost = round(bf.price_usd + ln.price_usd + dn.price_usd + (sn.price_usd if sn else 0), 2)
        total_cost += day_cost
        total_cal  += day_cal

        days_out.append(DayPlan(
            day=day_name,
            breakfast=bf, lunch=ln, dinner=dn, snack=sn,
            day_total_calories=round(day_cal, 1),
            day_total_cost_usd=day_cost,
        ))

    plan_json = json.dumps([d.model_dump() for d in days_out], default=str)

    user_id = user.user_id
    plan = WeeklyMealPlan(
        user_id=user_id, session_id=session_id,
        plan_json=plan_json,
        total_cost_usd=round(total_cost, 2),
        total_calories=round(total_cal, 1),
        avg_daily_cost=round(total_cost / 7, 2),
        avg_daily_calories=round(total_cal / 7, 1),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    return WeeklyPlanResponse(
        plan_id=plan.id, session_id=session_id,
        days=days_out,
        total_cost_usd=plan.total_cost_usd,
        total_calories=plan.total_calories,
        avg_daily_cost=plan.avg_daily_cost,
        avg_daily_calories=plan.avg_daily_calories,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def bmi_only(weight_kg, height_m):
    return calculate_bmi(weight_kg, height_m)

def get_all_foods(db: Session):
    rows = db.query(Food).order_by(Food.food_id).all()
    return [_row_to_food_item(r) for r in rows]

def _row_to_food_item(r: Food) -> FoodItem:
    return FoodItem(
        food_id=r.food_id, food_name=r.food_name,
        category=(r.category or "").strip(), calories=r.calories or 0,
        price_usd=r.price_usd or 0, meal_type=r.meal_type or "",
        price_riel=r.price_riel or 0, health_label=r.health_label or "",
        is_vegetarian=r.is_vegetarian or False,
        allergens=r.allergens or "",
        protein_g=r.protein_g or 0,
        carbs_g=r.carbs_g or 0,
        fat_g=r.fat_g or 0,
    )

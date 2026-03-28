"""
Recommendation engine — queries PostgreSQL food table,
applies BMI/budget rules, and stores every session to user_sessions.
"""
import random
from sqlalchemy.orm import Session
from sqlalchemy import or_

from db_models import Food, UserSession
from models import (
    UserInput, BMIResult, MealSlot, MealPlan,
    RecommendationResponse, FoodItem
)

# ── BMI ───────────────────────────────────────────────────────────────────────

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

ACTIVITY_MULTIPLIERS = {"sedentary":1.0,"light":1.1,"moderate":1.2,"active":1.35,"very_active":1.5}

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

# Meal slot keyword mapping for the real dataset meal_type values
MEAL_MATCH = {
    "breakfast": ["breakfast", "morning"],
    "lunch":     ["lunch", "morning/lunch", "breakfast/lunch"],
    "dinner":    ["dinner", "lunch/dinner"],
}

def _query_meal(db: Session, slot: str, bmi_status: str, max_price: float, exclude_ids: list) -> Food:
    keywords = MEAL_MATCH[slot]
    meal_filter = or_(*[Food.meal_type.ilike(f"%{kw}%") for kw in keywords])
    query = (db.query(Food)
               .filter(meal_filter)
               .filter(Food.price_usd <= max_price)
               .filter(Food.food_id.notin_(exclude_ids)))
    if bmi_status in ("Overweight", "Obese"):
        preferred = query.filter(Food.health_label != "High Calorie").all()
        if preferred:
            return random.choice(preferred)
    candidates = query.all()
    if not candidates:
        candidates = (db.query(Food).filter(meal_filter)
                        .filter(Food.food_id.notin_(exclude_ids)).all())
    return random.choice(candidates) if candidates else None

def _food_to_slot(f: Food) -> MealSlot:
    return MealSlot(food_id=f.food_id, food_name=f.food_name,
                    category=f.category.strip(), calories=f.calories,
                    price_usd=f.price_usd, price_riel=f.price_riel,
                    health_label=f.health_label)

def recommend(user: UserInput, db: Session) -> RecommendationResponse:
    daily_budget = round(user.budget / 30, 2) if user.budget_type == "monthly" else round(user.budget, 2)
    bmi_result   = calculate_bmi(user.weight_kg, user.height_m)
    calories     = estimate_calories(user.weight_kg, user.gender, user.activity)
    water        = estimate_water(user.weight_kg)

    b_budget = round(daily_budget * 0.30, 2)
    l_budget = round(daily_budget * 0.40, 2)
    d_budget = round(daily_budget * 0.30, 2)

    used_ids = []
    bf_row = _query_meal(db, "breakfast", bmi_result.status, b_budget, used_ids)
    if bf_row: used_ids.append(bf_row.food_id)
    ln_row = _query_meal(db, "lunch",     bmi_result.status, l_budget, used_ids)
    if ln_row: used_ids.append(ln_row.food_id)
    dn_row = _query_meal(db, "dinner",    bmi_result.status, d_budget, used_ids)

    def fallback(slot):
        kws = MEAL_MATCH[slot]
        rows = db.query(Food).filter(or_(*[Food.meal_type.ilike(f"%{k}%") for k in kws])).all()
        return random.choice(rows) if rows else db.query(Food).first()

    bf = _food_to_slot(bf_row or fallback("breakfast"))
    ln = _food_to_slot(ln_row or fallback("lunch"))
    dn = _food_to_slot(dn_row or fallback("dinner"))

    total_cal  = bf.calories + ln.calories + dn.calories
    total_cost = round(bf.price_usd + ln.price_usd + dn.price_usd, 2)

    session = UserSession(
        height_m=user.height_m, weight_kg=user.weight_kg,
        gender=user.gender, activity=user.activity,
        budget_input=user.budget, budget_type=user.budget_type,
        daily_budget_usd=daily_budget,
        bmi=bmi_result.bmi, bmi_status=bmi_result.status,
        daily_calories_kcal=calories, water_liters_per_day=water,
        breakfast_food_id=bf.food_id, breakfast_food_name=bf.food_name,
        breakfast_calories=bf.calories, breakfast_price_usd=bf.price_usd,
        lunch_food_id=ln.food_id, lunch_food_name=ln.food_name,
        lunch_calories=ln.calories, lunch_price_usd=ln.price_usd,
        dinner_food_id=dn.food_id, dinner_food_name=dn.food_name,
        dinner_calories=dn.calories, dinner_price_usd=dn.price_usd,
        total_meal_calories=total_cal, total_meal_cost_usd=total_cost,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return RecommendationResponse(
        session_id=session.id,
        bmi=bmi_result.bmi, bmi_status=bmi_result.status,
        bmi_description=bmi_result.description,
        daily_calories_kcal=calories, water_liters_per_day=water,
        daily_budget_usd=daily_budget,
        meal_plan=MealPlan(breakfast=bf, lunch=ln, dinner=dn),
        total_meal_calories=total_cal, total_meal_cost_usd=total_cost,
        diet_tip=DIET_TIPS[bmi_result.status],
    )

def bmi_only(weight_kg, height_m):
    return calculate_bmi(weight_kg, height_m)

def get_all_foods(db: Session, meal_type: str = None):
    q = db.query(Food)
    if meal_type:
        q = q.filter(Food.meal_type.ilike(f"%{meal_type}%"))
    return [FoodItem(food_id=r.food_id, food_name=r.food_name,
                     category=r.category.strip(), calories=r.calories,
                     price_usd=r.price_usd, meal_type=r.meal_type,
                     price_riel=r.price_riel, health_label=r.health_label)
            for r in q.order_by(Food.food_id).all()]

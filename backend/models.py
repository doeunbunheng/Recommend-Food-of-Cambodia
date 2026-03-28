from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime


# ── Enums ─────────────────────────────────────────────────────────────────────

class Gender(str, Enum):
    male   = "male"
    female = "female"

class ActivityLevel(str, Enum):
    sedentary   = "sedentary"
    light       = "light"
    moderate    = "moderate"
    active      = "active"
    very_active = "very_active"

class BudgetType(str, Enum):
    daily   = "daily"
    monthly = "monthly"


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterInput(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    email:    str = Field(..., description="Valid email address")
    password: str = Field(..., min_length=6, description="At least 6 characters")

class LoginInput(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      int
    username:     str

class UserOut(BaseModel):
    id:         int
    username:   str
    email:      str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── User preferences ──────────────────────────────────────────────────────────

class PreferenceInput(BaseModel):
    is_vegetarian:    bool           = False
    avoid_allergens:  List[str]      = []   # e.g. ["gluten","dairy"]
    max_cal_per_meal: Optional[float] = None
    preferred_budget: Optional[float] = None

class PreferenceOut(PreferenceInput):
    id:      int
    user_id: int
    model_config = {"from_attributes": True}


# ── Recommendation input ──────────────────────────────────────────────────────

class UserInput(BaseModel):
    height_m:    float        = Field(..., gt=0.5, lt=3.0,  description="Height in meters")
    weight_kg:   float        = Field(..., gt=10,  lt=300,  description="Weight in kg")
    gender:      Gender
    activity:    ActivityLevel
    budget:      float        = Field(..., gt=0,            description="Budget in USD")
    budget_type: BudgetType   = BudgetType.daily
    include_snack: bool       = False
    user_id:     Optional[int] = None  # set automatically from JWT when authenticated

    @field_validator("height_m")
    @classmethod
    def round_height(cls, v): return round(v, 2)

    @field_validator("weight_kg")
    @classmethod
    def round_weight(cls, v): return round(v, 1)

    model_config = {
        "json_schema_extra": {
            "example": {
                "height_m": 1.70,
                "weight_kg": 70,
                "gender": "male",
                "activity": "moderate",
                "budget": 5.0,
                "budget_type": "daily",
                "include_snack": True
            }
        }
    }


# ── Food items ────────────────────────────────────────────────────────────────

class FoodItem(BaseModel):
    food_id:      int
    food_name:    str
    category:     str
    calories:     float
    price_usd:    float
    meal_type:    str
    price_riel:   int
    health_label: str
    is_vegetarian: bool = False
    allergens:    str   = ""
    protein_g:    float = 0.0
    carbs_g:      float = 0.0
    fat_g:        float = 0.0
    avg_rating:   Optional[float] = None
    model_config  = {"from_attributes": True}

class MealSlot(BaseModel):
    food_id:      int
    food_name:    str
    category:     str
    calories:     float
    price_usd:    float
    price_riel:   int
    health_label: str
    is_vegetarian: bool = False
    protein_g:    float = 0.0
    carbs_g:      float = 0.0
    fat_g:        float = 0.0

class MealPlan(BaseModel):
    breakfast: MealSlot
    lunch:     MealSlot
    dinner:    MealSlot
    snack:     Optional[MealSlot] = None


# ── Recommendation response ───────────────────────────────────────────────────

class NutritionSummary(BaseModel):
    total_protein_g:  float
    total_carbs_g:    float
    total_fat_g:      float
    calorie_coverage: float   # total_meal_cal / target_cal  as %

class RecommendationResponse(BaseModel):
    session_id:           int
    bmi:                  float
    bmi_status:           str
    bmi_description:      str
    daily_calories_kcal:  int
    water_liters_per_day: float
    daily_budget_usd:     float
    meal_plan:            MealPlan
    total_meal_calories:  float
    total_meal_cost_usd:  float
    diet_tip:             str
    nutrition:            NutritionSummary
    budget_remaining_usd: float


# ── BMI ───────────────────────────────────────────────────────────────────────

class BMIResult(BaseModel):
    bmi:         float
    status:      str
    description: str


# ── Weekly plan ───────────────────────────────────────────────────────────────

class DayPlan(BaseModel):
    day:       str   # "Monday", "Tuesday", ...
    breakfast: MealSlot
    lunch:     MealSlot
    dinner:    MealSlot
    snack:     Optional[MealSlot] = None
    day_total_calories: float
    day_total_cost_usd: float

class WeeklyPlanResponse(BaseModel):
    plan_id:           int
    session_id:        int
    days:              List[DayPlan]
    total_cost_usd:    float
    total_calories:    float
    avg_daily_cost:    float
    avg_daily_calories: float


# ── Favorites ─────────────────────────────────────────────────────────────────

class FavoriteToggle(BaseModel):
    food_id: int

class FavoriteOut(BaseModel):
    id:        int
    food_id:   int
    food_name: str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Ratings ───────────────────────────────────────────────────────────────────

class RatingInput(BaseModel):
    food_id: int
    rating:  int = Field(..., ge=1, le=5)
    comment: str = ""

class RatingOut(BaseModel):
    id:        int
    food_id:   int
    food_name: str
    rating:    int
    comment:   str
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Analytics ─────────────────────────────────────────────────────────────────

class AnalyticsResponse(BaseModel):
    total_sessions:      int
    avg_bmi:             Optional[float]
    bmi_trend:           List[Dict]   # [{date, bmi}, ...]
    avg_daily_spend_usd: Optional[float]
    spend_trend:         List[Dict]   # [{date, cost}, ...]
    top_foods:           List[Dict]   # [{food_name, count}, ...]
    bmi_distribution:    Dict[str, int]  # {Underweight:N, Normal:N, ...}


# ── Session history ───────────────────────────────────────────────────────────

class SessionRecord(BaseModel):
    id:                   int
    created_at:           datetime
    height_m:             float
    weight_kg:            float
    gender:               str
    activity:             str
    daily_budget_usd:     float
    bmi:                  float
    bmi_status:           str
    daily_calories_kcal:  int
    water_liters_per_day: float
    breakfast_food_name:  Optional[str]
    lunch_food_name:      Optional[str]
    dinner_food_name:     Optional[str]
    snack_food_name:      Optional[str] = None
    total_meal_calories:  Optional[float]
    total_meal_cost_usd:  Optional[float]
    model_config = {"from_attributes": True}

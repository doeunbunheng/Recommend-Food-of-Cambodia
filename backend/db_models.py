from sqlalchemy import (
    Column, Integer, Float, String, DateTime, Text,
    Boolean, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Food(Base):
    __tablename__ = "foods"

    id            = Column(Integer, primary_key=True, index=True)
    food_id       = Column(Integer, unique=True, index=True)
    food_name     = Column(String(200), nullable=False)
    category      = Column(String(100))
    calories      = Column(Float)
    price_usd     = Column(Float)
    meal_type     = Column(String(100))
    price_riel    = Column(Integer)
    health_label  = Column(String(50))
    calorie_level = Column(String(20))
    price_level   = Column(String(20))
    is_vegetarian = Column(Boolean, default=False)
    allergens     = Column(String(200), default="")
    protein_g     = Column(Float, default=0.0)
    carbs_g       = Column(Float, default=0.0)
    fat_g         = Column(Float, default=0.0)
    description   = Column(Text, default="")

    ratings   = relationship("FoodRating",   back_populates="food")
    favorites = relationship("UserFavorite", back_populates="food")


class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    username   = Column(String(80), unique=True, nullable=False, index=True)
    email      = Column(String(200), unique=True, nullable=False, index=True)
    hashed_pw  = Column(String(200), nullable=False)
    is_active  = Column(Boolean, default=True)

    preferences  = relationship("UserPreference", back_populates="user", uselist=False)
    sessions     = relationship("UserSession",     back_populates="user")
    favorites    = relationship("UserFavorite",    back_populates="user")
    ratings      = relationship("FoodRating",      back_populates="user")
    weekly_plans = relationship("WeeklyMealPlan",  back_populates="user")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id               = Column(Integer, primary_key=True, index=True)
    user_id          = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    is_vegetarian    = Column(Boolean, default=False)
    avoid_allergens  = Column(String(200), default="")
    max_cal_per_meal = Column(Float, nullable=True)
    preferred_budget = Column(Float, nullable=True)

    user = relationship("User", back_populates="preferences")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id         = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=True)

    height_m         = Column(Float, nullable=False)
    weight_kg        = Column(Float, nullable=False)
    gender           = Column(String(10), nullable=False)
    activity         = Column(String(20), nullable=False)
    budget_input     = Column(Float, nullable=False)
    budget_type      = Column(String(10), nullable=False)

    daily_budget_usd     = Column(Float)
    bmi                  = Column(Float)
    bmi_status           = Column(String(20))
    daily_calories_kcal  = Column(Integer)
    water_liters_per_day = Column(Float)

    breakfast_food_id   = Column(Integer)
    breakfast_food_name = Column(String(200))
    breakfast_calories  = Column(Float)
    breakfast_price_usd = Column(Float)

    lunch_food_id   = Column(Integer)
    lunch_food_name = Column(String(200))
    lunch_calories  = Column(Float)
    lunch_price_usd = Column(Float)

    dinner_food_id   = Column(Integer)
    dinner_food_name = Column(String(200))
    dinner_calories  = Column(Float)
    dinner_price_usd = Column(Float)

    snack_food_id   = Column(Integer, nullable=True)
    snack_food_name = Column(String(200), nullable=True)
    snack_calories  = Column(Float, nullable=True)
    snack_price_usd = Column(Float, nullable=True)

    total_meal_calories = Column(Float)
    total_meal_cost_usd = Column(Float)

    user = relationship("User", back_populates="sessions")


class UserFavorite(Base):
    __tablename__ = "user_favorites"
    __table_args__ = (UniqueConstraint("user_id", "food_id", name="uq_user_food_fav"),)

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    food_id    = Column(Integer, ForeignKey("foods.food_id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="favorites")
    food = relationship(
        "Food", back_populates="favorites",
        foreign_keys=[food_id],
        primaryjoin="UserFavorite.food_id == Food.food_id",
    )


class FoodRating(Base):
    __tablename__ = "food_ratings"
    __table_args__ = (UniqueConstraint("user_id", "food_id", name="uq_user_food_rating"),)

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    food_id    = Column(Integer, ForeignKey("foods.food_id"), nullable=False)
    rating     = Column(Integer, nullable=False)
    comment    = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="ratings")
    food = relationship(
        "Food", back_populates="ratings",
        foreign_keys=[food_id],
        primaryjoin="FoodRating.food_id == Food.food_id",
    )


class WeeklyMealPlan(Base):
    __tablename__ = "weekly_meal_plans"

    id                 = Column(Integer, primary_key=True, index=True)
    user_id            = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id         = Column(Integer, ForeignKey("user_sessions.id"), nullable=False)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())
    plan_json          = Column(Text, nullable=False)
    total_cost_usd     = Column(Float)
    total_calories     = Column(Float)
    avg_daily_cost     = Column(Float)
    avg_daily_calories = Column(Float)

    user = relationship("User", back_populates="weekly_plans")

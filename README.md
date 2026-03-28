# 🍚 Budget-Aware Healthy Cambodian Food Recommendation System
**I4-AMS-A · Institute of Technology of Cambodia · 2025–2026**

Full-stack system: **FastAPI backend + PostgreSQL + plain HTML/CSS/JS frontend**.

---

## 📁 Project Structure

```
FoodRecommend/
├── backend/
│   ├── main.py                   # FastAPI app — all endpoints
│   ├── models.py                 # Pydantic request/response models
│   ├── db_models.py              # SQLAlchemy ORM (foods + user_sessions tables)
│   ├── database.py               # PostgreSQL connection & session factory
│   ├── auth.py                   # API key authentication
│   ├── init_db.py                # One-time setup: create tables + seed foods
│   ├── requirements.txt
│   ├── .env                      # ← YOUR secrets (never commit)
│   ├── .env.example              # Safe template to commit
│   ├── data/
│   │   ├── food_dataset_clean.csv   # 100+ real Cambodian dishes
│   │   └── Food_dataset.csv         # Original raw dataset
│   └── services/
│       └── recommendation.py     # BMI logic + PostgreSQL queries + session saving
└── frontend/
    ├── index.html                # 4-page app
    ├── css/style.css
    └── js/app.js
```

---

## 🚀 Setup & Run

### 1. Create PostgreSQL database
```sql
CREATE DATABASE food_recommend_db;
```

### 2. Configure .env
```bash
cd backend
cp .env.example .env
# Edit .env — set your DATABASE_URL and API_KEY
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Initialise database (run ONCE)
```bash
python init_db.py
# Creates tables + seeds all 100+ Cambodian foods from CSV
```

### 5. Start the API
```bash
uvicorn main:app --reload
# API: http://127.0.0.1:8000
# Docs: http://127.0.0.1:8000/docs
```

### 6. Open the frontend
Open `frontend/index.html` in your browser.

---

## 📡 API Endpoints

| Method | Endpoint              | Auth | Description                          |
|--------|-----------------------|------|--------------------------------------|
| GET    | `/`                   | ✗    | Welcome message                      |
| GET    | `/health-check`       | ✗    | Server status                        |
| POST   | `/recommend`          | ✓    | Get meal plan — **saves to PostgreSQL** |
| GET    | `/bmi`                | ✓    | Quick BMI calculator                 |
| GET    | `/foods`              | ✓    | All foods in database                |
| GET    | `/foods/filter`       | ✓    | Filter by meal_type / health_label / price |
| GET    | `/history`            | ✓    | All saved user sessions              |
| GET    | `/history/{id}`       | ✓    | Single session by ID                 |
| DELETE | `/history/{id}`       | ✓    | Delete a session                     |

**Auth header:** `X-API-Key: your-secret-key`

---

## 🗄️ PostgreSQL Tables

### `foods`
Seeded from `food_dataset_clean.csv` — never changes at runtime.

| Column | Type | Example |
|---|---|---|
| food_id | int | 1 |
| food_name | varchar | Amok |
| category | varchar | Main Dish |
| calories | float | 385.0 |
| price_usd | float | 3.75 |
| meal_type | varchar | Lunch/Dinner |
| price_riel | int | 15000 |
| health_label | varchar | Normal |

### `user_sessions`
One row per `/recommend` call.

| Column | Type | Description |
|---|---|---|
| id | int PK | Auto-increment |
| created_at | timestamp | When the request was made |
| height_m, weight_kg, gender, activity | | User inputs |
| budget_input, budget_type, daily_budget_usd | | Budget inputs |
| bmi, bmi_status, daily_calories_kcal, water_liters_per_day | | Computed health values |
| breakfast/lunch/dinner _food_id, _food_name, _calories, _price_usd | | Recommended meals |
| total_meal_calories, total_meal_cost_usd | | Totals |

---

## 👥 Team
| Name | ID |
|---|---|
| DOEUN Bunheng | e20221528 |
| CHHO Sengmeng | e20220296 |
| DIN Reaksa | e20221070 |
| CHHENG Sothean | e20220686 |

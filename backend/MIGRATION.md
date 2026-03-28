# Database Migration Guide — v2 → v3

## New tables added
Run these SQL statements against your PostgreSQL database:

```sql
-- 1. New columns on foods table
ALTER TABLE foods
  ADD COLUMN IF NOT EXISTS is_vegetarian BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS allergens VARCHAR(200) DEFAULT '',
  ADD COLUMN IF NOT EXISTS protein_g FLOAT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS carbs_g FLOAT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS fat_g FLOAT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS description TEXT DEFAULT '';

-- 2. New column on user_sessions
ALTER TABLE user_sessions
  ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id),
  ADD COLUMN IF NOT EXISTS snack_food_id INTEGER,
  ADD COLUMN IF NOT EXISTS snack_food_name VARCHAR(200),
  ADD COLUMN IF NOT EXISTS snack_calories FLOAT,
  ADD COLUMN IF NOT EXISTS snack_price_usd FLOAT;

-- 3. New tables (SQLAlchemy will auto-create these on startup)
-- users, user_preferences, user_favorites, food_ratings, weekly_meal_plans
-- → They are created automatically by Base.metadata.create_all()
```

## New environment variables
Add to your .env file:
```
JWT_SECRET=your-very-secret-key-here
TOKEN_EXPIRE_MINUTES=1440
```

## New pip packages
```
pip install python-jose[cryptography] passlib[bcrypt] python-multipart
```
Or just run: `pip install -r requirements.txt`

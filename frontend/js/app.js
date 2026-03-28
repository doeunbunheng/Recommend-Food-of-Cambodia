const API_BASE = "http://127.0.0.1:8000";

// API key is stored here on the frontend.
// In production, load this from an environment variable or a build-time injection.
// NEVER commit the real key to a public repository.
const API_KEY = "khmer-plate-secret-2025-itc-ams";

// Shared fetch helper — automatically attaches X-API-Key to every request
async function apiFetch(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
    ...(options.headers || {}),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 403) throw new Error("Invalid API key — access denied.");
  return res;
}

// ── PAGE NAVIGATION ──────────────────────────────────────────────────────────
function showPage(id) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.getElementById(id).classList.add("active");
  document.querySelectorAll(".nav-links a").forEach(a => {
    a.style.color = a.dataset.page === id ? "var(--kh-gold)" : "";
  });
  if (id === "page-foods") loadFoods();
}

// ── BMI GAUGE ────────────────────────────────────────────────────────────────
function drawGauge(bmi) {
  const canvas = document.getElementById("bmiGauge");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const cx = W / 2, cy = H * 0.72, r = 70;
  ctx.clearRect(0, 0, W, H);

  // Segments: underweight, normal, overweight, obese
  const segments = [
    { from: Math.PI, to: Math.PI * 1.25, color: "#1565C0" },
    { from: Math.PI * 1.25, to: Math.PI * 1.6, color: "#2E7D32" },
    { from: Math.PI * 1.6, to: Math.PI * 1.8, color: "#F57F17" },
    { from: Math.PI * 1.8, to: Math.PI * 2, color: "#C62828" },
  ];
  segments.forEach(s => {
    ctx.beginPath();
    ctx.arc(cx, cy, r, s.from, s.to);
    ctx.lineWidth = 18;
    ctx.strokeStyle = s.color;
    ctx.stroke();
  });

  // Needle
  const bmiClamped = Math.max(15, Math.min(40, bmi));
  const pct = (bmiClamped - 15) / 25;
  const angle = Math.PI + pct * Math.PI;
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(cx + Math.cos(angle) * (r - 10), cy + Math.sin(angle) * (r - 10));
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#1A0A00";
  ctx.lineCap = "round";
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(cx, cy, 5, 0, Math.PI * 2);
  ctx.fillStyle = "#1A0A00";
  ctx.fill();
}

// ── SUBMIT FORM ──────────────────────────────────────────────────────────────
async function submitForm(e) {
  e.preventDefault();
  const btn = document.getElementById("submitBtn");
  btn.classList.add("loading");
  btn.innerHTML = '<div class="spinner"></div> Analyzing...';

  const data = {
    height_m:    parseFloat(document.getElementById("height").value),
    weight_kg:   parseFloat(document.getElementById("weight").value),
    gender:      document.getElementById("gender").value,
    activity:    document.getElementById("activity").value,
    budget:      parseFloat(document.getElementById("budget").value),
    budget_type: document.getElementById("budgetType").value,
  };

  try {
    const res = await apiFetch("/recommend", {
      method: "POST",
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Server error");
    }
    const result = await res.json();
    renderResults(result);
  } catch (err) {
    document.getElementById("resultsPanel").innerHTML =
      `<div class="error-box">⚠️ ${err.message}. Make sure the FastAPI backend is running at <b>${API_BASE}</b>.</div>`;
  } finally {
    btn.classList.remove("loading");
    btn.innerHTML = '🍚 Get My Meal Plan';
  }
}

// ── RENDER RESULTS ───────────────────────────────────────────────────────────
function renderResults(r) {
  const badgeClass = {
    "Normal": "badge-normal",
    "Underweight": "badge-under",
    "Overweight": "badge-over",
    "Obese": "badge-obese",
  }[r.bmi_status] || "badge-normal";

  const mealIcons = { breakfast: "🌅", lunch: "☀️", dinner: "🌙" };
  const iconClass = { breakfast: "icon-breakfast", lunch: "icon-lunch", dinner: "icon-dinner" };

  function mealCard(meal, type) {
    const m = r.meal_plan[type];
    return `
    <div class="meal-card">
      <div class="meal-icon-wrap ${iconClass[type]}">${mealIcons[type]}</div>
      <div class="meal-main">
        <div class="meal-label">${type}</div>
        <div class="meal-name">${m.food_name}</div>
        <div class="meal-desc">${m.description}</div>
        <div class="meal-tags">
          <span class="meal-tag">${m.category}</span>
        </div>
      </div>
      <div class="meal-meta">
        <div class="meal-price">$${m.price_usd.toFixed(2)}</div>
        <div class="meal-cal">${m.calories_kcal} kcal</div>
      </div>
    </div>`;
  }

  const html = `
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-icon">⚖️</div>
        <div class="stat-value">${r.bmi}</div>
        <div class="stat-label">BMI</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">🔥</div>
        <div class="stat-value">${r.daily_calories_kcal}</div>
        <div class="stat-label">kcal / day</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">💧</div>
        <div class="stat-value">${r.water_liters_per_day}L</div>
        <div class="stat-label">Water / day</div>
      </div>
      <div class="stat-card">
        <div class="stat-icon">💰</div>
        <div class="stat-value">$${r.daily_budget_usd.toFixed(2)}</div>
        <div class="stat-label">Daily budget</div>
      </div>
    </div>

    <div class="bmi-card">
      <div class="bmi-gauge-wrap">
        <canvas id="bmiGauge" width="160" height="100"></canvas>
        <div class="bmi-value-label">
          <span class="bmi-big">${r.bmi}</span>
          <span class="bmi-sub">BMI</span>
        </div>
      </div>
      <div class="bmi-info">
        <h3>Health Status</h3>
        <p>${r.bmi_description}</p>
        <span class="bmi-badge ${badgeClass}">${r.bmi_status}</span>
      </div>
    </div>

    <div class="diet-tip">
      <strong>💡 Diet Tip</strong>
      ${r.diet_tip}
    </div>

    <p class="meal-section-title">🍽️ Today's Meal Plan</p>

    <div class="meals-grid">
      ${mealCard(r, "breakfast")}
      ${mealCard(r, "lunch")}
      ${mealCard(r, "dinner")}
    </div>

    <div class="total-bar">
      <div>
        <div class="lbl">Total Calories</div>
        <div class="val">${r.total_meal_calories} <span>kcal</span></div>
      </div>
      <div style="text-align:right">
        <div class="lbl">Total Cost</div>
        <div class="val"><span>$${r.total_meal_cost_usd.toFixed(2)}</span> / day</div>
      </div>
    </div>
  `;

  document.getElementById("resultsPanel").innerHTML = html;
  requestAnimationFrame(() => drawGauge(r.bmi));
}

// ── FOODS PAGE ───────────────────────────────────────────────────────────────
let allFoods = [];
let currentFilter = "all";

async function loadFoods() {
  const grid = document.getElementById("foodsGrid");
  grid.innerHTML = '<p style="color:var(--muted);text-align:center;padding:32px">Loading foods…</p>';
  try {
    const res = await apiFetch("/foods");
    if (!res.ok) throw new Error("Could not load foods");
    allFoods = await res.json();
    renderFoods();
  } catch (err) {
    grid.innerHTML = `<div class="error-box">⚠️ ${err.message}. Make sure the API is running at <b>${API_BASE}</b>.</div>`;
  }
}

function renderFoods() {
  const filtered = currentFilter === "all"
    ? allFoods
    : allFoods.filter(f => f.meal_type.toLowerCase() === currentFilter);

  const mealColors = {
    Breakfast: { bg: "#FFF3E0", color: "#E65100" },
    Lunch:     { bg: "#E8F5E9", color: "#2E7D32" },
    Dinner:    { bg: "#EDE7F6", color: "#512DA8" },
  };

  document.getElementById("foodsGrid").innerHTML = filtered.map(f => {
    const mc = mealColors[f.meal_type] || { bg: "#F5F5F5", color: "#555" };
    return `
    <div class="food-card">
      <div class="food-card-top">
        <div class="food-card-name">${f.food_name}</div>
        <span class="food-card-meal" style="background:${mc.bg};color:${mc.color}">${f.meal_type}</span>
      </div>
      <div class="food-card-desc">${f.description}</div>
      <div class="food-card-footer">
        <span class="food-price">$${f.price_usd.toFixed(2)}</span>
        <span class="food-cal">${f.calories_kcal} kcal</span>
      </div>
    </div>`;
  }).join("");
}

function setFilter(type) {
  currentFilter = type;
  document.querySelectorAll(".filter-btn").forEach(b => {
    b.classList.toggle("active", b.dataset.filter === type);
  });
  renderFoods();
}

// ── BMI QUICK CALC ───────────────────────────────────────────────────────────
async function quickBMI() {
  const h = parseFloat(document.getElementById("qHeight").value);
  const w = parseFloat(document.getElementById("qWeight").value);
  if (!h || !w) return;
  try {
    const res = await apiFetch(`/bmi?weight_kg=${w}&height_m=${h}`);
    const data = await res.json();
    const badgeClass = {
      "Normal": "badge-normal",
      "Underweight": "badge-under",
      "Overweight": "badge-over",
      "Obese": "badge-obese",
    }[data.status] || "badge-normal";
    document.getElementById("quickBmiResult").innerHTML = `
      <strong>BMI: ${data.bmi}</strong>
      <span class="bmi-badge ${badgeClass}" style="margin-left:8px">${data.status}</span>
      <p style="font-size:0.8rem;color:var(--muted);margin-top:6px">${data.description}</p>
    `;
  } catch {
    document.getElementById("quickBmiResult").innerHTML =
      '<span style="color:var(--kh-red)">API not reachable</span>';
  }
}

// ── INIT ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  showPage("page-home");
  document.getElementById("recommendForm").addEventListener("submit", submitForm);
});

// ── SESSION HISTORY ──────────────────────────────────────────────────────────
async function loadHistory() {
  const container = document.getElementById("historyList");
  container.innerHTML = '<p style="color:var(--muted);text-align:center;padding:32px">Loading history…</p>';
  try {
    const res = await apiFetch("/history?limit=20");
    if (!res.ok) throw new Error(await res.text());
    const sessions = await res.json();
    if (!sessions.length) {
      container.innerHTML = '<div class="empty-state"><div class="icon">📋</div><h3>No sessions yet</h3><p>Your recommendations will appear here after you submit the form.</p></div>';
      return;
    }
    container.innerHTML = sessions.map(s => `
      <div class="meal-card" style="flex-direction:column;gap:10px">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <span style="font-size:0.7rem;color:var(--muted);font-weight:600;text-transform:uppercase">Session #${s.id}</span>
            <div style="font-family:'Playfair Display',serif;font-size:1rem;font-weight:700">${s.gender.charAt(0).toUpperCase()+s.gender.slice(1)} · ${s.height_m}m · ${s.weight_kg}kg</div>
          </div>
          <div style="text-align:right">
            <div style="font-size:0.75rem;color:var(--muted)">${new Date(s.created_at).toLocaleString()}</div>
            <span class="bmi-badge ${s.bmi_status==='Normal'?'badge-normal':s.bmi_status==='Underweight'?'badge-under':s.bmi_status==='Overweight'?'badge-over':'badge-obese'}" style="margin-top:4px;display:inline-block">BMI ${s.bmi} · ${s.bmi_status}</span>
          </div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;font-size:0.8rem">
          <div style="background:var(--cream);padding:8px;border-radius:8px"><b>🌅 Breakfast</b><br/>${s.breakfast_food_name||'—'}</div>
          <div style="background:var(--cream);padding:8px;border-radius:8px"><b>☀️ Lunch</b><br/>${s.lunch_food_name||'—'}</div>
          <div style="background:var(--cream);padding:8px;border-radius:8px"><b>🌙 Dinner</b><br/>${s.dinner_food_name||'—'}</div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:0.8rem;color:var(--muted)">
          <span>💰 Budget: $${s.daily_budget_usd}/day</span>
          <span>🔥 ${s.total_meal_calories||0} kcal · $${(s.total_meal_cost_usd||0).toFixed(2)} total</span>
        </div>
      </div>
    `).join("");
  } catch (err) {
    container.innerHTML = `<div class="error-box">⚠️ ${err.message}</div>`;
  }
}

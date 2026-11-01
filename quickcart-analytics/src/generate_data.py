"""Reproducible synthetic quick-commerce dataset generator ("QuickCart").

The data is SIMULATED (no real company data). Realistic behavioural rules are
baked in so the analysis has genuine signal to discover:

  * Slow deliveries (> 20 min) and cancellations lower the chance of a repeat order.
  * Deep first-order discounts attract lower-loyalty, deal-seeking customers.
  * Acquisition channels differ in loyalty and discount sensitivity.
  * Festive (Diwali) windows lift basket size and order frequency.
  * Seasonal category mix (beverages in summer, pharmacy in monsoon).
  * Tier-2 cities have slower deliveries; evening/lunch peaks slow riders down.

Run:  python -m src.generate_data
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

SEED = 42
N_CUSTOMERS = 9_000
START = date(2025, 1, 1)
END = date(2026, 10, 31)

# city: (tier, share of customers, base delivery minutes)
CITIES = {
    "Delhi NCR": ("Tier 1", 0.18, 11.0),
    "Bengaluru": ("Tier 1", 0.17, 10.5),
    "Mumbai": ("Tier 1", 0.16, 11.5),
    "Hyderabad": ("Tier 1", 0.11, 11.0),
    "Pune": ("Tier 1", 0.08, 12.0),
    "Chennai": ("Tier 1", 0.07, 12.5),
    "Kolkata": ("Tier 1", 0.06, 14.0),
    "Chandigarh Tricity": ("Tier 2", 0.07, 15.5),
    "Ahmedabad": ("Tier 2", 0.05, 15.0),
    "Jaipur": ("Tier 2", 0.05, 16.0),
}

# channel: (share, loyalty ~ Beta(a, b), discount-sensitivity)
CHANNELS = {
    "Organic": (0.28, 3.0, 4.0, 0),
    "Referral": (0.14, 3.5, 3.5, 0),
    "Google Ads": (0.20, 2.5, 4.5, 1),
    "Paid Social": (0.24, 2.0, 5.0, 2),
    "Influencer": (0.14, 1.8, 5.5, 3),
}

AGE_GROUPS = {"18-24": 0.32, "25-34": 0.42, "35-44": 0.18, "45+": 0.08}
DEVICES = {"Android": 0.68, "iOS": 0.27, "Web": 0.05}
PAYMENTS = {"UPI": 0.60, "Card": 0.19, "COD": 0.11, "Wallet": 0.10}

DISCOUNT_LEVELS = np.array([0, 5, 10, 15, 20, 25])
DISCOUNT_BASE_P = np.array([0.30, 0.20, 0.20, 0.15, 0.10, 0.05])

# Diwali 2025 (20 Oct) and Diwali 2026 (8 Nov) shopping windows
FESTIVE_WINDOWS = [
    (date(2025, 10, 13), date(2025, 10, 23)),
    (date(2026, 10, 27), date(2026, 11, 9)),
]

HOUR_W = np.array([1, 0.5, 0.3, 0.2, 0.3, 0.8, 2, 4, 6, 6, 5, 4.5,
                   5.5, 6, 5, 4, 4.5, 5.5, 7, 8.5, 9, 8, 6, 3], dtype=float)
PEAK_HOURS = set(range(7, 11)) | set(range(12, 15)) | set(range(18, 23))

CATEGORIES = {
    # n products, price range (INR), margin range, demand weight
    "Fruits & Vegetables": dict(n=30, price=(20, 180), margin=(0.14, 0.26), w=0.20),
    "Dairy & Bread": dict(n=22, price=(25, 120), margin=(0.10, 0.20), w=0.17),
    "Snacks & Munchies": dict(n=28, price=(10, 250), margin=(0.22, 0.36), w=0.14),
    "Beverages": dict(n=24, price=(15, 300), margin=(0.20, 0.34), w=0.10),
    "Ready-to-Eat & Frozen": dict(n=20, price=(40, 350), margin=(0.18, 0.30), w=0.08),
    "Staples (Atta, Rice, Oil)": dict(n=22, price=(60, 700), margin=(0.07, 0.15), w=0.09),
    "Personal Care": dict(n=24, price=(40, 600), margin=(0.28, 0.45), w=0.07),
    "Household & Cleaning": dict(n=22, price=(30, 450), margin=(0.22, 0.38), w=0.06),
    "Pharmacy & Wellness": dict(n=18, price=(30, 500), margin=(0.20, 0.35), w=0.04),
    "Baby & Pet Care": dict(n=16, price=(80, 900), margin=(0.18, 0.32), w=0.03),
    "Electronics & Accessories": dict(n=14, price=(149, 1999), margin=(0.12, 0.24), w=0.02),
}

NAMES = {
    "Fruits & Vegetables": ["Tomato", "Onion", "Potato", "Banana", "Apple", "Spinach", "Coriander", "Capsicum", "Cucumber", "Carrot"],
    "Dairy & Bread": ["Toned Milk", "Curd", "Paneer", "Butter", "Brown Bread", "Eggs", "Cheese Slices", "Lassi"],
    "Snacks & Munchies": ["Potato Chips", "Namkeen Mix", "Chocolate Bar", "Biscuits", "Instant Noodles", "Popcorn", "Cookies", "Nachos", "Wafers"],
    "Beverages": ["Cola", "Orange Juice", "Energy Drink", "Cold Coffee", "Green Tea", "Mineral Water", "Iced Tea", "Soda"],
    "Ready-to-Eat & Frozen": ["Frozen Peas", "Paratha", "Veg Momos", "Ready Biryani", "Ice Cream Tub", "Frozen Fries", "Pasta Meal"],
    "Staples (Atta, Rice, Oil)": ["Wheat Atta", "Basmati Rice", "Sunflower Oil", "Toor Dal", "Sugar", "Salt", "Poha", "Mustard Oil"],
    "Personal Care": ["Shampoo", "Face Wash", "Body Lotion", "Toothpaste", "Deodorant", "Soap", "Sunscreen", "Hair Oil"],
    "Household & Cleaning": ["Detergent", "Dishwash Gel", "Floor Cleaner", "Tissue Roll", "Garbage Bags", "Air Freshener", "Sponge Pack"],
    "Pharmacy & Wellness": ["Pain Relief Gel", "ORS Sachets", "Vitamin C", "Bandage Pack", "Hand Sanitizer", "Cough Syrup"],
    "Baby & Pet Care": ["Baby Diapers", "Baby Wipes", "Dog Food", "Cat Litter", "Baby Lotion", "Pet Treats"],
    "Electronics & Accessories": ["USB-C Cable", "Earphones", "Power Bank", "LED Bulb", "AA Batteries", "Phone Charger"],
}
SIZES = ["250 g", "500 g", "1 kg", "Pack of 2", "Family Pack", "Premium"]


def is_festive(d: date) -> bool:
    return any(a <= d <= b for a, b in FESTIVE_WINDOWS)


def make_products(rng: np.random.Generator) -> pd.DataFrame:
    rows, pid = [], 1
    for cat, spec in CATEGORIES.items():
        lo, hi = spec["price"]
        mlo, mhi = spec["margin"]
        names = NAMES[cat]
        for i in range(spec["n"]):
            price = max(lo, int(round(float(np.exp(rng.uniform(np.log(lo), np.log(hi)))))))
            margin = float(rng.uniform(mlo, mhi))
            rows.append({
                "product_id": pid,
                "product_name": f"{names[i % len(names)]} {SIZES[(i // len(names)) % len(SIZES)]}",
                "category": cat,
                "price": float(price),
                "cost": round(price * (1 - margin), 2),
            })
            pid += 1
    return pd.DataFrame(rows)


def build_product_cdfs(products: pd.DataFrame, rng: np.random.Generator) -> dict:
    """Cumulative demand distributions per (month, festive) -> seasonality."""
    base = np.zeros(len(products))
    for cat, spec in CATEGORIES.items():
        idx = np.where(products.category.values == cat)[0]
        within = 1.0 / np.arange(1, len(idx) + 1) ** 0.8
        rng.shuffle(within)
        base[idx] = spec["w"] * within / within.sum()

    cdfs = {}
    for month in range(1, 13):
        for festive in (False, True):
            mult = {c: 1.0 for c in CATEGORIES}
            if month in (4, 5, 6):
                mult["Beverages"], mult["Fruits & Vegetables"] = 1.6, 1.1
            if month in (7, 8, 9):
                mult["Pharmacy & Wellness"] = 1.25
            if month in (12, 1, 2):
                mult["Ready-to-Eat & Frozen"] = 1.2
            if festive:
                mult.update({"Snacks & Munchies": 1.4, "Household & Cleaning": 1.5,
                             "Electronics & Accessories": 2.0, "Personal Care": 1.3})
            w = base * products.category.map(mult).values
            cdfs[(month, festive)] = np.cumsum(w / w.sum())
    return cdfs


def make_customers(rng: np.random.Generator):
    span = (END - START).days
    city_names = list(CITIES)
    chan_names = list(CHANNELS)
    cities = rng.choice(city_names, N_CUSTOMERS, p=[CITIES[c][1] for c in city_names])
    channels = rng.choice(chan_names, N_CUSTOMERS, p=[CHANNELS[c][0] for c in chan_names])
    loyalty = np.array([rng.beta(CHANNELS[c][1], CHANNELS[c][2]) for c in channels])
    offsets = (rng.beta(1.5, 1.0, N_CUSTOMERS) * (span - 3)).astype(int)  # growth: more late signups
    customers = pd.DataFrame({
        "customer_id": 100_000 + np.arange(1, N_CUSTOMERS + 1),
        "signup_date": [(START + timedelta(days=int(o))).isoformat() for o in offsets],
        "city": cities,
        "city_tier": [CITIES[c][0] for c in cities],
        "acquisition_channel": channels,
        "age_group": rng.choice(list(AGE_GROUPS), N_CUSTOMERS, p=list(AGE_GROUPS.values())),
        "device": rng.choice(list(DEVICES), N_CUSTOMERS, p=list(DEVICES.values())),
    })
    return customers, loyalty


def simulate_orders(customers: pd.DataFrame, loyalty: np.ndarray, products: pd.DataFrame,
                    cdfs: dict, rng: np.random.Generator):
    price = products.price.values
    cost = products.cost.values
    pid_arr = products.product_id.values
    hour_cdf = np.cumsum(HOUR_W / HOUR_W.sum())
    pay_names, pay_cdf = list(PAYMENTS), np.cumsum(list(PAYMENTS.values()))

    disc_probs = {}
    for bias in range(0, 9):
        p = DISCOUNT_BASE_P * np.exp(0.12 * bias * np.arange(6))
        disc_probs[bias] = np.cumsum(p / p.sum())

    orders, items = [], []
    oid = 0
    for row, loy in zip(customers.itertuples(index=False), loyalty):
        base_min = CITIES[row.city][2]
        sens = CHANNELS[row.acquisition_channel][3]
        d = date.fromisoformat(row.signup_date) + timedelta(days=int(rng.integers(0, 3)))
        n_orders = 0
        while d <= END:
            first = n_orders == 0
            festive = is_festive(d)
            hour = min(int(np.searchsorted(hour_cdf, rng.random())), 23)
            minute, sec = int(rng.integers(0, 60)), int(rng.integers(0, 60))

            delivery = (base_min + rng.normal(0, 3.0) + rng.exponential(1.5)
                        + (3.5 if hour in PEAK_HOURS else 0.0) + (2.5 if festive else 0.0))
            if rng.random() < 0.04:                      # rider-shortage tail events
                delivery += rng.uniform(8, 20)
            delivery = float(np.clip(delivery, 6, 60))
            late = delivery > 20

            n_items = int(np.clip(1 + rng.poisson(2.6 * (1.35 if festive else 1.0)), 1, 14))
            idx = np.unique(np.minimum(np.searchsorted(cdfs[(d.month, festive)], rng.random(n_items)),
                                       len(products) - 1))
            qty = 1 + rng.poisson(0.35, size=len(idx))
            gross = float((price[idx] * qty).sum())
            cogs = float((cost[idx] * qty).sum())

            dcdf = disc_probs[min(sens + (2 if first else 0), 8)]
            disc_pct = int(DISCOUNT_LEVELS[min(int(np.searchsorted(dcdf, rng.random())), 5)])
            disc_amt = round(gross * disc_pct / 100, 2)
            fee = 0.0 if gross >= 199 else 25.0
            net = round(gross - disc_amt + fee, 2)

            cancelled = rng.random() < (0.025 + 0.06 * late + 0.02 * (delivery > 30))
            rating = None
            if not cancelled and rng.random() < 0.38:
                rating = int(np.clip(round(4.7 - 0.10 * (delivery - 12) + rng.normal(0, 0.8)), 1, 5))

            oid += 1
            orders.append((
                oid, int(row.customer_id), f"{d.isoformat()} {hour:02d}:{minute:02d}:{sec:02d}",
                d.isoformat(), hour, d.weekday(), round(delivery, 1), disc_pct, fee, round(gross, 2),
                disc_amt, net, round(cogs, 2), "cancelled" if cancelled else "delivered", rating,
                pay_names[min(int(np.searchsorted(pay_cdf, rng.random())), 3)],
            ))
            items.extend((oid, int(pid_arr[i]), int(q), float(price[i])) for i, q in zip(idx, qty))
            n_orders += 1

            # ---- will the customer come back? ----
            p_cont = (0.66 + 0.28 * loy + min(0.14, 0.028 * n_orders)      # habit builds with each order
                      - (0.20 if late else 0.0) - (0.25 if cancelled else 0.0))
            if first and disc_pct >= 20 and loy < 0.35:
                p_cont -= 0.07                              # deal-seekers rarely stay
            if rng.random() > float(np.clip(p_cont, 0.05, 0.96)):
                break

            gap = 1 + int(rng.exponential(3 + 22 * (1 - loy) ** 1.3))
            if festive:
                gap = max(1, int(gap * 0.7))
            d = d + timedelta(days=gap)
            if d.weekday() < 5 and rng.random() < 0.22:     # weekend skew
                shift = 5 - d.weekday()
                if shift <= 3:
                    d = d + timedelta(days=shift)

    cols = ["order_id", "customer_id", "order_ts", "order_date", "order_hour", "dow", "delivery_minutes",
            "discount_pct", "delivery_fee", "gross_value", "discount_amount", "net_revenue", "cogs",
            "status", "rating", "payment_method"]
    orders_df = pd.DataFrame(orders, columns=cols)
    items_df = pd.DataFrame(items, columns=["order_id", "product_id", "quantity", "unit_price"])

    # chronological, human-friendly order ids
    orders_df = orders_df.sort_values("order_ts").reset_index(drop=True)
    new_ids = pd.Series(500_000 + np.arange(1, len(orders_df) + 1), index=orders_df.order_id)
    items_df["order_id"] = items_df.order_id.map(new_ids)
    orders_df["order_id"] = new_ids.loc[orders_df.order_id].values
    items_df = items_df.sort_values(["order_id", "product_id"]).reset_index(drop=True)
    orders_df["rating"] = orders_df.rating.astype("Int64")
    return orders_df, items_df


def main(raw_dir: Path = RAW_DIR) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(SEED)
    raw_dir.mkdir(parents=True, exist_ok=True)
    products = make_products(rng)
    cdfs = build_product_cdfs(products, rng)
    customers, loyalty = make_customers(rng)
    orders, items = simulate_orders(customers, loyalty, products, cdfs, rng)
    tables = {"customers": customers, "products": products, "orders": orders, "order_items": items}
    for name, df in tables.items():
        df.to_csv(raw_dir / f"{name}.csv", index=False)
    print(f"[generate_data] customers={len(customers):,} products={len(products)} "
          f"orders={len(orders):,} order_items={len(items):,} -> {raw_dir}")
    return tables


if __name__ == "__main__":
    main()

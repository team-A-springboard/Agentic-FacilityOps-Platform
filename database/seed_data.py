"""
Seeds facilityops.db with ~8 weeks of realistic synthetic data:
facilities, assets, hourly energy usage, daily occupancy, maintenance
sensor readings, security events and cost reports.

Run:  python database/seed_data.py
"""
import sqlite3
import random
import math
import os
from datetime import datetime, timedelta

random.seed(42)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "facilityops.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

DAYS_OF_HISTORY = 56  # 8 weeks
NOW = datetime(2026, 9, 3, 6, 0, 0)
START = NOW - timedelta(days=DAYS_OF_HISTORY)


def build_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.commit()
    return conn


def seed_facilities(conn):
    facilities = [
        ("Skyline Corporate Tower", "Corporate Office", "Bengaluru, IN"),
        ("Meridian IT Park - Block C", "IT Park", "Pune, IN"),
        ("Northgate University Campus", "University", "Hyderabad, IN"),
        ("Riverside General Hospital", "Hospital", "Chennai, IN"),
    ]
    conn.executemany(
        "INSERT INTO facilities (facility_name, facility_type, location) VALUES (?,?,?)",
        facilities,
    )
    conn.commit()
    return [row[0] for row in conn.execute("SELECT facility_id FROM facilities")]


ASSET_TEMPLATES = [
    ("Chiller Unit", "HVAC"),
    ("AHU", "HVAC"),
    ("Rooftop Package Unit", "HVAC"),
    ("Elevator", "Vertical Transport"),
    ("Diesel Generator", "Power"),
    ("UPS System", "Power"),
    ("Fire Pump", "Safety"),
    ("Water Booster Pump", "Plumbing"),
    ("Cooling Tower", "HVAC"),
    ("Transformer", "Power"),
]


def seed_assets(conn, facility_ids):
    asset_ids = []
    for fid in facility_ids:
        n_assets = random.randint(5, 7)
        chosen = random.sample(ASSET_TEMPLATES, n_assets)
        for i, (name, atype) in enumerate(chosen):
            installed = START - timedelta(days=random.randint(200, 2500))
            cur = conn.execute(
                """INSERT INTO assets (facility_id, asset_name, asset_type, status,
                   installed_on, expected_life_years) VALUES (?,?,?,?,?,?)""",
                (fid, f"{name} #{i+1}", atype, "Operational",
                 installed.strftime("%Y-%m-%d"), random.choice([8, 10, 12, 15])),
            )
            asset_ids.append((cur.lastrowid, fid, atype))
    conn.commit()
    return asset_ids


def seed_energy(conn, facility_ids):
    """Hourly-ish (every 3h) electricity + water usage for 56 days, with
    daily/weekly seasonality plus a handful of injected anomaly spikes."""
    rows = []
    for fid in facility_ids:
        base_kwh = random.uniform(55, 95)
        t = START
        while t <= NOW:
            hour = t.hour
            weekday = t.weekday()
            # daytime / weekday load curve
            day_factor = 0.55 + 0.45 * math.sin(math.pi * max(0, (hour - 6)) / 16) if 6 <= hour <= 22 else 0.35
            week_factor = 1.0 if weekday < 5 else 0.6
            noise = random.uniform(0.92, 1.08)
            kwh = round(base_kwh * day_factor * week_factor * noise, 2)

            # inject occasional anomaly spikes (~2% of readings)
            is_anomaly = random.random() < 0.02
            if is_anomaly:
                kwh = round(kwh * random.uniform(1.6, 2.2), 2)

            water = round(kwh * random.uniform(3.0, 4.2) * random.uniform(0.9, 1.1), 1)

            hvac = round(random.uniform(38, 50), 1)
            lighting = round(random.uniform(20, 30), 1)
            equipment = round(random.uniform(14, 22), 1)
            other = round(max(0, 100 - hvac - lighting - equipment), 1)

            rows.append((fid, t.strftime("%Y-%m-%d %H:%M:%S"), kwh, water,
                         hvac, lighting, equipment, other))
            t += timedelta(hours=3)
    conn.executemany(
        """INSERT INTO energy_usage (facility_id, timestamp, electricity_usage,
           water_usage, hvac_load_pct, lighting_load_pct, equipment_load_pct, other_load_pct)
           VALUES (?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()


ZONES = ["Office Floors", "Meeting Rooms", "Common Areas", "Parking Areas", "Cafeteria", "Lobby"]


def seed_occupancy(conn, facility_ids):
    rows = []
    for fid in facility_ids:
        capacities = {z: random.randint(80, 400) for z in ZONES}
        t = START
        while t <= NOW:
            weekday = t.weekday()
            hour = t.hour
            for z in ZONES:
                cap = capacities[z]
                if weekday >= 5:
                    occ_pct = random.uniform(0.02, 0.15)
                elif 9 <= hour <= 18:
                    peak = {"Office Floors": 0.85, "Meeting Rooms": 0.65, "Common Areas": 0.5,
                            "Parking Areas": 0.7, "Cafeteria": 0.4, "Lobby": 0.3}[z]
                    occ_pct = peak * random.uniform(0.75, 1.15)
                else:
                    occ_pct = random.uniform(0.03, 0.2)
                occ_pct = min(occ_pct, 1.05)
                rows.append((fid, z, int(cap * occ_pct), cap, t.strftime("%Y-%m-%d %H:%M:%S")))
            t += timedelta(hours=6)
    conn.executemany(
        """INSERT INTO occupancy_records (facility_id, zone, occupancy_count, capacity, timestamp)
           VALUES (?,?,?,?,?)""",
        rows,
    )
    conn.commit()


def seed_maintenance(conn, asset_ids):
    """Daily sensor readings (vibration, temperature, runtime) per asset,
    with a handful of assets trending toward failure."""
    degrading_assets = set(a[0] for a in random.sample(asset_ids, max(1, len(asset_ids) // 6)))
    rows = []
    for asset_id, fid, atype in asset_ids:
        base_vibe = random.uniform(1.5, 3.0)
        base_temp = random.uniform(45, 60) if atype in ("HVAC", "Power") else random.uniform(30, 45)
        runtime = 0.0
        t = START
        degrade = asset_id in degrading_assets
        day_index = 0
        total_days = (NOW - START).days
        while t <= NOW:
            drift = (day_index / max(1, total_days)) * random.uniform(2.5, 4.5) if degrade else 0
            vibe = round(base_vibe + drift + random.uniform(-0.15, 0.15), 2)
            temp = round(base_temp + drift * 1.8 + random.uniform(-1.2, 1.2), 1)
            runtime += random.uniform(4, 16)

            issue_type = "Routine Inspection"
            status = "Completed"
            if degrade and day_index > total_days * 0.7 and random.random() < 0.3:
                issue_type = random.choice(["Vibration Anomaly", "Overheating", "Unusual Noise"])
                status = random.choice(["Scheduled", "In Progress"])

            rows.append((asset_id, issue_type, t.strftime("%Y-%m-%d"), status,
                        vibe, temp, round(runtime, 1)))
            t += timedelta(days=1)
            day_index += 1
    conn.executemany(
        """INSERT INTO maintenance_records (asset_id, issue_type, maintenance_date,
           status, vibration_score, temperature_c, runtime_hours) VALUES (?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    return degrading_assets


def seed_security(conn, facility_ids):
    event_types = ["Unauthorized Access Attempt", "Tailgating Detected", "After-Hours Access",
                   "Forced Door Alarm", "Badge Mismatch", "CCTV Motion - Restricted Zone"]
    severities = ["Low", "Medium", "High", "Critical"]
    weights = [0.45, 0.3, 0.18, 0.07]
    rows = []
    for fid in facility_ids:
        n_events = random.randint(35, 60)
        for _ in range(n_events):
            t = START + timedelta(seconds=random.randint(0, int((NOW - START).total_seconds())))
            rows.append((fid, random.choice(event_types),
                        random.choices(severities, weights=weights)[0],
                        random.choice(ZONES), t.strftime("%Y-%m-%d %H:%M:%S")))
    conn.executemany(
        """INSERT INTO security_events (facility_id, event_type, severity, zone, timestamp)
           VALUES (?,?,?,?,?)""",
        rows,
    )
    conn.commit()


def seed_cost_reports(conn, facility_ids):
    categories = ["Energy", "Maintenance", "Security Operations", "Administrative"]
    rows = []
    for fid in facility_ids:
        d = START
        while d <= NOW:
            if d.day == 1 or d == START:
                for cat, base in zip(categories, [420000, 260000, 190000, 205000]):
                    amt = round(base * random.uniform(0.85, 1.15), 2)
                    rows.append((fid, cat, amt, d.strftime("%Y-%m-%d")))
            d += timedelta(days=1)
    conn.executemany(
        "INSERT INTO cost_reports (facility_id, category, amount, report_date) VALUES (?,?,?,?)",
        rows,
    )
    conn.commit()


def main():
    conn = build_db()
    facility_ids = seed_facilities(conn)
    asset_ids = seed_assets(conn, facility_ids)
    seed_energy(conn, facility_ids)
    seed_occupancy(conn, facility_ids)
    degrading = seed_maintenance(conn, asset_ids)
    seed_security(conn, facility_ids)
    seed_cost_reports(conn, facility_ids)
    conn.close()
    print(f"Seeded database at {os.path.abspath(DB_PATH)}")
    print(f"Facilities: {len(facility_ids)} | Assets: {len(asset_ids)} | Degrading assets: {len(degrading)}")


if __name__ == "__main__":
    main()

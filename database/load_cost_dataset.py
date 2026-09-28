"""
Milestone 4 dataset loader
--------------------------
Loads `Milestone_4_Facility_Cost_Optimization_Dataset.csv` (30 facilities x
24 months of cost / consumption / ROI data) into the `cost_optimization`
table inside facilityops.db so the Cost Optimization Agent can query it
with plain SQL, the same way every other agent does.

Idempotent: safe to call on every app startup — it drops and reloads the
table from the CSV each time, so the dataset always matches the file on
disk.

Run directly:
    python database/load_cost_dataset.py
"""
import csv
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "facilityops.db")
CSV_PATH = os.path.join(BASE_DIR, "cost_optimization_dataset.csv")

NUMERIC_COLUMNS = {
    "electricity_cost", "water_cost", "hvac_cost", "maintenance_cost",
    "security_cost", "cleaning_cost", "staffing_cost", "vendor_cost",
    "occupancy_rate", "energy_consumption_kwh", "maintenance_events",
    "equipment_downtime_hours", "security_incidents", "water_consumption_liters",
    "budget_allocated", "total_operational_cost", "cost_variance",
    "cost_per_occupant", "vendor_count", "potential_savings", "roi_percentage",
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS cost_optimization (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id               TEXT NOT NULL,      -- e.g. FAC-001 (portfolio cost-center id)
    facility_type             TEXT NOT NULL,
    month                     TEXT NOT NULL,       -- YYYY-MM
    electricity_cost          REAL,
    water_cost                REAL,
    hvac_cost                 REAL,
    maintenance_cost          REAL,
    security_cost             REAL,
    cleaning_cost             REAL,
    staffing_cost             REAL,
    vendor_cost               REAL,
    occupancy_rate            REAL,
    energy_consumption_kwh    REAL,
    maintenance_events        REAL,
    equipment_downtime_hours  REAL,
    security_incidents        REAL,
    water_consumption_liters  REAL,
    budget_allocated          REAL,
    total_operational_cost    REAL,
    cost_variance             REAL,
    cost_per_occupant         REAL,
    vendor_count              REAL,
    potential_savings         REAL,
    recommended_action        TEXT,
    priority                  TEXT,
    roi_percentage            REAL
);
"""


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load(conn=None):
    own_conn = conn is None
    if own_conn:
        conn = sqlite3.connect(DB_PATH)

    conn.execute("DROP TABLE IF EXISTS cost_optimization")
    conn.execute(CREATE_TABLE_SQL)

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        rows = []
        for row in reader:
            values = []
            for col in columns:
                v = row[col]
                values.append(_to_float(v) if col in NUMERIC_COLUMNS else v)
            rows.append(values)

    placeholders = ",".join(["?"] * len(columns))
    conn.executemany(
        f"INSERT INTO cost_optimization ({','.join(columns)}) VALUES ({placeholders})",
        rows,
    )
    conn.commit()

    if own_conn:
        count = conn.execute("SELECT COUNT(*) FROM cost_optimization").fetchone()[0]
        print(f"Loaded {count} cost-optimization records into {os.path.abspath(DB_PATH)}")
        conn.close()


if __name__ == "__main__":
    load()

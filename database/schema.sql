-- Agentic FacilityOps AI Platform — Database Schema
-- Matches the ER diagram in the project spec (Section 9)

DROP TABLE IF EXISTS alerts;
DROP TABLE IF EXISTS cost_reports;
DROP TABLE IF EXISTS security_events;
DROP TABLE IF EXISTS maintenance_records;
DROP TABLE IF EXISTS occupancy_records;
DROP TABLE IF EXISTS energy_usage;
DROP TABLE IF EXISTS assets;
DROP TABLE IF EXISTS facilities;

CREATE TABLE facilities (
    facility_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_name TEXT NOT NULL,
    facility_type TEXT NOT NULL,      -- Corporate Office, IT Park, University, Hospital
    location      TEXT NOT NULL
);

CREATE TABLE assets (
    asset_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id   INTEGER NOT NULL REFERENCES facilities(facility_id),
    asset_name    TEXT NOT NULL,
    asset_type    TEXT NOT NULL,      -- HVAC, Chiller, Elevator, Generator, Pump, UPS...
    status        TEXT NOT NULL DEFAULT 'Operational',   -- Operational, Warning, Critical, Down
    installed_on  TEXT,
    expected_life_years INTEGER DEFAULT 10
);

CREATE TABLE energy_usage (
    energy_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id       INTEGER NOT NULL REFERENCES facilities(facility_id),
    timestamp         TEXT NOT NULL,
    electricity_usage REAL NOT NULL,   -- kWh
    water_usage       REAL NOT NULL,   -- liters
    hvac_load_pct     REAL,
    lighting_load_pct REAL,
    equipment_load_pct REAL,
    other_load_pct    REAL
);

CREATE TABLE occupancy_records (
    occupancy_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id      INTEGER NOT NULL REFERENCES facilities(facility_id),
    zone             TEXT NOT NULL,
    occupancy_count  INTEGER NOT NULL,
    capacity         INTEGER NOT NULL,
    timestamp        TEXT NOT NULL
);

CREATE TABLE maintenance_records (
    maintenance_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id         INTEGER NOT NULL REFERENCES assets(asset_id),
    issue_type       TEXT NOT NULL,
    maintenance_date TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'Scheduled',  -- Scheduled, In Progress, Completed
    vibration_score  REAL,
    temperature_c    REAL,
    runtime_hours     REAL
);

CREATE TABLE security_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id  INTEGER NOT NULL REFERENCES facilities(facility_id),
    event_type   TEXT NOT NULL,     -- Unauthorized Access, Tailgating, Forced Entry, After-Hours Access
    severity     TEXT NOT NULL,     -- Low, Medium, High, Critical
    zone         TEXT,
    timestamp    TEXT NOT NULL
);

CREATE TABLE cost_reports (
    report_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id  INTEGER NOT NULL REFERENCES facilities(facility_id),
    category     TEXT NOT NULL,     -- Energy, Maintenance, Security Ops, Administrative
    amount       REAL NOT NULL,
    report_date  TEXT NOT NULL
);

CREATE TABLE alerts (
    alert_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_id  INTEGER NOT NULL REFERENCES facilities(facility_id),
    agent        TEXT NOT NULL,      -- Energy Agent, Maintenance Agent, Occupancy Agent, Security Agent, Cost Agent
    alert_type   TEXT NOT NULL,
    severity     TEXT NOT NULL,      -- Info, Warning, Critical
    message      TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'Open'   -- Open, Acknowledged, Resolved
);

"""
Agentic FacilityOps AI Platform
--------------------------------
Energy Agent + Maintenance Agent reference implementation.

Run:
    pip install -r requirements.txt
    python database/seed_data.py
    python app.py

Then open http://localhost:5000
"""
import os
import sqlite3
from functools import wraps

from flask import Flask, jsonify, render_template, g, request, session, redirect, url_for

from agents.energy_agent import EnergyAgent
from agents.maintenance_agent import MaintenanceAgent
from agents.occupancy_agent import OccupancyAgent
from agents.security_agent import SecurityAgent
from agents.cost_agent import CostOptimizationAgent
from agents.intelligence_engine import FacilityIntelligenceEngine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "facilityops.db")

app = Flask(__name__)
app.secret_key = os.environ.get("FACILITYOPS_SECRET_KEY", "dev-secret-change-me")

# Demo credentials — override with env vars for anything beyond local/demo use.
APP_USERNAME = os.environ.get("FACILITYOPS_USERNAME", "admin")
APP_PASSWORD = os.environ.get("FACILITYOPS_PASSWORD", "admin123")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@app.before_request
def require_login():
    exempt = {"login", "static"}
    if request.endpoint in exempt or request.endpoint is None:
        return
    if not session.get("logged_in"):
        return redirect(url_for("login", next=request.path))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == APP_USERNAME and password == APP_PASSWORD:
            session["logged_in"] = True
            session["username"] = username
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def ensure_db_exists():
    if not os.path.exists(DB_PATH):
        from database.seed_data import main as seed_main
        seed_main()

    # Milestone 4: (re)load the Cost Optimization dataset every startup so
    # the `cost_optimization` table always matches the CSV on disk, even if
    # facilityops.db already existed from an earlier milestone.
    from database.load_cost_dataset import load as load_cost_data
    conn = sqlite3.connect(DB_PATH)
    try:
        load_cost_data(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Page routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    conn = get_db()
    facilities = conn.execute("SELECT facility_id, facility_name, facility_type, location FROM facilities").fetchall()
    return render_template("index.html", facilities=[dict(f) for f in facilities])


@app.route("/energy")
def energy_dashboard():
    conn = get_db()
    facilities = conn.execute("SELECT facility_id, facility_name FROM facilities").fetchall()
    return render_template("energy_dashboard.html", facilities=[dict(f) for f in facilities])


@app.route("/maintenance")
def maintenance_dashboard():
    conn = get_db()
    facilities = conn.execute("SELECT facility_id, facility_name FROM facilities").fetchall()
    return render_template("maintenance_dashboard.html", facilities=[dict(f) for f in facilities])


@app.route("/occupancy")
def occupancy_dashboard():
    conn = get_db()
    facilities = conn.execute("SELECT facility_id, facility_name FROM facilities").fetchall()
    return render_template("occupancy_dashboard.html", facilities=[dict(f) for f in facilities])


@app.route("/security")
def security_dashboard():
    conn = get_db()
    facilities = conn.execute("SELECT facility_id, facility_name FROM facilities").fetchall()
    return render_template("security_dashboard.html", facilities=[dict(f) for f in facilities])


@app.route("/cost")
def cost_dashboard():
    agent = CostOptimizationAgent(get_db())
    return render_template("cost_dashboard.html", cost_facilities=agent.facility_list())


@app.route("/executive")
def executive_dashboard():
    conn = get_db()
    facilities = conn.execute("SELECT facility_id, facility_name FROM facilities").fetchall()
    return render_template("executive_dashboard.html", facilities=[dict(f) for f in facilities])


# ---------------------------------------------------------------------------
# Energy Agent API
# ---------------------------------------------------------------------------
@app.route("/api/energy/summary")
def api_energy_summary():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = EnergyAgent(get_db())
    return jsonify(agent.summary(fid, days))


@app.route("/api/energy/timeseries")
def api_energy_timeseries():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = EnergyAgent(get_db())
    return jsonify(agent.timeseries(fid, days))


@app.route("/api/energy/load-timeseries")
def api_energy_load_timeseries():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = EnergyAgent(get_db())
    return jsonify(agent.load_composition_series(fid, days))


@app.route("/api/energy/load-distribution")
def api_energy_load_distribution():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = EnergyAgent(get_db())
    return jsonify(agent.hvac_efficiency(fid, days))


@app.route("/api/energy/recommendations")
def api_energy_recommendations():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = EnergyAgent(get_db())
    return jsonify(agent.recommendations(fid, days))


@app.route("/api/energy/anomalies")
def api_energy_anomalies():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = EnergyAgent(get_db())
    return jsonify(agent.anomaly_detection(fid, days))


@app.route("/api/energy/forecast")
def api_energy_forecast():
    fid = request.args.get("facility_id", type=int)
    agent = EnergyAgent(get_db())
    return jsonify(agent.forecast_demand(fid))


# ---------------------------------------------------------------------------
# Maintenance Agent API
# ---------------------------------------------------------------------------
@app.route("/api/maintenance/summary")
def api_maintenance_summary():
    fid = request.args.get("facility_id", type=int)
    agent = MaintenanceAgent(get_db())
    return jsonify(agent.summary(fid))


@app.route("/api/maintenance/assets")
def api_maintenance_assets():
    fid = request.args.get("facility_id", type=int)
    agent = MaintenanceAgent(get_db())
    return jsonify(agent.asset_overview(fid))


@app.route("/api/maintenance/work-orders")
def api_maintenance_work_orders():
    fid = request.args.get("facility_id", type=int)
    agent = MaintenanceAgent(get_db())
    return jsonify(agent.generate_work_orders(fid))


@app.route("/api/maintenance/fleet-trend")
def api_maintenance_fleet_trend():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 30, type=int)
    agent = MaintenanceAgent(get_db())
    return jsonify(agent.fleet_trend(fid, days))


@app.route("/api/maintenance/asset/<int:asset_id>")
def api_maintenance_asset_detail(asset_id):
    conn = get_db()
    agent = MaintenanceAgent(conn)
    asset = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    if not asset:
        return jsonify({"error": "not found"}), 404
    records = conn.execute(
        """SELECT maintenance_date, vibration_score, temperature_c, runtime_hours
           FROM maintenance_records WHERE asset_id = ? ORDER BY maintenance_date ASC""",
        (asset_id,),
    ).fetchall()
    return jsonify({
        "asset": dict(asset),
        "health": agent.health_score(asset_id),
        "risk": agent.predict_failure_risk(asset_id),
        "history": [dict(r) for r in records],
    })


# ---------------------------------------------------------------------------
# Occupancy Agent API
# ---------------------------------------------------------------------------
@app.route("/api/occupancy/summary")
def api_occupancy_summary():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = OccupancyAgent(get_db())
    return jsonify(agent.summary(fid, days))


@app.route("/api/occupancy/zones")
def api_occupancy_zones():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = OccupancyAgent(get_db())
    return jsonify(agent.zone_utilization(fid, days))


@app.route("/api/occupancy/trend")
def api_occupancy_trend():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = OccupancyAgent(get_db())
    return jsonify(agent.occupancy_trend(fid, days))


@app.route("/api/occupancy/heatmap")
def api_occupancy_heatmap():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = OccupancyAgent(get_db())
    return jsonify(agent.heatmap(fid, days))


@app.route("/api/occupancy/overcrowding")
def api_occupancy_overcrowding():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = OccupancyAgent(get_db())
    return jsonify(agent.overcrowding_events(fid, days))


@app.route("/api/occupancy/forecast")
def api_occupancy_forecast():
    fid = request.args.get("facility_id", type=int)
    agent = OccupancyAgent(get_db())
    return jsonify(agent.forecast_usage(fid))


@app.route("/api/occupancy/recommendations")
def api_occupancy_recommendations():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = OccupancyAgent(get_db())
    return jsonify(agent.allocation_recommendations(fid, days))


# ---------------------------------------------------------------------------
# Security Agent API
# ---------------------------------------------------------------------------
@app.route("/api/security/summary")
def api_security_summary():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = SecurityAgent(get_db())
    return jsonify(agent.summary(fid, days))


@app.route("/api/security/events")
def api_security_events():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = SecurityAgent(get_db())
    return jsonify(agent.event_list(fid, days))


@app.route("/api/security/severity-distribution")
def api_security_severity_distribution():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = SecurityAgent(get_db())
    return jsonify(agent.severity_distribution(fid, days))


@app.route("/api/security/event-types")
def api_security_event_types():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = SecurityAgent(get_db())
    return jsonify(agent.event_type_distribution(fid, days))


@app.route("/api/security/zone-risk")
def api_security_zone_risk():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = SecurityAgent(get_db())
    return jsonify(agent.zone_risk(fid, days))


@app.route("/api/security/unauthorized-trend")
def api_security_unauthorized_trend():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = SecurityAgent(get_db())
    return jsonify(agent.unauthorized_access_trend(fid, days))


@app.route("/api/security/alerts")
def api_security_alerts():
    fid = request.args.get("facility_id", type=int)
    days = request.args.get("days", 14, type=int)
    agent = SecurityAgent(get_db())
    return jsonify(agent.generate_alerts(fid, days))


# ---------------------------------------------------------------------------
# Cost Optimization Agent API  (Milestone 4)
# ---------------------------------------------------------------------------
@app.route("/api/cost/summary")
def api_cost_summary():
    fid = request.args.get("facility_id")
    months = request.args.get("months", 12, type=int)
    agent = CostOptimizationAgent(get_db())
    return jsonify(agent.summary(fid, months))


@app.route("/api/cost/trend")
def api_cost_trend():
    fid = request.args.get("facility_id")
    months = request.args.get("months", 12, type=int)
    agent = CostOptimizationAgent(get_db())
    return jsonify(agent.monthly_trend(fid, months))


@app.route("/api/cost/breakdown")
def api_cost_breakdown():
    fid = request.args.get("facility_id")
    months = request.args.get("months", 12, type=int)
    agent = CostOptimizationAgent(get_db())
    return jsonify(agent.cost_breakdown(fid, months))


@app.route("/api/cost/ranking")
def api_cost_ranking():
    months = request.args.get("months", 12, type=int)
    agent = CostOptimizationAgent(get_db())
    return jsonify(agent.facility_ranking(months))


@app.route("/api/cost/vendor")
def api_cost_vendor():
    fid = request.args.get("facility_id")
    months = request.args.get("months", 12, type=int)
    agent = CostOptimizationAgent(get_db())
    return jsonify(agent.vendor_analysis(fid, months))


@app.route("/api/cost/budget-compliance")
def api_cost_budget_compliance():
    fid = request.args.get("facility_id")
    months = request.args.get("months", 12, type=int)
    agent = CostOptimizationAgent(get_db())
    return jsonify(agent.budget_compliance(fid, months))


@app.route("/api/cost/recommendations")
def api_cost_recommendations():
    fid = request.args.get("facility_id")
    months = request.args.get("months", 12, type=int)
    agent = CostOptimizationAgent(get_db())
    return jsonify(agent.recommendations(fid, months))


# ---------------------------------------------------------------------------
# Facility Analytics & Intelligence Engine / Executive Dashboard API  (Milestone 4)
# ---------------------------------------------------------------------------
@app.route("/api/executive/summary")
def api_executive_summary():
    fid = request.args.get("facility_id", type=int)
    engine = FacilityIntelligenceEngine(get_db())
    return jsonify(engine.executive_summary(fid))


@app.route("/api/executive/cost-distribution")
def api_executive_cost_distribution():
    engine = FacilityIntelligenceEngine(get_db())
    return jsonify(engine.cost.cost_breakdown(None, 12))


@app.route("/api/executive/ranking")
def api_executive_ranking():
    engine = FacilityIntelligenceEngine(get_db())
    return jsonify(engine.cost.facility_ranking(12))


@app.route("/api/executive/recommendations")
def api_executive_recommendations():
    fid = request.args.get("facility_id", type=int)
    engine = FacilityIntelligenceEngine(get_db())
    return jsonify(engine.consolidated_recommendations(fid))


@app.route("/api/executive/report")
def api_executive_report():
    fid = request.args.get("facility_id", type=int)
    engine = FacilityIntelligenceEngine(get_db())
    report_text = engine.facility_intelligence_report(fid)
    from flask import Response
    return Response(
        report_text,
        mimetype="text/plain",
        headers={"Content-Disposition": "attachment; filename=facility_intelligence_report.txt"},
    )


if __name__ == "__main__":
    ensure_db_exists()
    app.run(debug=True, host="0.0.0.0", port=5000)

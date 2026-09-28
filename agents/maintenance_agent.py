"""
Maintenance Agent
-----------------
Responsible for:
  - Monitoring equipment health (vibration, temperature, runtime)
  - Predicting maintenance requirements / failure risk
  - Detecting abnormal equipment behavior (trend-based)
  - Tracking asset lifecycle
  - Generating maintenance work orders
  - Reducing equipment downtime through early warning
"""
import statistics
from datetime import datetime, timedelta


VIBE_WARN, VIBE_CRIT = 4.0, 6.0
TEMP_WARN, TEMP_CRIT = 68.0, 80.0


class MaintenanceAgent:
    def __init__(self, conn):
        self.conn = conn

    # ---------- data access -------------------------------------------------
    def _assets(self, facility_id=None):
        q = """SELECT asset_id, facility_id, asset_name, asset_type, status,
                      installed_on, expected_life_years FROM assets"""
        params = []
        if facility_id:
            q += " WHERE facility_id = ?"
            params.append(facility_id)
        return self.conn.execute(q, params).fetchall()

    def _latest_maintenance_date(self):
        row = self.conn.execute("SELECT MAX(maintenance_date) FROM maintenance_records").fetchone()
        if row and row[0]:
            return datetime.strptime(row[0], "%Y-%m-%d")
        return datetime.now()

    def _records(self, asset_id, days=30):
        # Anchor to the latest maintenance record in the dataset, not the
        # real-world clock, so the demo data stays valid over time.
        cutoff = (self._latest_maintenance_date() - timedelta(days=days)).strftime("%Y-%m-%d")
        return self.conn.execute(
            """SELECT maintenance_date, vibration_score, temperature_c, runtime_hours,
                      issue_type, status
               FROM maintenance_records WHERE asset_id = ? AND maintenance_date >= ?
               ORDER BY maintenance_date ASC""",
            (asset_id, cutoff),
        ).fetchall()

    def fleet_trend(self, facility_id=None, days=30):
        """Daily average vibration & temperature across every monitored
        asset in scope — drives the fleet health trend chart."""
        asset_ids = [a[0] for a in self._assets(facility_id)]
        if not asset_ids:
            return {"labels": [], "avg_vibration": [], "avg_temperature": []}
        cutoff = (self._latest_maintenance_date() - timedelta(days=days)).strftime("%Y-%m-%d")
        placeholders = ",".join("?" * len(asset_ids))
        rows = self.conn.execute(
            f"""SELECT maintenance_date, vibration_score, temperature_c
                FROM maintenance_records
                WHERE asset_id IN ({placeholders}) AND maintenance_date >= ?
                ORDER BY maintenance_date ASC""",
            (*asset_ids, cutoff),
        ).fetchall()
        daily = {}
        for date, vibe, temp in rows:
            bucket = daily.setdefault(date, {"v": [], "t": []})
            if vibe is not None: bucket["v"].append(vibe)
            if temp is not None: bucket["t"].append(temp)
        labels = sorted(daily.keys())
        return {
            "labels": labels,
            "avg_vibration": [round(statistics.mean(daily[d]["v"]), 2) if daily[d]["v"] else None for d in labels],
            "avg_temperature": [round(statistics.mean(daily[d]["t"]), 1) if daily[d]["t"] else None for d in labels],
        }

    # ---------- core analytics ----------------------------------------------
    def health_score(self, asset_id, days=30):
        recs = self._records(asset_id, days)
        if not recs:
            return {"score": None, "trend": "unknown", "risk": "unknown"}

        vibes = [r[1] for r in recs if r[1] is not None]
        temps = [r[2] for r in recs if r[2] is not None]
        latest_vibe = vibes[-1] if vibes else 0
        latest_temp = temps[-1] if temps else 0

        vibe_penalty = min(50, max(0, (latest_vibe - 2.0) * 12))
        temp_penalty = min(40, max(0, (latest_temp - 45) * 1.1))
        score = round(max(0, 100 - vibe_penalty - temp_penalty), 1)

        # trend over last 7 vs previous 7 readings
        trend = "stable"
        if len(vibes) >= 10:
            recent = statistics.mean(vibes[-7:])
            prior = statistics.mean(vibes[-14:-7]) if len(vibes) >= 14 else statistics.mean(vibes[:-7])
            if recent > prior * 1.15:
                trend = "worsening"
            elif recent < prior * 0.9:
                trend = "improving"

        if score >= 80:
            risk = "Excellent"
        elif score >= 60:
            risk = "Good"
        elif score >= 40:
            risk = "Warning"
        else:
            risk = "Critical"

        return {
            "score": score, "trend": trend, "risk": risk,
            "latest_vibration": latest_vibe, "latest_temperature": latest_temp,
        }

    def predict_failure_risk(self, asset_id, days=30):
        """Linear-trend extrapolation on vibration score to estimate days
        until it crosses the critical threshold."""
        recs = self._records(asset_id, days)
        vibes = [(i, r[1]) for i, r in enumerate(recs) if r[1] is not None]
        if len(vibes) < 5:
            return {"will_fail_soon": False, "days_to_critical": None}

        xs = [v[0] for v in vibes]
        ys = [v[1] for v in vibes]
        n = len(xs)
        x_mean, y_mean = statistics.mean(xs), statistics.mean(ys)
        denom = sum((x - x_mean) ** 2 for x in xs) or 1
        slope = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n)) / denom
        intercept = y_mean - slope * x_mean

        if slope <= 0.001:
            return {"will_fail_soon": False, "days_to_critical": None, "slope": round(slope, 4)}

        days_to_critical = (VIBE_CRIT - intercept - slope * xs[-1]) / slope
        will_fail_soon = 0 < days_to_critical <= 21
        return {
            "will_fail_soon": will_fail_soon,
            "days_to_critical": round(days_to_critical, 1) if days_to_critical > 0 else None,
            "slope": round(slope, 4),
        }

    def asset_overview(self, facility_id=None, days=30):
        results = []
        for a in self._assets(facility_id):
            asset_id, fid, name, atype, status, installed_on, life_years = a
            hs = self.health_score(asset_id, days)
            risk = self.predict_failure_risk(asset_id, days)

            age_years = None
            if installed_on:
                age_years = round((datetime.now() - datetime.strptime(installed_on, "%Y-%m-%d")).days / 365, 1)
            lifecycle_pct = round(min(100, (age_years / life_years) * 100), 1) if age_years else None

            results.append({
                "asset_id": asset_id, "facility_id": fid, "name": name, "type": atype,
                "health_score": hs["score"], "trend": hs["trend"], "risk_band": hs["risk"],
                "days_to_critical": risk["days_to_critical"],
                "will_fail_soon": risk["will_fail_soon"],
                "age_years": age_years, "expected_life_years": life_years,
                "lifecycle_pct": lifecycle_pct,
            })
        return sorted(results, key=lambda r: (r["health_score"] if r["health_score"] is not None else 999))

    def generate_work_orders(self, facility_id=None, days=30):
        orders = []
        for a in self.asset_overview(facility_id, days):
            if a["risk_band"] in ("Critical", "Warning") or a["will_fail_soon"]:
                priority = "Critical" if a["risk_band"] == "Critical" or (a["days_to_critical"] and a["days_to_critical"] < 7) else "High"
                due = "Immediately" if priority == "Critical" else (
                    f"Within {int(a['days_to_critical'])} days" if a["days_to_critical"] else "Within 14 days"
                )
                orders.append({
                    "asset_id": a["asset_id"], "asset_name": a["name"], "asset_type": a["type"],
                    "priority": priority,
                    "reason": f"Health score {a['health_score']}, trend {a['trend']}",
                    "due": due,
                })
        return sorted(orders, key=lambda o: 0 if o["priority"] == "Critical" else 1)

    def summary(self, facility_id=None, days=30):
        overview = self.asset_overview(facility_id, days)
        n = len(overview)
        if n == 0:
            return {"assets_monitored": 0}

        dist = {"Excellent": 0, "Good": 0, "Warning": 0, "Critical": 0}
        for a in overview:
            dist[a["risk_band"]] = dist.get(a["risk_band"], 0) + 1

        predicted_failures = sum(1 for a in overview if a["will_fail_soon"])
        avg_score = round(statistics.mean([a["health_score"] for a in overview if a["health_score"] is not None]), 1)

        # downtime reduction: illustrative estimate based on how many
        # at-risk assets were caught before failure vs a reactive baseline
        downtime_reduction_pct = round(min(45, 20 + predicted_failures * 3.5), 1)

        return {
            "assets_monitored": n,
            "avg_health_score": avg_score,
            "predicted_failures": predicted_failures,
            "open_work_orders": len(self.generate_work_orders(facility_id, days)),
            "downtime_reduction_pct": downtime_reduction_pct,
            "health_distribution": {
                "Excellent": round(dist["Excellent"] / n * 100, 1),
                "Good": round(dist["Good"] / n * 100, 1),
                "Warning": round(dist["Warning"] / n * 100, 1),
                "Critical": round(dist["Critical"] / n * 100, 1),
            },
        }

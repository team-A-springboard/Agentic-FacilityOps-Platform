"""
Cost Optimization Agent
------------------------
Responsible for (per project spec, section 4.5):
  - Analyzing operational expenditures
  - Identifying cost-saving opportunities
  - Optimizing vendor utilization
  - Recommending resource allocation improvements
  - Monitoring budget compliance
  - Generating ROI reports

Data source: the Milestone 4 "Facility Cost Optimization Dataset" — 30
facilities (FAC-001..FAC-030) x 24 months of cost, consumption and ROI
data, loaded into the `cost_optimization` sqlite table by
database/load_cost_dataset.py.
"""
import statistics
from collections import defaultdict

COST_CATEGORIES = [
    ("electricity_cost", "Electricity"),
    ("water_cost", "Water"),
    ("hvac_cost", "HVAC"),
    ("maintenance_cost", "Maintenance"),
    ("security_cost", "Security"),
    ("cleaning_cost", "Cleaning"),
    ("staffing_cost", "Staffing"),
    ("vendor_cost", "Vendor Services"),
]

SELECT_COLUMNS = """facility_id, facility_type, month, electricity_cost, water_cost,
    hvac_cost, maintenance_cost, security_cost, cleaning_cost, staffing_cost,
    vendor_cost, occupancy_rate, energy_consumption_kwh, maintenance_events,
    equipment_downtime_hours, security_incidents, water_consumption_liters,
    budget_allocated, total_operational_cost, cost_variance, cost_per_occupant,
    vendor_count, potential_savings, recommended_action, priority, roi_percentage"""


class CostOptimizationAgent:
    def __init__(self, conn):
        self.conn = conn

    # ---------- data access -------------------------------------------------
    def _rows(self, facility_id=None, months=12):
        q = f"SELECT {SELECT_COLUMNS} FROM cost_optimization"
        params = []
        if facility_id:
            q += " WHERE facility_id = ?"
            params.append(facility_id)
        q += " ORDER BY month DESC"
        rows = [dict(r) for r in self.conn.execute(q, params).fetchall()]
        if months:
            keep_months = sorted({r["month"] for r in rows}, reverse=True)[:months]
            rows = [r for r in rows if r["month"] in keep_months]
        return rows

    def facility_list(self):
        rows = self.conn.execute(
            "SELECT DISTINCT facility_id, facility_type FROM cost_optimization ORDER BY facility_id"
        ).fetchall()
        return [{"facility_id": r["facility_id"], "facility_type": r["facility_type"]} for r in rows]

    # ---------- core analytics -----------------------------------------------
    def summary(self, facility_id=None, months=12):
        rows = self._rows(facility_id, months)
        if not rows:
            return {}
        total_cost = sum(r["total_operational_cost"] or 0 for r in rows)
        total_budget = sum(r["budget_allocated"] or 0 for r in rows)
        total_savings = sum(r["potential_savings"] or 0 for r in rows)
        total_variance = sum(r["cost_variance"] or 0 for r in rows)
        roi_values = [r["roi_percentage"] for r in rows if r["roi_percentage"] is not None]
        avg_roi = round(statistics.mean(roi_values), 1) if roi_values else 0
        cost_reduction_pct = round((total_savings / total_cost) * 100, 1) if total_cost else 0
        over_budget_months = sum(1 for r in rows if (r["cost_variance"] or 0) < 0)
        facility_health = round(max(0, min(100, 100 - abs(cost_reduction_pct - 15) * 1.2
                                            - (over_budget_months / len(rows)) * 20)), 0)
        optimizations = len({a.strip() for r in rows if r["recommended_action"]
                              for a in r["recommended_action"].split(";")})
        return {
            "records": len(rows),
            "facilities_covered": len({r["facility_id"] for r in rows}),
            "total_operational_cost": round(total_cost, 2),
            "total_budget_allocated": round(total_budget, 2),
            "total_cost_variance": round(total_variance, 2),
            "potential_savings": round(total_savings, 2),
            "cost_reduction_pct": cost_reduction_pct,
            "roi_generated_pct": avg_roi,
            "facility_health_score": facility_health,
            "optimizations_identified": optimizations,
            "over_budget_periods": over_budget_months,
        }

    def cost_breakdown(self, facility_id=None, months=12):
        """% share of total operational cost by category — drives the
        'Cost Distribution' chart in the executive dashboard."""
        rows = self._rows(facility_id, months)
        if not rows:
            return {}
        totals = {label: 0.0 for _, label in COST_CATEGORIES}
        for r in rows:
            for col, label in COST_CATEGORIES:
                totals[label] += r.get(col) or 0
        grand_total = sum(totals.values()) or 1
        return {label: round((v / grand_total) * 100, 1) for label, v in totals.items()}

    def monthly_trend(self, facility_id=None, months=12):
        rows = self._rows(facility_id, months)
        by_month = defaultdict(lambda: {"cost": 0.0, "budget": 0.0, "savings": 0.0})
        for r in rows:
            m = by_month[r["month"]]
            m["cost"] += r["total_operational_cost"] or 0
            m["budget"] += r["budget_allocated"] or 0
            m["savings"] += r["potential_savings"] or 0
        labels = sorted(by_month.keys())
        return {
            "labels": labels,
            "operational_cost": [round(by_month[m]["cost"], 0) for m in labels],
            "budget_allocated": [round(by_month[m]["budget"], 0) for m in labels],
            "potential_savings": [round(by_month[m]["savings"], 0) for m in labels],
        }

    def facility_ranking(self, months=12, limit=10):
        """Rank facilities across the portfolio by potential savings —
        surfaces the biggest cost-saving opportunities first."""
        rows = self._rows(None, months)
        by_facility = defaultdict(lambda: {
            "facility_type": None, "savings": 0.0, "cost": 0.0, "variance": 0.0,
            "roi": [], "priority_flags": 0,
        })
        for r in rows:
            f = by_facility[r["facility_id"]]
            f["facility_type"] = r["facility_type"]
            f["savings"] += r["potential_savings"] or 0
            f["cost"] += r["total_operational_cost"] or 0
            f["variance"] += r["cost_variance"] or 0
            if r["roi_percentage"] is not None:
                f["roi"].append(r["roi_percentage"])
            if r["priority"] in ("High", "Medium"):
                f["priority_flags"] += 1

        ranked = []
        for fid, f in by_facility.items():
            ranked.append({
                "facility_id": fid,
                "facility_type": f["facility_type"],
                "potential_savings": round(f["savings"], 0),
                "total_cost": round(f["cost"], 0),
                "cost_variance": round(f["variance"], 0),
                "avg_roi_pct": round(statistics.mean(f["roi"]), 1) if f["roi"] else 0,
                "over_budget": f["variance"] < 0,
                "priority_flags": f["priority_flags"],
            })
        ranked.sort(key=lambda x: -x["potential_savings"])
        return ranked[:limit]

    def vendor_analysis(self, facility_id=None, months=12):
        rows = self._rows(facility_id, months)
        if not rows:
            return {}
        vendor_costs = [r["vendor_cost"] or 0 for r in rows]
        vendor_counts = [r["vendor_count"] or 0 for r in rows if r["vendor_count"] is not None]
        avg_vendor_count = round(statistics.mean(vendor_counts), 1) if vendor_counts else 0
        total_vendor_cost = sum(vendor_costs)
        avg_cost_per_vendor = round(total_vendor_cost / sum(vendor_counts), 2) if sum(vendor_counts) else 0
        consolidation_candidates = sum(
            1 for r in rows
            if r["recommended_action"] and "Vendor consolidation" in r["recommended_action"]
        )
        return {
            "total_vendor_cost": round(total_vendor_cost, 2),
            "avg_active_vendors": avg_vendor_count,
            "avg_cost_per_vendor": avg_cost_per_vendor,
            "consolidation_opportunities": consolidation_candidates,
        }

    def budget_compliance(self, facility_id=None, months=12):
        rows = self._rows(facility_id, months)
        if not rows:
            return {}
        within = sum(1 for r in rows if (r["cost_variance"] or 0) >= 0)
        over = len(rows) - within
        compliance_pct = round((within / len(rows)) * 100, 1)
        worst = sorted(rows, key=lambda r: (r["cost_variance"] or 0))[:5]
        return {
            "compliance_pct": compliance_pct,
            "periods_within_budget": within,
            "periods_over_budget": over,
            "worst_variance_periods": [
                {"facility_id": r["facility_id"], "month": r["month"],
                 "variance": round(r["cost_variance"] or 0, 0)}
                for r in worst
            ],
        }

    def roi_report(self, facility_id=None, months=12):
        rows = self._rows(facility_id, months)
        roi_values = [r["roi_percentage"] for r in rows if r["roi_percentage"] is not None]
        if not roi_values:
            return {}
        return {
            "avg_roi_pct": round(statistics.mean(roi_values), 1),
            "max_roi_pct": round(max(roi_values), 1),
            "min_roi_pct": round(min(roi_values), 1),
            "roi_generated_est": round(sum(r["potential_savings"] or 0 for r in rows), 0),
        }

    def recommendations(self, facility_id=None, months=12):
        """Aggregate the dataset's recommended actions into prioritized,
        de-duplicated recommendation cards (same shape as the other agents)."""
        rows = self._rows(facility_id, months)
        buckets = defaultdict(lambda: {"count": 0, "savings": 0.0, "priority": "Low"})
        priority_rank = {"Critical": 3, "High": 2, "Medium": 1, "Low": 0}
        for r in rows:
            if not r["recommended_action"]:
                continue
            for action in [a.strip() for a in r["recommended_action"].split(";")]:
                b = buckets[action]
                b["count"] += 1
                b["savings"] += r["potential_savings"] or 0
                if priority_rank.get(r["priority"], 0) > priority_rank.get(b["priority"], 0):
                    b["priority"] = r["priority"]

        detail_map = {
            "Energy optimization": "Recurring energy overspend detected across reporting periods — "
                                    "retune HVAC setpoints, shift high-load tasks off-peak, and audit metering.",
            "Predictive maintenance": "Rising maintenance events / downtime hours indicate assets due for "
                                       "proactive servicing before failure escalates costs further.",
            "Vendor consolidation": "Multiple active vendors with overlapping scope inflate per-vendor "
                                     "overhead — consolidating contracts typically cuts vendor spend 8-15%.",
            "Space/resource optimization": "Occupancy rate vs. allocated space suggests underused floors — "
                                            "consolidating footprint reduces fixed operating cost.",
            "Security process optimization": "Security incident volume relative to spend suggests process, "
                                              "not headcount, is the bottleneck — review patrol/incident workflows.",
            "Routine monitoring": "Costs are within healthy range — continue routine monitoring, no "
                                   "immediate action required.",
        }

        recs = []
        for action, b in buckets.items():
            recs.append({
                "priority": b["priority"],
                "title": action,
                "detail": detail_map.get(action, f"Flagged in {b['count']} reporting period(s)."),
                "occurrences": b["count"],
                "est_savings": round(b["savings"], 0),
            })
        recs.sort(key=lambda r: (-priority_rank.get(r["priority"], 0), -r["est_savings"]))
        return recs

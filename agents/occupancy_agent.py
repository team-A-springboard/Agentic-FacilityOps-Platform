"""
Occupancy Agent
---------------
Responsible for:
  - Monitoring room and building occupancy
  - Analyzing space utilization by zone
  - Detecting overcrowding conditions
  - Optimizing workspace allocation
  - Generating occupancy heatmaps
  - Forecasting facility usage patterns
"""
import statistics
from datetime import datetime, timedelta

OVERCROWD_THRESHOLD = 0.90   # >=90% of zone capacity is flagged as overcrowded
UNDERUSED_THRESHOLD = 0.35   # <35% average utilization flags a zone as underused


class OccupancyAgent:
    def __init__(self, conn):
        self.conn = conn

    # ---------- data access -------------------------------------------------
    def _latest_timestamp(self):
        row = self.conn.execute("SELECT MAX(timestamp) FROM occupancy_records").fetchone()
        if row and row[0]:
            return datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        return datetime.now()

    def _records(self, facility_id=None, days=14):
        # Anchor to the latest occupancy record in the dataset, not the
        # real-world clock, so the demo data stays valid over time.
        cutoff = (self._latest_timestamp() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        q = """SELECT facility_id, zone, occupancy_count, capacity, timestamp
               FROM occupancy_records WHERE timestamp >= ?"""
        params = [cutoff]
        if facility_id:
            q += " AND facility_id = ?"
            params.append(facility_id)
        q += " ORDER BY timestamp ASC"
        return self.conn.execute(q, params).fetchall()

    def occupancy_trend(self, facility_id=None, days=14):
        """Daily overall occupancy rate (%) across all zones — drives the
        occupancy trend line chart."""
        rows = self._records(facility_id, days)
        daily = {}
        for r in rows:
            fid, zone, count, cap, ts = r
            day = ts[:10]
            bucket = daily.setdefault(day, [0, 0])
            bucket[0] += count
            bucket[1] += cap or 0
        labels = sorted(daily.keys())
        return {
            "labels": labels,
            "occupancy_rate_pct": [
                round(daily[d][0] / daily[d][1] * 100, 1) if daily[d][1] else 0 for d in labels
            ],
        }

    # ---------- core analytics ----------------------------------------------
    def zone_utilization(self, facility_id=None, days=14):
        rows = self._records(facility_id, days)
        zones = {}
        for r in rows:
            fid, zone, count, cap, ts = r
            pct = (count / cap * 100) if cap else 0
            z = zones.setdefault(zone, {"pcts": [], "capacity": cap, "latest": 0, "latest_ts": ""})
            z["pcts"].append(pct)
            if ts >= z["latest_ts"]:
                z["latest_ts"] = ts
                z["latest"] = count

        results = []
        for zone, z in zones.items():
            avg_pct = round(statistics.mean(z["pcts"]), 1) if z["pcts"] else 0
            peak_pct = round(max(z["pcts"]), 1) if z["pcts"] else 0
            status = "Overcrowded" if peak_pct >= OVERCROWD_THRESHOLD * 100 else (
                "Underused" if avg_pct < UNDERUSED_THRESHOLD * 100 else "Balanced")
            results.append({
                "zone": zone,
                "avg_utilization_pct": avg_pct,
                "peak_utilization_pct": peak_pct,
                "capacity": z["capacity"],
                "current_occupancy": z["latest"],
                "status": status,
            })
        return sorted(results, key=lambda z: -z["avg_utilization_pct"])

    def overcrowding_events(self, facility_id=None, days=14, threshold=OVERCROWD_THRESHOLD):
        rows = self._records(facility_id, days)
        events = []
        for r in rows:
            fid, zone, count, cap, ts = r
            if cap and count / cap >= threshold:
                events.append({
                    "facility_id": fid, "zone": zone, "occupancy_count": count,
                    "capacity": cap, "utilization_pct": round(count / cap * 100, 1),
                    "timestamp": ts,
                })
        return sorted(events, key=lambda e: -e["utilization_pct"])[:20]

    def heatmap(self, facility_id=None, days=14):
        """Average utilization % across weekday x time-of-day buckets."""
        rows = self._records(facility_id, days)
        weekday_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        grid = {}
        hours_seen = set()
        for r in rows:
            fid, zone, count, cap, ts = r
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            wd, hour = dt.weekday(), dt.hour
            hours_seen.add(hour)
            pct = (count / cap * 100) if cap else 0
            key = (wd, hour)
            bucket = grid.setdefault(key, [0.0, 0])
            bucket[0] += pct
            bucket[1] += 1

        hours = sorted(hours_seen)
        matrix = []
        for wd in range(7):
            row = []
            for hour in hours:
                bucket = grid.get((wd, hour))
                row.append(round(bucket[0] / bucket[1], 1) if bucket else 0)
            matrix.append(row)

        return {
            "weekdays": weekday_labels,
            "hours": [f"{h:02d}:00" for h in hours],
            "matrix": matrix,
        }

    def forecast_usage(self, facility_id=None, days_history=14, days_forward=7):
        """Weighted moving-average + trend forecast of total occupancy count per day."""
        rows = self._records(facility_id, days_history)
        if not rows:
            return []
        daily = {}
        for r in rows:
            fid, zone, count, cap, ts = r
            day = ts[:10]
            daily.setdefault(day, 0)
            daily[day] += count
        series = sorted(daily.items())
        if len(series) < 3:
            return []

        totals = [v for _, v in series]
        n = min(7, len(totals))
        recent = totals[-n:]
        avg = statistics.mean(recent)
        deltas = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
        trend = statistics.mean(deltas) if deltas else 0

        forecast = []
        last_date = datetime.strptime(series[-1][0], "%Y-%m-%d")
        value = avg
        for i in range(1, days_forward + 1):
            value = max(0, value + trend)
            forecast.append({
                "date": (last_date + timedelta(days=i)).strftime("%Y-%m-%d"),
                "forecast_occupancy": round(value),
            })
        return forecast

    def allocation_recommendations(self, facility_id=None, days=14):
        zones = self.zone_utilization(facility_id, days)
        recs = []
        overcrowded = [z for z in zones if z["status"] == "Overcrowded"]
        underused = [z for z in zones if z["status"] == "Underused"]

        for z in overcrowded:
            recs.append({
                "priority": "High",
                "title": f"{z['zone']} regularly overcrowded",
                "detail": f"Peak utilization hit {z['peak_utilization_pct']}% of capacity "
                          f"({z['capacity']} seats). Consider overflow space or staggered scheduling.",
            })
        if underused and overcrowded:
            recs.append({
                "priority": "Medium",
                "title": "Reallocation opportunity identified",
                "detail": f"{underused[0]['zone']} averages only {underused[0]['avg_utilization_pct']}% "
                          f"utilization while {overcrowded[0]['zone']} is over capacity — "
                          f"consider reassigning teams or repurposing the underused space.",
            })
        for z in underused:
            if not overcrowded:
                recs.append({
                    "priority": "Low",
                    "title": f"{z['zone']} underutilized",
                    "detail": f"Average utilization is {z['avg_utilization_pct']}% — evaluate "
                              f"reducing footprint or repurposing for another function.",
                })
        if not recs:
            recs.append({
                "priority": "Low",
                "title": "Space utilization within healthy range",
                "detail": "No overcrowding or significant underuse detected across monitored zones.",
            })
        return recs

    def summary(self, facility_id=None, days=14):
        zones = self.zone_utilization(facility_id, days)
        if not zones:
            return {"zones_monitored": 0}

        overall_rate = round(statistics.mean([z["avg_utilization_pct"] for z in zones]), 1)
        active_visitors = sum(z["current_occupancy"] for z in zones)
        overcrowding = self.overcrowding_events(facility_id, days)

        return {
            "zones_monitored": len(zones),
            "occupancy_rate_pct": overall_rate,
            "active_visitors": active_visitors,
            "overcrowding_events": len(overcrowding),
            "busiest_zone": zones[0]["zone"] if zones else None,
        }

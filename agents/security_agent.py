"""
Security Agent
---------------
Responsible for:
  - Monitoring access control systems
  - Detecting unauthorized access attempts
  - Analyzing CCTV / access-control events
  - Tracking visitor movement across zones
  - Generating security alerts
  - Supporting incident investigation
"""
from datetime import datetime, timedelta

SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
UNAUTHORIZED_TYPES = ("Unauthorized Access Attempt", "Tailgating Detected", "Forced Door Alarm", "Badge Mismatch")


class SecurityAgent:
    def __init__(self, conn):
        self.conn = conn

    # ---------- data access -------------------------------------------------
    def _latest_timestamp(self):
        row = self.conn.execute("SELECT MAX(timestamp) FROM security_events").fetchone()
        if row and row[0]:
            return datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        return datetime.now()

    def _events(self, facility_id=None, days=14):
        # Anchor to the latest security event in the dataset, not the
        # real-world clock, so the demo data stays valid over time.
        cutoff = (self._latest_timestamp() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        q = """SELECT event_id, facility_id, event_type, severity, zone, timestamp
               FROM security_events WHERE timestamp >= ?"""
        params = [cutoff]
        if facility_id:
            q += " AND facility_id = ?"
            params.append(facility_id)
        q += " ORDER BY timestamp DESC"
        return self.conn.execute(q, params).fetchall()

    # ---------- core analytics ----------------------------------------------
    def event_list(self, facility_id=None, days=14, limit=40):
        rows = self._events(facility_id, days)
        return [{
            "event_id": r[0], "facility_id": r[1], "event_type": r[2],
            "severity": r[3], "zone": r[4], "timestamp": r[5],
        } for r in rows[:limit]]

    def event_type_distribution(self, facility_id=None, days=14):
        rows = self._events(facility_id, days)
        dist = {}
        for r in rows:
            dist[r[2]] = dist.get(r[2], 0) + 1
        return dict(sorted(dist.items(), key=lambda x: -x[1]))

    def severity_distribution(self, facility_id=None, days=14):
        rows = self._events(facility_id, days)
        dist = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for r in rows:
            dist[r[3]] = dist.get(r[3], 0) + 1
        total = len(rows) or 1
        return {k: round(v / total * 100, 1) for k, v in dist.items()}

    def zone_risk(self, facility_id=None, days=14):
        rows = self._events(facility_id, days)
        zones = {}
        for r in rows:
            zone = r[4] or "Unspecified"
            z = zones.setdefault(zone, {"events": 0, "critical": 0, "high": 0})
            z["events"] += 1
            if r[3] == "Critical":
                z["critical"] += 1
            elif r[3] == "High":
                z["high"] += 1
        results = [{"zone": z, **v} for z, v in zones.items()]
        return sorted(results, key=lambda z: (-z["critical"], -z["high"], -z["events"]))

    def unauthorized_access_trend(self, facility_id=None, days=14):
        rows = self._events(facility_id, days)
        daily = {}
        for r in rows:
            if r[2] in UNAUTHORIZED_TYPES:
                day = r[5][:10]
                daily[day] = daily.get(day, 0) + 1
        labels = sorted(daily.keys())
        return {"labels": labels, "counts": [daily[d] for d in labels]}

    def generate_alerts(self, facility_id=None, days=14):
        """Escalation-worthy alerts: zones with repeated high/critical events
        or an unauthorized-access spike in the recent window."""
        alerts = []
        zone_risk = self.zone_risk(facility_id, days)
        for z in zone_risk:
            if z["critical"] >= 1:
                alerts.append({
                    "priority": "Critical",
                    "title": f"Critical security event(s) in {z['zone']}",
                    "detail": f"{z['critical']} critical-severity event(s) recorded in {z['zone']} "
                              f"over the last {days} days — recommend immediate review of access logs and CCTV footage.",
                })
            elif z["events"] >= 8:
                alerts.append({
                    "priority": "High",
                    "title": f"Elevated event volume in {z['zone']}",
                    "detail": f"{z['events']} security events recorded in {z['zone']} — "
                              f"above normal baseline, consider additional patrols or access review.",
                })

        trend = self.unauthorized_access_trend(facility_id, days)
        if trend["counts"] and trend["counts"][-1] >= 3:
            alerts.append({
                "priority": "High",
                "title": "Unauthorized access spike detected",
                "detail": f"{trend['counts'][-1]} unauthorized-access-type events on {trend['labels'][-1]} — "
                          f"investigate affected badge readers and doors.",
            })

        if not alerts:
            alerts.append({
                "priority": "Low",
                "title": "No active security escalations",
                "detail": "Event volume and severity are within normal range across all monitored zones.",
            })
        return sorted(alerts, key=lambda a: SEVERITY_ORDER.get(a["priority"], 4))

    def summary(self, facility_id=None, days=14):
        rows = self._events(facility_id, days)
        total = len(rows)
        unauthorized = sum(1 for r in rows if r[2] in UNAUTHORIZED_TYPES)
        critical = sum(1 for r in rows if r[3] == "Critical")
        # active visitors is illustrative — approximated from the most
        # recent day of activity in the returned window as a proxy for
        # current building traffic (rows are newest-first)
        latest_day = rows[0][5][:10] if rows else None
        active_visitors = sum(1 for r in rows if r[5][:10] == latest_day) * 8

        return {
            "total_events": total,
            "unauthorized_access_count": unauthorized,
            "critical_events": critical,
            "active_visitors_est": active_visitors,
            "zones_flagged": len([z for z in self.zone_risk(facility_id, days) if z["critical"] or z["high"] >= 2]),
        }

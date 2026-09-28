"""
Facility Analytics & Intelligence Engine
-----------------------------------------
Responsible for (per project spec, section 4.6):
  - Aggregating insights from all agents
  - Generating facility health scores
  - Performing anomaly / risk roll-up across domains
  - Producing operational forecasts summary
  - Supporting decision-making through consolidated AI recommendations

This is the cross-agent orchestration layer for Milestone 4: it calls into
the Energy, Maintenance, Occupancy, Security and Cost agents and blends
their outputs into a single executive view instead of duplicating logic.
"""
from agents.energy_agent import EnergyAgent
from agents.maintenance_agent import MaintenanceAgent
from agents.occupancy_agent import OccupancyAgent
from agents.security_agent import SecurityAgent
from agents.cost_agent import CostOptimizationAgent


class FacilityIntelligenceEngine:
    def __init__(self, conn):
        self.conn = conn
        self.energy = EnergyAgent(conn)
        self.maintenance = MaintenanceAgent(conn)
        self.occupancy = OccupancyAgent(conn)
        self.security = SecurityAgent(conn)
        self.cost = CostOptimizationAgent(conn)

    def _facility_health_from_domains(self, energy_s, maint_s, occ_overcrowd, sec_s):
        """Weighted composite: energy efficiency, asset health, security
        posture and occupancy pressure feed a single 0-100 score."""
        energy_score = energy_s.get("efficiency_score", 80) or 80
        maint_score = maint_s.get("avg_health_score", 80) or 80
        sec_events = sec_s.get("total_events", 0) or 0
        sec_score = max(0, 100 - sec_events * 1.5)
        overcrowd_count = len(occ_overcrowd) if isinstance(occ_overcrowd, list) else 0
        occ_score = max(0, 100 - overcrowd_count * 4)

        weighted = (energy_score * 0.3) + (maint_score * 0.3) + (sec_score * 0.2) + (occ_score * 0.2)
        return round(min(100, max(0, weighted)), 0)

    def executive_summary(self, facility_id=None, days=14, cost_months=12):
        """Facility Operations Output -> Executive Dashboard KPIs, matching
        the Milestone 4 mockup: Cost Reduction, ROI Generated,
        Facility Health, Optimizations."""
        energy_s = self.energy.summary(facility_id, days)
        maint_s = self.maintenance.summary(facility_id)
        occ_over = self.occupancy.overcrowding_events(facility_id, days)
        sec_s = self.security.summary(facility_id, days)
        cost_s = self.cost.summary(None, cost_months)  # cost dataset uses its own facility space

        health = self._facility_health_from_domains(energy_s, maint_s, occ_over, sec_s)

        sec_events = sec_s.get("total_events", 0) or 0
        overcrowd_count = len(occ_over) if isinstance(occ_over, list) else 0
        security_score = round(max(0, 100 - sec_events * 1.5), 0)
        occupancy_score = round(max(0, 100 - overcrowd_count * 4), 0)

        return {
            "facility_health_score": health,
            "cost_reduction_pct": cost_s.get("cost_reduction_pct", 0),
            "roi_generated_pct": cost_s.get("roi_generated_pct", 0),
            "optimizations_identified": cost_s.get("optimizations_identified", 0),
            "potential_savings": cost_s.get("potential_savings", 0),
            "total_operational_cost": cost_s.get("total_operational_cost", 0),
            "energy_efficiency_score": energy_s.get("efficiency_score", 0),
            "avg_asset_health": maint_s.get("avg_health_score", 0),
            "predicted_failures": maint_s.get("predicted_failures", 0),
            "security_events": sec_s.get("total_events", 0),
            "overcrowding_events": overcrowd_count,
            "security_score": security_score,
            "occupancy_score": occupancy_score,
        }

    def consolidated_recommendations(self, facility_id=None, days=14, cost_months=12, limit=8):
        """Merge recommendation feeds from every agent into one prioritized
        list for cross-agent decision-making."""
        priority_rank = {"Critical": 3, "High": 2, "Medium": 1, "Low": 0}
        merged = []

        for rec in self.energy.recommendations(facility_id, days):
            merged.append({**rec, "agent": "Energy Agent"})
        for rec in self.cost.recommendations(None, cost_months):
            merged.append({**rec, "agent": "Cost Optimization Agent"})

        try:
            for rec in self.occupancy.allocation_recommendations(facility_id, days):
                merged.append({**rec, "agent": "Occupancy Agent"})
        except Exception:
            pass

        merged.sort(key=lambda r: -priority_rank.get(r.get("priority", "Low"), 0))
        return merged[:limit]

    def facility_intelligence_report(self, facility_id=None, days=14, cost_months=12):
        """Full text report — the 'Generate facility intelligence reports'
        Milestone 4 deliverable, in a plain-text format suitable for
        download/printing."""
        summary = self.executive_summary(facility_id, days, cost_months)
        recs = self.consolidated_recommendations(facility_id, days, cost_months)
        breakdown = self.cost.cost_breakdown(None, cost_months)
        ranking = self.cost.facility_ranking(cost_months, limit=5)

        lines = []
        lines.append("AGENTIC FACILITYOPS AI PLATFORM")
        lines.append("Facility Intelligence Report")
        lines.append("=" * 50)
        lines.append("")
        lines.append("EXECUTIVE SUMMARY")
        lines.append("-" * 50)
        lines.append(f"Facility Health Score : {summary['facility_health_score']}/100")
        lines.append(f"Cost Reduction        : {summary['cost_reduction_pct']}%")
        lines.append(f"ROI Generated         : {summary['roi_generated_pct']}%")
        lines.append(f"Optimizations Found   : {summary['optimizations_identified']}")
        lines.append(f"Potential Savings     : {summary['potential_savings']:,}")
        lines.append(f"Total Operational Cost: {summary['total_operational_cost']:,}")
        lines.append("")
        lines.append("COST DISTRIBUTION")
        lines.append("-" * 50)
        for label, pct in breakdown.items():
            lines.append(f"  {label:<20} {pct}%")
        lines.append("")
        lines.append("TOP FACILITIES BY SAVINGS OPPORTUNITY")
        lines.append("-" * 50)
        for r in ranking:
            lines.append(f"  {r['facility_id']} ({r['facility_type']}): "
                         f"savings {r['potential_savings']:,} | ROI {r['avg_roi_pct']}%")
        lines.append("")
        lines.append("CONSOLIDATED RECOMMENDATIONS")
        lines.append("-" * 50)
        for r in recs:
            lines.append(f"  [{r.get('priority')}] ({r.get('agent')}) {r.get('title')}")
            lines.append(f"      {r.get('detail')}")
        lines.append("")
        lines.append("=" * 50)
        lines.append("Generated by the Facility Analytics & Intelligence Engine")
        return "\n".join(lines)

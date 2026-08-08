from fastapi import APIRouter, Depends
from fastapi.responses import Response
from datetime import datetime, timezone
import csv
import io

from auth import get_current_user
from ledger import ledger

router = APIRouter(prefix="/api/user", tags=["analytics"])


@router.get("/analytics")
async def get_analytics(current_user: dict = Depends(get_current_user), period: str = "day"):
    records, _ = await ledger.get_audit_log(limit=10000, skip=0, user_email=current_user["email"])
    now = datetime.now(timezone.utc)
    buckets: dict[str, dict] = {}
    for r in records:
        ts = r.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            continue
        if period == "day":
            key = dt.strftime("%Y-%m-%d")
        elif period == "week":
            iso = dt.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        else:
            key = dt.strftime("%Y-%m")
        bucket = buckets.setdefault(key, {"queries": 0, "co2_saved_g": 0.0, "green": 0})
        bucket["queries"] += 1
        bucket["co2_saved_g"] += r.get("co2_saved_vs_baseline", 0)
        if r.get("model_tier") == "green":
            bucket["green"] += 1
    result = [{"period": k, **v} for k, v in sorted(buckets.items())]
    return {"period": period, "data": result}


@router.get("/export")
async def export_queries(current_user: dict = Depends(get_current_user), format: str = "json"):
    records, _ = await ledger.get_audit_log(limit=10000, skip=0, user_email=current_user["email"])
    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["timestamp", "query", "tier", "model_used", "model_provider", "model_tier", "carbon_score", "region", "energy_source", "co2_estimated_g", "co2_saved_vs_baseline_g", "is_mocked"])
        for r in records:
            writer.writerow([r.get("timestamp",""), r.get("query",""), r.get("tier",""), r.get("model_used",""), r.get("model_provider",""), r.get("model_tier",""), r.get("carbon_score",""), r.get("region",""), r.get("energy_source",""), r.get("co2_estimated",""), r.get("co2_saved_vs_baseline",""), r.get("is_mocked","")])
        return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=ecoquery-export.csv"})
    return {"records": records, "count": len(records)}

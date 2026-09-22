from shared.database import SessionLocal
from job_sourcing.models import CollectionRun, JobSource

db = SessionLocal()
try:
    linkedin = db.query(JobSource).filter(JobSource.name == "linkedin").first()
    runs = db.query(CollectionRun).filter(CollectionRun.source_id == linkedin.id).order_by(CollectionRun.started_at.desc()).limit(5).all()
    
    print(f"=== Collection Runs for LinkedIn ===\n")
    print(f"Total runs: {len(runs)}\n")
    
    for run in runs:
        print(f"Run ID: {run.id}")
        print(f"  Started: {run.started_at}")
        print(f"  Finished: {run.finished_at}")
        print(f"  Status: {run.status}")
        print(f"  Offers collected: {run.offers_collected}")
        print(f"  Error: {run.error_message}")
        print()
finally:
    db.close()

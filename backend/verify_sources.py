from shared.database import SessionLocal
from job_sourcing.models import JobSource

db = SessionLocal()
try:
    sources = db.query(JobSource).all()
    print(f"Total sources: {len(sources)}\n")
    for s in sources:
        print(f"{s.name} | {s.type} | {s.base_url} | {s.is_active}")
finally:
    db.close()

"""Seed test companies into the database."""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.orm import Company


def load_companies_from_fixture(fixture_path: str = "fixtures/companies.json") -> list[dict]:
    """Load companies from JSON fixture file."""
    path = Path(fixture_path)
    if not path.exists():
        # Try relative to backend directory
        path = Path(__file__).parent.parent.parent / fixture_path

    with open(path) as f:
        return json.load(f)


def seed_companies(db: Session = None) -> int:
    """
    Seed test companies into database.

    Returns the number of companies added.
    """
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        companies_data = load_companies_from_fixture()
        added = 0

        for company_data in companies_data:
            # Check if company already exists by ticker
            if company_data.get("ticker"):
                existing = db.query(Company).filter(
                    Company.ticker == company_data["ticker"]
                ).first()
                if existing:
                    continue

            # Create company
            company = Company(**company_data)
            db.add(company)
            added += 1

        db.commit()
        return added
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    count = seed_companies()
    print(f"Seeded {count} companies into database")

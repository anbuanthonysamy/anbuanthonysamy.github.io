"""Seed companies into the database from fixtures."""
import json
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.orm import Company
from app.sources.companies_house import search_company_number

log = logging.getLogger(__name__)


def load_companies_from_fixture(fixture_path: str) -> list[dict]:
    """Load companies from JSON fixture file."""
    # Try multiple possible paths
    possible_paths = [
        Path(fixture_path),
        Path(__file__).parent.parent.parent / fixture_path,
        Path("/app") / fixture_path,
        Path(__file__).parent.parent.parent.parent / fixture_path,
    ]

    for path in possible_paths:
        if path.exists():
            with open(path) as f:
                return json.load(f)

    # If none found, raise error with all attempted paths
    raise FileNotFoundError(
        f"Could not find {fixture_path} in any of: {[str(p) for p in possible_paths]}"
    )


def seed_companies(universe: str = "seed", db: Session = None) -> int:
    """
    Seed companies into database from fixture.

    Args:
        universe: "seed" (5 test companies) or "sp500_ftse100" (real market data)
        db: Database session (creates one if None)

    Returns:
        Number of companies added.
    """
    if universe == "seed":
        fixture_path = "fixtures/companies.json"
    elif universe == "sp500_ftse100":
        fixture_path = "fixtures/sp500_ftse100.json"
    else:
        raise ValueError(f"Unknown universe: {universe}")

    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False

    try:
        companies_data = load_companies_from_fixture(fixture_path)
        added = 0

        for company_data in companies_data:
            existing = None
            if company_data.get("ticker"):
                existing = db.query(Company).filter(
                    Company.ticker == company_data["ticker"]
                ).first()

            if existing:
                # Upsert: update fixture-sourced fields so fixture corrections
                # (e.g. a corrected CIK) take effect without requiring a DB drop.
                for field in ("cik", "company_number", "name", "sector", "country", "market_cap_usd"):
                    new_val = company_data.get(field)
                    if new_val is not None and getattr(existing, field, None) != new_val:
                        setattr(existing, field, new_val)
            else:
                company = Company(**company_data)
                db.add(company)
                added += 1

        db.commit()

        # Auto-resolve Companies House numbers for UK companies that don't
        # have one yet. Fixtures carry only the name; the number is looked up
        # via the CH Search API (requires COMPANIES_HOUSE_API_KEY) and cached
        # onto the Company row so subsequent scans skip the lookup.
        resolved = 0
        uk_missing = db.query(Company).filter(
            Company.country == "UK", Company.company_number.is_(None)
        ).all()
        for company in uk_missing:
            number = search_company_number(company.name)
            if number:
                company.company_number = number
                resolved += 1
                log.info("Resolved Companies House number for %s: %s",
                         company.name, number)
            else:
                log.warning("No Companies House match for %s", company.name)
        if resolved:
            db.commit()

        return added
    finally:
        if should_close:
            db.close()


def seed_sp500_ftse100(db: Session = None) -> int:
    """Convenience function to seed S&P 500 + FTSE 100 companies."""
    return seed_companies(universe="sp500_ftse100", db=db)


if __name__ == "__main__":
    # Default to S&P 500/FTSE 100 for live data
    count = seed_sp500_ftse100()
    print(f"Seeded {count} S&P 500 + FTSE 100 companies into database")

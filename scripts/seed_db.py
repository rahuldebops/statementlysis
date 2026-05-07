import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.session import SyncSessionLocal
from app.db.models import Bank, ParserVersion
from app.extraction.bank_detector import BANK_NAMES, BANK_PATTERNS
from app.parsers.base import ParserConfig
from dataclasses import asdict

def seed():
    session = SyncSessionLocal()
    try:
        print("Seeding banks...")
        for bank_id, name in BANK_NAMES.items():
            # Check if bank exists
            existing = session.get(Bank, bank_id)
            if not existing:
                patterns = BANK_PATTERNS.get(bank_id, [])
                bank = Bank(
                    id=bank_id,
                    name=name,
                    display_name=name,
                    detection_patterns={"patterns": patterns}
                )
                session.add(bank)
                print(f"  Added bank: {bank_id}")
            else:
                print(f"  Bank already exists: {bank_id}")
        
        session.commit()

        print("Seeding parser versions...")
        parsers_dir = Path("app/parsers")
        supported_parsers = ["generic", "hdfc", "sbi", "icici"]
        
        for p_name in supported_parsers:
            config_path = parsers_dir / p_name / "config.json"
            if config_path.exists():
                config = ParserConfig.from_file(config_path)
                
                # For generic, bank_id is None in some contexts, but let's use a placeholder or skip if needed
                # Actually, the DB model says bank_id is NOT NULL in parser_versions
                # So we might need a "generic" bank or similar.
                
                b_id = p_name
                if p_name == "generic":
                    # Check if 'generic' bank exists
                    if not session.get(Bank, "generic"):
                        generic_bank = Bank(id="generic", name="Generic", display_name="Generic Parser")
                        session.add(generic_bank)
                        session.commit()
                
                # Check if parser version exists
                from sqlalchemy import select
                stmt = select(ParserVersion).where(
                    ParserVersion.bank_id == b_id,
                    ParserVersion.version == config.version
                )
                existing_pv = session.execute(stmt).scalar_one_or_none()
                
                if not existing_pv:
                    pv = ParserVersion(
                        bank_id=b_id,
                        version=config.version,
                        parser_class=f"app.parsers.{p_name}.parser.{p_name.upper()}Parser",
                        config=asdict(config),
                        is_active=True
                    )
                    session.add(pv)
                    print(f"  Added parser version: {b_id} v{config.version}")
                else:
                    print(f"  Parser version already exists: {b_id} v{config.version}")
        
        session.commit()
        print("Seeding complete.")

    except Exception as e:
        session.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    seed()

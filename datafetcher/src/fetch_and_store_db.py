#!/usr/bin/env python3
"""
Fetch data from Labcom and store in enhanced SQLite database.
Alternate version: Fetches credentials directly from database (accubase.sqlite).
"""
import sys
import os
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure we can import local modules even if run from outside src
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from labcom_client import LabcomClient
    from data_manager import DataManager
    from db_schema import Vessel # Import Vessel model
except ImportError as e:
    print(f"CRITICAL ERROR: Failed to import modules: {e}")
    print(f"PYTHONPATH: {sys.path}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("FetchStoreDB")

def get_vessel_credentials_from_db(vessel_id: str, db_path: str) -> Dict[str, str]:
    """
    Retrieve vessel credentials from the database.
    
    Args:
        vessel_id: The string ID of the vessel (e.g. 'mv_racer')
        db_path: Path to sqlite database
        
    Returns:
        Dictionary with vessel credentials (auth_token, name, etc)
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found at: {db_path}")

    engine = create_engine(f'sqlite:///{db_path}')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        vessel = session.query(Vessel).filter_by(vessel_id=vessel_id).first()
        
        if not vessel:
            raise ValueError(f"Vessel '{vessel_id}' not found in database.")
            
        if not vessel.auth_token:
            raise ValueError(f"No auth token found for vessel '{vessel_id}'.")
            
        return {
            'vessel_id': vessel.vessel_id,
            'vessel_name': vessel.vessel_name,
            'email': vessel.email,
            'auth_token': vessel.auth_token
        }
    finally:
        session.close()

def fetch_and_store_vessel_data_db(
    vessel_id: str, 
    days_back: int, 
    db_path: str
) -> Dict[str, Any]:
    """
    Fetch data for a vessel and store in the database using DB credentials.

    Args:
        vessel_id: The ID of the vessel to fetch.
        days_back: Number of days of history to fetch.
        db_path: Absolute path to the SQLite database.
    """
    logger.info(f"{'='*60}")
    logger.info(f"Starting fetch for vessel: {vessel_id}")
    logger.info(f"History: {days_back} days")
    logger.info(f"Database: {db_path}")
    logger.info("Source: Database Credentials")
    logger.info(f"{'='*60}")

    # 1. Load Credentials from DB
    try:
        vessel_config = get_vessel_credentials_from_db(vessel_id, db_path)
        logger.info(f"Loaded credentials for: {vessel_config['vessel_name']}")
    except Exception as e:
        logger.error(f"Failed to load credentials from DB: {e}")
        raise

    # 2. Initialize Components
    try:
        client = LabcomClient(vessel_config['auth_token'])
        # Initialize DataManager with the explicit database path
        dm = DataManager(db_path=db_path)
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise

    # 3. Connect to Labcom
    logger.info("Connecting to Labcom API...")
    try:
        cloud_account = client.get_cloud_account()
        if not cloud_account:
             raise Exception("Failed to retrieve cloud account information.")
        logger.info(f"Connected as: {cloud_account.get('name')} ({cloud_account.get('email')})")
    except Exception as e:
        logger.error(f"API Connection failed: {e}")
        raise

    # 4. Update Vessel in DB (Idempotent update)
    try:
        vessel_db_id = dm.add_or_update_vessel(
            vessel_id=vessel_config['vessel_id'],
            vessel_name=vessel_config['vessel_name'],
            email=vessel_config['email'],
            auth_token=vessel_config['auth_token'],
            labcom_account_id=cloud_account.get('id')
        )
        logger.info(f"Vessel updated/verified in DB with ID: {vessel_db_id}")
    except Exception as e:
        logger.error(f"Database error updating vessel: {e}")
        raise

    # 5. Sync Sampling Points
    logger.info("Syncing sampling points...")
    try:
        accounts = client.get_accounts()
        logger.info(f"Found {len(accounts)} sampling points in Labcom")

        for account in accounts:
            dm.add_sampling_point(
                vessel_id=vessel_db_id,
                code=f"LAB{account['id']}",
                name=account.get('name', 'Unknown'),
                labcom_account_id=account['id']
            )
    except Exception as e:
        logger.error(f"Failed to sync sampling points: {e}")
        raise

    # 6. Fetch Measurements
    logger.info(f"Fetching measurements for last {days_back} days...")
    try:
        from_date = datetime.now() - timedelta(days=days_back)
        to_date = datetime.now()

        measurements = client.get_all_measurements_for_vessel(
            from_date=from_date,
            to_date=to_date
        )
        logger.info(f"Fetched {len(measurements)} measurements from Labcom")
    except Exception as e:
        logger.error(f"Failed to fetch measurements from API: {e}")
        raise

    # 7. Store Measurements
    logger.info("Storing measurements in database...")
    try:
        stats = dm.store_measurements(
            vessel_id=vessel_db_id,
            measurements=measurements
        )

        logger.info(f"Stored: {stats['new']} new, {stats['duplicate']} duplicates")
        if stats['alerts'] > 0:
            logger.warning(f"ALERTS GENERATED: {stats['alerts']}")
    except Exception as e:
        logger.error(f"Failed to store measurements in DB: {e}")
        raise

    # 8. Create Fetch Log
    try:
        dm.create_fetch_log(
            vessel_id=vessel_db_id,
            status='success',
            measurements_fetched=len(measurements),
            measurements_new=stats['new'],
            measurements_duplicate=stats['duplicate'],
            date_range_from=from_date,
            date_range_to=to_date
        )
        logger.info("Fetch log created.")
    except Exception as e:
        logger.error(f"Failed to create fetch log: {e}")

    return stats

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    default_db = os.path.join(project_root, 'data', 'accubase.sqlite')

    parser = argparse.ArgumentParser(
        description="Fetch Labcom data using credentials from Accuport DB",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("vessel_id", help="The ID of the vessel to fetch (e.g., mt_aqua)")
    parser.add_argument("days", type=int, nargs='?', default=30, help="Days of history to fetch")
    parser.add_argument("--db", default=default_db, help="Path to sqlite database")
    
    args = parser.parse_args()

    try:
        fetch_and_store_vessel_data_db(
            vessel_id=args.vessel_id,
            days_back=args.days,
            db_path=args.db
        )
        logger.info("✓ SUCCESS: Data fetch and storage completed!")
    except Exception:
        logger.error("FAILURE: Operation failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()

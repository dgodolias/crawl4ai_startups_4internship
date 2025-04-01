import csv
import asyncio
from models.venue import Startup

def is_duplicate_startup(startup_name: str, seen_names: set) -> bool:
    """
    Check if a startup name has already been seen.
    Args:
        startup_name (str): The name of the startup to check.
        seen_names (set): Set of startup names that have already been seen.
    Returns:
        bool: True if the startup name has already been seen, False otherwise.
    """
    return startup_name in seen_names

def is_complete_startup(startup: dict, required_keys: list) -> bool:
    """
    Check if a startup object contains all required keys.
    Args:
        startup (dict): The startup object to check.
        required_keys (list): List of required keys in the startup object.
    Returns:
        bool: True if the startup object contains all required keys, False otherwise.
    """
    return all(key in startup and startup[key] for key in required_keys)

def save_startups_to_csv(startups: list, filename: str):
    """
    Save a list of startups to a CSV file.
    Args:
        startups (list): List of startup objects to save.
        filename (str): Name of the file to save to.
    """
    if not startups:
        print("No startups to save.")
        return

    # Use field names from the Startup model
    fieldnames = Startup.model_fields.keys()
    
    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(startups)
    
    print(f"Saved {len(startups)} startups to '{filename}'.")

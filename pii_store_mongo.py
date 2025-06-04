from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()  # Load variables from .env file

mongo_uri = os.getenv("MONGO_URI")
client = MongoClient(mongo_uri)
db = client["ats_system"]
pii_collection = db["pii_mappings"]

def store_mapping_with_id(collection_id, masked_value, original_value):
    """Store PII mapping in MongoDB."""
    pii_collection.insert_one({
        "collection_id": collection_id,
        "masked_value": masked_value,
        "original_value": original_value
    })

def does_collection_id_exist(collection_id):
    """Check if collection ID exists in MongoDB."""
    return pii_collection.find_one({"collection_id": collection_id}) is not None

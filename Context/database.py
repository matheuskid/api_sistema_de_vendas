from motor.motor_asyncio import AsyncIOMotorClient
from odmantic import AIOEngine
from dotenv import dotenv_values

config = dotenv_values(".env")

client = AsyncIOMotorClient(config["ATLAS_URI"])

engine = AIOEngine(client=client, database=config["DB_NAME"])

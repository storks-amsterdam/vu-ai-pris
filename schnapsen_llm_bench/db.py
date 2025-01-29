# Note: the module name is psycopg, not psycopg3
import psycopg
import os
from azure.cosmos import CosmosClient
from dotenv import load_dotenv

load_dotenv()

URL = os.environ['ACCOUNT_URI']
KEY = os.environ['ACCOUNT_KEY']


PGHOST = os.environ["PGHOST"]
PGUSER = os.environ["PGUSER"]
PGPORT = os.environ["PGPORT"]
PGDATABASE = os.environ["PGDATABASE"]
PGPASSWORD = os.environ["PGPASSWORD"]


def get_pg_connection() -> psycopg.connection:
    return psycopg.connect(host=PGHOST, user=PGUSER, port=PGPORT, dbname=PGDATABASE, password=PGPASSWORD)


def get_cosmos_client() -> CosmosClient:
    return CosmosClient(URL, credential=KEY)




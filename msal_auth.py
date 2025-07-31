import os
from msal import ConfidentialClientApplication, SerializableTokenCache
from sqlalchemy import create_engine, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class TokenCacheDB(Base):
    __tablename__ = 'token_cache'
    account_id = Column(String, primary_key=True)
    cache = Column(String)

db_path = os.getenv("TOKEN_DB_PATH", "sqlite:///token_cache.db")
engine = create_engine(db_path, connect_args={"check_same_thread": False})
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

def build_msal_app(cache=None):
    return ConfidentialClientApplication(
        os.getenv("CLIENT_ID"),
        authority=os.getenv("AUTHORITY"),
        client_credential=os.getenv("CLIENT_SECRET"),
        token_cache=cache
    )

def load_token_cache(account_id):
    db = SessionLocal()
    record = db.query(TokenCacheDB).filter_by(account_id=account_id).first()
    cache = SerializableTokenCache()
    if record and record.cache:
        cache.deserialize(record.cache)
    db.close()
    return cache

def save_token_cache(account_id, cache):
    if not isinstance(cache, SerializableTokenCache):
        return  # Skip saving if the cache is not serializable
    if not cache.has_state_changed:
        return
    db = SessionLocal()
    record = db.query(TokenCacheDB).filter_by(account_id=account_id).first()
    serialized = cache.serialize()
    if record:
        record.cache = serialized
    else:
        record = TokenCacheDB(account_id=account_id, cache=serialized)
        db.add(record)
    db.commit()
    db.close()

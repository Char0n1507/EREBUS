from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.sql import func
import logging

try:
    from ..config import DB_URL
except ImportError:
    DB_URL = "sqlite:///argus.db"

Base = declarative_base()

class Investigation(Base):
    __tablename__ = 'investigations'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    query = Column(String)
    status = Column(String, default="active") # active, closed
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    results = relationship("SearchResult", back_populates="investigation")

class SearchResult(Base):
    __tablename__ = 'search_results'
    
    id = Column(Integer, primary_key=True)
    investigation_id = Column(Integer, ForeignKey('investigations.id'))
    url = Column(String, nullable=False)
    title = Column(String)
    snippet = Column(Text)
    engine = Column(String)
    content = Column(Text) # Full HTML content (optional, can be large)
    processed = Column(Boolean, default=False) # If LLM/Analyzer has processed it
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    investigation = relationship("Investigation", back_populates="results")
    artifacts = relationship("Artifact", back_populates="result")

class Artifact(Base):
    __tablename__ = 'artifacts'
    
    id = Column(Integer, primary_key=True)
    result_id = Column(Integer, ForeignKey('search_results.id'))
    type = Column(String) # email, crypto, ssn, person, etc.
    value = Column(String)
    context = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    result = relationship("SearchResult", back_populates="artifacts")

class StorageManager:
    def __init__(self, db_url=DB_URL):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
    def create_investigation(self, name, query):
        session = self.Session()
        inv = Investigation(name=name, query=query)
        session.add(inv)
        session.commit()
        inv_id = inv.id
        session.close()
        return inv_id

    def add_result(self, investigation_id, result_data):
        session = self.Session()
        # Check if URL exists for this investigation? 
        # For now, just add.
        res = SearchResult(
            investigation_id=investigation_id,
            url=result_data.get('link'),
            title=result_data.get('title'),
            snippet=result_data.get('snippet', ''),
            engine=result_data.get('engine', 'unknown'),
            content=result_data.get('content', '')
        )
        session.add(res)
        session.commit()
        res_id = res.id
        session.close()
        return res_id

    def add_artifact(self, result_id, artifact_type, value, context=""):
        session = self.Session()
        art = Artifact(
            result_id=result_id,
            type=artifact_type,
            value=value,
            context=context
        )
        session.add(art)
        session.commit()
        session.close()

    def get_investigation(self, inv_id):
        session = self.Session()
        inv = session.query(Investigation).filter(Investigation.id == inv_id).first()
        session.close()
        return inv

    def get_unprocessed_results(self, limit=10):
        session = self.Session()
        results = session.query(SearchResult).filter(SearchResult.processed == False).limit(limit).all()
        session.close()
        return results

    def mark_processed(self, result_id):
        session = self.Session()
        res = session.query(SearchResult).filter(SearchResult.id == result_id).first()
        if res:
            res.processed = True
            session.commit()
        session.close()

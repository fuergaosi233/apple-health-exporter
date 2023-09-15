import os

import dotenv

dotenv.load_dotenv()
import uuid
from typing import List, Optional

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import JSON, UUID, Column, DateTime, String, create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import declarative_base, sessionmaker

import db  # type: ignore for timescale hook

app = FastAPI()
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "timescaledb://postgres:postgres@localhost:5432/postgres"
)
DATABASE_URL = DATABASE_URL.replace("postgresql://", "timescaledb://")

engine = create_engine(DATABASE_URL)
Base = declarative_base()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class MetricTable(Base):
    __tablename__ = "metrics"
    id = Column(UUID, default=uuid.uuid4, primary_key=True)
    name = Column(String)
    data = Column(JSON)
    timestamp = Column(DateTime())
    # Add index
    __table_args__ = {
        "timescaledb_hypertable": {
            "time_column_name": "timestamp",
            "partitioning_column": "name",
            "number_partitions": 10,
        }
    }


# AUto migrate
Base.metadata.create_all(engine)


class Datum(BaseModel):
    date: str
    source: Optional[str] = None
    qty: Optional[float] = None
    avg: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    deep: Optional[float] = None
    core: Optional[float] = None
    awake: Optional[float] = None
    asleep: Optional[float] = None
    sleep_end: Optional[str] = None
    in_bed_start: Optional[str] = None
    in_bed_end: Optional[str] = None
    sleep_start: Optional[str] = None
    rem: Optional[float] = None
    in_bed: Optional[float] = None


class Metric(BaseModel):
    units: str
    data: List[Datum]
    name: str


class Data(BaseModel):
    metrics: List[Metric]


class RequestData(BaseModel):
    data: Data


@app.post("/upload")
def upload_data(request_data: RequestData):
    ps = []
    for metric in request_data.data.metrics:
        for datum in metric.data:
            data = datum.model_dump()
            date = data.pop("date", None)
            ps.append(dict(name=metric.name, data=data, timestamp=date))
    with SessionLocal() as session:
        insert_ps = (
            insert(MetricTable)
            .values(ps)
            .on_conflict_do_nothing(index_elements=["name", "timestamp"])
        )
        session.execute(insert_ps)
        session.commit()
    return {"status": "Data uploaded successfully!"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

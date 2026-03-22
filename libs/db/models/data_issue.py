"""DataIssue — data quality alert records."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class DataIssue(Base):
    __tablename__ = "data_issue"

    issue_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=text("now()"))
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(50), nullable=False)
    table_name: Mapped[str] = mapped_column(String(50), nullable=False)
    record_key: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB)
    resolved_flag: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

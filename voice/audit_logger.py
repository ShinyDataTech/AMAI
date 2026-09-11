"""Immutable SQLite and JSON QA audit trail for micro-assembly inspection and operator overrides."""

from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class AuditRecord:
    event_id: str
    timestamp: str
    unit_id: str
    defect_type: str
    confidence: float
    inspection_result: str          # "PASS" | "REJECT_SCRAP" | "REWORK"
    operator_action: str            # "AUTONOMOUS" | "VOICE_OVERRIDE_PASS" | "VOICE_OVERRIDE_SCRAP" | "EMERGENCY_STOP"
    target_bin: str                 # "BIN_A_SCRAP" | "BIN_B_PASS" | "HOLD"
    defect_x: Optional[float] = None
    defect_y: Optional[float] = None
    defect_z: Optional[float] = None
    voice_transcript: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AuditLogger:
    """Manages immutable audit records with SQLite storage and JSON export."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, "data")
            os.makedirs(data_dir, exist_ok=True)
            self.db_path = os.path.join(data_dir, "audit_log.db")
        else:
            self.db_path = db_path
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_trail (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    defect_type TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    inspection_result TEXT NOT NULL,
                    operator_action TEXT NOT NULL,
                    target_bin TEXT NOT NULL,
                    defect_x REAL,
                    defect_y REAL,
                    defect_z REAL,
                    voice_transcript TEXT,
                    notes TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_trail (timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_unit ON audit_trail (unit_id)")

    def log(
        self,
        unit_id: str,
        defect_type: str,
        confidence: float,
        inspection_result: str,
        operator_action: str = "AUTONOMOUS",
        target_bin: str = "BIN_B_PASS",
        coords_3d: Optional[Tuple[float, float, float]] = None,
        voice_transcript: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> AuditRecord:
        """Appends an immutable audit event."""
        event_id = str(uuid.uuid4())
        ts = datetime.now(timezone.utc).isoformat()
        dx, dy, dz = coords_3d if coords_3d else (None, None, None)

        record = AuditRecord(
            event_id=event_id,
            timestamp=ts,
            unit_id=unit_id,
            defect_type=defect_type,
            confidence=float(confidence),
            inspection_result=inspection_result,
            operator_action=operator_action,
            target_bin=target_bin,
            defect_x=dx,
            defect_y=dy,
            defect_z=dz,
            voice_transcript=voice_transcript,
            notes=notes,
        )

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_trail (
                    event_id, timestamp, unit_id, defect_type, confidence,
                    inspection_result, operator_action, target_bin,
                    defect_x, defect_y, defect_z, voice_transcript, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.event_id, record.timestamp, record.unit_id,
                    record.defect_type, record.confidence, record.inspection_result,
                    record.operator_action, record.target_bin,
                    record.defect_x, record.defect_y, record.defect_z,
                    record.voice_transcript, record.notes,
                ),
            )
        return record

    def get_recent(self, limit: int = 50) -> List[AuditRecord]:
        """Retrieves the most recent audit records in descending chronological order."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM audit_trail ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            return [AuditRecord(**dict(row)) for row in rows]

    def get_metrics(self) -> Dict[str, Any]:
        """Calculates production yield, rejection rate, and operator intervention rate."""
        with self._get_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM audit_trail").fetchone()[0]
            passed = conn.execute("SELECT COUNT(*) FROM audit_trail WHERE inspection_result = 'PASS'").fetchone()[0]
            rejected = conn.execute("SELECT COUNT(*) FROM audit_trail WHERE inspection_result != 'PASS'").fetchone()[0]
            overrides = conn.execute("SELECT COUNT(*) FROM audit_trail WHERE operator_action != 'AUTONOMOUS'").fetchone()[0]

            yield_rate = (float(passed) / float(total) * 100.0) if total > 0 else 100.0

            # Defect breakdown
            cursor = conn.execute(
                "SELECT defect_type, COUNT(*) as cnt FROM audit_trail GROUP BY defect_type"
            )
            breakdown = {row["defect_type"]: row["cnt"] for row in cursor.fetchall()}

        return {
            "total_inspected": total,
            "passed": passed,
            "rejected": rejected,
            "overrides": overrides,
            "yield_rate_percent": round(yield_rate, 2),
            "defect_breakdown": breakdown,
        }

    def export_json(self, output_path: str) -> str:
        """Exports all audit events to a JSON file."""
        records = [r.to_dict() for r in self.get_recent(limit=10000)]
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)
        return output_path

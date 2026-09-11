"""Speechmatics streaming voice client and industrial QA intent recognition agent."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import os
import re
from typing import Callable, Dict, List, Optional


class VoiceIntent(str, Enum):
    OVERRIDE_PASS = "OVERRIDE_PASS"
    OVERRIDE_SCRAP = "OVERRIDE_SCRAP"
    FLAG_DEFECT = "FLAG_DEFECT"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    RESUME = "RESUME"
    QUERY_STATUS = "QUERY_STATUS"
    UNKNOWN = "UNKNOWN"


@dataclass
class VoiceCommand:
    intent: VoiceIntent
    raw_transcript: str
    confidence: float
    target_bin: Optional[str]
    action_description: str


class VoiceAgent:
    """Industrial voice interface powered by Speechmatics with zero-key simulated fallback."""

    INTENT_PATTERNS = [
        (
            VoiceIntent.EMERGENCY_STOP,
            r"(emergency stop|stop line|halt robot|kill motion|freeze|pause line)",
            None,
            "Immediate emergency halt triggered. Arm motion locked.",
        ),
        (
            VoiceIntent.RESUME,
            r"(resume line|continue|restart line|resume operation|unpause)",
            None,
            "Safety interlock cleared. Line resumed.",
        ),
        (
            VoiceIntent.OVERRIDE_PASS,
            r"(override.*pass|override reject|force pass|approve|pass.*(board|unit|part)|ignore defect|mark as pass|accept board)",
            "BIN_B_PASS",
            "Operator manual override: Routing unit to Bin B (Pass).",
        ),
        (
            VoiceIntent.OVERRIDE_SCRAP,
            r"(override.*scrap|override pass|force scrap|reject|scrap.*(board|unit|part)|fail board|mark as scrap|send to rework)",
            "BIN_A_SCRAP",
            "Operator manual override: Routing unit to Bin A (Scrap/Rework).",
        ),
        (
            VoiceIntent.FLAG_DEFECT,
            r"(flag.*(defect|bridge|fault|issue)|log issue|alert engineering|repeated fault|recurring defect)",
            None,
            "Engineering alert flagged. Quality telemetry notification generated.",
        ),
        (
            VoiceIntent.QUERY_STATUS,
            r"(status|yield rate|how many passed|metrics|show yield|inspection report)",
            None,
            "Quality metrics queried.",
        ),
    ]

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SPEECHMATICS_API_KEY")
        self.is_mock_mode = not bool(self.api_key)
        self.last_command: Optional[VoiceCommand] = None

    def parse_intent(self, transcript: str, confidence: float = 0.96) -> VoiceCommand:
        """Parses natural language speech transcript into formal industrial automation intents."""
        cleaned = transcript.strip().lower()

        for intent, pattern, target_bin, desc in self.INTENT_PATTERNS:
            if re.search(pattern, cleaned):
                cmd = VoiceCommand(
                    intent=intent,
                    raw_transcript=transcript,
                    confidence=confidence,
                    target_bin=target_bin,
                    action_description=desc,
                )
                self.last_command = cmd
                return cmd

        cmd = VoiceCommand(
            intent=VoiceIntent.UNKNOWN,
            raw_transcript=transcript,
            confidence=0.50,
            target_bin=None,
            action_description="Command not recognized. Maintaining autonomous protocol.",
        )
        self.last_command = cmd
        return cmd

    def simulate_speech_command(self, sample_text: str) -> VoiceCommand:
        """Simulates real-time Speechmatics transcription stream from spoken audio."""
        return self.parse_intent(sample_text, confidence=0.98)

    def get_quick_commands(self) -> List[Dict[str, str]]:
        """Returns preset speech trigger phrases for operator dashboard testing."""
        return [
            {"label": "Pass Override", "text": "Override reject, pass unit to assembly"},
            {"label": "Scrap Override", "text": "Override pass, scrap unit to rework bin"},
            {"label": "Flag Recurring Fault", "text": "Flag recurring solder bridge defect for engineering"},
            {"label": "E-Stop Line", "text": "Emergency stop, freeze all arm motion"},
            {"label": "Resume Line", "text": "Resume line operation and continue cycle"},
            {"label": "Query Yield", "text": "Show current yield rate and line status"},
        ]

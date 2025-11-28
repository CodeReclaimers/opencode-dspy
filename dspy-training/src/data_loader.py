"""
Load and validate OpenCode session logs from JSON files.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
import logging

logger = logging.getLogger(__name__)


class ActionModel(BaseModel):
    """Represents a single tool call action"""
    step: int
    tool: str
    args: Dict[str, Any]
    timestamp: str
    result: Optional[Any] = None
    success: Optional[bool] = None


class OutcomeModel(BaseModel):
    """Represents the outcome of a session"""
    success: bool
    taskCompleted: bool
    metrics: Dict[str, Any]
    evaluation: Optional[Dict[str, float]] = None


class SessionExample(BaseModel):
    """Represents a single training example from OpenCode"""
    input: Dict[str, Any]
    actions: List[ActionModel]
    output: Dict[str, str]
    outcome: OutcomeModel
    agent: Dict[str, Any]
    metadata: Dict[str, Any]
    
    @field_validator('actions')
    @classmethod
    def validate_actions(cls, v):
        if not v:
            logger.warning("Example has no actions")
        return v


class SessionLog(BaseModel):
    """Complete session log file"""
    session: str
    generated: str
    totalExamples: int
    totalTurns: Optional[int] = None
    successfulTurns: Optional[int] = None
    overallSuccess: Optional[bool] = None
    totalToolCalls: Optional[int] = None
    outcome: Optional[OutcomeModel] = None  # Made optional, not present in all exports
    examples: List[SessionExample]


class DataLoader:
    """Loads and validates OpenCode session logs"""
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            logger.warning(f"Data directory does not exist: {self.data_dir}")
            self.data_dir.mkdir(parents=True, exist_ok=True)
        
    def load_all_sessions(self) -> List[SessionLog]:
        """Load all JSON session logs from directory"""
        json_files = list(self.data_dir.glob("*.json"))
        logger.info(f"Found {len(json_files)} JSON files in {self.data_dir}")
        
        if not json_files:
            logger.warning(f"No JSON files found in {self.data_dir}")
            return []
        
        sessions = []
        for json_file in json_files:
            try:
                session = self.load_session(json_file)
                sessions.append(session)
            except Exception as e:
                logger.error(f"Failed to load {json_file}: {e}")
                
        logger.info(f"Successfully loaded {len(sessions)} sessions")
        return sessions
    
    def load_session(self, filepath: Path) -> SessionLog:
        """Load and validate a single session log"""
        with open(filepath, 'r') as f:
            data = json.load(f)
            return SessionLog(**data)
    
    def filter_successful(self, sessions: List[SessionLog]) -> List[SessionLog]:
        """Filter to only successful sessions"""
        successful = [
            s for s in sessions 
            if s.overallSuccess or (s.outcome and s.outcome.success and s.outcome.taskCompleted)
        ]
        logger.info(f"Filtered to {len(successful)} successful sessions out of {len(sessions)} total")
        return successful
    
    def extract_examples(self, sessions: List[SessionLog]) -> List[SessionExample]:
        """Extract all examples from session logs"""
        examples = []
        for session in sessions:
            examples.extend(session.examples)
        
        logger.info(f"Extracted {len(examples)} total examples from {len(sessions)} sessions")
        return examples

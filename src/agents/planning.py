from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import uuid
from datetime import datetime

class PlanStatus(Enum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class StepStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class AgentGoal:
    """Simple agent goal"""
    description: str
    success_criteria: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> Dict[str, Any]:
        """Simple validation"""
        valid = len(self.description) > 0
        return {"valid": valid}

@dataclass
class PlanStep:
    """Single workflow step"""
    tool_name: str
    server_name: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List['PlanStep'] = field(default_factory=list)
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    result: Dict[str, Any] = field(default_factory=dict)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def can_execute(self) -> bool:
        """Check if step can run"""
        return all(dep.status == StepStatus.COMPLETED for dep in self.dependencies)
    
    def mark_ready(self):
        """Mark as ready"""
        if self.can_execute():
            self.status = StepStatus.READY
    
    def start_execution(self):
        """Start step"""
        self.status = StepStatus.RUNNING
        self.start_time = datetime.now()
    
    def mark_completed(self, result: Dict[str, Any] = None):
        """Mark as completed"""
        self.status = StepStatus.COMPLETED
        self.end_time = datetime.now()
        if result:
            self.result = result
    
    def mark_failed(self, error: str):
        """Mark as failed"""
        self.status = StepStatus.FAILED
        self.end_time = datetime.now()
        self.result = {"error": error}

@dataclass
class WorkflowPlan:
    """Simple workflow plan"""
    goal: AgentGoal
    steps: List[PlanStep] = field(default_factory=list)
    status: PlanStatus = PlanStatus.CREATED
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def add_step(self, step: PlanStep):
        """Add step to plan"""
        self.steps.append(step)
        self._update_step_readiness()
    
    def get_ready_steps(self) -> List[PlanStep]:
        """Get steps ready to execute"""
        return [step for step in self.steps if step.status == StepStatus.READY]
    
    def get_running_steps(self) -> List[PlanStep]:
        """Get running steps"""
        return [step for step in self.steps if step.status == StepStatus.RUNNING]
    
    def get_completed_steps(self) -> List[PlanStep]:
        """Get completed steps"""
        return [step for step in self.steps if step.status == StepStatus.COMPLETED]
    
    def get_failed_steps(self) -> List[PlanStep]:
        """Get failed steps"""
        return [step for step in self.steps if step.status == StepStatus.FAILED]
    
    def _update_step_readiness(self):
        """Update which steps are ready"""
        for step in self.steps:
            if step.status == StepStatus.PENDING and step.can_execute():
                step.mark_ready()
    
    def validate_plan(self) -> Dict[str, Any]:
        """Simple plan validation"""
        issues = []
        
        goal_validation = self.goal.validate()
        if not goal_validation["valid"]:
            issues.append("Invalid goal")
        
        if not self.steps:
            issues.append("No steps defined")
        
        return {"valid": len(issues) == 0, "issues": issues}
    
    def start_execution(self):
        """Start plan execution"""
        if self.status == PlanStatus.CREATED:
            self.validate_plan()
        
        self.status = PlanStatus.IN_PROGRESS
        self.start_time = datetime.now()
        self._update_step_readiness()
    
    def check_completion(self) -> bool:
        """Check if plan is complete"""
        if self.status != PlanStatus.IN_PROGRESS:
            return False
        
        all_completed = all(step.status == StepStatus.COMPLETED for step in self.steps)
        has_failed = any(step.status == StepStatus.FAILED for step in self.steps)
        
        if all_completed:
            self.status = PlanStatus.COMPLETED
            self.end_time = datetime.now()
            return True
        elif has_failed:
            self.status = PlanStatus.FAILED
            self.end_time = datetime.now()
            return True
        
        return False
    

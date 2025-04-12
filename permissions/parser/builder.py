"""Statement builder component for creating structured permission statements."""

from typing import Dict, Any

from ..base import StatementBuilderInterface
from ..models import (
    PermissionStatement,
    Condition,
    LogicalOperator
)

class SimpleStatementBuilder(StatementBuilderInterface):
    """Simple implementation of the StatementBuilderInterface."""
    
    def build(self, interpreted_data: Dict[str, Any]) -> PermissionStatement:
        """
        Build a structured permission statement from interpreted data.
        
        Args:
            interpreted_data: The interpreted data from the Interpreter
            
        Returns:
            PermissionStatement: The built permission statement
        """
        # Validate required fields
        if not interpreted_data.get("command"):
            raise ValueError("Missing command in interpreted data")
        
        if not interpreted_data.get("access_types"):
            raise ValueError("Missing access types in interpreted data")
        
        if not interpreted_data.get("resource_type"):
            raise ValueError("Missing resource type in interpreted data")
        
        # Convert conditions to Condition objects
        conditions = []
        for condition_data in interpreted_data.get("conditions", []):
            conditions.append(
                Condition(
                    field=condition_data["field"],
                    operator=condition_data["operator"],
                    value=condition_data["value"],
                    field_type=condition_data.get("field_type")
                )
            )
        
        # Create and return the PermissionStatement
        return PermissionStatement(
            command=interpreted_data["command"],
            access_type=interpreted_data["access_types"],
            resource_type=interpreted_data["resource_type"],
            conditions=conditions,
            logical_operator=interpreted_data.get("logical_operator", LogicalOperator.AND)
        ) 
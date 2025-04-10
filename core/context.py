from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import uuid

class ModuleResult(BaseModel):
    """Result of module processing."""
    success: bool = True
    data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @classmethod
    def success_result(cls, data: Optional[Dict[str, Any]] = None, metadata: Optional[Dict[str, Any]] = None) -> "ModuleResult":
        """Create a successful result."""
        return cls(
            success=True,
            data=data or {},
            metadata=metadata or {}
        )
    
    @classmethod
    def error_result(cls, error: str, metadata: Optional[Dict[str, Any]] = None) -> "ModuleResult":
        """Create an error result."""
        return cls(
            success=False,
            error=error,
            metadata=metadata or {}
        )

class ModuleContext(BaseModel):
    """Context passed between modules during processing."""
    request: Dict[str, Any] = Field(default_factory=dict)  # Original request data
    data: Dict[str, Any] = Field(default_factory=dict)     # Module-specific data
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Additional metadata
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    runtime_type: str = "generic"
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the context data."""
        return self.data.get(key, default)
    
    def with_data(self, **kwargs) -> "ModuleContext":
        """Create a new context with updated data."""
        new_data = self.data.copy()
        new_data.update(kwargs)
        return self.model_copy(update={"data": new_data})
    
    def with_result(self, result: ModuleResult) -> "ModuleContext":
        """Create a new context with data from a module result.
        
        Args:
            result: The module result to apply
            
        Returns:
            A new context with the result data applied
            
        Raises:
            ValueError: If the result indicates failure
        """
        if not result.success:
            # Return a new context with the error in metadata
            return self.model_copy(update={
                "data": {
                    **self.data,
                    "error": result.error,
                    "error_metadata": result.metadata
                }
            })
            
        # Return a new context with the successful result data
        return self.model_copy(update={
            "data": {
                **self.data,
                **result.data,
                **result.metadata
            }
        })
    
    # Type-specific convenience methods
    def get_identity(self) -> Optional[Dict[str, Any]]:
        """Get identity data from context."""
        return self.get("identity")
    
    def get_permissions(self) -> Optional[Dict[str, Any]]:
        """Get permissions data from context."""
        return self.get("permissions")
    
    def get_credentials(self) -> Optional[Dict[str, Any]]:
        """Get credentials data from context."""
        return self.get("credentials") 
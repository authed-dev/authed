from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from .models import AuditContext, AuditRecord

class AuditLogger(ABC):
    """
    Base interface for all audit loggers.
    Supports span-based or log-based backends (e.g., OpenTelemetry, file, DB).
    """

    @abstractmethod
    async def start(
        self,
        run_id: str,
        identity_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditContext:
        """
        Initialize a new audit context. May start a span or trace under the hood.
        
        Parameters:
            run_id: Unique identifier for this audit session
            identity_id: Optional identity being audited
            resource: Optional resource being accessed
            action: Optional action being performed
            metadata: Optional additional metadata
            
        Returns:
            AuditContext: The initialized audit context
        """
        pass

    @abstractmethod
    async def log_event(
        self,
        context: AuditContext,
        event_type: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record an audit event, optionally structured (e.g., log line, span event).
        
        Parameters:
            context: The audit context this event belongs to
            event_type: Type of event (from AuditEventType or custom string)
            attributes: Optional event-specific attributes
        """
        pass

    @abstractmethod
    async def end(
        self,
        context: AuditContext,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """
        Finalize the audit session (e.g., end span, flush logs).
        
        Parameters:
            context: The audit context to finalize
            success: Whether the operation was successful
            error: Optional error message if unsuccessful
        """
        pass

    @abstractmethod
    async def query_records(self, 
                           start_time: Optional[str] = None, 
                           end_time: Optional[str] = None, 
                           run_id: Optional[str] = None,
                           identity_id: Optional[str] = None,
                           resource: Optional[str] = None,
                           action: Optional[str] = None,
                           success: Optional[bool] = None,
                           error_code: Optional[str] = None,
                           limit: int = 100,
                           offset: int = 0) -> List[AuditRecord]:
        """
        Query audit records with optional filters.
        
        Parameters:
            start_time: Optional ISO formatted start time filter
            end_time: Optional ISO formatted end time filter
            run_id: Optional run ID filter
            identity_id: Optional identity ID filter
            resource: Optional resource filter
            action: Optional action filter
            success: Optional success filter
            error_code: Optional error code filter
            limit: Maximum number of records to return
            offset: Offset for pagination
        
        Returns:
            List of audit records matching the filters
            
        Raises:
            AuditError: If the records cannot be queried
        """
        pass
    
    def create_record(self, 
                     resource_accessed: Optional[str] = None,
                     action_requested: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> AuditRecord:
        """
        Create a new audit record.
        
        Parameters:
            resource_accessed: The resource being accessed
            action_requested: The action being performed
            metadata: Additional execution-wide metadata
            
        Returns:
            AuditRecord: A new audit record
        """
        record = AuditRecord(
            resource_accessed=resource_accessed,
            action_requested=action_requested,
            metadata=metadata or {}
        )
        return record
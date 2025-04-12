"""Main parser component that combines tokenizer, interpreter, and builder."""

from typing import Optional

from ..base import (
    PermissionParser as BasePermissionParser, 
    BaseTokenizer, 
    BaseInterpreter, 
    BaseStatementBuilder,
    BaseSchemaProvider
)
from ..models import PermissionStatement
from .tokenizer import Tokenizer
from .interpreter import Interpreter
from .builder import StatementBuilder

class PermissionParser(BasePermissionParser):
    """Simple implementation of the PermissionParser interface."""
    
    def __init__(
        self,
        tokenizer: Optional[BaseTokenizer] = None,
        interpreter: Optional[BaseInterpreter] = None,
        builder: Optional[BaseStatementBuilder] = None,
        schema_provider: Optional[BaseSchemaProvider] = None
    ):
        """
        Initialize the permission parser with optional components.
        
        Args:
            tokenizer: The tokenizer to use (defaults to Tokenizer)
            interpreter: The interpreter to use (defaults to Interpreter)
            builder: The statement builder to use (defaults to StatementBuilder)
            schema_provider: Schema provider for field mapping and type information
                             (will be passed to interpreter if no interpreter is provided)
        """
        self.tokenizer = tokenizer or Tokenizer()
        # If no interpreter is provided, create one with the schema_provider
        self.interpreter = interpreter or Interpreter(schema_provider=schema_provider)
        self.builder = builder or StatementBuilder()
        self.schema_provider = schema_provider
    
    async def parse_statement(self, statement_text: str) -> PermissionStatement:
        """
        Parse a permission statement from text.
        
        Uses the configured tokenizer, interpreter, and builder components
        to process the input text. If a schema_provider was supplied during
        initialization, it will be used by the interpreter for field mapping 
        and type inference.
        
        Args:
            statement_text: The text to parse
            
        Returns:
            PermissionStatement: The parsed permission statement
        """
        # Tokenize the statement
        tokens = self.tokenizer.tokenize(statement_text)
        
        # Interpret the tokens
        interpreted_data = self.interpreter.interpret(tokens)
        
        # Build the statement
        return self.builder.build(interpreted_data) 
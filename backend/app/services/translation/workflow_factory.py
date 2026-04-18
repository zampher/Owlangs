# SPDX-FileCopyrightText: 2026 Zampher
# SPDX-License-Identifier: MPL-2.0

"""
Workflow Factory

Creates and configures workflow instances based on workflow type.
"""

from typing import Dict, Type, Any, Optional
from workflow.base import Workflow, WorkflowConfig
from logger import unified_logger as logger
from logger.logger import LogModule


class WorkflowFactory:
    """Factory for creating workflow instances."""
    
    def __init__(self):
        """Initialize workflow factory with workflow mappings."""
        self._workflow_classes: Dict[str, Type[Workflow]] = {}
        self._load_workflow_classes()
    
    def _load_workflow_classes(self):
        """Load workflow class mappings."""
        try:
            from workflow.docx_workflow import DocxWorkflow
            from workflow.md_based_workflow import MarkdownBasedWorkflow
            from workflow.txt_workflow import TXTWorkflow
            from workflow.json_workflow import JsonWorkflow
            from workflow.xlsx_workflow import XlsxWorkflow
            from workflow.html_workflow import HtmlWorkflow
            from workflow.srt_workflow import SrtWorkflow
            from workflow.epub_workflow import EpubWorkflow
            from workflow.mobi_workflow import MobiWorkflow
            from workflow.qt_ts_workflow import QtTsWorkflow
            from workflow.pptx_workflow import PptxWorkflow
            
            self._workflow_classes = {
                "markdown_based": MarkdownBasedWorkflow,
                "txt": TXTWorkflow,
                "json": JsonWorkflow,
                "xlsx": XlsxWorkflow,
                "docx": DocxWorkflow,
                "html": HtmlWorkflow,
                "srt": SrtWorkflow,
                "epub": EpubWorkflow,
                "mobi": MobiWorkflow,
                "qt_ts": QtTsWorkflow,
                "pptx": PptxWorkflow,
            }
        except ImportError as e:
            logger.error(LogModule.WORKFLOW, f"[WORKFLOW-FACTORY] Failed to import workflow classes: {e}", exc_info=True)
            raise
    
    def get_workflow_class(self, workflow_type: str) -> Optional[Type[Workflow]]:
        """
        Get workflow class by type.
        
        Args:
            workflow_type: Workflow type identifier
            
        Returns:
            Workflow class or None if not found
        """
        return self._workflow_classes.get(workflow_type)
    
    def create_workflow(
        self,
        workflow_type: str,
        config: Optional[WorkflowConfig] = None,
        task_id: Optional[str] = None,
        task_state: Optional[Dict[str, Any]] = None,
        payload: Optional[Any] = None,
        synthesized_prompt: Optional[str] = None
    ) -> Optional[Workflow]:
        """
        Create a workflow instance.
        
        Args:
            workflow_type: Workflow type identifier
            config: Optional workflow configuration (if provided, used directly)
            task_id: Optional task identifier (for config building)
            task_state: Optional task state (for config building)
            payload: Optional payload (for config building)
            synthesized_prompt: Optional synthesized prompt (for config building)
            
        Returns:
            Workflow instance or None if type not found
        """
        workflow_class = self.get_workflow_class(workflow_type)
        if workflow_class is None:
            logger.warning(LogModule.WORKFLOW, f"[WORKFLOW-FACTORY] Unknown workflow type: {workflow_type}")
            return None
        
        # If config is provided, use it directly
        if config:
            try:
                return workflow_class(config=config)
            except Exception as e:
                logger.error(LogModule.WORKFLOW, f"[WORKFLOW-FACTORY] Failed to create workflow {workflow_type}: {e}", exc_info=True)
                return None
        
        # Otherwise, try to build config from task_id + task_state + payload (synthesized_prompt optional; builder will synthesize if None)
        if task_id and task_state and payload:
            try:
                from backend.app.services.translation.workflow_config_builder import WorkflowConfigBuilder
                config_builder = WorkflowConfigBuilder(task_id, task_state)
                config = config_builder.build_workflow_config(workflow_type, payload, synthesized_prompt)
                if config:
                    return workflow_class(config=config)
            except Exception as e:
                logger.error(LogModule.WORKFLOW, f"[WORKFLOW-FACTORY] Failed to build config for {workflow_type}: {e}", exc_info=True)
        
        # Fallback: create workflow without config
        try:
            return workflow_class()
        except Exception as e:
            logger.error(LogModule.WORKFLOW, f"[WORKFLOW-FACTORY] Failed to create workflow {workflow_type}: {e}", exc_info=True)
            return None
    
    def get_supported_workflow_types(self) -> list:
        """
        Get list of supported workflow types.
        
        Returns:
            List of workflow type strings
        """
        return list(self._workflow_classes.keys())


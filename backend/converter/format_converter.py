"""
Document format converter module.
Supports PDF to DOCX conversion using pdf2docx library.
"""

import asyncio
import logging
import os
import tempfile
import uuid
import threading
import time
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Global storage for conversion tasks
conversion_tasks: Dict[str, Dict[str, Any]] = {}
conversion_files: Dict[str, Dict[str, Any]] = {}  # Store file info for cleanup


class ConversionError(Exception):
    """Custom exception for conversion errors"""
    pass


class FormatConverter:
    """Document format converter"""
    
    def __init__(self):
        self.supported_formats = {
            'pdf': ['docx'],
            # Future: 'docx': ['pdf'], 'txt': ['docx']
        }
    
    async def _send_log(self, log_queue: Optional[asyncio.Queue], message: str):
        """Send log message to frontend if log_queue is provided"""
        if log_queue:
            try:
                await log_queue.put(message)
            except Exception as e:
                logger.warning(LogModule.CONVERT, f"Failed to send log to frontend: {e}")
    
    def get_supported_targets(self, source_format: str) -> list[str]:
        """Get supported target formats for a source format"""
        return self.supported_formats.get(source_format.lower(), [])
    
    async def convert_pdf_to_docx(
        self, 
        pdf_path: str, 
        output_path: str,
        quality: str = 'high',
        log_queue: Optional[asyncio.Queue] = None
    ) -> None:
        """Convert PDF to DOCX format with optimized settings
        
        Args:
            pdf_path: Path to input PDF file
            output_path: Path to output DOCX file
            quality: Conversion quality (not used, kept for compatibility)
            log_queue: Optional queue for sending log messages to frontend
        """
        try:
            from pdf2docx import Converter
        except ImportError:
            raise ConversionError("pdf2docx library not installed. Please install it with: pip install pdf2docx")
        
        # Ensure os module is available in function scope
        import os
        
        try:
            logger.info(LogModule.CONVERT, f"Starting PDF to DOCX conversion: {pdf_path} -> {output_path}")
            await self._send_log(log_queue, "Starting PDF to DOCX conversion...")
            
            # Create output directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Initialize converter with optimized settings
            cv = Converter(pdf_path)
            await self._send_log(log_queue, "Analyzing PDF document...")
            
            # Set conversion parameters for better performance
            # These parameters can help optimize the conversion process
            try:
                # Try to set some optimization parameters if available
                if hasattr(cv, 'set_optimization_level'):
                    cv.set_optimization_level(1)  # Medium optimization
            except:
                pass  # Ignore if not supported
            
            # Convert with quality settings
            await self._send_log(log_queue, "Converting document format...")
            
            # Log CPU configuration before starting conversion
            total_cores = os.cpu_count()
            cpu_count = max(4, total_cores // 2)
            await self._send_log(log_queue, f"System detected {total_cores} CPU cores, using {cpu_count} cores for conversion")
            
            # Start conversion in a separate thread to avoid blocking
            
            conversion_completed = threading.Event()
            conversion_error = [None]
            
            def convert_worker():
                try:
                    # Use optimized conversion with multi-processing
                    try:
                        cv.convert(output_path, multi_processing=True, cpu_count=cpu_count)
                    except TypeError:
                        # Final fallback to basic conversion
                        cv.convert(output_path)
                    conversion_completed.set()
                except Exception as e:
                    conversion_error[0] = e
                    conversion_completed.set()
            
            # Start conversion in background thread
            convert_thread = threading.Thread(target=convert_worker)
            convert_thread.start()
            
            # Monitor progress
            start_time = time.time()
            while not conversion_completed.is_set():
                elapsed = time.time() - start_time
                if elapsed > 30:  # After 30 seconds, show progress
                    await self._send_log(log_queue, f"Conversion in progress... {int(elapsed)} seconds elapsed")
                    start_time = time.time()  # Reset to avoid spam
                time.sleep(5)  # Check every 5 seconds
            
            # Wait for thread to complete
            convert_thread.join()
            
            # Check for errors
            if conversion_error[0]:
                raise conversion_error[0]
            
            cv.close()
            
            logger.info(LogModule.CONVERT, f"PDF to DOCX conversion completed: {output_path}")
            await self._send_log(log_queue, "Conversion completed!")
            
        except Exception as e:
            logger.error(LogModule.CONVERT, f"PDF to DOCX conversion failed: {e}")
            raise ConversionError(f"Conversion failed: {str(e)}")
    
    async def convert(
        self,
        source_path: str,
        target_format: str,
        quality: str = 'high',
        task_id: str = None,
        log_queue: Optional[asyncio.Queue] = None
    ) -> str:
        """Convert document to target format"""
        
        # Ensure os module is available in function scope
        import os
        
        # Determine source format from file extension
        source_format = Path(source_path).suffix.lower().lstrip('.')
        
        # Check if conversion is supported
        supported_targets = self.get_supported_targets(source_format)
        if target_format not in supported_targets:
            raise ConversionError(f"Conversion from {source_format} to {target_format} is not supported")
        
        # Generate unique conversion ID
        convert_id = str(uuid.uuid4())
        
        # Create temporary output file
        temp_dir = tempfile.gettempdir()
        output_filename = f"{Path(source_path).stem}.{target_format}"
        output_path = os.path.join(temp_dir, f"convert_{convert_id}_{output_filename}")
        
        # Store conversion task info
        conversion_tasks[convert_id] = {
            'task_id': task_id,
            'source_path': source_path,
            'target_format': target_format,
            'output_path': output_path,
            'status': 'processing',
            'start_time': datetime.now(),
            'error': None
        }
        
        # Store file info for cleanup
        conversion_files[convert_id] = {
            'output_path': output_path,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(minutes=30)  # 30 minutes retention
        }
        
        try:
            # Perform conversion based on format
            if source_format == 'pdf' and target_format == 'docx':
                await self.convert_pdf_to_docx(source_path, output_path, quality, log_queue)
            else:
                raise ConversionError(f"Conversion from {source_format} to {target_format} not implemented")
            
            # Update task status
            conversion_tasks[convert_id]['status'] = 'completed'
            conversion_tasks[convert_id]['end_time'] = datetime.now()
            
            logger.info(LogModule.CONVERT, f"Conversion completed: {convert_id}")
            return convert_id
            
        except Exception as e:
            # Update task status with error
            conversion_tasks[convert_id]['status'] = 'failed'
            conversion_tasks[convert_id]['error'] = str(e)
            conversion_tasks[convert_id]['end_time'] = datetime.now()
            
            # Clean up failed conversion file
            if os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except:
                    pass
            
            logger.error(LogModule.CONVERT, f"Conversion failed: {convert_id}, error: {e}")
            await self._send_log(log_queue, f"Conversion failed: {str(e)}")
            raise
    
    def get_conversion_status(self, convert_id: str) -> Dict[str, Any]:
        """Get conversion task status"""
        if convert_id not in conversion_tasks:
            raise ConversionError(f"Conversion task {convert_id} not found")
        
        task = conversion_tasks[convert_id]
        return {
            'convert_id': convert_id,
            'status': task['status'],
            'error': task.get('error'),
            'start_time': task['start_time'].isoformat(),
            'end_time': task.get('end_time').isoformat() if task.get('end_time') else None,
            'target_format': task.get('target_format', 'docx')
        }
    
    def get_conversion_file(self, convert_id: str) -> Optional[str]:
        """Get converted file path if conversion is completed"""
        if convert_id not in conversion_tasks:
            return None
        
        task = conversion_tasks[convert_id]
        if task['status'] != 'completed':
            return None
        
        output_path = task['output_path']
        if not os.path.exists(output_path):
            return None
        
        return output_path
    
    def cleanup_expired_files(self):
        """Clean up expired conversion files"""
        now = datetime.now()
        expired_convert_ids = []
        
        for convert_id, file_info in conversion_files.items():
            if now > file_info['expires_at']:
                expired_convert_ids.append(convert_id)
        
        for convert_id in expired_convert_ids:
            try:
                file_info = conversion_files[convert_id]
                output_path = file_info['output_path']
                
                # Remove file if it exists
                if os.path.exists(output_path):
                    os.remove(output_path)
                    logger.info(LogModule.CONVERT, f"Cleaned up expired conversion file: {output_path}")
                
                # Remove from tracking
                del conversion_files[convert_id]
                if convert_id in conversion_tasks:
                    del conversion_tasks[convert_id]
                    
            except Exception as e:
                logger.error(LogModule.CONVERT, f"Failed to cleanup conversion file {convert_id}: {e}")


# Global converter instance
converter = FormatConverter()


async def cleanup_task():
    """Background task to clean up expired files"""
    while True:
        try:
            converter.cleanup_expired_files()
        except Exception as e:
            logger.error(LogModule.CONVERT, f"Cleanup task error: {e}")
        
        # Run cleanup every 5 minutes
        await asyncio.sleep(300)

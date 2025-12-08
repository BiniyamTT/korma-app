import logging
import sys

def setup_logging():
    # Create a custom logger
    logger = logging.getLogger("korma_ingest")
    logger.setLevel(logging.DEBUG)
    
    # Get the directory where this script is located
    import os
    log_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create handlers
    c_handler = logging.StreamHandler(sys.stdout)
    f_handler_all = logging.FileHandler(os.path.join(log_dir, 'all_logs.log'))
    f_handler_error = logging.FileHandler(os.path.join(log_dir, 'error_logs.log'))
    
    # Set levels
    c_handler.setLevel(logging.INFO)
    f_handler_all.setLevel(logging.DEBUG)
    f_handler_error.setLevel(logging.ERROR)
    
    # Create formatters and add to handlers
    c_format = logging.Formatter('%(message)s') # Simple format for console
    f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    c_handler.setFormatter(c_format)
    f_handler_all.setFormatter(f_format)
    f_handler_error.setFormatter(f_format)
    
    # Add handlers to the logger
    # Check if handlers already exist to avoid duplicates if called multiple times
    if not logger.handlers:
        logger.addHandler(c_handler)
        logger.addHandler(f_handler_all)
        logger.addHandler(f_handler_error)
    
    return logger

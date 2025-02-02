import time
from functools import wraps
from typing import Callable, Any
import logging

def retry_on_failure(max_attempts: int = 3, delay: float = 5.0):
    """
    Decorator to retry a function on failure.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempts = 0
            last_error = None
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    last_error = e
                    
                    if attempts == max_attempts:
                        logging.error(f"Final attempt failed for {func.__name__}: {str(e)}")
                        raise last_error
                    
                    logging.warning(
                        f"Attempt {attempts}/{max_attempts} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {delay} seconds..."
                    )
                    time.sleep(delay)
            
            raise last_error
        return wrapper
    return decorator
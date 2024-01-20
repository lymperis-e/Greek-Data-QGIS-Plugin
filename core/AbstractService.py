class ServiceNotExists(Exception):
    """Raised when a requested service does not exist."""
    
    def __init__(self, service_name):
        self.service_name = service_name
        
    def __str__(self):
        return f"Service '{self.service_name}' does not exist."

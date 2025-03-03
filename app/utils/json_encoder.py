from datetime import datetime
from bson import ObjectId
import json

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

def custom_dumps(obj, **kwargs):
    """
    Custom JSON dumps function that handles MongoDB ObjectId and datetime objects
    
    Args:
        obj: The object to serialize
        **kwargs: Additional arguments to pass to json.dumps
        
    Returns:
        str: JSON string representation of the object
    """
    return json.dumps(obj, cls=CustomJSONEncoder, **kwargs)

def custom_loads(s, **kwargs):
    """
    Custom JSON loads function that handles ISO format dates
    
    Args:
        s: The JSON string to deserialize
        **kwargs: Additional arguments to pass to json.loads
        
    Returns:
        The deserialized object
    """
    def datetime_parser(dct):
        for k, v in dct.items():
            if isinstance(v, str):
                try:
                    dct[k] = datetime.fromisoformat(v)
                except (ValueError, TypeError):
                    pass
        return dct
    
    return json.loads(s, object_hook=datetime_parser, **kwargs)
import socket
from typing import Optional, List, Dict
def can_access_internal_service(host, port=22, timeout=2):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False

def agent_done(data: dict) -> Optional[str]:
    outputs: List[Dict] = data.get("all_model_outputs", [])
    done_item = next((item for item in outputs if "done" in item), None)
    if done_item:
        return done_item["done"]
    return None
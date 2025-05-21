import socket
def can_access_internal_service(host, port=22, timeout=2):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False
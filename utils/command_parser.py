def extract_room(message: str) -> str:
    rooms = ["stue", "kjokken"]
    for room in rooms:
        if room in message.lower():
            return room
    return None

def extract_action(message: str) -> str:
    message = message.lower()
    if any(x in message for x in ["skru på", "på"]):
        return "på"
    if any(x in message for x in ["skru av", "av"]):
        return "av"
    if any(x in message for x in ["dim", "dimme"]):
        return "dim"
    return None

def extract_value(message: str) -> Optional[int]:
    import re
    match = re.search(r"(\d+)%?", message)
    return int(match.group(1)) if match else None

def extract_flow_name(message: str) -> str:
    """Henter ut flow-navnet fra meldingen"""
    flow_triggers = ["kjør flow", "start flow", "flow"]
    message = message.lower()
    
    for trigger in flow_triggers:
        if trigger in message:
            # Finn teksten etter flow-triggeren
            flow_name = message.split(trigger)[-1].strip()
            return flow_name
    return None
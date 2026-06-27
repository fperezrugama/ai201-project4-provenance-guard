"""Request validation for the submission API."""


def validate_submission(payload):
    """Validate a POST /submit JSON body.

    Returns an error message (str) describing the first problem found, or
    None if the payload is valid. Type checks guard against non-string
    fields, which would otherwise raise on .strip() and surface as a 500.
    """
    if not isinstance(payload, dict):
        return "Invalid request - JSON body required"

    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return "Invalid input - text field required"

    creator_id = payload.get("creator_id")
    if not isinstance(creator_id, str) or not creator_id.strip():
        return "Invalid input - creator_id field required"

    return None

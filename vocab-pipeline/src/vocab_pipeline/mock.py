import json
from hashlib import sha256

from .models import CandidateSense, GeneratedSense


def mock_response(candidate: CandidateSense, prompt_version: str) -> GeneratedSense:
    payload = {
        "candidate": candidate.model_dump(mode="json"),
        "model": "mock",
        "prompt_version": prompt_version,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return GeneratedSense(
        sense_id=candidate.sense_id,
        simple_definition="A sample definition for offline testing",
        example_en=f'The sample entry shows the term "{candidate.lemma}".',
        target_level="unknown",
        model_id="mock",
        prompt_version=prompt_version,
        generation_hash=sha256(encoded).hexdigest(),
    )

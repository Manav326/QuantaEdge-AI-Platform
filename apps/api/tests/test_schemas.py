from app.schemas import DocumentStatus, LearningAnswerRequest
from datetime import datetime, timezone
from uuid import uuid4


def test_learning_request_accepts_opaque_institution_reference():
    payload = LearningAnswerRequest(
        institution_ref="inst-123",
        learner_ref="learner-9",
        question="Explain measurement.",
        course_id="CLASS_6",
        subject_id="SCIENCE",
    )
    assert payload.institution_ref == "inst-123"


def test_document_status_can_validate_orm_like_objects():
    class Document:
        id = uuid4()
        status = "queued"
        chunk_count = 0
        error_code = None
        created_at = datetime.now(timezone.utc)

    result = DocumentStatus.model_validate(Document())
    assert result.status == "queued"


def test_memory_payload_requires_institution_scoped_consent_reference():
    from app.schemas import MemoryCreateRequest

    payload = MemoryCreateRequest(
        institution_ref="inst-12",
        learner_ref="learner-5",
        memory_type="revision_need",
        content="Needs another example for fractions.",
        consent_confirmed=True,
        consent_ref="consent-event-901",
    )
    assert payload.institution_ref == "inst-12"
    assert payload.consent_ref == "consent-event-901"

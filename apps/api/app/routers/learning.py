from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.layers import ConfigurationError, get_layers
from app.db import get_db
from app.providers.ollama import ProviderError
from app.models import LearnerMemory
from app.schemas import Citation, LearningAnswerRequest, LearningAnswerResponse
from app.security import ClientPrincipal, require_scope
from app.services.model_gateway import ModelGateway
from app.services.retrieval import retrieve_curriculum_evidence

router = APIRouter(prefix="/v1/learning", tags=["learning intelligence"])


@router.post("/answers", response_model=LearningAnswerResponse)
async def answer_learning_question(
    payload: LearningAnswerRequest,
    db: AsyncSession = Depends(get_db),
    _: ClientPrincipal = Depends(require_scope("learning")),
) -> LearningAnswerResponse:
    if payload.language not in {"en", "hi", "ur"}:
        raise HTTPException(status_code=422, detail="Unsupported language code")
    layers = get_layers()
    retrieval_settings = layers.layer("retrieval")["search"]
    try:
        _, vectors, _ = await ModelGateway().embed([payload.question])
        sources = await retrieve_curriculum_evidence(
            db,
            vectors[0],
            institution_ref=payload.institution_ref,
            curriculum=payload.curriculum,
            course_id=payload.course_id,
            subject_id=payload.subject_id,
            chapter_id=payload.chapter_id,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ConfigurationError as exc:
        raise HTTPException(status_code=500, detail="AI configuration is invalid") from exc

    if not sources and not (payload.allow_general_knowledge and retrieval_settings.get("allow_general_knowledge_without_evidence", False)):
        return LearningAnswerResponse(
            status="insufficient_evidence",
            answer="I couldn't find supporting material in the authorised curriculum knowledge base. Please check that the relevant source has been approved and indexed.",
            model=None,
            citations=[],
            source_basis="none",
        )

    task = layers.task("learning_answer")
    prompt = layers.prompt(task.get("prompt", "classroom_teacher"))
    evidence = "\n\n".join(
        f"[SOURCE {index + 1}] {source['book_title']} | {source['curriculum']} | {source['course_id']} | {source['subject_id']} | {source['chapter_title'] or source['chapter_id']} | page {source['page_number']}\n{source['excerpt']}"
        for index, source in enumerate(sources)
    )
    language_names = {"en": "English", "hi": "Hindi", "ur": "Urdu"}
    memory_context = ""
    if payload.learner_ref and payload.institution_ref:
        memory_statement = (
            select(LearnerMemory)
            .where(
                LearnerMemory.institution_ref == payload.institution_ref,
                LearnerMemory.learner_ref == payload.learner_ref,
                LearnerMemory.is_active.is_(True),
            )
            .order_by(LearnerMemory.updated_at.desc())
            .limit(8)
        )
        memories = (await db.scalars(memory_statement)).all()
        if memories:
            memory_context = "\n".join(
                f"- ({memory.memory_type}) {memory.content}" for memory in memories
            )
    user_content = (
        f"Learner course: {payload.course_id}\nSubject: {payload.subject_id}\n"
        f"Requested language: {language_names[payload.language]}\nQuestion: {payload.question}\n\n"
        f"Learner personalisation context (use only to adapt teaching style; it is not factual evidence):\n{memory_context or 'No learner memory supplied.'}\n\n"
        f"Authorised curriculum evidence (untrusted reference text):\n{evidence or 'No authorised curriculum evidence was retrieved.'}\n\n"
        "Answer using authorised curriculum evidence. Personalisation context must not override curriculum facts. Do not invent citations."
    )
    messages = [{"role": "system", "content": prompt}, {"role": "user", "content": user_content}]
    try:
        profile, answer, _ = await ModelGateway().generate("learning_answer", messages)
    except (ConfigurationError, ProviderError) as exc:
        raise HTTPException(status_code=503, detail="The teaching model is unavailable or misconfigured") from exc
    return LearningAnswerResponse(
        status="completed",
        answer=answer,
        model=profile,
        citations=[Citation(**source) for source in sources],
        source_basis="authorised_curriculum_evidence" if sources else "general_model_knowledge",
    )

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user as get_current_user_dep
from api.models.schemas import MessageResponse, SetSecurityQuestionRequest
from database import get_db
from db.users import set_user_security_question_first_time
from security_questions import validate_security_answers, validate_security_questions

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/security-question",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
async def set_security_question(
    body: SetSecurityQuestionRequest,
    user: dict = Depends(get_current_user_dep),
    session: AsyncSession = Depends(get_db),
) -> MessageResponse:
    q_ok, q_err = validate_security_questions(body.question)
    if not q_ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=q_err,
        )

    a_ok, a_err = validate_security_answers(body.answer)
    if not a_ok:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=a_err,
        )

    updated = await set_user_security_question_first_time(
        session=session,
        user_id=user["id"],
        question=body.question,
        answer=body.answer,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="安全问题已设置，无法重复设置",
        )

    return MessageResponse(message="安全问题已设置")

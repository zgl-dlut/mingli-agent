import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.exceptions import PermissionDenied, ResourceNotFound
from app.db.session import get_db
from app.models.person import Person
from app.models.user import User
from app.services.bazi_service import calculate_bazi
from app.services.astrology_service import calculate_astrology
from app.services.payment_service import deduct_points

logger = logging.getLogger(__name__)
from app.config import settings
from app.skills.orchestrator import generate_full_analysis

router = APIRouter(prefix="/api/persons", tags=["persons"])


class PersonRequest(BaseModel):
    name: str
    gender: str
    birth_date: str
    birth_time: str
    birth_location: str
    birth_lat: float
    birth_lng: float
    calendar_type: str = 'solar'
    province: str = ''
    city: str = ''


class PersonResponse(BaseModel):
    id: int
    name: str
    gender: str
    birth_date: str
    birth_time: str
    birth_location: str
    birth_lat: float
    birth_lng: float
    calendar_type: str = 'solar'
    province: str = ''
    city: str = ''
    created_at: str


@router.post("")
async def create_person(
    request: PersonRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    # 去重检查：同一用户相同生辰（性别+出生日期+出生时间+出生地点）已存在时，返回已有记录，不重复扣费
    existing = await db.execute(
        select(Person).where(
            Person.user_id == current_user.id,
            Person.gender == request.gender,
            Person.birth_date == request.birth_date,
            Person.birth_time == request.birth_time,
            Person.birth_location == request.birth_location,
        ).limit(1)
    )
    dup = existing.scalar_one_or_none()
    if dup:
        logger.info(f"[person] 重复创建检测: user={current_user.id} 已有相同生辰 person_id={dup.id}，跳过扣费")
        return {"person": dup, "duplicated": True}

    # 先生成排盘数据，成功后再扣费，避免排盘失败却已扣积分
    try:
        bazi_data = generate_full_analysis(
            birth_date=request.birth_date,
            birth_time=request.birth_time,
            longitude=request.birth_lng,
            latitude=request.birth_lat,
            gender=request.gender,
            location=request.birth_location,
        )
    except Exception as e:
        logger.error(f"[person] 排盘失败: user={current_user.id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"排盘失败，请稍后重试: {str(e)}")

    astro_chart = calculate_astrology(
        birth_date=request.birth_date,
        birth_time=request.birth_time,
        latitude=request.birth_lat,
        longitude=request.birth_lng,
    )

    person = Person(
        user_id=current_user.id,
        name=request.name,
        gender=request.gender,
        birth_date=request.birth_date,
        birth_time=request.birth_time,
        birth_location=request.birth_location,
        birth_lat=request.birth_lat,
        birth_lng=request.birth_lng,
        calendar_type=request.calendar_type,
        province=request.province,
        city=request.city,
        bazi_data_json=bazi_data,
    )
    db.add(person)
    await db.commit()
    await db.refresh(person)

    # 排盘和人物创建成功后再扣费
    await deduct_points(
        db, current_user.id, settings.POINTS_FIRST_READING,
        f"创建人物{request.name}，生成命盘",
        biz_type="first_reading",
    )
    
    from app.services.ai_service import generate_first_reading
    from app.models.session import ChatSession
    from app.models.message import ChatMessage
    
    session = ChatSession(
        person_id=person.id,
        bazi_data_json=bazi_data,
        astro_data_json=astro_chart.model_dump(),
        title=f"{person.name}的命盘",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=f"出生时间：{person.birth_date} {person.birth_time}({'公历' if person.calendar_type == 'solar' else '农历'})\n出生地点：{person.birth_location}\n性别：{'男' if person.gender == 'male' else '女'}",
    )
    db.add(user_message)
    await db.commit()
    
    return {
        "person": {
            "id": person.id,
            "name": person.name,
            "gender": person.gender,
            "birth_date": person.birth_date,
            "birth_time": person.birth_time,
            "birth_location": person.birth_location,
            "birth_lat": person.birth_lat,
            "birth_lng": person.birth_lng,
            "calendar_type": person.calendar_type,
            "province": person.province,
            "city": person.city,
        },
        "session_id": session.id,
        "bazi_data": bazi_data,
        "astro_data": astro_chart.model_dump(),
    }


@router.get("")
async def get_persons(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(
        select(Person).where(Person.user_id == current_user.id).order_by(Person.created_at.desc())
    )
    persons = result.scalars().all()
    
    from app.models.session import ChatSession
    
    result_list = []
    for person in persons:
        session_result = await db.execute(
            select(ChatSession).where(ChatSession.person_id == person.id)
        )
        session = session_result.scalar_one_or_none()
        
        # 如果 bazi_data_json 为 null，自动生成并持久化（兼容旧数据）
        bazi_data = person.bazi_data_json
        if not bazi_data:
            bazi_data = generate_full_analysis(
                birth_date=person.birth_date,
                birth_time=person.birth_time,
                longitude=person.birth_lng,
                latitude=person.birth_lat,
                gender=person.gender,
                location=person.birth_location,
            )
            person.bazi_data_json = bazi_data
            await db.commit()
            await db.refresh(person)
        
        result_list.append({
            "id": person.id,
            "name": person.name,
            "gender": person.gender,
            "birth_date": person.birth_date,
            "birth_time": person.birth_time,
            "birth_location": person.birth_location,
            "birth_lat": person.birth_lat,
            "birth_lng": person.birth_lng,
            "calendar_type": person.calendar_type,
            "province": person.province,
            "city": person.city,
            "session_id": session.id if session else None,
            "bazi_data": bazi_data,
            "created_at": person.created_at.isoformat(),
        })
    
    return result_list


@router.get("/{person_id}")
async def get_person(
    person_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    
    if not person:
        raise ResourceNotFound("人物不存在")
    if person.user_id != current_user.id:
        raise PermissionDenied("无权访问")
    
    from app.models.session import ChatSession
    
    session_result = await db.execute(
        select(ChatSession).where(ChatSession.person_id == person.id)
    )
    session = session_result.scalar_one_or_none()
    
    # 如果 bazi_data_json 为 null，自动生成并持久化（兼容旧数据）
    bazi_data = person.bazi_data_json
    if not bazi_data:
        bazi_data = generate_full_analysis(
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            longitude=person.birth_lng,
            latitude=person.birth_lat,
            gender=person.gender,
            location=person.birth_location,
        )
        person.bazi_data_json = bazi_data
        await db.commit()
        await db.refresh(person)
    
    return {
        "id": person.id,
        "name": person.name,
        "gender": person.gender,
        "birth_date": person.birth_date,
        "birth_time": person.birth_time,
        "birth_location": person.birth_location,
        "birth_lat": person.birth_lat,
        "birth_lng": person.birth_lng,
        "calendar_type": person.calendar_type,
        "province": person.province,
        "city": person.city,
        "session_id": session.id if session else None,
        "bazi_data": bazi_data,
        "created_at": person.created_at.isoformat(),
    }


@router.put("/{person_id}")
async def update_person(
    person_id: int,
    request: PersonRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()
    
    if not person:
        raise ResourceNotFound("人物不存在")
    if person.user_id != current_user.id:
        raise PermissionDenied("无权访问")
    
    person.name = request.name
    person.gender = request.gender
    person.birth_date = request.birth_date
    person.birth_time = request.birth_time
    person.birth_location = request.birth_location
    person.birth_lat = request.birth_lat
    person.birth_lng = request.birth_lng
    person.calendar_type = request.calendar_type
    person.province = request.province
    person.city = request.city
    
    await db.commit()
    await db.refresh(person)
    
    return {
        "id": person.id,
        "name": person.name,
        "gender": person.gender,
        "birth_date": person.birth_date,
        "birth_time": person.birth_time,
        "birth_location": person.birth_location,
        "birth_lat": person.birth_lat,
        "birth_lng": person.birth_lng,
        "calendar_type": person.calendar_type,
        "province": person.province,
        "city": person.city,
    }


@router.post("/{person_id}/ensure-session")
async def ensure_session(
    person_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    """确保 person 对应的 session 存在。

    session 被误删但 person 还在时，按 person 信息重建 session（含 bazi/astro 数据）。
    幂等：session 存在则直接返回，不重复创建、不扣费。
    """
    result = await db.execute(select(Person).where(Person.id == person_id))
    person = result.scalar_one_or_none()

    if not person:
        raise ResourceNotFound("人物不存在")
    if person.user_id != current_user.id:
        raise PermissionDenied("无权访问")

    from app.models.session import ChatSession
    from app.models.message import ChatMessage

    # 查现有 session：存在则直接返回
    session_result = await db.execute(
        select(ChatSession).where(ChatSession.person_id == person.id)
    )
    session = session_result.scalar_one_or_none()
    if session:
        return {"session_id": session.id, "created": False}

    # session 不存在，按 person 信息重建
    # 优先从 Person 读取已持久化的排盘数据
    if person.bazi_data_json:
        bazi_data = person.bazi_data_json
    else:
        # 兜底：如果 Person 中没有排盘数据，则生成并持久化
        bazi_data = generate_full_analysis(
            birth_date=person.birth_date,
            birth_time=person.birth_time,
            longitude=person.birth_lng,
            latitude=person.birth_lat,
            gender=person.gender,
            location=person.birth_location,
        )
        person.bazi_data_json = bazi_data
        await db.commit()
    
    astro_chart = calculate_astrology(
        birth_date=person.birth_date,
        birth_time=person.birth_time,
        latitude=person.birth_lat,
        longitude=person.birth_lng,
    )

    session = ChatSession(
        person_id=person.id,
        bazi_data_json=bazi_data,
        astro_data_json=astro_chart.model_dump(),
        title=f"{person.name}的命盘",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    # 重建初始 user 消息（与 create_person 一致，保证首次报告生成的"发送内容"存在）
    calendar_label = "公历" if person.calendar_type == "solar" else "农历"
    user_message = ChatMessage(
        session_id=session.id,
        role="user",
        content=f"出生时间：{person.birth_date} {person.birth_time}({calendar_label})\n出生地点：{person.birth_location}\n性别：{'男' if person.gender == 'male' else '女'}",
    )
    db.add(user_message)
    await db.commit()

    return {"session_id": session.id, "created": True}


@router.delete("/{person_id}")
async def delete_person(
    person_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    import traceback
    try:
        result = await db.execute(select(Person).where(Person.id == person_id))
        person = result.scalar_one_or_none()

        if not person:
            raise ResourceNotFound("人物不存在")
        if person.user_id != current_user.id:
            raise PermissionDenied("无权访问")

        from app.models.session import ChatSession
        from app.models.message import ChatMessage

        session_result = await db.execute(
            select(ChatSession).where(ChatSession.person_id == person.id)
        )
        session = session_result.scalar_one_or_none()

        if session:
            await db.execute(ChatMessage.__table__.delete().where(ChatMessage.session_id == session.id))
            await db.delete(session)

        await db.delete(person)
        await db.commit()

        return {"message": "删除成功"}
    except Exception as e:
        error_detail = traceback.format_exc()
        print(f"[DELETE PERSON ERROR] person_id={person_id}, user_id={current_user.id}:\n{error_detail}", flush=True)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")

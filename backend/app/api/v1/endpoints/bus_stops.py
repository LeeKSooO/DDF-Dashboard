from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.session import get_db
from app.db.models import BusStop

router = APIRouter()

@router.get("/", response_model=List[dict])
async def get_all_bus_stops(db: AsyncSession = Depends(get_db)):
    """모든 정류장 정보 조회"""
    try:
        from sqlalchemy import select
        
        stmt = select(BusStop).filter(BusStop.is_active == True)
        result = await db.execute(stmt)
        stops = result.scalars().all()
        
        bus_stops = []
        for stop in stops:
            bus_stops.append({
                "stop_id": stop.stop_id,
                "stop_name": stop.stop_name,
                "latitude": float(stop.latitude),
                "longitude": float(stop.longitude), 
                "district": stop.district,
                "is_active": stop.is_active
            })
            
        return bus_stops
        
    except Exception as e:
        print(f"정류장 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="정류장 데이터 조회 실패")

@router.get("/{stop_id}", response_model=dict)
async def get_bus_stop(stop_id: str, db: AsyncSession = Depends(get_db)):
    """특정 정류장 정보 조회"""
    try:
        from sqlalchemy import select
        
        stmt = select(BusStop).filter(
            BusStop.stop_id == stop_id,
            BusStop.is_active == True
        )
        result = await db.execute(stmt)
        stop = result.scalar_one_or_none()
        
        if not stop:
            raise HTTPException(status_code=404, detail="정류장을 찾을 수 없습니다")
            
        return {
            "stop_id": stop.stop_id,
            "stop_name": stop.stop_name,
            "latitude": float(stop.latitude),
            "longitude": float(stop.longitude),
            "district": stop.district,
            "is_active": stop.is_active
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"정류장 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="정류장 데이터 조회 실패")
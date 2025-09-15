"""
Time-related tools for LLM function calling
시간 관련 도구들 (LLM Function Calling용)
"""

from datetime import datetime, date, timedelta
import pytz
from typing import Dict, Any, Optional

def get_current_time_info() -> Dict[str, Any]:
    """현재 시간 정보 반환 (LLM Function Calling용)"""

    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    today = now.date()

    return {
        "current_date": today.isoformat(),
        "current_datetime": now.isoformat(),
        "formatted_date": today.strftime('%Y년 %m월 %d일'),
        "day_of_week": today.strftime('%A'),
        "year": today.year,
        "month": today.month,
        "day": today.day,
        "hour": now.hour,
        "minute": now.minute,
        "timezone": "Asia/Seoul"
    }

def get_relative_date(relative_term: str) -> Dict[str, Any]:
    """상대적 시간 표현을 절대 날짜로 변환"""

    kst = pytz.timezone('Asia/Seoul')
    now = datetime.now(kst)
    today = now.date()

    relative_dates = {
        "오늘": today,
        "어제": today - timedelta(days=1),
        "그저께": today - timedelta(days=2),
        "내일": today + timedelta(days=1),
        "모레": today + timedelta(days=2)
    }

    if relative_term in relative_dates:
        target_date = relative_dates[relative_term]
        return {
            "relative_term": relative_term,
            "absolute_date": target_date.isoformat(),
            "formatted_date": target_date.strftime('%Y년 %m월 %d일'),
            "is_valid": True
        }

    return {
        "relative_term": relative_term,
        "error": f"알 수 없는 상대 시간 표현: {relative_term}",
        "is_valid": False
    }

def check_date_in_data_range(target_date: str) -> Dict[str, Any]:
    """주어진 날짜가 실제 데이터 범위 내에 있는지 확인"""

    # 실제 데이터 범위 (하드코딩 - 실제로는 DB에서 조회)
    DATA_START = date(2025, 7, 19)
    DATA_END = date(2025, 7, 31)

    try:
        check_date = date.fromisoformat(target_date)
        is_in_range = DATA_START <= check_date <= DATA_END

        return {
            "target_date": target_date,
            "is_in_data_range": is_in_range,
            "data_start": DATA_START.isoformat(),
            "data_end": DATA_END.isoformat(),
            "suggestion": DATA_END.isoformat() if not is_in_range else None,
            "message": "데이터 범위 내" if is_in_range else f"데이터 범위 밖 (가능 기간: {DATA_START} ~ {DATA_END})"
        }
    except ValueError:
        return {
            "target_date": target_date,
            "error": "잘못된 날짜 형식",
            "is_in_data_range": False
        }

# LangChain Tools 형식으로 래핑
LANGCHAIN_TIME_TOOLS = [
    {
        "name": "get_current_time",
        "description": "현재 날짜와 시간 정보를 가져옵니다",
        "function": get_current_time_info
    },
    {
        "name": "parse_relative_date",
        "description": "오늘, 어제 등의 상대적 시간 표현을 절대 날짜로 변환합니다",
        "function": get_relative_date
    },
    {
        "name": "check_data_availability",
        "description": "특정 날짜의 데이터가 존재하는지 확인합니다",
        "function": check_date_in_data_range
    }
]
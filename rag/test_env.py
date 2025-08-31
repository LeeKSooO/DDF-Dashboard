import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv(override=True)

# 환경 변수에서 값 가져오기
api_key = os.getenv("WATSONX_APIKEY")
project_id = os.getenv("WATSONX_PROJECT_ID")

print(f"API Key: {api_key}")
print(f"Project ID: {project_id}")

# 값이 제대로 로드되었는지 확인하는 간단한 조건문 추가
if api_key and project_id:
    print("\n✅ .env 파일이 성공적으로 로드되었습니다.")
else:
    print("\n❌ .env 파일 로드 실패! 환경 변수가 제대로 설정되지 않았습니다.")
    if not api_key:
        print("-> 'WATSONX_APIKEY'가 비어있습니다.")
    if not project_id:
        print("-> 'WATSONX_PROJECT_ID'가 비어있습니다.")
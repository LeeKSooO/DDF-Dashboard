import os
from dotenv import load_dotenv
from ibm_watsonx_ai import Credentials
from ibm_watsonx_ai.foundation_models import Model
from ibm_watsonx_ai.foundation_models.utils.enums import ModelTypes

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv(override=True)

# watsonx.ai 자격 증명 설정
credentials = Credentials(
    url="https://us-south.ml.cloud.ibm.com",
    api_key=os.getenv("WATSONX_APIKEY"),
)
project_id = os.getenv("WATSONX_PROJECT_ID")

# 필수 정보가 없으면 오류를 발생시킵니다.
if not credentials.api_key or not project_id:
    raise ValueError("IBM watsonx.ai API key or Project ID not found. Please set them in your environment or .env file.")

# 모델 파라미터 설정
parameters = {
    "decoding_method": "greedy",
    "min_new_tokens": 10,
    "max_new_tokens": 100,
    "temperature": 0.1
}

# watsonx.ai 모델 객체 생성
try:
    print("🚀 watsonx.ai 모델 객체 초기화 중...")
    model = Model(
        model_id="ibm/granite-3-8b-instruct",
        params=parameters,
        credentials=credentials,
        project_id=project_id
    )
    print("✅ 모델 객체 초기화 성공!")

    # 모델 호출 및 답변 생성
    print("📝 모델에게 질문을 던지는 중...")
    question = "안녕, 세상! 간단하게 자기소개 해줘."
    response = model.generate_text(prompt=question)

    print("\n---------- 답변 ----------")
    print(response)
    print("--------------------------")
    print("\n🎉 모델이 성공적으로 응답했습니다!")

except Exception as e:
    print(f"\n❌ 오류 발생! 모델 호출 실패.")
    print(f"오류 내용: {e}")
    print("\n⚠️ 다음을 확인해 주세요:")
    print("1. API 키와 프로젝트 ID가 정확한가요?")
    print("2. watsonx.ai 계정이 활성화되어 있나요?")
    print("3. 인터넷 연결 상태는 양호한가요?")
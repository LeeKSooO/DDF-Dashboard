#!/bin/bash

# MST-GCN 모델 아카이브 생성 스크립트

# --- 1. 변수 설정 ---

# 모델 이름 및 버전
MODEL_NAME="mstgcn"
VERSION="1.0"

# 모델 클래스 정의 파일: MSTGCN, MSTGCN_submodule 등 클래스가 정의된 .py 파일 경로
MODEL_DEFINITION_FILE="../models/mstgcn_architecture.py"

# 학습된 모델 가중치 파일 경로
SERIALIZED_MODEL_FILE="../ddf_model/mstgcn_model_v1.pt"

# 핸들러 파일 경로: 다중 입력을 처리하도록 작성된 핸들러
HANDLER_FILE="handlers/mstgcn_handler.py"

# 추가 파일 목록: 추론에 필요한 모든 외부 파일을 쉼표로 구분하여 나열
# 1. stats.npz: 데이터 정규화를 위한 평균/표준편차
# 2. adj_mx.npy: 체비셰프 다항식 생성을 위한 인접 행렬
# 3. valid_stop_ids.npy: 학습에 사용된 957개 정류장 ID (순서 보장)
EXTRA_FILES="../ddf_model/stats.npz,../ddf_model/adj_mx.npy,../ddf_model/valid_stop_ids.npy,../ddf_model/valid_stop_ids.txt"

# 아카이브(.mar) 파일이 저장될 폴더
EXPORT_PATH="model-store/"

# 모델 저장소 디렉토리 생성
mkdir -p "$EXPORT_PATH"

# --- 2. 필요한 파일 존재 확인 ---

echo "필요한 파일 존재 확인 중..."

# 모델 정의 파일 확인
if [ ! -f "$MODEL_DEFINITION_FILE" ]; then
    echo "모델 정의 파일이 없습니다: $MODEL_DEFINITION_FILE"
    exit 1
fi

# 학습된 모델 파일 확인
if [ ! -f "$SERIALIZED_MODEL_FILE" ]; then
    echo "학습된 모델 파일이 없습니다: $SERIALIZED_MODEL_FILE"
    exit 1
fi

# 핸들러 파일 확인
if [ ! -f "$HANDLER_FILE" ]; then
    echo "핸들러 파일이 없습니다: $HANDLER_FILE"
    exit 1
fi

# 추가 파일 확인
IFS=',' read -ra EXTRA_FILES_ARRAY <<< "$EXTRA_FILES"
for file in "${EXTRA_FILES_ARRAY[@]}"; do
    if [ ! -f "$file" ]; then
        echo "추가 파일이 없습니다: $file"
        exit 1
    fi
done

echo "✅ 모든 필요한 파일이 존재합니다."

# --- 3. 모델 아카이브 생성 ---

echo ""
echo "MST-GCN 모델 아카이브 생성을 시작합니다..."
echo "모델 이름: $MODEL_NAME"
echo "버전: $VERSION"
echo "모델 정의 파일: $MODEL_DEFINITION_FILE"
echo "학습된 모델 파일: $SERIALIZED_MODEL_FILE"
echo "핸들러 파일: $HANDLER_FILE"
echo "추가 파일: $EXTRA_FILES"
echo "출력 경로: $EXPORT_PATH"
echo ""

torch-model-archiver \
    --model-name "$MODEL_NAME" \
    --version "$VERSION" \
    --model-file "$MODEL_DEFINITION_FILE" \
    --serialized-file "$SERIALIZED_MODEL_FILE" \
    --handler "$HANDLER_FILE" \
    --extra-files "$EXTRA_FILES" \
    --export-path "$EXPORT_PATH" \
    --force

# --- 4. 결과 확인 ---

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ MST-GCN 모델 아카이브 생성 완료!"
    echo "생성된 파일: ${EXPORT_PATH}${MODEL_NAME}.mar"
    echo ""
    echo "📋 아카이브 내용:"
    echo "  - 모델 정의: $MODEL_DEFINITION_FILE"
    echo "  - 모델 가중치: $SERIALIZED_MODEL_FILE"
    echo "  - 핸들러: $HANDLER_FILE"
    echo "  - 정규화 통계: ../ddf_model/stats.npz"
    echo "  - 인접 행렬: ../ddf_model/adj_mx.npy"
    echo ""
    echo "🚀 TorchServe 시작 명령어:"
    echo "torchserve --start --model-store ${EXPORT_PATH} --models ${MODEL_NAME}=${MODEL_NAME}.mar --ts-config config/config.properties"
else
    echo ""
    echo "❌ 모델 아카이브 생성 실패"
    echo "위의 오류 메시지를 확인하여 문제를 해결하세요."
    exit 1
fi
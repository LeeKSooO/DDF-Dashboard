#!/usr/bin/env python3
import os
import sys
from langchain_ollama import ChatOllama

def test_ollama_connection():
    """Ollama 연결 및 모델 테스트"""
    try:
        print("🔍 Ollama 연결 테스트 중...")
        
        # 채팅 모델 테스트
        llm = ChatOllama(model="qwen2.5:7b-instruct", temperature=0.1)
        
        test_prompt = """당신은 DRT(수요응답형 교통) 전문가입니다. 
DRT의 주요 특징 3가지를 간단히 설명해주세요."""
        
        print("💭 모델 응답 생성 중...")
        response = llm.invoke(test_prompt)
        
        # 응답 처리
        if hasattr(response, 'content'):
            answer = response.content
        else:
            answer = str(response)
            
        print("\n✅ Ollama 연결 성공!")
        print(f"🤖 모델 응답:\n{answer}")
        return True
        
    except Exception as e:
        print(f"❌ Ollama 연결 실패: {str(e)}")
        return False

def check_requirements():
    """필요한 패키지들 확인"""
    print("📋 시스템 요구사항 확인...")
    
    required_packages = [
        'langchain_ollama',
        'langchain_community', 
        'langchain_chroma',
        'pandas',
        'sqlalchemy',
        'fuzzywuzzy'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} - 설치 필요")
            missing.append(package)
    
    return missing

def check_papers_directory():
    """papers 폴더 확인"""
    papers_dir = "../papers/"
    if os.path.exists(papers_dir):
        # 하위 폴더까지 검색
        pdf_files = []
        for root, dirs, files in os.walk(papers_dir):
            for file in files:
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(root, file))
        
        print(f"📚 papers 폴더: {len(pdf_files)}개 PDF 파일 발견")
        if pdf_files:
            print("   상위 3개 파일:")
            for pdf in pdf_files[:3]:
                print(f"   - {os.path.basename(pdf)}")
        return len(pdf_files)
    else:
        print("❌ papers 폴더를 찾을 수 없습니다.")
        return 0

def main():
    print("🚀 DRT RAG 시스템 빠른 진단")
    print("=" * 50)
    
    # 1. 패키지 확인
    missing = check_requirements()
    
    # 2. papers 폴더 확인  
    pdf_count = check_papers_directory()
    
    # 3. Ollama 테스트
    ollama_ok = test_ollama_connection()
    
    print("\n" + "=" * 50)
    print("📊 진단 결과:")
    
    if missing:
        print(f"❌ 설치 필요한 패키지: {', '.join(missing)}")
        print(f"   설치 명령: pip install {' '.join(missing)}")
    else:
        print("✅ 모든 필수 패키지 설치됨")
    
    if pdf_count > 0:
        print(f"✅ PDF 문서: {pdf_count}개 준비됨")
    else:
        print("❌ PDF 문서가 없습니다. papers/ 폴더를 확인하세요.")
    
    if ollama_ok:
        print("✅ Ollama 모델 연결 성공")
    else:
        print("❌ Ollama 연결 실패")
        print("   확인사항:")
        print("   - ollama serve 실행 여부")
        print("   - ollama pull qwen2.5:7b-instruct 모델 설치")
    
    # 종합 판정
    if not missing and pdf_count > 0 and ollama_ok:
        print("\n🎉 모든 시스템이 준비되었습니다!")
        print("   python rag_app_3.py 실행 가능")
    else:
        print("\n⚠️  일부 문제가 있습니다. 위의 지침을 따라 해결해주세요.")

if __name__ == "__main__":
    main()
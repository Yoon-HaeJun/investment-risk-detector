import streamlit as st
import requests

# 페이지 기본 설정
st.set_page_config(page_title="Investment Risk Detector", page_icon="🚨", layout="centered")

st.title("🚨 기업 투자 리스크 탐지기")
st.markdown("KOSPI 상위 50개 기업의 재무 상태와 악재성 공시를 분석하여 위험도를 알려드립니다.")

# 사용자 입력 폼
corp_name = st.text_input("🔍 분석할 기업명을 입력하세요 (예: 삼성전자, 카카오):", "")
analyze_button = st.button("리스크 분석 시작")

# 백엔드 API 통신 및 화면 렌더링
if analyze_button and corp_name:
    with st.spinner(f"'{corp_name}'의 공시 및 재무 데이터를 분석 중입니다..."):
        try:
            # FastAPI 백엔드 서버로 GET 요청
            API_URL = f"http://127.0.0.1:8000/api/risk/{corp_name}"
            response = requests.get(API_URL)
            
            if response.status_code == 200:
                result = response.json()
                
                # --- [결과 화면 그리기] ---
                st.subheader(f"📊 {result['corp_name']} 종합 리스크 평가 결과")
                
                # 점수에 따른 색상 및 메세지 박스 처리
                grade = result['grade']
                if "안전" in grade:
                    st.success(f"**등급: {grade}** (총점: {result['total_score']}점)")
                elif "주의" in grade:
                    st.warning(f"**등급: {grade}** (총점: {result['total_score']}점)")
                else:
                    st.error(f"**등급: {grade}** (총점: {result['total_score']}점)")

                # 세부 리스크 내역 컬럼 나누기
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 💰 재무 리스크")
                    st.write(f"**점수:** {result['financial_risk']['score']}점")
                    for detail in result['financial_risk']['details']:
                        st.write(f"- {detail}")
                        
                with col2:
                    st.markdown("#### 📄 공시 리스크")
                    st.write(f"**점수:** {result['text_risk']['score']}점")
                    for detail in result['text_risk']['details']:
                        st.write(f"- {detail}")
                        
            elif response.status_code == 404:
                st.error("❌ 지원하지 않는 기업명입니다. KOSPI 상위 종목을 입력해 주세요.")
            else:
                st.error("❌ 서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.")
                
        except requests.exceptions.ConnectionError:
            st.error("🚨 백엔드 API 서버(FastAPI)가 꺼져 있습니다. 먼저 서버를 실행해 주세요.")
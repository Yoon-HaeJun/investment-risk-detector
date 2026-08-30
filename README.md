# 🚨 AI Investment Risk Detector (기업 투자 리스크 탐지기)

국내 상장사 전체를 대상으로 재무제표와 공시 데이터를 수집하고, 금융 특화 AI 언어모델(KR-FinBERT)을 활용해 기업의 숨겨진 투자 리스크를 직관적인 100점 만점 차감식으로 평가하는 풀스택 웹 대시보드입니다.

---

## 🎯 핵심 기능 (Key Features)

* **AI 기반 공시 감성 분석 (NLP):** DART API의 접수번호(`rcept_no`)를 활용하여 공시 원문을 긁어온 뒤, 500자 단위 Chunking 기법과 KR-FinBERT 모델을 통해 치명적인 악재(소송, 부도 등) 문맥을 탐지합니다.
* **자동화된 재무 건전성 스코어링:** 가장 최근 재무제표를 바탕으로 부채비율 200% 초과, 영업이익 적자 등의 재무 리스크를 산출합니다.
* **직관적인 UX 및 검색 시스템:** 100점 만점 기준의 차감식 UI를 제공하며, 종목코드(예: 035420) 또는 별명(예: 네이버) 검색 기능을 지원합니다. 평가 완료 후 위험 공시의 보고서명(`report_nm`)을 직접 명시하여 사용자 신뢰도를 높입니다.

---

## 🛠️ 기술 스택 (Tech Stack)

* **Data Engineering:** OpenDART API, Pandas, BeautifulSoup, LXML
* **AI / ML (NLP):** PyTorch, HuggingFace Transformers (KR-FinBERT)
* **Backend:** Python, FastAPI, Uvicorn
* **Frontend:** Streamlit

---

## 🚀 실행 방법 (How to Run)

**1. 환경 변수 설정 (.env)**
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 발급받은 DART API 키를 입력합니다.
`DART_API_KEY="본인의_API_키를_입력하세요"`

**2. 필요 패키지 설치**
`pip install fastapi uvicorn streamlit requests opendartreader bs4 lxml torch transformers pandas python-dotenv`

**3. 백엔드 서버 실행 (FastAPI)**
새 터미널을 열고 아래 명령어를 실행하여 AI 모델을 메모리에 적재하고 서버를 구동합니다.
`uvicorn src.api.main:app --reload`

**4. 프론트엔드 서버 실행 (Streamlit)**
백엔드가 켜진 상태에서 새로운 터미널을 열고 대시보드를 실행합니다.
`streamlit run src/frontend/app.py`
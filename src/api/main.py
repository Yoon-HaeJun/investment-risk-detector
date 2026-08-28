import os
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from opendartreader import OpenDartReader

# 경로 설정 및 환경 변수 로드
# 현재 파일(main.py) 위치를 기준으로 프로젝트 최상단 디렉토리를 찾습니다.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# DART API 초기화
api_key = os.environ.get('DART_API_KEY')
if not api_key:
    raise RuntimeError("🚨 .env 파일에 DART_API_KEY가 설정되지 않았습니다.")
dart = OpenDartReader(api_key)

# KOSPI 50 매핑 데이터 로드 (서버가 켜질 때 1회만 메모리에 적재)
CSV_PATH = os.path.join(BASE_DIR, 'data', 'kospi_top50_mapping.csv')
try:
    mapping_df = pd.read_csv(CSV_PATH, dtype={'corp_code': str})
except FileNotFoundError:
    mapping_df = pd.DataFrame()

# FastAPI 앱 초기화
app = FastAPI(
    title="Investment Risk Detector API",
    description="기업 공시 및 재무 기반 투자 리스크 탐지 서비스 API"
)

# 종합 리스크 평가 함수
def calculate_total_risk(corp_name: str, corp_code: str):
    result = {
        "corp_name": corp_name,
        "total_score": 0,
        "grade": "✅ 안전 (Safe)",
        "financial_risk": {"score": 0, "details": []},
        "text_risk": {"score": 0, "details": []}
    }
    
    # [재무 평가]
    try:
        finstate = dart.finstate(corp_code, '2025', reprt_code='11011')
        if finstate is not None and not finstate.empty:
            def clean_amt(val): return float(str(val).replace(',', '')) if not pd.isna(val) else 0
            
            liab_row = finstate[finstate['account_nm'] == '부채총계']
            eqty_row = finstate[finstate['account_nm'] == '자본총계']
            op_row = finstate[finstate['account_nm'] == '영업이익']

            if not liab_row.empty and not eqty_row.empty:
                liab = clean_amt(liab_row['thstrm_amount'].values[0])
                eqty = clean_amt(eqty_row['thstrm_amount'].values[0])
                if eqty > 0 and (liab / eqty) * 100 > 200:
                    result["financial_risk"]["score"] += 30
                    result["financial_risk"]["details"].append("부채비율 200% 초과")

            if not op_row.empty:
                curr_op = clean_amt(op_row['thstrm_amount'].values[0])
                prev_op = clean_amt(op_row['frmtrm_amount'].values[0])
                if curr_op < 0:
                    result["financial_risk"]["score"] += 40
                    result["financial_risk"]["details"].append("영업이익 적자 발생")
                elif prev_op > 0 and curr_op < prev_op:
                    result["financial_risk"]["score"] += 30
                    result["financial_risk"]["details"].append("영업이익 전년 대비 감소")
    except Exception as e:
        result["financial_risk"]["details"].append("재무 데이터 공시 전이거나 수집 오류 발생")

    # [텍스트 공시 평가]
    try:
        today = datetime.now()
        bgn_de = (today - relativedelta(years=1)).strftime('%Y%m%d')
        end_de = today.strftime('%Y%m%d')

        disclosures = dart.list(corp_code, start=bgn_de, end=end_de)
        if disclosures is not None and not disclosures.empty:
            filtered_df = disclosures[disclosures['flr_nm'] == corp_name]
            fatal_df = filtered_df[filtered_df['report_nm'].str.contains('감자|횡령|배임|상장폐지|부도', regex=True, na=False)]
            warn_df = filtered_df[filtered_df['report_nm'].str.contains('유상증자|소송|해지|생산중단|영업정지', regex=True, na=False)]

            if not fatal_df.empty:
                result["text_risk"]["score"] += (100 * len(fatal_df))
                result["text_risk"]["details"].append(f"🚨 치명적 악재 ({len(fatal_df)}건 발견):")
                # 발견된 실제 보고서명(report_nm)을 리스트에 하나씩 추가
                for report_name in fatal_df['report_nm'].tolist():
                    result["text_risk"]["details"].append(f"  👉 {report_name}")
                    
            if not warn_df.empty:
                result["text_risk"]["score"] += (30 * len(warn_df))
                result["text_risk"]["details"].append(f"⚠️ 주의성 악재 ({len(warn_df)}건 발견):")
                for report_name in warn_df['report_nm'].tolist():
                    result["text_risk"]["details"].append(f"  👉 {report_name}")
    except Exception as e:
         pass # 공시가 아예 없는 경우 통과

    # [종합 점수]
    total_score = result["financial_risk"]["score"] + result["text_risk"]["score"]
    result["total_score"] = total_score
    if total_score >= 100:
        result["grade"] = "🚨 위험 (Danger)"
    elif total_score >= 40:
        result["grade"] = "⚠️ 주의 (Caution)"
    else:
        result["grade"] = "✅ 안전 (Safe)"

    return result

# API 엔드포인트 정의
@app.get("/")
def health_check():
    return {"status": "ok", "message": "리스크 탐지 API 서버가 정상 작동 중입니다 🚀"}

@app.get("/api/risk/{corp_name}")
def get_risk_score(corp_name: str):
    # 예외 처리: 데이터가 로드되지 않았거나 KOSPI 50에 없는 기업인 경우
    if mapping_df.empty:
        raise HTTPException(status_code=500, detail="매핑 테이블이 로드되지 않았습니다.")
        
    corp_info = mapping_df[mapping_df['corp_name'] == corp_name]
    if corp_info.empty:
        raise HTTPException(status_code=404, detail=f"'{corp_name}'은(는) 지원하는 KOSPI 상위 종목이 아닙니다.")
        
    # 고유번호 추출 및 평가 함수 호출
    corp_code = str(corp_info['corp_code'].values[0]).zfill(8)
    return calculate_total_risk(corp_name, corp_code)
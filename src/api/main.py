import os
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from opendartreader import OpenDartReader

# 환경 변수 로드 및 DART 객체 생성
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, '.env'))

api_key = os.environ.get('DART_API_KEY')
dart = OpenDartReader(api_key)

# 국내 전체 상장사 고유번호 로드
print("⏳ 국내 전체 상장사 데이터를 DART에서 불러오는 중입니다... (약 5~10초 소요)")
all_corp_df = dart.corp_codes

# null이 아니면서, 공백을 제거했을 때 빈 문자열이 아닌 데이터만 상장사로 취급
mapping_df = all_corp_df[
    all_corp_df['stock_code'].notna() & 
    (all_corp_df['stock_code'].str.strip() != "")
].copy()
print(f"✅ 총 {len(mapping_df)}개의 상장사 데이터 로드 완료! (비상장사 제외)")

app = FastAPI(title="Investment Risk Detector API")

# 100점 차감식 스코어링 로직으로 전면 개편
def calculate_total_risk(corp_name: str, corp_code: str):
    result = {
        "corp_name": corp_name,
        "total_score": 100, # 100점 만점에서 시작
        "grade": "✅ 안전 (Safe)",
        "financial_risk": {"penalty": 0, "details": []},
        "text_risk": {"penalty": 0, "details": []}
    }
    
    financial_penalty = 0
    text_penalty = 0
    
    # [재무 평가 차감]
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
                    financial_penalty += 30
                    result["financial_risk"]["details"].append("부채비율 200% 초과 (-30점)")

            if not op_row.empty:
                curr_op = clean_amt(op_row['thstrm_amount'].values[0])
                prev_op = clean_amt(op_row['frmtrm_amount'].values[0])
                if curr_op < 0:
                    financial_penalty += 40
                    result["financial_risk"]["details"].append("영업이익 적자 발생 (-40점)")
                elif prev_op > 0 and curr_op < prev_op:
                    financial_penalty += 30
                    result["financial_risk"]["details"].append("영업이익 전년 대비 감소 (-30점)")
    except Exception:
        pass

    # [텍스트 공시 평가 차감]
    try:
        today = datetime.now()
        bgn_de = (today - relativedelta(years=1)).strftime('%Y%m%d')
        end_de = today.strftime('%Y%m%d')

        disclosures = dart.list(corp_code, start=bgn_de, end=end_de)
        if disclosures is not None and not disclosures.empty:
            filtered_df = disclosures[disclosures['flr_nm'] == corp_name]
            # '[기재정정]' 또는 '[첨부추가]'가 포함된 중복 보고서 제외
            filtered_df = filtered_df[~filtered_df['report_nm'].str.contains(r'\[기재정정\]|\[첨부추가\]', na=False)]
            fatal_df = filtered_df[filtered_df['report_nm'].str.contains('감자|횡령|배임|상장폐지|부도', regex=True, na=False)]
            warn_df = filtered_df[filtered_df['report_nm'].str.contains('유상증자|소송|해지|생산중단|영업정지', regex=True, na=False)]

            if not fatal_df.empty:
                penalty = 100 * len(fatal_df)
                text_penalty += penalty
                result["text_risk"]["details"].append(f"🚨 치명적 악재 {len(fatal_df)}건 발견 (-{penalty}점):")
                for r_name in fatal_df['report_nm'].tolist():
                    result["text_risk"]["details"].append(f"  👉 {r_name}")
                    
            if not warn_df.empty:
                penalty = 30 * len(warn_df)
                text_penalty += penalty
                result["text_risk"]["details"].append(f"⚠️ 주의성 악재 {len(warn_df)}건 발견 (-{penalty}점):")
                for r_name in warn_df['report_nm'].tolist():
                    result["text_risk"]["details"].append(f"  👉 {r_name}")
    except Exception:
         pass

    # [최종 스코어 및 등급 산출]
    result["financial_risk"]["penalty"] = financial_penalty
    result["text_risk"]["penalty"] = text_penalty
    
    # 총점에서 점수를 빼되, 0점 밑으로는 내려가지 않게 max() 함수로 방어
    final_score = 100 - financial_penalty - text_penalty
    result["total_score"] = max(0, final_score) 

    # 점수 구간 변경 (100점 만점 기준)
    if result["total_score"] <= 40:
        result["grade"] = "🚨 위험 (Danger)"
    elif result["total_score"] <= 79:
        result["grade"] = "⚠️ 주의 (Caution)"
    else:
        result["grade"] = "✅ 안전 (Safe)"

    return result

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.get("/api/risk/{search_query}")
def get_risk_score(search_query: str):
    if mapping_df.empty:
        raise HTTPException(status_code=500, detail="매핑 테이블이 로드되지 않았습니다.")
        
    # 자주 헷갈리는 기업명 사전
    aliases = {
        "네이버": "NAVER",
        "케이티": "KT",
        "에스케이": "SK",
        "엘지": "LG"
    }
    # 검색어가 사전에 있으면 변환하고, 없으면 원래 검색어 유지
    refined_query = aliases.get(search_query, search_query)

    # 검색어가 6자리 숫자(종목코드)인지 이름인지 판별하여 검색
    if refined_query.isdigit() and len(refined_query) == 6:
        # 종목코드(stock_code)로 정확히 검색
        matches = mapping_df[mapping_df['stock_code'] == refined_query]
    else:
        # 기업명(corp_name)으로 포함 검색 (대소문자 무시)
        matches = mapping_df[mapping_df['corp_name'].str.contains(refined_query, case=False, na=False)]
    
    if matches.empty:
        raise HTTPException(status_code=404, detail=f"'{search_query}'와(과) 일치하는 상장사가 없습니다. 정확한 법인명이나 6자리 종목코드를 입력해 주세요.")
        
    # 정확히 일치하는 이름이 있으면 우선 선택, 없으면 검색결과 중 첫 번째 기업 선택
    exact_match = matches[matches['corp_name'] == refined_query]
    if not exact_match.empty:
        target_corp = exact_match.iloc[0]
    else:
        target_corp = matches.iloc[0]
        
    real_corp_name = target_corp['corp_name']
    corp_code = str(target_corp['corp_code']).zfill(8)
    
    return calculate_total_risk(real_corp_name, corp_code)
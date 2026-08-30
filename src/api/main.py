import os
import re
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from opendartreader import OpenDartReader
from bs4 import BeautifulSoup
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# 환경 변수 로드 및 DART 객체 생성
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, '.env'))

api_key = os.environ.get('DART_API_KEY')
dart = OpenDartReader(api_key)

# 국내 전체 상장사 데이터 로드
print("⏳ 국내 상장사 데이터를 로드 중입니다...")
all_corp_df = dart.corp_codes
mapping_df = all_corp_df[all_corp_df['stock_code'].notna() & (all_corp_df['stock_code'].str.strip() != "")].copy()

# KR-FinBERT AI 모델 전역 로드
print("🧠 딥러닝 AI 언어모델(KR-FinBERT)을 메모리에 적재 중입니다...")
model_name = "snunlp/KR-FinBERT-SC"
tokenizer = AutoTokenizer.from_pretrained(model_name)
nlp_model = AutoModelForSequenceClassification.from_pretrained(model_name)
print("✅ 백엔드 서버 및 AI 준비 완료!")

app = FastAPI(title="AI Investment Risk Detector API")

def calculate_total_risk(corp_name: str, corp_code: str):
    result = {
        "corp_name": corp_name,
        "total_score": 100,
        "grade": "✅ 안전 (Safe)",
        "financial_risk": {"penalty": 0, "details": []},
        "text_risk": {"penalty": 0, "details": []}
    }
    financial_penalty = 0
    text_penalty = 0
    
    # 재무 평가 차감
    try:
        finstate = dart.finstate(corp_code, '2025', reprt_code='11011')
        if finstate is not None and not finstate.empty:
            def clean_amt(val): return float(str(val).replace(',', '')) if not pd.isna(val) else 0
            liab_row = finstate[finstate['account_nm'] == '부채총계']
            eqty_row = finstate[finstate['account_nm'] == '자본총계']
            op_row = finstate[finstate['account_nm'] == '영업이익']

            if not liab_row.empty and not eqty_row.empty:
                if clean_amt(eqty_row['thstrm_amount'].values[0]) > 0 and (clean_amt(liab_row['thstrm_amount'].values[0]) / clean_amt(eqty_row['thstrm_amount'].values[0])) * 100 > 200:
                    financial_penalty += 30
                    result["financial_risk"]["details"].append("부채비율 200% 초과 (-30점)")

            if not op_row.empty:
                curr_op = clean_amt(op_row['thstrm_amount'].values[0])
                if curr_op < 0:
                    financial_penalty += 40
                    result["financial_risk"]["details"].append("영업이익 적자 발생 (-40점)")
    except Exception:
        pass

    # AI 기반 공시 텍스트 평가 차감
    try:
        today = datetime.now()
        bgn_de = (today - relativedelta(months=3)).strftime('%Y%m%d') # 실시간 처리를 위해 최근 3개월로 제한
        end_de = today.strftime('%Y%m%d')

        disclosures = dart.list(corp_code, start=bgn_de, end=end_de)
        if disclosures is not None and not disclosures.empty:
            # 정정 공시 제외 전처리
            filtered_df = disclosures[~disclosures['report_nm'].str.contains(r'\[기재정정\]|\[첨부추가\]', na=False)]
            
            # API 및 서버 부하 방지를 위해 가장 최근 공시 최대 3개만 AI 검사 진행
            recent_docs = filtered_df.head(3)
            
            for _, row in recent_docs.iterrows():
                r_no = row['rcept_no']
                r_name = row['report_nm']
                
                # 원문 수집 및 전처리
                raw_xml = dart.document(r_no)
                soup = BeautifulSoup(raw_xml, 'xml')
                clean_text = re.sub(r'\s+', ' ', soup.get_text(separator=' ', strip=True))
                
                if len(clean_text) < 50:
                    continue
                    
                # 텍스트 Chunking 및 추론
                chunk_size = 500
                chunks = [clean_text[i:i+chunk_size] for i in range(0, len(clean_text), chunk_size)]
                max_neg = 0.0
                
                for chunk in chunks:
                    inputs = tokenizer(chunk, return_tensors="pt", truncation=True, max_length=512)
                    with torch.no_grad():
                        outputs = nlp_model(**inputs)
                        probs = F.softmax(outputs.logits, dim=-1)
                        neg_prob = probs[0][0].item() * 100
                        if neg_prob > max_neg:
                            max_neg = neg_prob
                
                # 80% 이상의 강력한 부정 확률이 나오면 패널티 부과
                if max_neg >= 80.0:
                    penalty = 40
                    text_penalty += penalty
                    result["text_risk"]["details"].append(f"🚨 AI 문맥 위험 감지 (-{penalty}점): {r_name} (Risk: {max_neg:.1f}%)")
                    
    except Exception as e:
         pass

    # 최종 스코어 및 등급 산출
    result["financial_risk"]["penalty"] = financial_penalty
    result["text_risk"]["penalty"] = text_penalty
    result["total_score"] = max(0, 100 - financial_penalty - text_penalty) 

    if result["total_score"] <= 40:
        result["grade"] = "🚨 위험 (Danger)"
    elif result["total_score"] <= 79:
        result["grade"] = "⚠️ 주의 (Caution)"
    else:
        result["grade"] = "✅ 안전 (Safe)"

    return result

@app.get("/api/risk/{search_query}")
def get_risk_score(search_query: str):
    if mapping_df.empty:
        raise HTTPException(status_code=500, detail="매핑 테이블 미로드")
        
    aliases = {"네이버": "NAVER", "케이티": "KT", "에스케이": "SK", "엘지": "LG"}
    refined_query = aliases.get(search_query, search_query)

    if refined_query.isdigit() and len(refined_query) == 6:
        matches = mapping_df[mapping_df['stock_code'] == refined_query]
    else:
        matches = mapping_df[mapping_df['corp_name'].str.contains(refined_query, case=False, na=False)]
    
    if matches.empty:
        raise HTTPException(status_code=404, detail="일치하는 상장사가 없습니다.")
        
    exact_match = matches[matches['corp_name'] == refined_query]
    target_corp = exact_match.iloc[0] if not exact_match.empty else matches.iloc[0]
    
    return calculate_total_risk(target_corp['corp_name'], str(target_corp['corp_code']).zfill(8))
# 📊 기업 공시 기반 투자 리스크 탐지 서비스 (Investment Risk Detector)

## 1. 프로젝트 배경 및 문제 정의
- **Problem:** 기업의 공시와 재무 정보는 방대하여, 개인 투자자가 중요한 위험 변화를 실시간으로 파악하기 어려움.
- **Solution:** DART 공시 및 재무 데이터를 자동 수집하고, 룰베이스 및 ML(기계학습) 모델을 통해 기업별 위험도(Risk Score)를 평가하여 대시보드 형태로 제공.

## 2. 주요 기능
* **데이터 자동 수집 파이프라인:** OpenDART 및 KRX API를 활용한 주요 기업 공시/재무 데이터 수집.
* Rule-based 위험 공시 1차 필터링 로직 구현 완료

## 3. 디렉토리 구조
investment-risk-detector/

├── data/              # 데이터 적재 폴더 (git ignore)

├── docs/              # 기획 및 트러블슈팅 문서

├── notebooks/         # EDA 및 모델링 실험 (Jupyter)

└── README.md
# 주식모임 연구소

일요일 주식모임에서 시장 해석, 주도섹터, 기업 분석, 공동 관심종목, 회의록을 한곳에 축적하는 Flask 웹앱입니다.

## 핵심 기능

- 시장 온도계: 지수·수급·거래대금과 시장 해석 기록
- 주도주 레이더: 섹터 강도, 상태, 대표 종목과 다음 확인사항 관리
- 기업 한 장 분석: 투자논리·상승 촉매·위험·실적·수급·밸류·차트 기록
- 공동 관심종목: 회원별 관심 이유와 상태 공유, CSV 내려받기
- 모임 기록: 결론과 다음 주 확인사항 축적

## PC에서 실행

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

브라우저에서 `http://localhost:5000`으로 접속합니다.

## Render 배포

압축을 푼 뒤 이 폴더 안의 파일들을 GitHub 저장소 최상단에 올립니다. Render에서 Web Service로 연결하면 `render.yaml` 또는 아래 설정을 사용할 수 있습니다.

- Build Command: `pip install -r requirements.txt`
- Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
- Health Check Path: `/healthz`

무료 Render 서버는 재시작되면 기본 SQLite 파일이 사라질 수 있습니다. 장기 운영 시 영구 디스크를 연결하고 환경변수 `DB_PATH=/var/data/stock_lab.db`를 지정하거나 외부 데이터베이스로 이전해야 합니다.

## 현재 범위

실제 시장 수치와 종목 가격은 사용자가 확인한 값만 입력하도록 만들었습니다. 자동 시세조회, 회원 로그인, 수정 이력 및 권한 분리는 아직 포함하지 않았습니다.

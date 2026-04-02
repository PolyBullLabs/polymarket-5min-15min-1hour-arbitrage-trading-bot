# Copy Trading Bot

Part of [copy-trading-bot-hub](https://github.com/sinusflow/copy-trading-bot-hub). Clone: `git clone https://github.com/sinusflow/copy-trading-bot-hub.git` then `cd copy-trading-bot-hub/Binance-Bybit-Copy-Trding-Bot`.

> Multi-exchange copy trading bot that mirrors pro traders' strategies in real-time

암호화폐 거래소 API를 활용하여 프로 트레이더의 매매 전략을 실시간으로 복사하고 자동 실행하는 트레이딩 봇입니다.

---

## 주요 기능

- **실시간 전략 복사** — 프로 트레이더의 매수/매도를 WebSocket으로 실시간 추적
- **자동 주문 실행** — 각 사용자 계정에 맞춰 자동으로 주문 및 포트폴리오 관리
- **위험 관리** — 레버리지, 손절(Stop-Loss), 최대 거래량 제한
- **실시간 알림** — Telegram/Discord 연동으로 거래 내역 즉시 알림
- **멀티 거래소** — Binance, Bybit 등 복수 거래소 동시 지원

## 아키텍처

```
┌─────────────┐     WebSocket      ┌──────────────────┐
│  Pro Trader  │ ─────────────────→ │   Master Server   │
│  (Exchange)  │                    │  (master.py)      │
└─────────────┘                    └────────┬─────────┘
                                            │
                              ┌─────────────┼─────────────┐
                              ▼             ▼             ▼
                     ┌──────────┐  ┌──────────┐  ┌──────────┐
                     │ Follower │  │ Follower │  │ Follower │
                     │ Account 1│  │ Account 2│  │ Account 3│
                     └──────────┘  └──────────┘  └──────────┘
```

## 기술 스택

| 구분 | 기술 |
|------|------|
| Language | Python |
| Exchange API | Binance API, Bybit API |
| Real-time | WebSocket |
| Web Dashboard | HTML, Flask |
| Security | python-dotenv |

## 프로젝트 구조

```
copy-treading/
├── master.py            # 마스터 트레이더 전략 추적
├── followers.py         # 팔로워 계정 주문 실행
├── bittuth.py           # Bithumb 거래소 연동
├── bittus_follower.py   # Bithumb 팔로워 로직
├── server.py            # 웹 대시보드 서버
├── static/              # 프론트엔드 리소스
├── requirements.txt     # Python 의존성
└── .gitignore
```

## 실행 방법

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정 (.env)
BINANCE_API_KEY=your_key
BINANCE_SECRET_KEY=your_secret

# 실행
python master.py
```

## 배운 점

- 복수 거래소 API 연동 및 차이점 처리
- WebSocket 기반 실시간 데이터 처리와 동시성 문제 해결
- 자동화된 포트폴리오 관리 시스템 설계
- API 키 보안 관리 및 Rate Limit 핸들링

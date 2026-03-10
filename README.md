<div align="center">

<img src="https://capsule-render.vercel.app/api?type=venom&height=220&color=0:0c1228,50:1a1060,100:070b18&text=OptiTrade&fontSize=52&fontColor=f0f4ff&fontAlignY=45&desc=Multi-Agent%20F%26O%20Trading%20System%20%E2%80%A2%20Nifty50&descAlignY=68&descSize=16&descColor=8b98b8&animation=twinkling&stroke=6366f1&strokeWidth=1" width="100%"/>

<p>
  <img src="https://img.shields.io/badge/Status-LIVE%20BETA-2dd4bf?style=for-the-badge&labelColor=0c1228"/>
  <img src="https://img.shields.io/badge/Version-v0.1-6366f1?style=for-the-badge&labelColor=0c1228"/>
  <img src="https://img.shields.io/badge/Infra-AWS%20ap--south--1-f5c842?style=for-the-badge&logo=amazonaws&logoColor=f5c842&labelColor=0c1228"/>
  <img src="https://img.shields.io/badge/Market-Nifty50%20F%26O-a855f7?style=for-the-badge&labelColor=0c1228"/>
</p>

</div>

---

## What is OptiTrade?

OptiTrade is a **production-grade multi-agent AI system** for Nifty50 Futures & Options trading. Specialised AI agents collaborate in real time — scanning options chains, monitoring Open Interest shifts, analysing Implied Volatility, and synthesising risk-calibrated trade signals.

Part of **[NexAlpha](https://legitscarf.github.io/nexalpha.github.io/)** — bringing institutional-grade AI intelligence to Indian markets.

---

## How It Works

```
Market Data Feed
      │
      ▼
┌─────────────────────────────────────────────────────┐
│                  OptiTrade Engine                   │
│                                                     │
│  ┌───────────┐  ┌───────────┐  ┌────────────────┐  │
│  │  Scanner  │  │    OI     │  │  IV Monitor    │  │
│  │  Agent    │→ │  Analyst  │→ │  Agent         │  │
│  └───────────┘  └───────────┘  └────────────────┘  │
│                        │                            │
│                        ▼                            │
│              ┌──────────────────┐                   │
│              │  Signal Synthesis│                   │
│              │  Agent           │                   │
│              └──────────────────┘                   │
└─────────────────────────────────────────────────────┘
      │
      ▼
  Trade Signal Output
```

| Agent | Role |
|:------|:-----|
| **Scanner Agent** | Scans live options chain across strikes and expiries |
| **OI Analyst** | Monitors Open Interest buildup and unwinding patterns |
| **IV Monitor** | Tracks Implied Volatility percentile and skew |
| **Signal Agent** | Synthesises inputs into risk-calibrated trade signals |

---

## Tech Stack

<div align="center">

![CrewAI](https://img.shields.io/badge/CrewAI-0c1228?style=for-the-badge&logo=robot-framework&logoColor=f5c842)
![Python](https://img.shields.io/badge/Python-0c1228?style=for-the-badge&logo=python&logoColor=3776ab)
![Streamlit](https://img.shields.io/badge/Streamlit-0c1228?style=for-the-badge&logo=streamlit&logoColor=ff4b4b)
![AWS EC2](https://img.shields.io/badge/AWS%20EC2-0c1228?style=for-the-badge&logo=amazonaws&logoColor=f5c842)
![Jenkins](https://img.shields.io/badge/Jenkins-0c1228?style=for-the-badge&logo=jenkins&logoColor=d33833)
![Docker](https://img.shields.io/badge/Docker-0c1228?style=for-the-badge&logo=docker&logoColor=2496ed)

</div>

---

## Infrastructure

```yaml
cloud       : AWS ap-south-1 (Mumbai)
compute     : EC2 with Auto Scaling Groups
load_balancer: Application Load Balancer
ci_cd       : Jenkins + GitHub Webhooks
process_mgmt: systemd
security    : IAM roles · Environment isolation · Secrets management
```

---

## Key Features

- **Multi-agent orchestration** — specialised agents handle distinct analytical tasks in parallel
- **Real-time options chain analysis** — live OI, IV, PCR, and Greeks monitoring
- **Risk-calibrated signals** — signals weighted by market context and volatility regime
- **Production CI/CD** — automated deployments via Jenkins and GitHub webhooks
- **24/7 uptime** — systemd-managed services on AWS with auto-recovery

---

## Status & Roadmap

| Milestone | Status |
|:----------|:------:|
| Core multi-agent architecture | ✅ Done |
| AWS production deployment | ✅ Done |
| CI/CD pipeline | ✅ Done |
| Live options chain feed | ✅ Done |
| V2 — Backtesting engine | 🔄 In Progress |
| V2 — Strategy builder UI | 🔄 In Progress |
| Mobile alerts integration | 📋 Planned |

---

<div align="center">

[![Visit OptiTrade](https://img.shields.io/badge/Visit%20OptiTrade-Live%20App-6366f1?style=for-the-badge&labelColor=0c1228)](http://optitrade-alb-1721764571.ap-south-1.elb.amazonaws.com/)
&nbsp;
[![NexAlpha](https://img.shields.io/badge/NexAlpha-Website-f5c842?style=for-the-badge&labelColor=0c1228)](https://legitscarf.github.io/nexalpha.github.io/)
&nbsp;
[![Built By](https://img.shields.io/badge/Built%20by-Arpan%20Mallik-2dd4bf?style=for-the-badge&labelColor=0c1228)](https://github.com/legitscarf)

<br/>

> ⚠️ **Beta Notice:** OptiTrade v0.1 is in active development. Signals are for informational purposes only and do not constitute financial advice.

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:070b18,50:0c1228,100:111827&height=80&section=footer" width="100%"/>

</div>

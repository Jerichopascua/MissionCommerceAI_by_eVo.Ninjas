# 🚀 Problem Statement: MissionCommerce AI + Sim.PesoWeb

**Team Evo.Ninjas** | **AMD Developer Hackathon: Act III** | **Track 3: Reinvent Commerce**

---

## 🎯 The Organizers' Challenge

> *"Retailers have product data, transactions, inventory, reviews, support conversations, and marketing results. These sources are often disconnected, which makes it difficult to turn them into useful decisions. Build a product that helps a business attract, serve, convert, or retain customers."*

---

## 💡 Our Problem Statement

**Retail businesses manage stores by product, not by what customers are trying to do 🛍️, and they find out about operational leaks only after money is gone 💸. Neither can be tested safely at scale before it reaches real stores 🧪.**

This breaks into three core problems for one target ecosystem.

### 👥 Target Users & Ecosystem

| User Role | Their Situation |
| :--- | :--- |
| **🏬 Retail Owner or Manager**<br>*(Convenience, grocery, pharmacy, parts shops, multi-branch chains)* | Runs 1 to $N$ branches on a POS/ERP. Has sales, stock, cash, and supplier data, but no unified system connects it into proactive operational decisions. |
| **💻 POS/ERP Provider**<br>*(PesoWeb, our SaaS platform)* | Sells to thousands of tenants and cannot test every edge case, customer volume surge, or business type before customers hit it in production. |

---

## 🔍 Detailed Problem Breakdown

### 🛒 Problem 1: Stores are managed by product, not by customer mission
* A shopper at 6:00 PM is on an **"After-Work Top-Up"** mission 🌆.
* A shopper at 7:00 AM is on a **"Grab-and-Go Breakfast"** mission 🌅.
* Product-level reports hide these intent drivers. As a result, stocking, pricing, and bundling decisions are purely guessed. Furthermore, sales, inventory, reviews, and support data sit in disconnected silos.

### 💸 Problem 2: Operational leaks are detected too late
* Cash variances at close 💵, mismatched shelf inventory 📦, unsold expired stock ⏰, abnormal refunds, and short delivery shipments represent huge retail margin losses.
* Basic POS alerts catch simple thresholds (e.g., low stock), but subtle operational leaks are noticed only after the loss occurs, leaving the root cause ambiguous (*"Is it theft, operational error, or process failure?"*).

### 🧪 Problem 3: Static mock data fails to test retail software under real conditions
* Static mock data cannot reproduce human habits, repeat customer behavior, sudden demand surges, supplier bottlenecks, or cashier cash-out anomalies.
* Development teams cannot answer: *"If this were a real live business, would our system catch operational leaks, and could it sustain peak volume?"*

---

## ⚡ Our Solution

We built two tightly integrated systems:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      🤖 SIM.PESOWEB (Synthetic World)                   │
│   Simulated Business Owners 🏪 ───► Live PesoWeb APIs ◄─── Virtual Shoppers 🛒  │
│   (Mode 1: Quick Sim ⚡  |  Mode 2: Day-to-Day 📆  |  Mode 3: Scenario 🧪)  │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼ (Telemetry Stream)
┌─────────────────────────────────────────────────────────────────────────┐
│                     🧠 MISSIONCOMMERCE.AI (Intelligence)                │
│   • Mission Intent Classifier 🎯      • PyTorch ML Demand Forecasting 📈 │
│   • vLLM Incident Investigator 🔎    • Commercial Recommendation Engine 💡│
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   🔥 AMD INSTINCT GPU HARDWARE (ROCm)                   │
│          vLLM Engine ⚡ PyTorch Pipeline ⚡ Accelerated Event Stream        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1. 🌐 Sim.PesoWeb: A Synthetic Retail World
* **Virtual Business Owners**: Sign up to the real PesoWeb SaaS, select plans, open branches, hire staff, and load product lines.
* **Persistent Customer Agents**: Thousands to millions of synthetic customer personas with distinct behavioral archetypes shop across branches.
* **Three Simulation Modes**:
  * ⚡ **Quick Sim**: Fast-forward simulation at high scale to test volume and long-term trends.
  * 📆 **Day-to-Day**: Virtual user agents operate the real PesoWeb POS/ERP system in real-time.
  * 🧪 **Scenario Sim**: Inject specific anomalies (demand spikes 📈, supplier delays 🚚, cash shortages 💵, batch expirations ⌛).

### 2. 🧠 MissionCommerce AI: Intelligence Layer
* **Mission Detection**: Identifies shopper intent from time, basket combinations, and branch signals.
* **Statistical / ML Forecasting**: Uses statistical and ML models (PyTorch) for accurate demand forecasting.
* **Proactive Recommendations**: Recommends optimized stock allocations, dynamic pricing, promotional bundles, transfers, and purchase orders.
* **vLLM Incident Investigator**: Investigates undetected operational leaks and explains root causes with structured evidence. *(Note: The LLM acts as the explainer and orchestrator—not the numerical forecasting engine).*

### 🔥 Powered by AMD ROCm Infrastructure
* **vLLM on ROCm**: High-throughput reasoning for incident investigation and narrative explanations.
* **PyTorch on ROCm**: High-performance tensor execution for demand forecasting, anomaly detection, and mission classification models.
* **Accelerated Event Generation**: Real-time throughput monitored live via `rocm-smi`.

---

## 📊 What We Measure (Hypotheses Framework)

| Loop | Metric / Measure | Method & Verification |
| :--- | :--- | :--- |
| 📈 **Growth** | Sales, Waste, and Margin (Week 0 vs. Week 3) | Same random seed run twice: Baseline vs. AI-driven actions |
| 🎯 **Growth** | Mission Detection Precision & Recall | Evaluated against simulator's ground-truth customer intents |
| 🔮 **Growth** | Forecast Error vs. Naive Baseline | Tested against a held-out simulated week |
| 🛡️ **Protection**| Detection Coverage | Percentage of injected incidents caught by POS, found by AI, or missed |
| ⚡ **Scale** | Events/Sec & Virtual-Days/Sec on AMD | Measured live on aggregated AMD ROCm lanes |

---

## 🏆 Why This Fits Track 3 (Reinvent Commerce)

* **🏢 Real Merchant Problem**: Directly addresses cash variance, shrinkage, expiry loss, and mission-blind inventory management.
* **💼 Useful Commercial Actions**: Delivers actionable recommendations for inventory rebalancing, dynamic bundling, transfers, and purchase orders.
* **🎯 Relevant Context**: Tailored to convenience stores, grocery/pharmacy chains, and auto parts verticals.
* **📈 Measurable Impact**: Benchmarks performance with Week 0 vs. Week 3 KPI delta tracking.
* **⚙️ Proper AI Architecture**: Separates numeric ML forecasting from LLM reasoning and orchestration.
* **🔥 AMD Hardware Utilization**: Showcases vLLM and PyTorch execution on AMD Instinct hardware via ROCm.

---

## 📝 Scope & Honest Limits

* 🧪 **Simulation Bounds**: Synthetic data proves detection capabilities and scale performance; it does not predict real-world macro markets.
* ⚡ **Quick Sim Aggregation**: High-velocity runs use aggregated pipeline shortcuts and are explicitly labeled as such.
* 🤖 **Uncalibrated Archetypes**: Customer and owner populations are generated from LLM archetypes with structural constraints, not calibrated against proprietary real-world datasets.
* ⚖️ **Neutral Terminology**: Cash discrepancies are reported strictly as *"unexplained cash variance"*, never as definitive theft claims.
* 🚫 **Out of Scope**: Online reservation pickup, physical work orders, customer complaint ticketing, supplier procurement quality grading, and serial number warranty tracking.

---

## 📄 Submission Drafts

### ⏱️ Short Description
> MissionCommerce AI detects customer intent and hidden operational leaks in retail stores, while Sim.PesoWeb validates performance by running the actual SaaS platform inside an AI-generated synthetic retail world powered by AMD ROCm.

### 📜 Long Description
> Retailers hold extensive sales, stock, and cash data, yet manage stores by product SKUs rather than customer missions. Operational leaks—such as cash variance, inventory shrinkage, and expired stock—are frequently discovered long after financial losses occur. Static mock data cannot simulate these dynamic store conditions. 
> 
> To solve this, we built **Sim.PesoWeb**, a synthetic retail world where simulated merchants register on our production PesoWeb POS/ERP, configure branches, hire staff, and process transactions from persistent virtual customer personas. The simulator operates in three modes: **Quick Sim** (scaled fast-forwarding), **Day-to-Day** (real API transactions), and **Scenario Sim** (targeted anomaly injections).
> 
> On top of this world runs **MissionCommerce AI**. It identifies customer shopping missions, forecasts demand using statistical/ML models, recommends commercial actions, and investigates operational leaks. Every injected scenario is benchmarked across POS alerts, AI detection, or missed incidents. Both the PyTorch models and the vLLM investigator run on AMD Instinct accelerators via ROCm with live performance monitoring.
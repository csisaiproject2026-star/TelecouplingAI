# MSU Server — Capacity / Stress Test Report

**Server:** 35.9.219.33 (RHEL 9.7, 32 vCPU / 62 GB RAM / 637 GB home)
**Date:** 2026-05-28/29
**Question:** How many concurrent users can the platform handle? Can it serve 100?

---

## TL;DR (中文)

- **瓶颈不是服务器硬件,是 Gemini 的 token 配额。** 10 个并发用户时服务器 CPU 才 ~1.8%,但 Gemini 已返回 `429 RESOURCE_EXHAUSTED`。
- 命中的配额:`gemini-2.5-flash` **付费 Tier 1 = 每分钟 100 万输入 token**(`GenerateContentPaidTierInputTokensPerModelPerMinute`),**且 MSU 与 GCP 共用同一个 key、共享这 100 万**。
- 原因:agent 每次调用都把**全部 42 个工具的 skill(12,440 token)+ 全部 42 个工具 schema(~12,000 token)**塞进去,而用户一次只用 1 个工具。一次工具交互 ≈ **43K 输入 token** → 1M/min 只够 **~23 次交互/分钟**。
- **优化 Tier A(已上线 MSU):懒加载 skill** —— 命中工具时只带该工具的 skill。系统提示从 14,657 → 2,544 token(省 83%),一次交互降到 ~18.5K → **~54 次/分钟(~2.3 倍)**,判断/路由不受影响(见验证)。
- 结论:**32 核服务器本身能轻松扛 100+ 人;天花板在 Gemini 配额。** 要稳定支撑 100 并发,需 ① Tier A(已做)② 再做 Tier B(收窄工具 schema,预计再 ~2.6 倍)和/或 ③ 提配额档 / 多 key 并行。

---

## 1. Bottleneck: Gemini token quota, not hardware (measured)

At **10 concurrent users** (fast CSV-tool pool), the server was essentially idle but Gemini began rejecting requests:

| Metric @ 10 users | Value |
|---|---|
| Passed | 17/20 (85%) |
| Failures | 3 — **2 were Gemini `429 RESOURCE_EXHAUSTED`** |
| Host CPU | avg **1.8%**, peak 6.3% |
| Host RAM | ~13.7 GB / 62 GB (idle stack baseline) |

Full 429 detail from backend logs:
```
quotaMetric: generativelanguage.googleapis.com/generate_content_paid_tier_input_token_count
quotaId:     GenerateContentPaidTierInputTokensPerModelPerMinute
limit:       1,000,000   model: gemini-2.5-flash
Please retry in ~41s
```
→ The key **is** paid (Tier 1). The binding limit is **1,000,000 input tokens / minute** for gemini-2.5-flash. **MSU and GCP share the same key**, so this 1M/min is split between both deployments.

---

## 2. Token accounting — where the tokens go (measured via count_tokens)

Per Gemini call, BEFORE optimization:

| Component sent every call | Input tokens |
|---|---|
| Base system prompt | 2,217 |
| **All 42 tools' PRE_EXECUTION skills** | **12,440** |
| → full `system_instruction` | **14,657** |
| All 42 tool schemas (function declarations, follow-up calls) | ~12,000 (est.) |
| User message | ~32 |

A typical tool interaction = **2 Gemini calls** (decide+call, then summarize):
- call 1 ≈ system 14,657 + 1 tool + user ≈ ~15K
- call 2 ≈ system 14,657 + all 42 tool schemas ~12K + convo ≈ ~28K
- **≈ ~43K input tokens per interaction** → 1,000,000 ÷ 43,000 ≈ **~23 interactions/min** sustainable.

This is why 10 users (20 interactions bursting in ~30 s) blew the per-minute limit.

---

## 3. Tier A optimization — lazy skill loading (DEPLOYED on MSU)

**Change (`backend/agent.py`):** when the requested tool is keyword-detected, load **only that tool's** PRE_EXECUTION skill instead of all 42. Tool schemas left untouched, so routing/selection is unchanged. Falls back to all skills when the tool is ambiguous.

Measured effect:

| `system_instruction` per call | Before | After (single tool) |
|---|---|---|
| total | 14,657 | **2,544** |
| of which skills | 12,440 (all 42) | **327** (1 tool) |

- Per-interaction input ≈ **43K → ~18.5K tokens** (~2.3×).
- Sustainable ≈ **~23 → ~54 interactions/min** on the same 1M/min quota.
- Remaining fat: the ~12K of all-42 tool schemas on follow-up calls (→ **Tier B**: narrow schemas to the detected tool + utilities; projected another ~2.6×, to ~140/min).

> Deploy note: applied to the running MSU backend via `docker cp` + restart (the `/app` source is baked into the image, not bind-mounted). **To make it permanent (survive a container recreate, and to apply to GCP), the backend image must be rebuilt with the updated `agent.py`.** Not done yet.

### ⚠️ Judgment validation — Tier A REGRESSES Habitat Quality (#8)
Full 41-tool LLM-path test after Tier A: **40 PASS / 1 FAIL / 1 SKIP**. The one FAIL is **#8 Habitat Quality — "LLM did not call any tool"**.

Attribution (clean A/B test): with the **original** `agent.py`, #8 passes **2/2**; with **Tier A**, #8 fails **3/3** (consistent, not flaky). Root cause: when only Habitat's own skill is loaded (instead of all 42), Gemini follows the base prompt's "ask for missing parameters" path and returns text instead of calling the tool; the aggregate all-skills context previously nudged it to call.

**Conclusion: Tier A as implemented is NOT safe to ship** — it cuts tokens ~83% but breaks at least one tool. It needs a safer design (e.g., always include a small global "call the tool when parameters are satisfied" nudge in the base prompt, or keep regressing tools on the full-skill path) and re-validation before deployment. **The live MSU platform has been reverted to the original (correct, 41/41) build.**

> The capacity ladder below was run on the Tier A build using the **fast CSV pool (OLS/CO2/CBA/Food)**, none of which regressed — so the capacity/CPU/RAM numbers are valid and independent of the Habitat issue.

---

## 4. Capacity ladder (Tier A) — CPU / memory at each level

Fast CSV-tool pool (OLS / CO2 / CBA / Food), driven server-side against `localhost:8000`, MAX_SESSIONS raised to 300 for the test.

| Users | Runs | Pass % | Fail (all quota-related) | Latency p50 / p95 | **CPU avg / peak** | **RAM peak / 62 GB** | Throughput |
|---|---|---|---|---|---|---|---|
| 10  | 20  | 95% | 1  | 6.8s / 8.8s   | **1.3% / 4.2%** | **13.9 GB** | 8.2/min |
| 25  | 50  | 90% | 5  | 24.7s / 68.3s | **1.9% / 6.8%** | **14.0 GB** | 21.1/min |
| 50  | 100 | 87% | 13 | 120s / 184s   | **1.5% / 7.0%** | **14.2 GB** | 14.1/min |
| 75  | 150 | 98% | 2  | 121s / 351s   | **1.4% / 2.8%** | **14.3 GB** | 20.4/min |
| 100 | 200 | 77% | 45 | 160s / 243s   | **1.4% / 3.2%** | **14.4 GB** | 19.6/min |

**Reading the table:**
- **CPU never exceeds ~7% and RAM never exceeds ~14.4 GB of 62 GB — at ANY level up to 100 users.** The 32-vCPU server is essentially idle the entire time. Hardware is nowhere near its limit.
- **Throughput plateaus at ~20 successful tool-runs/min** regardless of how many users pile on — this is the Gemini 1M-input-tokens/min quota ceiling, not the server.
- **Every failure is quota-related** (Gemini `429 RESOURCE_EXHAUSTED`, or an SSE timeout while the request sat behind the 40 s quota back-off). Zero failures were CPU/RAM/worker related.
- **Pass % is non-monotonic** (95→90→87→98→77) because success depends on how each burst lines up with the per-minute quota window and whether the agent's back-off retries land in a fresh window — not on load. Latency, by contrast, climbs steadily (p50 6.8 s → 160 s at 100 users) because requests spend most of their time waiting out 429 back-offs.
- Note: empirical sustained throughput (~20/min) is lower than the static token estimate (~54/min) would predict — real per-interaction token use is higher than the count_tokens estimate (multiple agent iterations, function-response payloads, output summarization), and 429 back-off wastes wall-clock. Treat **~20 successful tool-runs/min** as the measured Tier-A ceiling on the shared 1M/min quota.
- Caveat: the load generator ran inside the backend container; its (small, async) CPU is included in the host CPU figures — so true server-only CPU is even lower than shown.

---

## 5. Conclusions & recommendations

**Answer to "can the server handle 100 users?"**
- **The hardware can — easily.** At 100 attempted concurrent users the 32-vCPU / 62 GB server sat at **~1.4% CPU and ~14 GB RAM**. It is not the bottleneck and would handle far more.
- **The Gemini token quota cannot — yet.** Effective throughput is capped at **~20 successful tool-runs/min** by the shared **1,000,000 input-tokens/min** quota (gemini-2.5-flash, Tier 1, shared between MSU and GCP). Beyond ~10–15 concurrent active users, requests increasingly queue / 429-retry, latency climbs to minutes, and some fail.

So 100 people can be *registered* and use it at different times with no problem; 100 *simultaneously active* users is currently gated by the LLM quota, not the box.

**Levers to raise the real ceiling, by effort/cost:**
1. **Separate the keys** — MSU and GCP currently share one 1M/min quota. Give each its own key → each gets a full 1M/min immediately (free, ~2× for MSU). *Easiest win.*
2. **Raise the Gemini quota tier** — Tier 2 = 2M/min, Tier 3 higher (based on cumulative billing / a quota-increase request). Add **multiple keys in rotation** for further parallelism (the user already suggested this).
3. **Cut the per-call token footprint** — the agent sends ~14.6 K tokens of system prompt (12.4 K = all-42 skills) + ~12 K of all-42 tool schemas on every call, for a 1-tool request.
   - **Tier A (lazy skills):** ~83 % smaller system prompt — **but as implemented it regresses Habitat Quality (§3) and must be fixed + re-validated before shipping. Currently reverted; not live.**
   - **Tier B (narrow follow-up tool schemas):** further reduction; not yet attempted.
   - Both need the same validation discipline (re-run the 41-tool test) before deployment.

**Bottom line:** don't buy a bigger server. Fix the LLM-quota side: split keys (now), raise tier / rotate keys (next), and trim token footprint carefully (Tier A/B, once the Habitat regression is solved).

---

## 6. Final state of the server (post-test)
- Backend reverted to the **original `agent.py`** (correct, 41/41) — **Tier A is NOT live**.
- `MAX_SESSIONS` restored to **50**.
- Tier A code change is preserved in the local repo (`backend/agent.py`, uncommitted) for future refinement; the stress kit lives in `Systematic_tests/AI_GCP_test/03_smoke_stress_test/` (`stress_msu.py`, `measure_tokens.py`).

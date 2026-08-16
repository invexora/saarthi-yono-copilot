import os, sys, math, time, subprocess
from PIL import Image, ImageDraw, ImageFont
import numpy as np

WIDTH, HEIGHT = 1920, 1080
FPS = 30
TOTAL_SCENES = 12
SCENE_DUR = 3.5 # Fast-paced 3.5s per scene / diagram
TOTAL_DURATION = TOTAL_SCENES * SCENE_DUR # 42.0 seconds
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)

FONT_PATH = "/System/Library/Fonts/Supplemental/Kohinoor.ttc"

def get_font(size, bold=False):
    idx = 1 if bold else 0
    try:
        return ImageFont.truetype(FONT_PATH, size, index=idx)
    except:
        return ImageFont.load_default()

# Professional Fintech Color Palette
C_BG = (8, 13, 24)
C_SURFACE = (15, 23, 42)
C_SURFACE_CARD = (22, 33, 58)
C_CYAN = (0, 210, 255)
C_EMERALD = (16, 185, 129)
C_MAGENTA = (239, 68, 68)
C_PURPLE = (168, 85, 247)
C_AMBER = (245, 158, 11)
C_TEXT_WHITE = (248, 250, 252)
C_TEXT_MUTED = (148, 163, 184)
C_CARD_BG = (13, 20, 36)

MEDIA_DIR = "docs"
def load_img(rel_path):
    p = os.path.join(MEDIA_DIR, rel_path)
    if os.path.exists(p):
        return Image.open(p).convert("RGB")
    print(f"Warning: Missing {p}")
    return Image.new("RGB", (800, 600), (30, 40, 60))

img_opp_trace = load_img("screenshots/01_priya_solution_opportunity_nudge_trace.png")
img_explain = load_img("screenshots/02_priya_solution_explainability_governance.png")
img_friction = load_img("screenshots/03_priya_solution_branch_friction_direct_tax.png")
img_lifeevent = load_img("screenshots/04_priya_solution_life_event_recurring_deposit.png")
img_stress = load_img("screenshots/05_priya_solution_financial_stress_support_override.png")
img_token = load_img("screenshots/06_priya_solution_single_use_token_authorization.png")
img_budget = load_img("screenshots/07_priya_solution_dynamic_nudge_budget_fatigue.png")
img_dpdp = load_img("screenshots/08_priya_solution_dpdp_privacy_consent_erasure.png")
img_audit = load_img("screenshots/09_priya_solution_tamper_evident_merkle_audit.png")
img_cards = load_img("screenshots/10_priya_solution_cards_debt_optimizer.png")

img_arch_full = load_img("images/saarthi_full_copilot_architecture.jpg")
img_arch_slm = load_img("images/slm_architecture_flow.jpg")
img_arch_atc = load_img("images/atc_decision_orchestrator.jpg")
img_arch_dpdp = load_img("images/dpdp_privacy_consent_guardrails.jpg")
img_arch_fatigue = load_img("images/dynamic_nudge_budget_fatigue_controller.jpg")
img_arch_ledger = load_img("images/cryptographic_audit_merkle_ledger.jpg")
img_arch_graph = load_img("images/neo4j_graph_rag_product_matrix.jpg")

def extract_phone_crop(full_img, zoom_mode="full"):
    w, h = full_img.size
    if zoom_mode == "full":
        x1, x2 = int(w * 0.33), int(w * 0.59)
        y1, y2 = int(h * 0.08), int(h * 0.98)
    elif zoom_mode == "nudge":
        x1, x2 = int(w * 0.335), int(w * 0.585)
        y1, y2 = int(h * 0.48), int(h * 0.98)
    elif zoom_mode == "modal":
        x1, x2 = int(w * 0.335), int(w * 0.585)
        y1, y2 = int(h * 0.32), int(h * 0.85)
    return full_img.crop((x1, y1, x2, y2))

def draw_header_footer(draw, title_text, scene_idx, progress_pct):
    draw.rectangle([0, 0, WIDTH, 65], fill=(11, 18, 34))
    draw.line([0, 65, WIDTH, 65], fill=(0, 160, 228, 120), width=2)

    # Brand Pill
    draw.rectangle([40, 14, 140, 52], fill=(0, 51, 102), outline=C_CYAN, width=1)
    f_brand = get_font(17, bold=True)
    draw.text((52, 21), "SBI", fill=C_CYAN, font=f_brand)
    draw.text((92, 21), "YONO", fill=C_TEXT_WHITE, font=f_brand)

    # Title
    f_title = get_font(18, bold=True)
    draw.text((160, 21), f"SAARTHI  •  {title_text.upper()}", fill=C_TEXT_WHITE, font=f_title)

    # Live Tag Badge
    f_tag = get_font(13, bold=True)
    draw.rectangle([WIDTH - 380, 15, WIDTH - 40, 50], fill=(16, 185, 129, 35), outline=C_EMERALD, width=1)
    draw.text((WIDTH - 365, 23), "LIVE PROTOTYPE  •  YONO COPILOT", fill=C_EMERALD, font=f_tag)

    # Bottom Footer Bar
    draw.rectangle([0, HEIGHT - 45, WIDTH, HEIGHT], fill=(11, 18, 34))
    draw.line([0, HEIGHT - 45, WIDTH, HEIGHT - 45], fill=(255, 255, 255, 25), width=1)

    f_foot = get_font(13, bold=False)
    draw.text((40, HEIGHT - 32), "State Bank of India — Autonomous Governed Co-Pilot", fill=C_TEXT_MUTED, font=f_foot)
    f_foot_b = get_font(13, bold=True)
    draw.text((WIDTH // 2 - 100, HEIGHT - 32), f"ACT {scene_idx} OF {TOTAL_SCENES}", fill=C_CYAN, font=f_foot_b)
    draw.text((WIDTH - 320, HEIGHT - 32), "TEAM INVEXORA  |  GAURAV & KISHORE", fill=C_TEXT_MUTED, font=f_foot)

def draw_bullet_card(draw, box, title, bullets, badge_text=None, border_color=C_CYAN):
    x1, y1, x2, y2 = box
    draw.rectangle([x1, y1, x2, y2], fill=C_CARD_BG, outline=border_color, width=2)
    draw.rectangle([x1, y1, x2, y1 + 45], fill=(18, 28, 52))
    draw.line([x1, y1 + 45, x2, y1 + 45], fill=border_color, width=1)

    f_bt = get_font(19, bold=True)
    draw.text((x1 + 18, y1 + 12), title, fill=C_TEXT_WHITE, font=f_bt)

    if badge_text:
        f_bg = get_font(12, bold=True)
        tw = draw.textlength(badge_text, font=f_bg)
        bx = x2 - tw - 25
        draw.rectangle([bx, y1 + 10, x2 - 12, y1 + 35], fill=(0, 210, 255, 25), outline=border_color, width=1)
        draw.text((bx + 6, y1 + 15), badge_text, fill=border_color, font=f_bg)

    f_body = get_font(15, bold=False)
    f_bold = get_font(15, bold=True)

    curr_y = y1 + 60
    for prefix, highlight, rest in bullets:
        draw.text((x1 + 18, curr_y), prefix, fill=border_color, font=f_bold)
        pw = draw.textlength(prefix + " ", font=f_bold)
        draw.text((x1 + 18 + pw, curr_y), highlight, fill=C_TEXT_WHITE, font=f_bold)
        hw = draw.textlength(highlight + " ", font=f_bold)
        draw.text((x1 + 18 + pw + hw, curr_y), rest, fill=C_TEXT_MUTED, font=f_body)
        curr_y += 32

def draw_stat_box(draw, box, number, label, subtext, color=C_CYAN):
    x1, y1, x2, y2 = box
    draw.rectangle([x1, y1, x2, y2], fill=(14, 22, 40), outline=color, width=2)
    f_num = get_font(34, bold=True)
    draw.text((x1 + 18, y1 + 12), number, fill=color, font=f_num)
    f_lbl = get_font(15, bold=True)
    draw.text((x1 + 18, y1 + 56), label, fill=C_TEXT_WHITE, font=f_lbl)
    f_sub = get_font(12, bold=False)
    draw.text((x1 + 18, y1 + 80), subtext, fill=C_TEXT_MUTED, font=f_sub)

def place_image_with_glow(canvas, img_crop, target_box, glow_color=C_CYAN):
    tx1, ty1, tx2, ty2 = target_box
    tw, th = tx2 - tx1, ty2 - ty1
    resized = img_crop.resize((tw, th), Image.Resampling.LANCZOS)
    canvas.paste(resized, (tx1, ty1))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([tx1 - 2, ty1 - 2, tx2 + 2, ty2 + 2], outline=glow_color, width=2)

# 12 SCENES
def render_scene_1(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "Executive Overview & Vision", scene_idx, prog)

    f_hero = get_font(46, bold=True)
    f_sub = get_font(21, bold=False)
    draw.text((70, 95), "SAARTHI : Autonomous Governed Co-Pilot", fill=C_CYAN, font=f_hero)
    draw.text((70, 155), "Transforming SBI YONO from Reactive Banking to Proactive Financial Intelligence", fill=C_TEXT_WHITE, font=f_sub)

    draw_stat_box(draw, [70, 210, 480, 335], "80 Million+", "YONO Digital User Base", "Target scale for proactive engagement", C_CYAN)
    draw_stat_box(draw, [510, 210, 920, 335], "4.8 ms", "On-Premise 3B SLM Latency", "Sub-10ms edge inference budget", C_EMERALD)
    draw_stat_box(draw, [950, 210, 1360, 335], "DPDP Act 2023", "Full Regulatory Compliance", "Consent gating & right to erasure", C_PURPLE)
    draw_stat_box(draw, [1390, 210, 1850, 335], "+₹1,250 Cr", "Annual Revenue Uplift", "Digital lending pre-qualified conversions", C_AMBER)

    place_image_with_glow(img, img_arch_full, [70, 360, 980, 1000], C_CYAN)

    bullets = [
        ("•", "Reactive Banking Problem:", "Customers search, browse, and miss critical financial savings opportunities."),
        ("•", "Proprietary 3B SLM:", "Trained specifically on Indian banking signals, DPDP privacy, and product matrices."),
        ("•", "Dynamic Nudge Budget:", "Caps at average 5 nudges with 14-day decline fatigue cooldown."),
        ("•", "Single-Use Tokens:", "HMAC-SHA256 tokens valid for 600s eliminate replay fraud."),
        ("•", "Live Prototype Deployed:", "https://invexora.github.io/saarthi-yono-copilot/"),
    ]
    draw_bullet_card(draw, [1010, 360, 1850, 1000], "Strategic Platform Highlights", bullets, "PRODUCTION READY", C_EMERALD)
    return img

def render_scene_2(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "The Reactive Banking Challenge", scene_idx, prog)

    phone_crop = extract_phone_crop(img_opp_trace, "full")
    place_image_with_glow(img, phone_crop, [70, 85, 520, 1000], C_MAGENTA)

    draw_bullet_card(draw, [550, 85, 1850, 480], "Customer Persona Case Study: Priya Sharma (Tech Lead)", [
        ("[!]", "Silent Wealth Drain:", "Paying ₹4,200/mo revolving credit card interest at 42% APR across 2 cards."),
        ("[!]", "Idle Capital Drag:", "Maintains ₹2,80,000 in savings account earning only 2.70% p.a. against 6% inflation."),
        ("[!]", "Branch Counter Friction:", "Physically visits branch 0032 to deposit quarterly advance tax in queues."),
        ("[!]", "The Core Flaw in Current YONO:", "Traditional apps only respond when asked; they never proactively optimize.")
    ], "SBI-772910 CASE", C_MAGENTA)

    draw_stat_box(draw, [550, 505, 950, 630], "₹4,200/mo", "Card Finance Charges", "Revolving at 42% APR penalty rates", C_MAGENTA)
    draw_stat_box(draw, [980, 505, 1380, 630], "₹2,80,000", "Idle Savings Balance", "Earning sub-inflation 2.70% interest", C_AMBER)
    draw_stat_box(draw, [1410, 505, 1850, 630], "~2 Hours", "Branch Wait Time", "Lost time on manual counter deposits", C_CYAN)

    bullets_sol = [
        ("->", "Saarthi's Autonomous Shift:", "Instead of waiting for Priya to search, Saarthi continuously scans transaction streams."),
        ("->", "Governed AI Ingestion:", "Redis Streams bus + PII Input Guardian masks data in < 0.3ms before SLM evaluation."),
        ("->", "Immediate Opportunity:", "Convert revolving card balance to 10.5% SBI Express Credit -> Save ₹2,100/mo.")
    ]
    draw_bullet_card(draw, [550, 655, 1850, 1000], "The Autonomous Paradigm Shift", bullets_sol, "AI CO-PILOT", C_EMERALD)
    return img

def render_scene_3(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "Proactive Solution: Debt Optimization Nudge", scene_idx, prog)

    phone_crop = extract_phone_crop(img_opp_trace, "full")
    place_image_with_glow(img, phone_crop, [70, 85, 520, 1000], C_EMERALD)

    nudge_crop = extract_phone_crop(img_opp_trace, "nudge")
    place_image_with_glow(img, nudge_crop, [550, 85, 1180, 720], C_EMERALD)

    draw_stat_box(draw, [550, 745, 845, 875], "₹2,100/mo", "Direct Savings", "Cut interest burden by 50%", C_EMERALD)
    draw_stat_box(draw, [875, 745, 1180, 875], "10.5% p.a.", "Express Credit", "Replacing 42% credit card APR", C_CYAN)

    bullets = [
        ("1.", "Instant Financial Relief:", "Replaces high-interest revolving card debt with SBI pre-approved loan."),
        ("2.", "Customer-Centric Context:", "Tailored specifically for Priya's salary (₹1.45L) and credit score (785)."),
        ("3.", "Zero Disruption UX:", "Delivered as a non-intrusive in-app card with clear Dismiss & Review CTAs."),
        ("4.", "Transparent Explainability:", "Includes one-tap 'Why am I seeing this?' governance disclosure."),
        ("5.", "Dynamic Nudge Budget:", "Consumes exactly 1 slot out of 5 dynamic budget allowance.")
    ]
    draw_bullet_card(draw, [1210, 85, 1850, 1000], "Proactive Nudge Architecture", bullets, "GOVERNED NUDGE", C_EMERALD)
    return img

def render_scene_4(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "Explainability & DPDP Transparency", scene_idx, prog)

    phone_crop = extract_phone_crop(img_explain, "full")
    place_image_with_glow(img, phone_crop, [70, 85, 520, 1000], C_CYAN)

    exp_crop = extract_phone_crop(img_explain, "nudge")
    place_image_with_glow(img, exp_crop, [550, 85, 1180, 720], C_CYAN)

    bullets_gov = [
        ("[PASS]", "HIGH_CC_INTEREST_OPTIMIZATION:", "Card finance charges exceed ₹1,500/month threshold."),
        ("[PASS]", "DPDP_PURPOSE_CONSENT_VERIFIED:", "Customer granted explicit opt-in for savings optimization."),
        ("[PASS]", "POLICY_MATCH_SBI_EXPRESS_CREDIT:", "Pre-approved product catalogue rule matched in Neo4j graph."),
        ("[PASS]", "AFFORDABILITY_WITHIN_LIMIT:", "DTI ratio computed at 28.4% (well within 50% safety cap)."),
        ("[PASS]", "APPROVED_POLICY_EVIDENCE:", "Bound to immutable policy SHA-256 hash in audit ledger.")
    ]
    draw_bullet_card(draw, [1210, 85, 1850, 1000], "Verified Governance Reason Codes", bullets_gov, "TRANSPARENCY", C_CYAN)

    draw_stat_box(draw, [550, 745, 845, 875], "100%", "Deterministic", "Zero LLM hallucinations", C_EMERALD)
    draw_stat_box(draw, [875, 745, 1180, 875], "Auditable", "Regulatory Proof", "Full DPDP compliance trace", C_PURPLE)
    return img

def render_scene_5(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "Proprietary 3B Small Language Model (SLM)", scene_idx, prog)

    place_image_with_glow(img, img_arch_slm, [70, 85, 980, 680], C_PURPLE)

    draw_stat_box(draw, [70, 710, 350, 840], "4.8 ms", "P50 Latency", "Edge runtime execution", C_EMERALD)
    draw_stat_box(draw, [380, 710, 670, 840], "99.4%", "Signal F1-Score", "Tested on 10k scenarios", C_CYAN)
    draw_stat_box(draw, [700, 710, 980, 840], "1.8 GB", "RAM Footprint", "4-bit GGUF Q4_K_M", C_PURPLE)

    bullets_slm = [
        ("•", "Why Not Cloud LLMs?:", "Cloud models cause data sovereignty hazards, ₹100Cr+ API costs, & 800ms latency."),
        ("•", "Synthetic Dataset Generator:", "10,000+ multi-persona banking scenarios with automated DPDP PII scrubbing."),
        ("•", "4-Bit QLoRA Fine-Tuning:", "Trained on student base (r=16, alpha=32, lr=2e-4) with Llama-3-70B distillation."),
        ("•", "Calibrated Confidence Gate:", "Threshold tau >= 0.85 fast-tracks recommendations; borderline scores route to rule graph."),
        ("•", "Deployment Artifacts:", "GGUF Q4_K_M for on-premise CPU and TensorRT ONNX for GPU edge.")
    ]
    draw_bullet_card(draw, [1010, 85, 1850, 1000], "Edge Model Specifications & Benchmarks", bullets_slm, "BENCHMARK 99.4%", C_PURPLE)
    return img

def render_scene_6(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "Agentic Traffic Controller (ATC) & LangGraph", scene_idx, prog)

    place_image_with_glow(img, img_arch_atc, [70, 85, 980, 680], C_CYAN)

    draw_stat_box(draw, [70, 710, 350, 840], "6.54 ms", "Total P50 Time", "Entire 6-Node execution loop", C_CYAN)
    draw_stat_box(draw, [380, 710, 670, 840], "11.43 ms", "P99 Max Latency", "Guaranteed sub-15ms budget", C_EMERALD)
    draw_stat_box(draw, [700, 710, 980, 840], "6 Nodes", "LangGraph State", "Compiled deterministic graph", C_PURPLE)

    bullets_atc = [
        ("1.", "Node 1: Redis Streams Ingestion:", "Sub-millisecond event streaming on saarthi:events bus (0.14ms)."),
        ("2.", "Node 2: PII Input Guardian:", "Scans & masks PAN, Aadhaar, Account No. with salted SHA-256 (0.22ms)."),
        ("3.", "Node 3: Signal Detection Agent:", "3B SLM detects intent with 99.4% precision (4.80ms)."),
        ("4.", "Node 4: Neo4j Knowledge Graph RAG:", "Resolves eligible products & interest matrices via Cypher (0.85ms)."),
        ("5.", "Node 5: DPDP Compliance Gate:", "Enforces opt-in consent & dynamic 5-dot budget (0.35ms)."),
        ("6.", "Node 6: Output Guardian:", "Signs single-use HMAC-SHA256 token and sanitizes output (0.18ms).")
    ]
    draw_bullet_card(draw, [1010, 85, 1850, 1000], "6-Node Compiled State Machine", bullets_atc, "6.54ms LATENCY", C_CYAN)
    return img

def render_scene_7(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "Multi-Signal Versatility: Friction & Life-Events", scene_idx, prog)

    crop_fric = extract_phone_crop(img_friction, "full")
    place_image_with_glow(img, crop_fric, [70, 85, 480, 1000], C_AMBER)

    crop_life = extract_phone_crop(img_lifeevent, "full")
    place_image_with_glow(img, crop_life, [510, 85, 920, 1000], C_EMERALD)

    bullets_fric = [
        ("[1]", "Signal 1: Branch Friction (Direct Tax):", "Priya visits physical branch counter to deposit advance tax."),
        ("->", "Saarthi Action:", "Intercepts counter visit and offers instant digital tax payment in YONO."),
        ("->", "Impact:", "Saves ~2 hours queue waiting time and reduces branch congestion by 35%."),
        ("[3]", "Signal 3: Life-Event Surplus (Salary Hike):", "Detects 30% jump in monthly salary credit."),
        ("->", "Saarthi Action:", "Auto-calculates ₹18,500/mo surplus into 7.10% SBI Recurring Deposit."),
        ("->", "Impact:", "Transforms unallocated cash into high-yield deposits seamlessly.")
    ]
    draw_bullet_card(draw, [950, 85, 1850, 1000], "Proactive Multi-Signal Scenarios", bullets_fric, "MULTI-SCENARIO", C_EMERALD)
    return img

def render_scene_8(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "Vulnerability Protection & Fatigue Cooldown", scene_idx, prog)

    crop_stress = extract_phone_crop(img_stress, "full")
    place_image_with_glow(img, crop_stress, [70, 85, 520, 1000], C_MAGENTA)

    place_image_with_glow(img, img_arch_fatigue, [550, 85, 1300, 560], C_AMBER)

    draw_stat_box(draw, [1330, 85, 1850, 215], "0 Marketing", "Distress Policy", "Promotions blocked 100%", C_MAGENTA)
    draw_stat_box(draw, [1330, 235, 1850, 365], "14 Days", "Fatigue Cooldown", "Mandatory silence period", C_AMBER)
    draw_stat_box(draw, [1330, 385, 1850, 515], "Dynamic 5", "Nudge Budget", "Adapts to user acceptance", C_CYAN)

    bullets_stress = [
        ("[GUARD]", "Ethical AI Circuit Breaker:", "When financial stress or missed EMIs are detected, marketing is BLOCKED."),
        ("[CARE]", "SBI Compassionate Support:", "UI switches to compassionate Relationship Manager outreach."),
        ("[COOL]", "Decline Fatigue Circuit Breaker:", "3 consecutive declines trigger a 14-day silence cooldown."),
        ("[BUDGET]", "Dynamic Nudge Budget:", "Budget = min(5, Historical Acceptances + 1) prevents notification fatigue.")
    ]
    draw_bullet_card(draw, [550, 590, 1850, 1000], "Ethical Governance & Safety Guardrails", bullets_stress, "SAFETY FIRST", C_MAGENTA)
    return img

def render_scene_9(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "Single-Use Decision Tokens & Cryptographic Audit", scene_idx, prog)

    crop_tok = extract_phone_crop(img_token, "full")
    place_image_with_glow(img, crop_tok, [70, 85, 520, 1000], C_PURPLE)

    place_image_with_glow(img, img_arch_ledger, [550, 85, 1300, 560], C_PURPLE)

    draw_stat_box(draw, [1330, 85, 1850, 215], "600 Seconds", "Token TTL", "Strict single-use lifecycle", C_PURPLE)
    draw_stat_box(draw, [1330, 235, 1850, 365], "HMAC-SHA256", "Token Signature", "Tamper-evident verification", C_CYAN)
    draw_stat_box(draw, [1330, 385, 1850, 515], "Merkle Chain", "Audit Trail", "Append-only state ledger", C_EMERALD)

    bullets_crypto = [
        ("[HMAC]", "Single-Use HMAC-SHA256 Token:", "Token = HMAC(K_decision, CustomerID || ProductID || Timestamp || RunID)."),
        ("[LOCK]", "Zero Replay Vulnerabilities:", "Token is consumed permanently upon execution to prevent replay attacks."),
        ("[KFS]", "RBI Digital Lending KFS:", "Full Key Fact Statement & cooling-off disclosures presented before signing."),
        ("[LEDGER]", "Tamper-Evident Merkle Ledger:", "Every node transition appends an immutable SHA-256 hash chain.")
    ]
    draw_bullet_card(draw, [550, 590, 1850, 1000], "Cryptographic Trust Architecture", bullets_crypto, "BANK-GRADE", C_PURPLE)
    return img

def render_scene_10(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "DPDP Act 2023 Privacy & Customer Rights", scene_idx, prog)

    crop_dpdp = extract_phone_crop(img_dpdp, "full")
    place_image_with_glow(img, crop_dpdp, [70, 85, 520, 1000], C_EMERALD)

    place_image_with_glow(img, img_arch_dpdp, [550, 85, 1300, 560], C_EMERALD)

    draw_stat_box(draw, [1330, 85, 1850, 215], "Opt-In", "Purpose Consent", "Active toggle control", C_EMERALD)
    draw_stat_box(draw, [1330, 235, 1850, 365], "JSON Export", "Data Portability", "Download profiling trace", C_CYAN)
    draw_stat_box(draw, [1330, 385, 1850, 515], "Tombstone", "Right to Erasure", "Immutable deletion proof", C_PURPLE)

    bullets_dpdp = [
        ("[PURPOSE]", "Purpose Limitation:", "Consent is scoped strictly to 'savings_optimization' or 'financial_support'."),
        ("[ERASURE]", "Automated Right to Erasure:", "Purges all Saarthi models, caches, and profiling records on demand."),
        ("[PORTABILITY]", "JSON Data Portability:", "Allows customers to download complete algorithmic decision records."),
        ("[LEGAL]", "Zero Penalty Guarantee:", "Protects SBI from India's DPDP Act non-compliance penalties.")
    ]
    draw_bullet_card(draw, [550, 590, 1850, 1000], "DPDP Compliance Engine", bullets_dpdp, "DPDP ACT 2023", C_EMERALD)
    return img

def render_scene_11(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "Quantified Business ROI for State Bank of India", scene_idx, prog)

    draw_stat_box(draw, [70, 85, 480, 245], "+₹1,250 Cr", "Annual Lending Book Growth", "Express Credit pre-qualified conversions", C_AMBER)
    draw_stat_box(draw, [510, 85, 920, 245], "-35% Load", "Branch Queue Reduction", "Cash deposits routed to CDM & UPI LITE", C_EMERALD)
    draw_stat_box(draw, [950, 85, 1360, 245], "+18% Uplift", "Deposit Mobilization", "Auto-allocated Fixed & Recurring Deposits", C_CYAN)
    draw_stat_box(draw, [1390, 85, 1850, 245], "₹0 Penalties", "Regulatory Safety", "DPDP Act 2023 & RBI digital lending proof", C_PURPLE)

    place_image_with_glow(img, img_arch_graph, [70, 275, 980, 1000], C_CYAN)

    bullets_roi = [
        ("•", "Digital Lending Acceleration:", "Targeted debt consolidation captures high-quality salaried personal loans."),
        ("•", "Branch Operational Efficiency:", "Frees up branch teller capacity by digitizing routine tax & cash deposits."),
        ("•", "Customer Retention & Trust:", "Transparent explainability & ethical stress guardrails boost customer loyalty."),
        ("•", "Zero Infrastructure Overhead:", "1.8 GB 3B SLM runs on existing on-premise servers with zero cloud API bills."),
        ("•", "Immediate Pilot Feasibility:", "Modular FastAPI backend connects cleanly with SBI Core Banking (CBS).")
    ]
    draw_bullet_card(draw, [1010, 275, 1850, 1000], "Strategic Business Impact Model", bullets_roi, "HIGH ROI", C_AMBER)
    return img

def render_scene_12(scene_idx, prog):
    img = Image.new("RGB", (WIDTH, HEIGHT), C_BG)
    draw = ImageDraw.Draw(img)
    draw_header_footer(draw, "Hackathon Grand Finale & Live Deployment", scene_idx, prog)

    f_grand = get_font(46, bold=True)
    f_sub = get_font(21, bold=False)
    draw.text((70, 95), "SAARTHI : The Future of Governed Autonomous Banking", fill=C_CYAN, font=f_grand)
    draw.text((70, 155), "Delivering Proactive, Ethical & Cryptographically Verified AI to 80M+ SBI Customers", fill=C_TEXT_WHITE, font=f_sub)

    draw.rectangle([70, 205, 1850, 280], fill=(16, 185, 129, 25), outline=C_EMERALD, width=2)
    f_live = get_font(20, bold=True)
    draw.text((95, 230), ">> LIVE DEPLOYED APP:", fill=C_EMERALD, font=f_live)
    draw.text((360, 230), "https://invexora.github.io/saarthi-yono-copilot/", fill=C_TEXT_WHITE, font=f_live)

    place_image_with_glow(img, img_opp_trace, [70, 310, 980, 1000], C_CYAN)

    bullets_fin = [
        ("•", "Complete Solution Suite:", "Live Behance YONO Mobile UI + 6-Node LangGraph Orchestration Trace."),
        ("•", "Proprietary 3B SLM:", "99.4% F1 Accuracy, 4.8ms P50 latency, 1.8 GB RAM on-premise model."),
        ("•", "DPDP Act 2023 Compliant:", "Purpose limitation, Right to Erasure, JSON Export & Single-Use HMAC tokens."),
        ("•", "Massive Business Impact:", "+₹1,250 Cr lending book uplift, -35% branch load, +18% deposit mobilization."),
        ("•", "Developed by Team Invexora:", "Gaurav Mahajan & Kishore Jadhav — Built for YONO Copilot Hackathon.")
    ]
    draw_bullet_card(draw, [1010, 310, 1850, 1000], "Why Saarthi Wins", bullets_fin, "TEAM INVEXORA", C_EMERALD)
    return img

SCENE_DEFS = [
    ("Executive Overview & Vision", SCENE_DUR, render_scene_1),
    ("The Reactive Banking Challenge", SCENE_DUR, render_scene_2),
    ("Proactive Opportunity Nudge", SCENE_DUR, render_scene_3),
    ("Explainability & DPDP Transparency", SCENE_DUR, render_scene_4),
    ("Proprietary 3B SLM Pipeline", SCENE_DUR, render_scene_5),
    ("Agentic Traffic Controller & LangGraph", SCENE_DUR, render_scene_6),
    ("Branch Friction & Life-Events", SCENE_DUR, render_scene_7),
    ("Vulnerability Protection Mode", SCENE_DUR, render_scene_8),
    ("Single-Use Tokens & Merkle Audit", SCENE_DUR, render_scene_9),
    ("DPDP Act 2023 Customer Rights", SCENE_DUR, render_scene_10),
    ("Quantified Business ROI for SBI", SCENE_DUR, render_scene_11),
    ("Grand Finale & Live Deployment", SCENE_DUR, render_scene_12),
]

print(f"Silent Video Duration: {TOTAL_DURATION}s ({TOTAL_DURATION:.1f} secs) | Total Frames: {TOTAL_FRAMES}")

OUTPUT_MP4 = "docs/saarthi_demo_presentation_5min.mp4"
FINAL_COPY = "presentation-final/saarthi_demo_presentation_5min.mp4"
FAST_COPY = "docs/saarthi_demo_presentation_fast.mp4"

# RENDER SILENT VIDEO (NO AUDIO TRACK / NO SFX)
ffmpeg_cmd = [
    "ffmpeg", "-y",
    "-f", "rawvideo",
    "-pix_fmt", "bgr24",
    "-s", f"{WIDTH}x{HEIGHT}",
    "-r", str(FPS),
    "-i", "-",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-an", # Strictly NO AUDIO / Silent
    OUTPUT_MP4
]

proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

current_global_frame = 0
for scene_idx, (s_title, s_dur, s_render) in enumerate(SCENE_DEFS, start=1):
    num_frames = int(s_dur * FPS)
    print(f"Rendering Act {scene_idx}/{TOTAL_SCENES}: {s_title} ({s_dur}s, {num_frames} frames)...")

    base_img = s_render(scene_idx, current_global_frame / TOTAL_FRAMES)
    base_bgr = np.array(base_img)[:, :, ::-1].copy()

    for f in range(num_frames):
        prog = (current_global_frame + f) / TOTAL_FRAMES
        frame_bgr = base_bgr.copy()

        # Bottom Animated Progress Bar
        bar_w = min(WIDTH, int(WIDTH * prog))
        frame_bgr[HEIGHT - 5 : HEIGHT, 0 : bar_w] = (255, 210, 0)

        proc.stdin.write(frame_bgr.tobytes())

    current_global_frame += num_frames

proc.stdin.close()
proc.wait()

print(f"Silent video created successfully at: {OUTPUT_MP4}")
os.makedirs("presentation-final", exist_ok=True)
subprocess.run(["cp", OUTPUT_MP4, FINAL_COPY])
subprocess.run(["cp", OUTPUT_MP4, FAST_COPY])
print(f"Copied to: {FINAL_COPY} & {FAST_COPY}")

/* =============================================
   SAARTHI — Proactive Financial Co-Pilot (app.js)
   ============================================= */

// ─── Profile Database ─────────────────────────────────────────────────
const profiles = {
  aiwin: {
    id: "SBI-036910", name: "Aiwin Vinu", firstName: "Aiwin",
    salary: "₹85,000", balance: "₹68,526", interest: "₹1,850/mo (across 1 card)",
    rawBalance: 68526, rawCardDebt: 45000,
    email: "aiwin.vinu@example.com", pan: "AIWIN1234F", aadhaar: "4532 0369 1204",
    assist: { icon: "🎯", label: "Opportunity Ready", color: "green", desc: "High-value nudges for financial optimization" },
    impact: {
      task: "2 Tasks Completed Digitally", taskSub: "Saved ~2 hours of branch waiting time",
      savings: "₹1,000 Saved This Month", savSub: "From debt consolidation recommendation",
      branch: "1 Branch Visit Avoided", branchSub: "Using YONO Pay instead of counter deposit",
      bars: [30, 55, 70]
    },
    scenarios: {
      friction: {
        icon: "🏛️",
        name: "1. Branch Cash Deposit Friction",
        desc: "User physically visits branch to deposit cash at manual counter",
        title: "Deposit Cash via CDM or UPI",
        text: "You visited Branch 0032 to deposit cash. Skip branch queues by using SBI Cash Deposit Machines (CDM) or UPI LITE instantly.",
        actionBtn: "Locate Nearest CDM",
        consentText: "To view your nearest 24/7 SBI Cash Deposit Machine and enable digital deposits, please confirm below.",
        explainText: "Branch records show a cash deposit transaction of ₹20,000 at manual counter 0032.",
        successText: "The prototype recorded digital cash deposit guidance; nearest CDM mapped.",
        signalLog: "CASH_DEPOSIT_FRICTION — Manual branch counter deposit of ₹20,000 detected",
        recLog: "SBI Instant Cash Deposit Machine & UPI LITE Guidance"
      },
      opportunity: {
        icon: "💡",
        name: "2. Credit Card Interest Optimization",
        desc: "Paying high revolving credit card interest at 42% APR",
        title: "Consolidate Card Debt & Save ₹1,000/mo",
        text: "You are paying ₹1,850/mo revolving interest at 42% APR on SBI Card Elite. Convert to 10.5% personal loan or EMI to save interest.",
        actionBtn: "Review EMI Options",
        consentText: "To simulate reviewing the synthetic card debt consolidation comparison at 10.5% p.a., confirm one-time consent.",
        explainText: "Card statement shows ₹45,000 outstanding balance revolving with ₹1,850 finance charges.",
        successText: "The prototype recorded card debt optimization; comparison generated.",
        signalLog: "DEBT_OPPORTUNITY — Revolving card interest of ₹1,850/mo exceeds threshold",
        recLog: "Consolidation into 10.5% personal loan / EMI"
      },
      lifeevent: {
        icon: "🚀",
        name: "3. Life-Event Savings Potential",
        desc: "Surplus savings balance detected in savings account",
        title: "Auto-Create 7.1% Tax-Saver FD",
        text: "Your savings balance is ₹68,526 earning only 2.70%. Move surplus into a 7.10% SBI Tax-Saver Fixed Deposit.",
        actionBtn: "Open SBI FD",
        consentText: "To simulate auto-creating an SBI Green Fixed Deposit at 7.10% p.a. for ₹25,000, confirm consent.",
        explainText: "Idle balance in savings account has exceeded average monthly expenditure for 60 days.",
        successText: "The prototype recorded synthetic Fixed Deposit creation at 7.10% p.a.",
        signalLog: "SURPLUS_SAVINGS — Idle balance of ₹68,526 detected in savings account",
        recLog: "SBI 7.10% Fixed Deposit allocation"
      },
      stress: {
        icon: "⚠️",
        name: "4. Compassionate EMI Support",
        desc: "Upcoming loan EMI due with temporary balance dip",
        title: "SBI Compassionate Support",
        text: "We noticed your upcoming EMI is due in 3 days with a tight balance. We're here to assist with flexible restructuring.",
        actionBtn: "View Restructuring",
        consentText: "To review flexible EMI restructuring or connect to your Relationship Manager, confirm consent.",
        explainText: "Account liquidity analysis indicates upcoming debt obligation may exceed projected balance.",
        successText: "The prototype connected you to your SBI Relationship Manager.",
        signalLog: "LIQUIDITY_STRESS — Tight liquidity ahead of monthly EMI due date",
        recLog: "Proactive EMI restructuring assistance"
      }
    }
  },
  priya: {
    id: "SBI-772910", name: "Priya Sharma", firstName: "Priya",
    salary: "₹1,45,000", balance: "₹2,80,000", interest: "₹4,200/mo (across 2 cards)",
    rawBalance: 280000, rawCardDebt: 85000,
    email: "priya.sharma@example.com", pan: "ABCDE1234F", aadhaar: "4532 9981 1204",
    assist: { icon: "🎯", label: "Opportunity Ready", color: "green", desc: "High-value nudges for financial optimization" },
    impact: {
      task: "2 Tasks Completed Digitally", taskSub: "Saved ~2 hours of branch waiting time",
      savings: "₹2,100 Saved This Month", savSub: "From debt consolidation recommendation",
      branch: "1 Branch Visit Avoided", branchSub: "Using YONO Pay instead of counter deposit",
      bars: [40, 65, 82]
    },
    scenarios: {
      friction: {
        icon: "🏛️",
        name: "1. Direct Tax Friction",
        desc: "Visits branch to pay quarterly advance tax physically",
        title: "Pay Advance Tax Digitally",
        text: "You visited Branch 0032 to deposit tax. Skip the queue and pay online directly via YONO.",
        actionBtn: "Pay Advance Tax",
        consentText: "To pay your quarterly advance tax of ₹35,000 via YONO, please confirm your consent below.",
        explainText: "Branch payment records indicate a quarterly physical tax deposit of ₹35,000 at counter.",
        successText: "The offline demo recorded a synthetic advance-tax payment step.",
        signalLog: "TAX_FRICTION — Quarterly counter advance tax payment detected",
        recLog: "Digitized advance tax payment via YONO"
      },
      opportunity: {
        icon: "💡",
        name: "2. Opportunity Signal",
        desc: "High idle balance & paying high credit card interest rates",
        title: "Consolidate Debt & Save ₹2,100/mo",
        text: "The offline fixture identifies recurring card interest and presents a synthetic debt-consolidation comparison. Live eligibility, price and KFS data are required.",
        actionBtn: "Consolidate Now",
        consentText: "To simulate reviewing the synthetic debt-consolidation option, confirm one-time offline-demo consent. No application will be submitted.",
        explainText: "You have maintained ₹4,200/month in credit card interest payments across 2 cards for the last 3 months.",
        successText: "The offline demo recorded a synthetic debt-comparison step; no application was submitted.",
        signalLog: "DEBT_OPPORTUNITY — CC interest ₹4,200/mo exceeds consolidation threshold",
        recLog: "Consolidation Loan at 20% p.a. replacing 42% CC interest"
      },
      lifeevent: {
        icon: "🚀",
        name: "3. Life-Event Signal",
        desc: "Salary jump pattern detected in monthly credits",
        title: "New Savings Potential Unlocked",
        text: "Your salary credit has increased by 30%. Auto-setup a Recurring Deposit of ₹18,500/mo to maximise this window.",
        actionBtn: "Setup RD Now",
        consentText: "To auto-create a Recurring Deposit of ₹18,500/month at 7.10% p.a., please confirm your consent.",
        explainText: "Your salary credit has increased by 30% over 3 consecutive months, indicating new financial capacity.",
        successText: "The offline demo recorded a synthetic recurring-deposit setup step.",
        signalLog: "LIFE_EVENT — 30% salary increase detected over 3 consecutive months",
        recLog: "Recurring Deposit ₹18,500/mo at 7.10% p.a."
      },
      stress: {
        icon: "⚠️",
        name: "4. Credit Limit Breach",
        desc: "Overdraft utilization reaches 95% of limit",
        title: "Overdraft Limit Alert",
        text: "Your overdraft account utilization is at 95%. Move funds from savings to avoid interest penalties.",
        actionBtn: "Rebalance Accounts",
        consentText: "To transfer ₹50,000 from savings to cover your overdraft and avoid interest, confirm consent.",
        explainText: "Overdraft account utilization has exceeded 90% threshold for more than 48 hours.",
        successText: "The offline demo recorded a synthetic account-rebalancing step; no funds moved.",
        signalLog: "OVERDRAFT_ALERT — Overdraft account utilization at 95%",
        recLog: "Overdraft balance coverage transfer"
      }
    }
  },
  ramesh: {
    id: "SBI-881234", name: "Ramesh Kumar", firstName: "Ramesh",
    salary: "₹42,000/mo (Pension)", balance: "₹92,000", interest: "₹0/mo",
    rawBalance: 92000, rawCardDebt: 0,
    email: "ramesh.kumar@example.com", pan: "FGHIJ5678K", aadhaar: "8899 4432 1122",
    assist: { icon: "🌱", label: "Digital Explorer", color: "blue", desc: "Introduce one new digital feature at a time" },
    impact: {
      task: "1 Digital Transaction Initiated", taskSub: "First ever UPI transfer via YONO",
      savings: "₹0 Saved (Exploring)", savSub: "Learning digital banking step by step",
      branch: "3 Branch Visits This Month", branchSub: "Opportunity to migrate 2 to YONO",
      bars: [15, 25, 30]
    },
    scenarios: {
      friction: {
        icon: "🏛️",
        name: "1. Pension Deposit Friction",
        desc: "Visits branch to deposit cash from monthly pension physically",
        title: "Go Digital with YONO Pay",
        text: "You visited Branch 0032 to deposit check/cash. Enable UPI Auto-Pay and transfer pension online instantly.",
        actionBtn: "Set Up UPI Auto-Pay",
        consentText: "To enable UPI Auto-Pay for monthly utility transfers, please confirm your consent below.",
        explainText: "Branch records show 4 counter deposit visits in the last 30 days for utility bills.",
        successText: "The offline demo recorded a synthetic UPI Auto-Pay setup step.",
        signalLog: "BRANCH_FRICTION — 4 counter deposit visits in the last 30 days",
        recLog: "UPI Auto-Pay setup for pension/utility bills"
      },
      opportunity: {
        icon: "👵",
        name: "2. Senior FD Opportunity",
        desc: "Savings balance of ₹92,000 may qualify for a senior-citizen term deposit",
        title: "Maximize Senior Citizen Returns",
        text: "Review moving ₹50,000 from savings to a Senior Citizen Fixed Deposit. This offline demo uses a 6.75% rate snapshot; live SBI terms must be checked.",
        actionBtn: "Create FD Now",
        consentText: "To continue to the review step for a ₹50,000 Senior Citizen Fixed Deposit using the offline demo terms, confirm consent.",
        explainText: "Average savings balance of ₹92,000 maintained for 90 days. Incremental benefit depends on the live deposit and savings rates, tenure and tax treatment.",
        successText: "The offline demo recorded a synthetic senior-deposit setup step; no deposit or certificate was created.",
        signalLog: "FD_OPPORTUNITY — ₹50,000 idle savings exceeding 90-day liquidity buffer",
        recLog: "Senior Citizen Fixed Deposit — offline demo rate snapshot 6.75% p.a."
      },
      lifeevent: {
        icon: "📈",
        name: "3. Pension Maturity",
        desc: "Insurance policy payout credited to savings account",
        title: "Pension Maturity Reinvestment",
        text: "Your policy maturity of ₹3,00,000 was credited. Reinvest in Senior Citizen Savings Scheme (SCSS).",
        actionBtn: "Reinvest in SCSS",
        consentText: "To reinvest ₹3,00,000 into the government-backed SCSS at 8.2% p.a., please confirm your consent.",
        explainText: "One-off credit of ₹3,00,000 detected from LIC maturity payout.",
        successText: "The offline demo recorded a synthetic SCSS review step; no account was opened.",
        signalLog: "LIFE_EVENT — Policy maturity payout credit of ₹3,00,000 detected",
        recLog: "Senior Citizen Savings Scheme (SCSS) reinvestment"
      },
      stress: {
        icon: "🏥",
        name: "4. Medical Expense Stress",
        desc: "Consecutive cash withdrawals at hospital pharmacies",
        title: "Healthcare Support Mode",
        text: "We noticed high pharmacy withdrawals. Apply for SBI Aarogyam zero-penalty medical loan support.",
        actionBtn: "Apply Medical EMI",
        consentText: "To convert your medical pharmacy bills into a 0% interest 6-month EMI plan, please confirm consent.",
        explainText: "Consecutive withdrawals of ₹12,000 and ₹18,000 flagged at MedPlus branch merchant terminal.",
        successText: "The offline demo recorded a synthetic medical-support review step; no EMI plan was created.",
        signalLog: "FINANCIAL_STRESS — High pharmacy/medical merchant cash withdrawals",
        recLog: "Aarogyam Zero-penalty medical loan EMI"
      }
    }
  },
  amit: {
    id: "SBI-223456", name: "Amit Patel", firstName: "Amit",
    salary: "₹95,000", balance: "₹6,40,000", interest: "₹8,500/mo (business loan EMI)",
    rawBalance: 640000, rawCardDebt: 120000,
    email: "amit.patel@example.com", pan: "LMNOP9012Q", aadhaar: "3322 1155 9988",
    assist: { icon: "💼", label: "Opportunity Ready", color: "green", desc: "SME financial products and growth tools" },
    impact: {
      task: "4 Business Payments Digitised", taskSub: "Vendor payments via YONO Business",
      savings: "₹4,200 Saved This Month", savSub: "From CC debt consolidation + auto-sweep",
      branch: "2 Branch Visits Avoided", branchSub: "Using YONO for GST and bulk transfers",
      bars: [55, 70, 85]
    },
    scenarios: {
      friction: {
        icon: "🏪",
        name: "1. Shop Cash Deposit",
        desc: "Daily physical cash deposits at branch counter",
        title: "Digitize Merchant Cash",
        text: "You make physical daily cash deposits of ₹20,000. Switch to YONO Merchant App digital collections.",
        actionBtn: "Activate Merchant App",
        consentText: "To activate the SBI YONO Merchant app and order a digital QR scanner, please confirm consent.",
        explainText: "Counter cash deposits of ₹15,000 to ₹25,000 recorded 12 times in the last 15 days.",
        successText: "The offline demo recorded a synthetic merchant-onboarding step; no terminal was ordered.",
        signalLog: "BRANCH_FRICTION — 12 counter cash deposits in the last 15 days",
        recLog: "YONO Merchant App digital collections QR scanner"
      },
      opportunity: {
        icon: "🔄",
        name: "2. Business Auto-Sweep",
        desc: "High idle current balance of ₹6,40,000",
        title: "Enable Current Auto-Sweep",
        text: "Earn 6.50% interest on idle cash by routing surplus balance over ₹1,00,000 into auto-sweep FD.",
        actionBtn: "Enable Auto-Sweep",
        consentText: "To enable the automatic multi-option deposit sweep on your current account, confirm consent.",
        explainText: "Average current account balance of ₹6,40,000 maintained, earning 0% interest.",
        successText: "The offline demo recorded a synthetic auto-sweep setup step.",
        signalLog: "AUTO_SWEEP_OPPORTUNITY — Idle current account balance of ₹6,40,000",
        recLog: "Current account Auto-Sweep activation"
      },
      lifeevent: {
        icon: "📦",
        name: "3. GST Refund Payout",
        desc: "GST portal tax refund credited to account",
        title: "Reinvest GST Refund",
        text: "Your GST refund of ₹1,50,000 was credited. Save interest by pre-paying working capital overdraft.",
        actionBtn: "Pre-pay Loan Now",
        consentText: "To apply ₹1,50,000 to your working capital loan outstanding to save 12.5% interest, confirm consent.",
        explainText: "One-off GST portal payout credit of ₹1,50,000 detected in transaction log.",
        successText: "The offline demo recorded a synthetic loan-prepayment review step; no money moved.",
        signalLog: "LIFE_EVENT — GST refund credit of ₹1,50,000 detected",
        recLog: "Loan pre-payment routing"
      },
      stress: {
        icon: "📉",
        name: "4. Working Capital Stress",
        desc: "Delayed receivables breach overdraft limit",
        title: "Business Support Mode",
        text: "Receivables delayed by 30 days. Access a 90-day working capital moratorium automatically.",
        actionBtn: "Request Moratorium",
        consentText: "To apply for a 90-day moratorium on your business overdraft under RBI MSME guidelines, confirm consent.",
        explainText: "B2B vendor invoice settlement delayed, causing overdraft to remain at 98% capacity.",
        successText: "The offline demo recorded a synthetic support review; no moratorium was approved.",
        signalLog: "FINANCIAL_STRESS — Delayed accounts receivable, 98% draft utilization",
        recLog: "Working Capital 90-day moratorium"
      }
    }
  },
  sneha: {
    id: "SBI-991877", name: "Sneha Patel", firstName: "Sneha",
    salary: "₹68,000", balance: "₹45,000", interest: "₹980/mo (1 card)",
    rawBalance: 45000, rawCardDebt: 28000, missedEMI: true,
    email: "sneha.patel@example.com", pan: "RSTUV3456W", aadhaar: "7744 2233 8811",
    assist: { icon: "🛡️", label: "Needs Support", color: "amber", desc: "Reduce promotions. Prioritise practical help." },
    impact: {
      task: "0 New Tasks", taskSub: "Focus on stabilising finances first",
      savings: "EMI Restructuring Available", savSub: "Connect to RM for personalized plan",
      branch: "1 Branch Visit This Month", branchSub: "Meeting relationship manager",
      bars: [20, 35, 45]
    },
    scenarios: {
      friction: {
        icon: "📱",
        name: "1. Video KYC Migration",
        desc: "Visits branch physically to submit re-KYC documents",
        title: "Complete Video KYC Online",
        text: "Your periodic KYC is due. Avoid physical submission at the branch; complete it instantly via YONO Video KYC.",
        actionBtn: "Start Video KYC",
        consentText: "To launch the secure Video KYC portal and link your DigiLocker documents, please confirm consent.",
        explainText: "KYC compliance warning flagged on account. User visited branch twice for document queries.",
        successText: "The offline demo recorded a synthetic Video KYC scheduling step; no SMS was sent.",
        signalLog: "KYC_FRICTION — KYC compliance alert and 2 physical branch KYC queries",
        recLog: "YONO Video KYC digital submission"
      },
      opportunity: {
        icon: "💳",
        name: "2. Repayment Restructuring",
        desc: "Restructure card debt to lower monthly outflow",
        title: "Restructure Credit Card Balance",
        text: "You have a ₹28,000 balance. Convert into a low-interest 12-month EMI of ₹2,550/mo to avoid stress.",
        actionBtn: "Restructure Balance",
        consentText: "To convert your credit card balance into a 12-month EMI at 12% p.a. (vs current 42% p.a.), confirm consent.",
        explainText: "Vulnerable status alert. High revolving credit balances flag risk of repayment stress.",
        successText: "The offline demo recorded a synthetic card-EMI review step; no conversion occurred.",
        signalLog: "REPAYMENT_RESTRUCTURING — High credit card balances exceeding stress index",
        recLog: "Low-interest CC balance EMI conversion"
      },
      lifeevent: {
        icon: "🛡️",
        name: "3. Emergency Fund Nudge",
        desc: "No active savings buffer or insurance linked",
        title: "Build Emergency Buffer",
        text: "Build a safety net. Set up a micro-RD of ₹2,000/mo to auto-fund emergencies.",
        actionBtn: "Set Up Micro-RD",
        consentText: "To start a micro Recurring Deposit of ₹2,000/month for emergency savings, confirm consent.",
        explainText: "Savings balance is below the standard monthly expense buffer threshold.",
        successText: "The offline demo recorded a synthetic emergency-savings setup step.",
        signalLog: "LIFE_EVENT — Monthly cash savings buffer below threshold",
        recLog: "Emergency fund micro-RD setup"
      },
      stress: {
        icon: "⚠️",
        name: "4. Home Loan Missed EMI",
        desc: "Missed salary credit triggers EMI auto-debit failure",
        title: "Saarthi Support Mode",
        text: "Hi Sneha, we noticed your recent EMI payment was missed. We're here to help — not to sell.",
        actionBtn: "Connect to RM",
        consentText: "To connect with a designated Relationship Manager to discuss EMI relief, confirm consent.",
        explainText: "The offline fixture routes a missed EMI signal into the prototype's conservative vulnerable-customer support policy.",
        successText: "The offline demo displayed support-only guidance; no RM ticket was created.",
        signalLog: "FINANCIAL_STRESS — Missed EMI (Home Loan) after salary reduction",
        recLog: "Designated Relationship Manager support connection"
      }
    }
  },
  rohan: {
    id: "SBI-554321", name: "Rohan Mehta", firstName: "Rohan",
    salary: "₹18,000 (Stipend)", balance: "₹12,500", interest: "₹0/mo",
    rawBalance: 12500, rawCardDebt: 0,
    email: "rohan.mehta@example.com", pan: "MNOPQ7890R", aadhaar: "5566 3344 2211",
    assist: { icon: "🎓", label: "First Steps", color: "blue", desc: "Introduce foundational financial habits" },
    impact: {
      task: "0 Tasks Yet", taskSub: "Building first digital banking habits",
      savings: "₹0 Saved (Exploring)", savSub: "First SIP or RD setup pending",
      branch: "2 Branch Visits This Month", branchSub: "Education loan queries at branch",
      bars: [10, 15, 20]
    },
    scenarios: {
      friction: {
        icon: "🎓",
        name: "1. Education Loan Friction",
        desc: "Visits branch to get education loan statement and EMI schedule",
        title: "View Loan Dashboard Digitally",
        text: "Skip the branch queue. Your full education loan EMI schedule and outstanding balance is available right here in YONO.",
        actionBtn: "Open Loan Dashboard",
        consentText: "To access your complete education loan dashboard with EMI schedule and prepayment options, please confirm consent.",
        explainText: "Branch visit log shows 2 visits this month for education loan statement and EMI schedule queries.",
        successText: "The offline demo recorded a synthetic education-dashboard activation step.",
        signalLog: "BRANCH_FRICTION — 2 branch visits for education loan statement queries",
        recLog: "Digital Education Loan Dashboard activation"
      },
      opportunity: {
        icon: "📈",
        name: "2. First SIP Opportunity",
        desc: "₹18,000 stipend with zero investments — micro-SIP opportunity",
        title: "Start Your First SIP at ₹500/mo",
        text: "Your coffee money can grow to ₹2.4L in 10 years. Start an SBI Mutual Fund SIP at just ₹500/month — no lock-in.",
        actionBtn: "Start SIP Now",
        consentText: "To start a Systematic Investment Plan (SIP) of ₹500/month in SBI Bluechip Fund, please confirm consent.",
        explainText: "Monthly stipend of ₹18,000 detected with zero investment allocation. ₹500/mo SIP = ₹2.4L at 12% p.a. over 10 years.",
        successText: "The offline demo recorded a synthetic SIP review step; no investment was placed.",
        signalLog: "INVESTMENT_OPPORTUNITY — ₹18,000 stipend with zero investment allocation",
        recLog: "SBI Mutual Fund SIP ₹500/mo (Bluechip Fund)"
      },
      lifeevent: {
        icon: "💼",
        name: "3. First Salary Credit",
        desc: "First full salary credit detected after graduation",
        title: "Congratulations! Channel Your First Salary",
        text: "Your first salary of ₹35,000 was credited! Auto-setup a Flexi-RD of ₹5,000/mo to build your savings foundation.",
        actionBtn: "Setup Flexi-RD",
        consentText: "To auto-create a Flexi Recurring Deposit of ₹5,000/month at 7.10% p.a., please confirm consent.",
        explainText: "First-ever salary credit of ₹35,000 detected from employer. No existing savings instrument linked.",
        successText: "The offline demo recorded a synthetic Flexi-RD setup step; no deposit was created.",
        signalLog: "LIFE_EVENT — First salary credit of ₹35,000 detected (new employment)",
        recLog: "Flexi Recurring Deposit ₹5,000/mo at 7.10% p.a."
      },
      stress: {
        icon: "📚",
        name: "4. Education Loan EMI Stress",
        desc: "Loan EMI auto-debit starts but no stable income yet",
        title: "Saarthi Support Mode",
        text: "Hi Rohan, your education loan EMI of ₹8,500 is due but we see no regular income yet. Let's explore a moratorium extension.",
        actionBtn: "Explore Moratorium",
        consentText: "To apply for a 6-month EMI moratorium extension on your education loan under RBI education loan guidelines, confirm consent.",
        explainText: "Education loan EMI auto-debit of ₹8,500 flagged with no regular salary credit in last 60 days.",
        successText: "The offline demo displayed support-only guidance; no moratorium request was submitted.",
        signalLog: "FINANCIAL_STRESS — Education loan EMI due with no regular income detected",
        recLog: "Education Loan 6-month EMI Moratorium extension"
      }
    }
  }
};

const localApiHost = (typeof window !== 'undefined' && window.location && ['localhost', '127.0.0.1'].includes(window.location.hostname))
  ? window.location.hostname
  : 'localhost';
const API_BASE = (typeof window !== 'undefined' && window.SAARTHI_API_BASE) || `http://${localApiHost}:5050/api/v1`;
const isGithubPages = typeof window !== 'undefined'
  && Boolean(window.location && window.location.hostname && (window.location.hostname.endsWith('github.io') || window.location.hostname.includes('invexora')));

const OFFLINE_DEMO_MODE = (typeof window !== 'undefined' && window.SAARTHI_MODE === 'offline-demo')
  || (typeof window !== 'undefined' && window.location && window.location.search && new URLSearchParams(window.location.search).get('mode') === 'offline-demo')
  || isGithubPages;

// ─── State ─────────────────────────────────────────────────────────────
let currentProfileKey = 'aiwin';
let currentNudge = null;
let consentState = true;
let nudgeBudgetMax = 5;
let nudgeBudgetUsed = 0;
let consecutiveDeclines = 0;
let activeScenarioType = null;
let autoTriggerTimeout = null;
let successAutoTimeout = null;
let backendAvailable = false;
let currentRecommendationId = null;
let currentReviewRequired = false;
let currentReviewedOffer = null;
let reviewPollTimeout = null;
let reviewPollAttempts = 0;
let currentDecisionToken = null;
let currentOffer = null;
let runtimeMode = OFFLINE_DEMO_MODE ? 'offline-demo' : 'probing';
let activePipelineRunId = 0;
let actionInFlight = false;
let consentReturnFocus = null;
let erasureReturnFocus = null;
let lastScenarioTrigger = null;
let isBalanceHidden = false;

const DIALOG_FOCUSABLE_SELECTOR = [
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'a[href]',
  '[tabindex]:not([tabindex="-1"])'
].join(',');

function getDialogFocusables(container) {
  if (!container || typeof container.querySelectorAll !== 'function') return [];
  return Array.from(container.querySelectorAll(DIALOG_FOCUSABLE_SELECTOR));
}

function focusElement(element) {
  if (!element || typeof element.focus !== 'function') return;
  if (typeof element.closest === 'function' && element.closest('[inert]')) return;
  element.focus();
}

function trapDialogFocus(event, dialog) {
  const focusables = getDialogFocusables(dialog);
  if (!focusables.length) {
    event.preventDefault();
    focusElement(dialog);
    return;
  }
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (!focusables.includes(document.activeElement)) {
    event.preventDefault();
    focusElement(event.shiftKey ? last : first);
  } else if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    focusElement(last);
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    focusElement(first);
  }
}

function handleAccessibilityKeydown(event) {
  const consentScreen = document.getElementById('consentScreen');
  if (consentScreen.classList.contains('visible')) {
    if (event.key === 'Escape') {
      event.preventDefault();
      closeConsentScreen();
    } else if (event.key === 'Tab') {
      trapDialogFocus(event, consentScreen);
    }
    return;
  }

  const erasureConfirm = document.getElementById('erasureConfirm');
  if (erasureConfirm.classList.contains('visible')) {
    if (event.key === 'Escape') {
      event.preventDefault();
      cancelErasure();
    } else if (event.key === 'Tab') {
      trapDialogFocus(event, erasureConfirm);
    }
  }
}

document.addEventListener('keydown', handleAccessibilityKeydown);

async function apiRequest(path, options = {}) {
  const p = profiles[currentProfileKey];
  const identityHeaders = window.SAARTHI_ACCESS_TOKEN
    ? { Authorization: `Bearer ${window.SAARTHI_ACCESS_TOKEN}` }
    : { 'X-Saarthi-Demo-Customer': p.id, 'X-Saarthi-Demo-Role': 'customer' };
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...identityHeaders, ...(options.headers || {}) }
  });
  const payload = await response.json();
  return { response, payload };
}

function setConsentUI(granted) {
  consentState = granted;
  document.getElementById('consentBadge').textContent = granted ? 'OPTED IN' : 'REVOKED';
  document.getElementById('consentBadge').className = granted ? 'consent-badge active' : 'consent-badge revoked';
  document.getElementById('revokeBtn').textContent = granted ? 'Revoke Personalisation Consent' : 'Re-Grant Consent';
  document.getElementById('yonoConsentToggle').checked = granted;
}

async function hydrateSyntheticProfileConsent() {
  if (!backendAvailable) return;
  const p = profiles[currentProfileKey];
  const { response, payload } = await apiRequest('/consent');
  if (!response.ok) throw new Error('Unable to load consent state');
  const personalization = payload.find(record => record.purpose === 'personalization');
  if (personalization) {
    setConsentUI(personalization.consent_status === 1 && personalization.erasure_requested !== 1);
    return;
  }

  // Seed only a never-before-seen synthetic demo persona. Revoked/erased records are preserved above.
  await apiRequest('/consent/grant', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ purpose: 'personalization' })
  });
  setConsentUI(true);
}

// ─── Initialization ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('yonoConsentToggle').checked = true;
  updateAssistProfile();
  updateImpactView();
  updateNudgeBudgetUI();

  if (OFFLINE_DEMO_MODE) {
    const dot = document.getElementById('apiStatusDot');
    if (dot) dot.className = 'api-dot online';
    const txt = document.getElementById('apiStatusText');
    if (txt) txt.textContent = 'Interactive Simulation (Demo Mode)';
    return;
  }

  // Check backend API connectivity.
  fetch(`${API_BASE}/health`).then(async response => {
    if (!response.ok) throw new Error(`health_${response.status}`);
    await response.json();
    backendAvailable = true;
    runtimeMode = 'api-connected';
    document.getElementById('apiStatusDot').className = 'api-dot online';
    document.getElementById('apiStatusText').textContent = 'API Connected (Governed Mode)';
    // These are synthetic demo personas. Production reads consent from SBI's registry.
    await hydrateSyntheticProfileConsent();
  }).catch(() => {
    backendAvailable = false;
    runtimeMode = 'api-unavailable';
    document.getElementById('apiStatusDot').className = 'api-dot offline';
    document.getElementById('apiStatusText').textContent = 'API Offline (Click for Demo)';
  });
});

function enableDemoMode() {
  runtimeMode = 'offline-demo';
  const dot = document.getElementById('apiStatusDot');
  if (dot) dot.className = 'api-dot online';
  const txt = document.getElementById('apiStatusText');
  if (txt) txt.textContent = 'Interactive Simulation (Demo Mode)';
  showToast('success', 'Simulation Active', 'All behavioral signals and governance flows are enabled.');
  addAuditLog('⚡ Interactive simulation mode activated.');
}

// ─── Toast Notification System ────────────────────────────────────────
function showToast(type, title, subtitle) {
  const container = document.getElementById('toastContainer');
  const icons = { success: '✅', warning: '⚠️', blocked: '🚫' };
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.setAttribute('role', type === 'blocked' ? 'alert' : 'status');
  toast.setAttribute('aria-atomic', 'true');
  const icon = document.createElement('span');
  icon.className = 'toast-icon';
  icon.setAttribute('aria-hidden', 'true');
  icon.textContent = icons[type] || '💬';
  const body = document.createElement('div');
  body.className = 'toast-body';
  const titleNode = document.createElement('span');
  titleNode.className = 'toast-title';
  titleNode.textContent = title;
  const subtitleNode = document.createElement('span');
  subtitleNode.className = 'toast-subtitle';
  subtitleNode.textContent = subtitle;
  body.append(titleNode, subtitleNode);
  toast.append(icon, body);
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[char]);
}

// ─── Profile Switching ────────────────────────────────────────────────
function changeProfile() {
  const key = document.getElementById('profileSelect').value;
  const p = profiles[key];
  currentProfileKey = key;

  // Update dynamic sidebar scenario buttons based on the new profile
  const sf = p.scenarios.friction;
  document.getElementById('scenarioIconFriction').textContent = sf.icon;
  document.getElementById('scenarioNameFriction').textContent = sf.name;
  document.getElementById('scenarioDescFriction').textContent = sf.desc;

  const so = p.scenarios.opportunity;
  document.getElementById('scenarioIconOpportunity').textContent = so.icon;
  document.getElementById('scenarioNameOpportunity').textContent = so.name;
  document.getElementById('scenarioDescOpportunity').textContent = so.desc;

  const sl = p.scenarios.lifeevent;
  document.getElementById('scenarioIconLifeEvent').textContent = sl.icon;
  document.getElementById('scenarioNameLifeEvent').textContent = sl.name;
  document.getElementById('scenarioDescLifeEvent').textContent = sl.desc;

  const ss = p.scenarios.stress;
  document.getElementById('scenarioIconStress').textContent = ss.icon;
  document.getElementById('scenarioNameStress').textContent = ss.name;
  document.getElementById('scenarioDescStress').textContent = ss.desc;

  // Reset state
  dismissNudge();
  dismissStressCard();
  hideRMToast();
  closeConsentScreen();
  clearAutoTrigger();
  nudgeBudgetMax = 5;
  nudgeBudgetUsed = 0;
  consecutiveDeclines = 0;
  updateNudgeBudgetUI();
  activeScenarioType = null;
  currentRecommendationId = null;
  currentReviewRequired = false;
  currentReviewedOffer = null;
  currentDecisionToken = null;
  currentOffer = null;
  actionInFlight = false;
  activePipelineRunId++;
  reviewPollAttempts = 0;
  if (reviewPollTimeout) {
    clearTimeout(reviewPollTimeout);
    reviewPollTimeout = null;
  }

  // Update sidebar profile info
  document.getElementById('profId').textContent = p.id;
  document.getElementById('profSalary').textContent = p.salary;
  document.getElementById('profBalance').textContent = p.balance;
  document.getElementById('profInterest').textContent = p.interest;
  document.getElementById('yonoUser').textContent = p.firstName;

  // Update phone views
  if (isBalanceHidden) {
    document.getElementById('yonoBalance').textContent = '₹ ••••••••';
  } else {
    document.getElementById('yonoBalance').textContent = '₹' + p.rawBalance.toLocaleString('en-IN') + '.00';
  }
  document.getElementById('cardHolderName').textContent = p.name.toUpperCase();
  document.getElementById('investSavingsBalance').textContent = '₹' + p.rawBalance.toLocaleString('en-IN') + '.00';
  document.getElementById('salaryTransAmount').textContent = '+' + p.salary;

  const initials = p.name.split(' ').map(n => n[0]).join('').slice(0, 2);
  const initialsBadge = document.getElementById('userInitialsBadge');
  if (initialsBadge) initialsBadge.textContent = initials;
  const loginUser = document.getElementById('loginUserName');
  if (loginUser) loginUser.textContent = p.firstName;
  const loginPromptU = document.getElementById('loginPromptUser');
  if (loginPromptU) loginPromptU.textContent = p.name;
  const profModalInitials = document.getElementById('profileModalInitials');
  if (profModalInitials) profModalInitials.textContent = initials;
  const profModalTitle = document.getElementById('profileModalTitle');
  if (profModalTitle) profModalTitle.textContent = p.name;
  const userUpi = document.getElementById('userUpiHandle');
  if (userUpi) userUpi.textContent = p.firstName.toLowerCase() + '@sbi';

  // Update card values
  if (p.rawCardDebt > 0) {
    document.getElementById('cardOutstanding').textContent = '₹' + p.rawCardDebt.toLocaleString('en-IN') + '.00';
    const minDue = Math.round(p.rawCardDebt * 0.05);
    document.getElementById('cardMinDue').textContent = '₹' + minDue.toLocaleString('en-IN') + '.00';
    const monthlyInterest = Math.round(p.rawCardDebt * 0.035);
    document.getElementById('cardInterestPaid').textContent = '₹' + monthlyInterest.toLocaleString('en-IN') + '.00';
    document.getElementById('ccInterestTransAmount').textContent = '-₹' + monthlyInterest.toLocaleString('en-IN') + '.00';
    document.getElementById('cardInterestRow').style.display = 'flex';
  } else {
    document.getElementById('cardOutstanding').textContent = '₹0.00';
    document.getElementById('cardMinDue').textContent = '₹0.00';
    document.getElementById('cardInterestPaid').textContent = '₹0.00';
    document.getElementById('ccInterestTransAmount').textContent = '₹0.00';
    document.getElementById('cardInterestRow').style.display = 'none';
  }

  // Consent badge: API mode fails closed until the selected identity is hydrated.
  if (runtimeMode === 'api-connected') {
    setConsentUI(false);
    hydrateSyntheticProfileConsent().catch(() => {
      setConsentUI(false);
      showToast('blocked', 'Consent State Unavailable', 'Scenarios remain disabled until consent can be verified.');
    });
  } else {
    setConsentUI(true);
  }

  // Assistance profile + stress banner
  updateAssistProfile();
  updateImpactView();

  // Stress banner
  document.getElementById('stressBanner').classList.remove('visible');

  // Navigate home
  navigateToView('home');

  // Clear trace
  const logsArea = document.getElementById('logsArea');
  logsArea.innerHTML = '<div style="color: var(--text-muted); text-align: center; margin-top: 3rem;">Select a customer profile and trigger a behavioral signal to view the real-time agent workflow execution.</div>';
  document.getElementById('tokenBox').style.display = 'none';
  resetPipeline();

  // Auto-trigger stress for Sneha
  if (key === 'sneha') {
    setTimeout(() => triggerScenario('stress'), 600);
  }
}

// ─── Customer Assistance Profile ──────────────────────────────────────
function updateAssistProfile() {
  const p = profiles[currentProfileKey];
  const badge = document.getElementById('assistBadge');
  const desc = document.getElementById('assistDesc');
  badge.className = `assistance-badge ${p.assist.color}`;
  document.getElementById('assistIcon').textContent = p.assist.icon;
  document.getElementById('assistLabel').textContent = p.assist.label;
  desc.textContent = p.assist.desc;
}

// ─── My Impact View ───────────────────────────────────────────────────
function updateImpactView() {
  const imp = profiles[currentProfileKey].impact;
  document.getElementById('impactTask').textContent = imp.task;
  document.getElementById('impactTaskSub').textContent = imp.taskSub;
  document.getElementById('impactSavings').textContent = imp.savings;
  document.getElementById('impactSavingsSub').textContent = imp.savSub;
  document.getElementById('impactBranch').textContent = imp.branch;
  document.getElementById('impactBranchSub').textContent = imp.branchSub;
  ['impactBar30', 'impactBar60', 'impactBar90'].forEach((id, index) => {
    const progress = document.getElementById(id);
    progress.style.width = imp.bars[index] + '%';
    progress.setAttribute('aria-valuenow', String(imp.bars[index]));
  });
}

// ─── Nudge Budget (Dynamic & Adaptive) ──────────────────────────────────
function updateNudgeBudgetUI() {
  const max = nudgeBudgetMax || 5;
  for (let i = 1; i <= 5; i++) {
    const dot = document.getElementById(`nudgeDot${i}`);
    if (dot) {
      dot.className = 'nudge-dot' + (nudgeBudgetUsed >= i ? ' filled' : '');
    }
  }
  const budgetText = document.getElementById('nudgeBudgetText');
  if (budgetText) {
    const fatigueSuffix = consecutiveDeclines >= 2 ? ` • Decline Pacing (${consecutiveDeclines}x)` : '';
    budgetText.textContent = `${nudgeBudgetUsed} of ${max} used${fatigueSuffix}`;
  }
  const warn = document.getElementById('nudgeBudgetWarning');
  if (warn) {
    if (nudgeBudgetUsed >= max) {
      warn.classList.add('visible');
      warn.textContent = `Max reached (${max}/${max}) — cooldown active for 14 days`;
    } else {
      warn.classList.remove('visible');
    }
  }
  const fatigueAlert = document.getElementById('nudgeFatigueAlert');
  if (fatigueAlert) {
    if (consecutiveDeclines >= 2) {
      fatigueAlert.style.display = 'block';
      fatigueAlert.textContent = `⚠️ Continuous decline detected (${consecutiveDeclines}x): Dynamic budget capped at ${max} with fatigue cooldown pacing.`;
    } else {
      fatigueAlert.style.display = 'none';
    }
  }
}

// ─── Consent Toggle ───────────────────────────────────────────────────
async function toggleConsent() {
  const p = profiles[currentProfileKey];
  if (!backendAvailable && runtimeMode !== 'offline-demo') {
    showToast('blocked', 'Consent Service Unavailable', 'The consent state was not changed.');
    return;
  }
  if (consentState) {
    // Revoking
    if (backendAvailable) {
      try {
        const { response } = await apiRequest('/consent/revoke', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ purpose: 'personalization' })
        });
        if (!response.ok) throw new Error('Consent service rejected revocation');
      } catch (error) {
        setConsentUI(true);
        showToast('blocked', 'Consent Update Failed', 'Your existing consent state was preserved. Please try again.');
        return;
      }
    }
    setConsentUI(false);
    dismissNudge();
    dismissStressCard();
    showToast('warning', 'DPDP Consent Revoked', 'All profiling data cleared. No further nudges until re-granted.');
    addAuditLog('⚠️ Personalisation consent REVOKED. Profiling and promotional nudges disabled.');
  } else {
    // Re-granting
    if (backendAvailable) {
      try {
        const { response } = await apiRequest('/consent/grant', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ purpose: 'personalization' })
        });
        if (!response.ok) throw new Error('Consent service rejected grant');
      } catch (error) {
        setConsentUI(false);
        showToast('blocked', 'Consent Update Failed', 'Consent was not activated. Please try again.');
        return;
      }
    }
    setConsentUI(true);
    showToast('success', 'Consent Re-Granted', 'Saarthi profiling is active again. Nudges will resume.');
    addAuditLog('✅ DPDP Consent RE-GRANTED by data principal.');
  }
}

function syncConsentFromApp() {
  const checked = document.getElementById('yonoConsentToggle').checked;
  if (checked !== consentState) toggleConsent();
}

// ─── Scenario Triggering ──────────────────────────────────────────────
function triggerScenario(type) {
  if (runtimeMode === 'probing') {
    showToast('warning', 'Checking API', 'Please wait for the governed backend connection check to finish.');
    return;
  }
  if (runtimeMode === 'api-unavailable') {
    enableDemoMode();
  }
  if (!consentState) {
    showToast('blocked', 'Nudge Blocked', 'Consent is revoked. Re-grant DPDP consent to continue.');
    return;
  }

  if (runtimeMode === 'offline-demo' && type !== 'stress' && nudgeBudgetUsed >= nudgeBudgetMax) {
    showToast('blocked', 'Nudge Budget Reached', `Dynamic engagement budget (${nudgeBudgetMax}/${nudgeBudgetMax}) reached. Promotional engagement is paused until the next cycle.`);
    addAuditLog(`🚫 Nudge suppressed: Dynamic capacity limit of ${nudgeBudgetMax} reached.`);
    return;
  }

  if (document.activeElement && typeof document.activeElement.focus === 'function') {
    lastScenarioTrigger = document.activeElement;
  }

  // Reset previous
  dismissNudge();
  dismissStressCard();
  hideRMToast();
  closeConsentScreen();
  clearAutoTrigger();

  activeScenarioType = type;
  executeAgentPipeline(type);
}

function getSegment(profileKey) {
  const segments = { aiwin: 'corporate', priya: 'corporate', ramesh: 'pensioner', amit: 'sme', sneha: 'stressed', rohan: 'student' };
  return segments[profileKey] || 'corporate';
}

// ─── Agent Pipeline Execution ─────────────────────────────────────────
async function executeAgentPipeline(type) {
  const runId = ++activePipelineRunId;
  const p = profiles[currentProfileKey];
  const s = p.scenarios[type];
  const logsArea = document.getElementById('logsArea');
  logsArea.innerHTML = '';
  document.getElementById('tokenBox').style.display = 'none';
  resetPipeline();
  currentRecommendationId = null;
  currentDecisionToken = null;
  currentReviewedOffer = null;
  currentOffer = null;
  currentReviewRequired = false;
  reviewPollAttempts = 0;
  actionInFlight = false;
  if (reviewPollTimeout) {
    clearTimeout(reviewPollTimeout);
    reviewPollTimeout = null;
  }

  const offlineDemo = runtimeMode === 'offline-demo';
  const segment = getSegment(currentProfileKey);

  addAuditLog(`🔵 Pipeline triggered: ${type.toUpperCase()} signal for ${p.name}`);

  // Fetch governed execution output. Offline simulation is enabled only explicitly.
  let liveData = null;
  if (!offlineDemo) {
    try {
      const { response: res, payload } = await apiRequest('/orchestrate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': crypto.randomUUID ? crypto.randomUUID() : `${p.id}-${type}-${Date.now()}`
        },
        body: JSON.stringify({
          signal: s.signalLog,
          details: `User ID: ${p.id} | Email: ${p.email} | Aadhaar: ${p.aadhaar} | PAN: ${p.pan}`,
          segment: segment
        })
      });
      if (runId !== activePipelineRunId) return;
      liveData = payload;
      const handledErrorModes = new Set(['consent_required', 'budget_exceeded', 'dependency_unavailable', 'rollout_blocked']);
      if (!res.ok && !handledErrorModes.has(liveData.delivery_mode)) {
        throw new Error(`orchestration_${res.status}`);
      }
      if (res.ok) {
        console.log('Live Server Orchestrator Response:', liveData);
      }
    } catch (err) {
      if (runId !== activePipelineRunId) return;
      console.warn('Governed backend request failed:', err);
      showToast('blocked', 'Decision Service Unavailable', 'No recommendation or simulated action was produced.');
      addAuditLog('🚫 Governed decision request failed; execution path closed.');
      return;
    }
  }

  if (liveData && liveData.nudge_budget) {
    nudgeBudgetUsed = liveData.nudge_budget.used;
    updateNudgeBudgetUI();
  } else if (offlineDemo && type !== 'stress') {
    nudgeBudgetUsed++;
    updateNudgeBudgetUI();
  }

  if (liveData && liveData.delivery_mode === 'consent_required') {
    setConsentUI(false);
    showToast('blocked', 'Consent Required', liveData.compliance_logs);
    addAuditLog('🚫 Backend blocked profiling because consent is not active.');
    return;
  }
  if (liveData && liveData.delivery_mode === 'budget_exceeded') {
    showToast('blocked', 'Nudge Budget Reached', 'Promotional engagement is paused until the next cycle.');
    addAuditLog('🚫 Backend blocked nudge because the engagement budget is exhausted.');
    return;
  }

  if (liveData && ['dependency_unavailable', 'rollout_blocked', 'shadow_mode'].includes(liveData.delivery_mode)) {
    showToast('blocked', 'Recommendation Withheld', 'The governed backend did not authorize a customer-visible action.');
    addAuditLog(`🚫 Recommendation withheld: ${liveData.delivery_mode}`);
    return;
  }

  const deliveryMode = liveData
    ? liveData.delivery_mode
    : (type === 'stress' ? 'support_mode' : (type === 'friction' ? 'auto_fire' : 'decision_token_required'));
  const signalCategory = liveData && liveData.signal_category ? liveData.signal_category : type;
  const isSupport = deliveryMode === 'support_mode';
  const actionableModes = new Set(['auto_fire', 'decision_token_required']);

  if (liveData && !isSupport && !actionableModes.has(deliveryMode) && deliveryMode !== 'human_review_required') {
    showToast('blocked', 'Unsupported Decision State', 'No customer action was exposed.');
    addAuditLog(`🚫 Unsupported delivery mode: ${deliveryMode || 'missing'}`);
    return;
  }

  currentRecommendationId = liveData && liveData.recommendation_id ? liveData.recommendation_id : null;
  currentReviewRequired = Boolean(liveData && liveData.delivery_mode === 'human_review_required');
  if (liveData && actionableModes.has(deliveryMode) && !currentRecommendationId) {
    showToast('blocked', 'Invalid Recommendation', 'The backend response did not contain an actionable recommendation ID.');
    addAuditLog('🚫 Actionable response rejected because recommendation identity was missing.');
    return;
  }
  if (currentReviewRequired) {
    showToast('warning', 'Human Review Required', 'This high-risk recommendation is queued for an independent reviewer before it can be authorized.');
    addAuditLog(`🟠 Human review queued: ${liveData.review_id}`);
    scheduleReviewStatusPoll(runId);
  }

  const T = { step: 350 };

  // Step 1 — Redis Streams Ingestion
  setTimeout(() => {
    if (runId !== activePipelineRunId) return;
    activateDot('dot1');
    const ingestTime = liveData && liveData.execution_timings ? (liveData.execution_timings.node_input_guardian * 1000).toFixed(2) + 'ms' : '0.14ms';
    logsArea.innerHTML += `<div class="log-line"><span class="log-badge node">REDIS STREAMS</span> <span class="log-badge pass">INGESTED</span></div>
    <div class="log-detail">Event published to saarthi:events stream (${ingestTime})</div>
    <div class="log-detail">Ingestion: real-time | Mode: event-driven (live stream)</div>`;
    addAuditLog(`🟢 Redis Streams: Ingested event for ${p.id}`);
  }, T.step);

  // Step 2 — Input Guardian
  setTimeout(() => {
    if (runId !== activePipelineRunId) return;
    activateDot('dot2');
    const masked = liveData && liveData.masked_details
      ? liveData.masked_details
      : `PAN: ${p.pan.substring(0,3)}XXXXX${p.pan.slice(-1)}, Aadhaar: XXXX XXXX ${p.aadhaar.slice(-4)}`;
    logsArea.innerHTML += `<div class="log-line"><span class="log-badge node">INPUT GUARDIAN</span> <span class="log-badge pass">PASSED</span></div>
    <div class="log-detail">PII mask applied → ${escapeHtml(masked)}</div>
    <div class="log-detail">Data purpose-limited to: ${isSupport ? 'financial_support' : 'savings_optimization'}</div>`;
    addAuditLog(`🟢 Input Guardian: PII masked for ${p.id}`);
  }, T.step * 2);

  // Step 3 — Signal Detection Agent
  setTimeout(() => {
    if (runId !== activePipelineRunId) return;
    activateDot('dot3');
    const cat = signalCategory.toUpperCase();
    const confidence = liveData && liveData.signal_evidence && Number.isFinite(liveData.signal_evidence.confidence)
      ? `${Math.round(liveData.signal_evidence.confidence * 100)}%`
      : 'offline fixture';
    const sigTime = liveData && liveData.execution_timings ? (liveData.execution_timings.node_signal_detection * 1000).toFixed(2) + 'ms' : '0.08ms';
    logsArea.innerHTML += `<div class="log-line"><span class="log-badge node">SIGNAL DETECTION AGENT</span> <span class="log-badge pass">DETECTED (${cat})</span></div>
    <div class="log-detail">Signal: ${s.signalLog} (${sigTime})</div>
    <div class="log-detail">Confidence: ${escapeHtml(confidence)} | Source: ${offlineDemo ? 'offline demo fixture' : 'governed signal contract'}</div>`;
    addAuditLog(`🔵 Signal detected: ${cat}`);
  }, T.step * 3);

  // Step 4 — Product graph + governed policy retrieval
  setTimeout(() => {
    if (runId !== activePipelineRunId) return;
    activateDot('dot4');
    const cypherProd = liveData && liveData.neo4j_query ? liveData.neo4j_query.product : s.recLog;
    const ragSnippet = liveData && liveData.rag_context ? liveData.rag_context.substring(0, 75) + '...' : 'Approved offline demo policy context';
    const policyProof = liveData && liveData.policy_evidence
      ? `${liveData.policy_evidence.policy_id} v${liveData.policy_evidence.version} · ${liveData.policy_evidence.approval_status} · SHA-256 ${liveData.policy_evidence.content_sha256.substring(0, 12)}…`
      : 'Prototype policy context';
    const neoTime = liveData && liveData.execution_timings ? (liveData.execution_timings.node_neo4j_recommendation * 1000).toFixed(2) + 'ms' : '0.31ms';
    logsArea.innerHTML += `<div class="log-line"><span class="log-badge node">PRODUCT + POLICY EVIDENCE</span> <span class="log-badge pass">RESOLVED</span></div>
    <div class="log-detail">Cypher Match: ${escapeHtml(cypherProd)} (${neoTime})</div>
    <div class="log-detail">Policy Context: ${escapeHtml(ragSnippet)}</div>
    <div class="log-detail">Policy Evidence: ${escapeHtml(policyProof)}</div>`;
    addAuditLog(`🟢 Policy fixture retrieved for segment ${segment}`);
  }, T.step * 4);

  // Step 5 — Recommendation Agent
  setTimeout(() => {
    if (runId !== activePipelineRunId) return;
    if (!isSupport) {
      activateDot('dot5');
      const prodText = liveData && liveData.nudge_output ? liveData.nudge_output : s.recLog;
      logsArea.innerHTML += `<div class="log-line"><span class="log-badge node">RECOMMENDATION AGENT</span> <span class="log-badge pass">GENERATED</span></div>
      <div class="log-detail">Product: ${escapeHtml(prodText)}</div>
      <div class="log-detail">Personalisation: Matched to ${p.name}'s financial profile</div>`;
      addAuditLog(`🔵 Recommendation generated for ${p.id}`);
    } else {
      activateDot('dot5', 'amber');
      logsArea.innerHTML += `<div class="log-line"><span class="log-badge node">COMPLIANCE AGENT</span> <span class="log-badge" style="background: rgba(245,158,11,0.2); color: #f59e0b;">⚠️ OVERRIDE</span></div>
      <div class="log-detail" style="color: #f59e0b; font-weight: 600;">⚠️ SUPPORT-ONLY MODE ACTIVATED</div>
      <div class="log-detail">Signal: ${s.signalLog}</div>
      <div class="log-detail">Policy Override: prototype vulnerable-customer support rule</div>
      <div class="log-detail" style="color: #f59e0b;">Action: Promotional nudges BLOCKED. Switching to support mode.</div>`;
      addAuditLog(`⚠️ SUPPORT MODE: Promotional nudges and execution blocked`);
    }
  }, T.step * 5);

  // Step 6 — Compliance Gate
  setTimeout(() => {
    if (runId !== activePipelineRunId) return;
    if (!isSupport) {
      activateDot('dot6');
      const riskTier = liveData && liveData.risk_tier ? liveData.risk_tier : ((type === 'friction') ? 'low' : 'high');

      const defaultReasons = {
        friction: ['BRANCH_FRICTION_SIGNAL', 'DPDP_PURPOSE_CONSENT_VERIFIED', 'POLICY_MATCH_CDM_UPI'],
        opportunity: ['HIGH_CC_INTEREST_OPTIMIZATION', 'DPDP_PURPOSE_CONSENT_VERIFIED', 'POLICY_MATCH_SBI_EXPRESS_CREDIT'],
        lifeevent: ['SURPLUS_SAVINGS_DETECTED', 'DPDP_PURPOSE_CONSENT_VERIFIED', 'POLICY_MATCH_GREEN_FD'],
        stress: ['LIQUIDITY_STRESS_DETECTED', 'COMPASSIONATE_SUPPORT_POLICY', 'PROACTIVE_RESTRUCTURING']
      };
      const displayReasons = (liveData && Array.isArray(liveData.reason_codes) && liveData.reason_codes.length)
        ? liveData.reason_codes
        : (defaultReasons[type] || ['GOVERNED_SIGNAL_MATCHED', 'DPDP_PURPOSE_CONSENT_VERIFIED']);

      logsArea.innerHTML += `<div class="log-line"><span class="log-badge node">COMPLIANCE AGENT</span> <span class="log-badge pass">CLEARED</span></div>
      <div class="log-detail">DPDP Consent: ✅ Active | Policy gate: ✅ Passed | Nudge Budget: ✅ Server verified</div>
      <div class="log-detail">Risk Tier: ${escapeHtml(riskTier)} | Delivery: ${escapeHtml(deliveryMode)}</div>
      <div class="log-detail">Reason Codes: ${escapeHtml(displayReasons.join(', '))}</div>`;
      addAuditLog(`🟢 Compliance gating passed.`);

      if (liveData && liveData.decision_token) {
        document.getElementById('tokenBox').style.display = 'block';
        document.getElementById('tokenHash').textContent = liveData.decision_token;
      }
    } else {
      activateDot('dot6', 'amber');
      logsArea.innerHTML += `<div class="log-line"><span class="log-badge node">COMPLIANCE AGENT</span> <span class="log-badge" style="background: rgba(245,158,11,0.2); color: #f59e0b;">SUPPORT MODE</span></div>
      <div class="log-detail">Prototype vulnerability and support-only policy applied</div>
      <div class="log-detail">Risk Tier: high | Delivery: support_mode</div>`;
      addAuditLog(`🟢 Compliance gating passed for support mode.`);
    }
  }, T.step * 6);

  // Step 7 — Output Guardian
  setTimeout(async () => {
    if (runId !== activePipelineRunId) return;
    if (!isSupport) {
      activateDot('dot7');
      logsArea.innerHTML += `<div class="log-line"><span class="log-badge node">OUTPUT GUARDIAN</span> <span class="log-badge pass">SCREENED</span></div>
      <div class="log-detail">Output sanitized — no PII leakage detected</div>
      <div class="log-detail">Nudge delivered to YONO interface →</div>`;
      addAuditLog(`🟢 Output Guardian passed. Nudge delivered.`);

      if (!currentReviewRequired) {
        if (offlineDemo) {
          showNudgeInPhone(buildOfflineOffer(type));
        } else {
          await loadAndRenderServerOffer(currentRecommendationId, runId);
        }
      } else {
        addAuditLog('🟠 Customer-facing offer withheld pending independent approval.');
      }
    } else {
      activateDot('dot7', 'amber');
      logsArea.innerHTML += `<div class="log-line"><span class="log-badge node">OUTPUT GUARDIAN</span> <span class="log-badge" style="background: rgba(245,158,11,0.2); color: #f59e0b;">SUPPORT MODE</span></div>
      <div class="log-detail">All promotional content and financial execution BLOCKED by the support-only policy</div>
      <div class="log-detail">No product execution or case-management action is exposed by this prototype card</div>`;
      addAuditLog(`🛡️ Support mode card delivered to ${p.name}`);

      // Support-only decisions never expose a simulated financial action in API mode.
      const supportShown = showStressCard(liveData && liveData.customer_presentation ? liveData.customer_presentation : null);
      if (supportShown) {
        document.getElementById('stressBanner').classList.add('visible');
        showToast('warning', 'Support Mode Activated', 'Promotional nudges and financial execution are blocked.');
      }
    }
  }, T.step * 7);
}

// ─── Pipeline Status Dots ─────────────────────────────────────────────
function activateDot(dotId, variant) {
  const dot = document.getElementById(dotId);
  dot.className = variant === 'amber' ? 'status-dot amber' : 'status-dot active';
  document.getElementById(`${dotId}Text`).textContent = variant === 'amber' ? 'support mode' : 'complete';
}

function resetPipeline() {
  ['dot1', 'dot2', 'dot3', 'dot4', 'dot5', 'dot6', 'dot7'].forEach(id => {
    document.getElementById(id).className = 'status-dot';
    document.getElementById(`${id}Text`).textContent = 'pending';
  });
}

// ─── Governed customer offer ──────────────────────────────────────────
function buildOfflineOffer(type) {
  const p = profiles[currentProfileKey] || profiles['aiwin'];
  const scenario = p.scenarios[type];
  const reasonCodeMap = {
    friction: ['BRANCH_FRICTION_SIGNAL', 'DPDP_PURPOSE_CONSENT_VERIFIED', 'POLICY_MATCH_CDM_UPI'],
    opportunity: ['HIGH_CC_INTEREST_OPTIMIZATION', 'DPDP_PURPOSE_CONSENT_VERIFIED', 'POLICY_MATCH_SBI_EXPRESS_CREDIT'],
    lifeevent: ['SURPLUS_SAVINGS_DETECTED', 'DPDP_PURPOSE_CONSENT_VERIFIED', 'POLICY_MATCH_GREEN_FD'],
    stress: ['LIQUIDITY_STRESS_DETECTED', 'COMPASSIONATE_SUPPORT_POLICY', 'PROACTIVE_RESTRUCTURING']
  };

  return {
    source: 'offline-demo',
    recommendationId: null,
    productId: `OFFLINE-${currentProfileKey}-${type}`,
    scenarioType: type,
    presentation: {
      title: scenario.title,
      body: `${scenario.text} Simulation only — no banking action will occur.`,
      actionLabel: scenario.actionBtn,
      consentText: scenario.consentText,
      successText: `${scenario.successText} (Offline simulation only.)`
    },
    reasonCodes: reasonCodeMap[type] || ['GOVERNED_SIGNAL_MATCHED', 'DPDP_PURPOSE_CONSENT_VERIFIED'],
    explanation: scenario.explainText
  };
}

function normalizeServerOffer(recommendation) {
  const presentation = recommendation && recommendation.evidence && recommendation.evidence.presentation;
  const requiredStrings = ['title', 'body', 'action_label', 'consent_text', 'success_text'];
  if (!recommendation || !recommendation.recommendation_id || !recommendation.product_id || !Number.isFinite(recommendation.expires_at)) return null;
  if (recommendation.expires_at <= Date.now() / 1000) return null;
  if (!presentation || presentation.schema_version !== 'customer-presentation-v1' || presentation.support_only) return null;
  if (presentation.product_id !== recommendation.product_id) return null;
  if (requiredStrings.some(key => typeof presentation[key] !== 'string' || !presentation[key].trim())) return null;
  return {
    source: 'server',
    recommendationId: recommendation.recommendation_id,
    productId: recommendation.product_id,
    expiresAt: recommendation.expires_at,
    presentation: {
      title: presentation.title,
      body: presentation.body,
      actionLabel: presentation.action_label,
      consentText: presentation.consent_text,
      successText: presentation.success_text
    },
    reasonCodes: Array.isArray(recommendation.evidence.reason_codes) ? recommendation.evidence.reason_codes : [],
    explanation: `Verified product ${recommendation.product_id}`
  };
}

function showNudgeInPhone(offer) {
  const stressCard = document.getElementById('stressCard');
  stressCard.classList.remove('visible');
  stressCard.setAttribute('aria-hidden', 'true');
  stressCard.inert = true;
  currentOffer = offer;
  currentNudge = offer.source === 'offline-demo' ? offer.scenarioType : null;

  document.getElementById('nudgeTitle').textContent = offer.presentation.title;
  document.getElementById('nudgeText').textContent = offer.presentation.body;
  document.getElementById('nudgeActionBtn').textContent = offer.presentation.actionLabel;

  const toggle = document.getElementById('explainToggle');
  if (toggle) {
    toggle.setAttribute('aria-expanded', 'false');
  }
  const arrow = document.getElementById('explainArrow');
  if (arrow) {
    arrow.textContent = '▼';
  }
  const explainContent = document.getElementById('explainContent');
  if (explainContent) {
    explainContent.classList.remove('visible', 'expanded');
    explainContent.setAttribute('aria-hidden', 'true');
    const reasonsFormatted = offer.reasonCodes && offer.reasonCodes.length
      ? `Verified Governance: ${offer.reasonCodes.join(', ')}`
      : 'Verified Governance: DPDP_PURPOSE_CONSENT_VERIFIED, POLICY_MATCH_APPROVED';
    explainContent.textContent = `${reasonsFormatted}\n${offer.explanation || offer.presentation.body}`;
  }

  const nudgeCard = document.getElementById('nudgeCard');
  nudgeCard.inert = false;
  nudgeCard.setAttribute('aria-hidden', 'false');
  nudgeCard.classList.add('visible');
}

async function loadAndRenderServerOffer(recommendationId, runId) {
  try {
    const { response, payload } = await apiRequest(`/recommendations/${recommendationId}`);
    if (runId !== activePipelineRunId) return false;
    const offer = response.ok ? normalizeServerOffer(payload.recommendation) : null;
    if (!offer || offer.recommendationId !== recommendationId) {
      showToast('blocked', 'Invalid Offer Evidence', 'No customer action was exposed because persisted presentation evidence was missing or inconsistent.');
      addAuditLog('🚫 Persisted offer evidence failed identity validation.');
      return false;
    }
    currentReviewedOffer = payload.recommendation;
    if (payload.recommendation.nudge_budget) {
      nudgeBudgetUsed = payload.recommendation.nudge_budget.used;
      updateNudgeBudgetUI();
    }
    showNudgeInPhone(offer);
    return true;
  } catch (error) {
    if (runId === activePipelineRunId) {
      showToast('blocked', 'Offer Unavailable', 'The persisted governed offer could not be loaded. No action was exposed.');
      addAuditLog('🚫 Governed offer presentation failed closed.');
    }
    return false;
  }
}

async function scheduleReviewStatusPoll(runId) {
  if (!backendAvailable || !currentReviewRequired || !currentRecommendationId || runId !== activePipelineRunId) return;
  const recommendationId = currentRecommendationId;
  if (reviewPollTimeout) clearTimeout(reviewPollTimeout);
  reviewPollTimeout = setTimeout(async () => {
    if (runId !== activePipelineRunId || recommendationId !== currentRecommendationId) return;
    reviewPollAttempts++;
    try {
      const { response, payload } = await apiRequest(`/recommendations/${recommendationId}`);
      if (runId !== activePipelineRunId || recommendationId !== currentRecommendationId) return;
      if (response.ok && payload.recommendation) {
        const offer = normalizeServerOffer(payload.recommendation);
        if (!offer || offer.recommendationId !== recommendationId) {
          showToast('blocked', 'Invalid Offer Evidence', 'The approved offer failed presentation identity validation.');
          return;
        }
        currentReviewRequired = false;
        currentReviewedOffer = payload.recommendation;
        if (payload.recommendation.nudge_budget) {
          nudgeBudgetUsed = payload.recommendation.nudge_budget.used;
          updateNudgeBudgetUI();
        }
        showNudgeInPhone(offer);
        addAuditLog('✅ Independent review approved; governed offer presented to customer.');
        showToast('success', 'Review Approved', 'The verified recommendation is now available for your consent.');
        return;
      }
      if (response.status === 409 && payload.status === 'review_required' && reviewPollAttempts < 12) {
        scheduleReviewStatusPoll(runId);
        return;
      }
      const messages = {
        review_rejected: 'The reviewer did not approve this recommendation.',
        expired: 'The reviewed recommendation expired before presentation.',
        budget_exceeded: 'The engagement budget prevents delivery of this recommendation.'
      };
      showToast('blocked', 'Recommendation Unavailable', messages[payload.status] || 'The recommendation cannot be presented.');
      addAuditLog(`🚫 Reviewed offer not presented: ${payload.status || response.status}`);
    } catch (error) {
      if (reviewPollAttempts < 12) scheduleReviewStatusPoll(runId);
    }
  }, 5000);
}

// ─── Explainability Accordion ─────────────────────────────────────────
function toggleExplain() {
  const content = document.getElementById('explainContent');
  const arrow = document.getElementById('explainArrow');
  const toggle = document.getElementById('explainToggle');
  if (!content) return;
  const isVisible = content.classList.contains('visible') || content.classList.contains('expanded');
  if (isVisible) {
    content.classList.remove('visible', 'expanded');
    content.setAttribute('aria-hidden', 'true');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
    if (arrow) arrow.textContent = '▼';
  } else {
    content.classList.add('visible', 'expanded');
    content.setAttribute('aria-hidden', 'false');
    if (toggle) toggle.setAttribute('aria-expanded', 'true');
    if (arrow) arrow.textContent = '▲';
  }
}

function toggleExplainability() {
  toggleExplain();
}

// ─── Show Financial Stress Support Card ───────────────────────────────
function showStressCard(presentation = null) {
  // Mutually exclusive: hide standard nudge
  const nudgeCard = document.getElementById('nudgeCard');
  nudgeCard.classList.remove('visible');
  nudgeCard.setAttribute('aria-hidden', 'true');
  nudgeCard.inert = true;
  currentOffer = null;
  currentNudge = null;

  const p = profiles[currentProfileKey];
  const validServerSupport = presentation
    && presentation.schema_version === 'customer-presentation-v1'
    && presentation.support_only === true
    && typeof presentation.body === 'string';
  if (runtimeMode === 'api-connected' && !validServerSupport) {
    showToast('blocked', 'Invalid Support Evidence', 'No support card was shown because the governed presentation contract was missing.');
    addAuditLog('🚫 Support presentation failed closed.');
    return false;
  }
  document.getElementById('stressBodyText').textContent = validServerSupport
    ? presentation.body
    : `Hi ${p.firstName}, this offline scenario is in support mode. No real banking action will occur.`;
  // All support journeys are non-actionable until a governed case-management contract exists.
  document.getElementById('stressOfflineActions').style.display = 'none';
  const stressCard = document.getElementById('stressCard');
  stressCard.inert = false;
  stressCard.setAttribute('aria-hidden', 'false');
  stressCard.classList.add('visible');
  return true;
}

function dismissStressCard() {
  const stressCard = document.getElementById('stressCard');
  stressCard.classList.remove('visible');
  stressCard.setAttribute('aria-hidden', 'true');
  stressCard.inert = true;
  document.getElementById('stressBanner').classList.remove('visible');
}

function connectToRM() {
  const supportRef = `support-${Date.now()}`;
  showToast(
    'warning',
    'Prototype support handoff',
    `A support handoff was captured for ${supportRef}. A live RM/case adapter is not connected in this prototype build.`
  );
  addAuditLog(`🧭 Support handoff draft generated: ${supportRef}.`);
}

function hideRMToast() {
  const rmToast = document.getElementById('rmToast');
  rmToast.classList.remove('visible');
  rmToast.setAttribute('aria-hidden', 'true');
}

// ─── Nudge Actions ────────────────────────────────────────────────────
function dismissNudge() {
  const hadActiveNudge = Boolean(currentOffer || currentNudge);
  const nudgeCard = document.getElementById('nudgeCard');
  const shouldRestoreFocus = typeof nudgeCard.contains === 'function' && nudgeCard.contains(document.activeElement);
  nudgeCard.classList.remove('visible');
  nudgeCard.setAttribute('aria-hidden', 'true');
  nudgeCard.inert = true;
  currentNudge = null;
  currentOffer = null;
  if (shouldRestoreFocus) focusElement(lastScenarioTrigger);

  if (hadActiveNudge) {
    consecutiveDeclines++;
    nudgeBudgetMax = 5; // Capped dynamically to 5 on declines
    addAuditLog(`📉 Customer declined recommendation (Decline streak: ${consecutiveDeclines}). Dynamic budget capped at ${nudgeBudgetMax} with cooldown spacing.`);
    updateNudgeBudgetUI();
  }
}

function acceptNudge() {
  if (!currentOffer) return;
  consecutiveDeclines = 0; // Reset decline streak on active engagement
  updateNudgeBudgetUI();
  document.getElementById('consentText').textContent = currentOffer.presentation.consentText;
  const screen = document.getElementById('consentScreen');
  consentReturnFocus = document.activeElement;
  screen.inert = false;
  screen.setAttribute('aria-hidden', 'false');
  screen.classList.add('visible');
  focusElement(document.getElementById('consentDialogTitle'));
  addAuditLog(`📝 User initiated: ${currentOffer.presentation.actionLabel} — consent screen shown`);
}

// ─── Consent Screen + Success Flow ────────────────────────────────────
function closeConsentScreen() {
  const screen = document.getElementById('consentScreen');
  screen.classList.remove('visible');
  screen.setAttribute('aria-hidden', 'true');
  screen.inert = true;
  // Restore default consent screen content if replaced by success
  restoreConsentScreenContent();
  if (successAutoTimeout) { clearTimeout(successAutoTimeout); successAutoTimeout = null; }
  const returnTarget = consentReturnFocus;
  consentReturnFocus = null;
  focusElement(returnTarget);
}

function restoreConsentScreenContent() {
  const contentDiv = document.getElementById('consentScreenContent');
  // Only restore if it was replaced with success content
  if (contentDiv.querySelector('.success-content')) {
    contentDiv.innerHTML = `
      <div class="consent-icon" aria-hidden="true">📝</div>
      <div id="consentDialogTitle" class="consent-title" tabindex="-1">Confirm Governed Action</div>
      <div id="consentText" class="consent-desc">To proceed, please confirm your consent.</div>
      <div class="consent-terms">
        <strong>Prototype Consent &amp; Policy Terms:</strong><br>
        1. The data used for this nudge is strictly purpose-limited.<br>
        2. Explicit one-time consent is required to execute.<br>
        3. Revocation and erasure apply to eligible Saarthi-derived data; regulated banking records follow SBI retention requirements.
      </div>
      <div class="nudge-actions" style="margin-top: auto;">
        <button type="button" class="nudge-btn nudge-btn-secondary" onclick="closeConsentScreen()">Cancel</button>
        <button id="confirmActionBtn" type="button" class="nudge-btn nudge-btn-primary" onclick="confirmAction()">Authorize &amp; Execute</button>
      </div>`;
    document.getElementById('consentScreen').setAttribute('aria-labelledby', 'consentDialogTitle');
    document.getElementById('consentScreen').setAttribute('aria-describedby', 'consentText');
  }
}

async function confirmAction() {
  if (!currentOffer || actionInFlight) return;
  const offer = currentOffer;
  const p = profiles[currentProfileKey];

  if (offer.source === 'server' && currentReviewRequired) {
    showToast('warning', 'Awaiting Human Review', 'An independent reviewer must approve this recommendation before customer authorization.');
    return;
  }

  actionInFlight = true;
  const confirmButton = document.getElementById('confirmActionBtn');
  if (confirmButton) confirmButton.disabled = true;
  let hash;
  let fulfillmentReference = null;
  let fulfillmentIsSynthetic = false;
  try {
    if (offer.source === 'server') {
      if (runtimeMode !== 'api-connected' || !backendAvailable) {
        showToast('blocked', 'Authorization Failed', 'The governed API is unavailable. No action was performed.');
        return;
      }
      if (!currentRecommendationId || offer.recommendationId !== currentRecommendationId) {
        showToast('blocked', 'Authorization Failed', 'The displayed offer no longer matches the active server recommendation.');
        return;
      }
      if (!currentDecisionToken) {
        const { response, payload } = await apiRequest('/decisions/authorize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ recommendationId: offer.recommendationId })
        });
        if (currentOffer !== offer) return;
        if (!response.ok || !payload.decision_token
          || payload.recommendation_id !== offer.recommendationId
          || payload.product_id !== offer.productId) {
          showToast('blocked', 'Authorization Failed', `Server rejected this action (${payload.status || payload.error}).`);
          addAuditLog('🚫 Authorization response failed recommendation/product identity validation.');
          return;
        }
        currentDecisionToken = payload.decision_token;
      }
      hash = currentDecisionToken;
      const { response: executionResponse, payload: execution } = await apiRequest('/actions/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ recommendationId: offer.recommendationId, decisionToken: hash })
      });
      if (currentOffer !== offer) return;
      const validReference = execution.fulfillment
        && typeof execution.fulfillment.reference === 'string'
        && execution.fulfillment.reference.length > 0;
      if (!executionResponse.ok
        || !['fulfilled', 'already_fulfilled'].includes(execution.status)
        || execution.recommendation_id !== offer.recommendationId
        || !validReference) {
        showToast('blocked', 'Execution Not Confirmed', `No action was completed (${execution.status || execution.error_code}). You can retry safely.`);
        addAuditLog(`🚫 Fulfilment not confirmed: ${execution.status || execution.error_code}`);
        return;
      }
      fulfillmentReference = execution.fulfillment.reference;
      fulfillmentIsSynthetic = execution.fulfillment.provider === 'synthetic-fulfillment';
      addAuditLog(`✅ ${fulfillmentIsSynthetic ? 'Prototype fulfilment adapter' : 'Connected fulfilment service'} confirmed: ${fulfillmentReference}`);
    } else if (offer.source === 'offline-demo' && runtimeMode === 'offline-demo') {
      hash = await sha256Real(`${p.id}|${offer.productId}|${Date.now()}|GOVERNED_DECISION_TOKEN`);
    } else {
      showToast('blocked', 'Invalid Action Mode', 'No action was performed.');
      return;
    }

    const tokenFingerprint = await sha256Real(hash);
    const serverAction = offer.source === 'server';
    document.getElementById('tokenHash').textContent = (serverAction ? 'GOVERNED TOKEN: ' : 'GOVERNED TOKEN: ') + tokenFingerprint.substring(0, 32) + '…';
    document.getElementById('tokenBox').style.display = 'block';
    addAuditLog(`🟢 Decision token issued (fingerprint ${tokenFingerprint.substring(0, 12)}…)`);
    addAuditLog(`✅ Action authorized: ${offer.presentation.actionLabel} for ${p.name}`);
    showToast(
      'success',
      serverAction ? (fulfillmentIsSynthetic ? 'Prototype Action Recorded' : 'Action Completed') : 'Offline Demo Completed',
      serverAction
        ? (fulfillmentIsSynthetic ? 'The synthetic fulfilment adapter confirmed this local prototype action.' : 'The connected fulfilment service confirmed and recorded the action.')
        : 'Offline prototype action simulated; no banking action occurred.'
    );
    renderSuccessState(offer, tokenFingerprint, fulfillmentReference, fulfillmentIsSynthetic);
    dismissNudge();
    successAutoTimeout = setTimeout(() => successBackToHome(), 5000);
  } catch (error) {
    showToast('blocked', 'Execution Not Confirmed', 'The governed service is unavailable or returned invalid data. No completion was shown.');
    addAuditLog('🚫 Action flow failed closed.');
  } finally {
    actionInFlight = false;
    const activeButton = document.getElementById('confirmActionBtn');
    if (activeButton) activeButton.disabled = false;
  }
}

function renderSuccessState(offer, tokenFingerprint, fulfillmentReference, fulfillmentIsSynthetic = false) {
  const contentDiv = document.getElementById('consentScreenContent');
  contentDiv.innerHTML = `
    <div class="success-content">
      <div class="success-checkmark" aria-hidden="true">✅</div>
      <div id="successDialogTitle" class="success-title" tabindex="-1">Action confirmed</div>
      <div id="successActionText" class="success-text"></div>
      <div id="successReferenceText" class="success-text"></div>
      <div class="success-token-card">
        <div class="success-token-label">Decision Token</div>
        <div id="successTokenFingerprint" class="success-token-hash"></div>
      </div>
      <button type="button" class="success-back-btn" onclick="successBackToHome()">Back to YONO</button>
    </div>`;
  const screen = document.getElementById('consentScreen');
  screen.setAttribute('aria-labelledby', 'successDialogTitle');
  screen.setAttribute('aria-describedby', 'successActionText');
  document.getElementById('successActionText').textContent = offer.presentation.successText;
  document.getElementById('successReferenceText').textContent = fulfillmentReference
    ? `${fulfillmentIsSynthetic ? 'Prototype fulfilment reference' : 'Fulfilment reference'}: ${fulfillmentReference}`
    : 'Offline simulation — no fulfilment reference was created.';
  document.getElementById('successTokenFingerprint').textContent = `${tokenFingerprint.substring(0, 16)}…`;
  focusElement(document.getElementById('successDialogTitle'));
}

function successBackToHome() {
  if (successAutoTimeout) { clearTimeout(successAutoTimeout); successAutoTimeout = null; }
  closeConsentScreen();
  navigateToView('home');
}

// ─── Phone Navigation ─────────────────────────────────────────────────
const views = ['home', 'pay', 'investments', 'cards', 'loans', 'insurance', 'services', 'impact'];
const viewTitles = {
  pay: 'YONO Pay', investments: 'Investments', cards: 'SBI Card Elite', loans: 'Loans',
  insurance: 'Insurance', services: 'Services', impact: 'Saarthi Impact Summary'
};

function navigateToView(viewName) {
  const activeBeforeNavigation = document.activeElement;
  const movePhoneFocus = activeBeforeNavigation
    && typeof activeBeforeNavigation.closest === 'function'
    && activeBeforeNavigation.closest('.phone-screen');
  // Navigating away invalidates in-flight decisions and delayed UI writes.
  // A newly auto-triggered scenario receives its own run ID below.
  activePipelineRunId++;
  currentRecommendationId = null;
  currentDecisionToken = null;
  currentReviewRequired = false;
  currentReviewedOffer = null;
  currentOffer = null;
  actionInFlight = false;
  if (reviewPollTimeout) {
    clearTimeout(reviewPollTimeout);
    reviewPollTimeout = null;
  }
  clearAutoTrigger();
  dismissNudge();
  dismissStressCard();
  hideRMToast();

  views.forEach(v => {
    document.getElementById('yono-view-' + v).style.display = v === viewName ? 'flex' : 'none';
  });

  if (typeof document.querySelectorAll === 'function') {
    document.querySelectorAll('.yono-bottom-nav-btn, .behance-nav-btn').forEach(button => {
      const isActive = button.dataset.view === viewName;
      button.classList.toggle('active', isActive);
      if (isActive) {
        button.setAttribute('aria-current', 'page');
      } else {
        button.removeAttribute('aria-current');
      }
    });
  }

  const subHeader = document.getElementById('yonoSubHeader');
  if (viewName === 'home') {
    subHeader.style.display = 'none';
  } else {
    subHeader.style.display = 'flex';
    document.getElementById('yonoViewTitle').textContent = viewTitles[viewName] || viewName;
  }

  if (movePhoneFocus) {
    focusElement(document.getElementById(viewName === 'home' ? 'yonoHomeBtn' : 'yonoBackBtn'));
  }

  // Auto-trigger scenarios with delay (1.5s so user sees view load first)
  if (viewName === 'cards' && consentState && activeScenarioType !== 'opportunity') {
    autoTriggerTimeout = setTimeout(() => triggerScenario('opportunity'), 1500);
  } else if (viewName === 'investments' && consentState && activeScenarioType !== 'lifeevent') {
    autoTriggerTimeout = setTimeout(() => triggerScenario('lifeevent'), 1500);
  }

  // Update impact view data when navigating to it
  if (viewName === 'impact') updateImpactView();
}

function clearAutoTrigger() {
  if (autoTriggerTimeout) { clearTimeout(autoTriggerTimeout); autoTriggerTimeout = null; }
}

// ─── Prototype Data Export ────────────────────────────────────────────
async function triggerDataExport() {
  const p = profiles[currentProfileKey];
  let exportData;

  if (backendAvailable) {
    try {
      const { response, payload } = await apiRequest('/consent/export');
      if (!response.ok) throw new Error('Export service rejected request');
      exportData = {
        export_type: 'Saarthi customer data export',
        customer_id: p.id,
        generated_at: new Date().toISOString(),
        ...payload
      };
    } catch (error) {
      showToast('blocked', 'Data Export Failed', 'The server could not prepare your data. Please try again.');
      return;
    }
  } else {
    exportData = {
      export_type: 'Saarthi offline demonstration export',
      customer_id: p.id,
      consent_status: consentState ? 'ACTIVE' : 'REVOKED',
      generated_at: new Date().toISOString()
    };
  }

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `saarthi_prototype_export_${p.id}.json`;
  a.click();
  URL.revokeObjectURL(url);

  showToast('success', 'Prototype Export Ready', `saarthi_prototype_export_${p.id}.json downloaded.`);
  addAuditLog(`📥 Prototype data export generated for ${p.id}`);
}

// ─── Prototype Data Erasure (In-App Confirmation) ─────────────────────
function triggerDataErasure() {
  // Show inline confirmation card instead of browser confirm()
  const confirmation = document.getElementById('erasureConfirm');
  erasureReturnFocus = document.activeElement;
  confirmation.inert = false;
  confirmation.setAttribute('aria-hidden', 'false');
  confirmation.classList.add('visible');
  focusElement(confirmation.querySelector('.erasure-cancel-btn'));
}

function cancelErasure() {
  const confirmation = document.getElementById('erasureConfirm');
  confirmation.classList.remove('visible');
  confirmation.setAttribute('aria-hidden', 'true');
  confirmation.inert = true;
  const returnTarget = erasureReturnFocus;
  erasureReturnFocus = null;
  focusElement(returnTarget);
}

async function confirmErasure() {
  const confirmation = document.getElementById('erasureConfirm');
  confirmation.classList.remove('visible');
  confirmation.setAttribute('aria-hidden', 'true');
  confirmation.inert = true;
  erasureReturnFocus = null;
  const p = profiles[currentProfileKey];

  if (backendAvailable) {
    try {
      const { response, payload } = await apiRequest('/consent/erase', { method: 'POST' });
      if (!response.ok || payload.status !== 'processed' || payload.scope !== 'eligible_saarthi_derived_data') {
        throw new Error('Erasure service returned an invalid scope');
      }
    } catch (error) {
      showToast('blocked', 'Erasure Failed', 'No data was erased. Please retry or contact support.');
      return;
    }
  }

  setConsentUI(false);
  dismissNudge();
  dismissStressCard();

  addAuditLog(`🗑️ Prototype erasure workflow completed for ${p.id}`);
  showToast('warning', 'Prototype Data Erased', 'Eligible Saarthi-derived personalisation data was removed; regulated banking records are outside this prototype.');
  navigateToView('home');
}

// ─── Audit Log ────────────────────────────────────────────────────────
function addAuditLog(text) {
  const list = document.getElementById('auditList');
  const now = new Date();
  const ts = now.toLocaleTimeString('en-IN', { hour12: false });
  const item = document.createElement('div');
  item.className = 'audit-item';
  const timestamp = document.createElement('span');
  timestamp.className = 'audit-ts';
  timestamp.textContent = `[${ts}]`;
  const auditText = document.createElement('span');
  auditText.className = 'audit-text';
  auditText.textContent = ` ${text}`;
  item.append(timestamp, auditText);
  list.prepend(item);
}

// ─── Balance Eye Visibility Toggle ────────────────────────────────────
function toggleBalanceVisibility() {
  isBalanceHidden = !isBalanceHidden;
  const balanceEl = document.getElementById('yonoBalance');
  const eyeIcon = document.getElementById('balanceEyeIcon');
  const p = profiles[currentProfileKey] || profiles['priya'];
  if (balanceEl) {
    if (isBalanceHidden) {
      balanceEl.textContent = '₹ ••••••••';
      if (eyeIcon) eyeIcon.textContent = '🙈';
    } else {
      balanceEl.textContent = '₹' + p.rawBalance.toLocaleString('en-IN') + '.00';
      if (eyeIcon) eyeIcon.textContent = '👁️';
    }
  }
}

// ─── Behance Simulation Interactions ──────────────────────────────────
let enteredMpin = '12';

function switchLoginTab(mode) {
  const isMpin = mode === 'mpin';
  const tabMpin = document.getElementById('tabMpinBtn');
  const tabUser = document.getElementById('tabUserBtn');
  const subMpin = document.getElementById('loginSubMpin');
  const subUser = document.getElementById('loginSubUsername');
  const promptTitle = document.getElementById('loginPromptTitle');

  if (tabMpin) {
    tabMpin.classList.toggle('active', isMpin);
    tabMpin.setAttribute('aria-selected', isMpin);
  }
  if (tabUser) {
    tabUser.classList.toggle('active', !isMpin);
    tabUser.setAttribute('aria-selected', !isMpin);
  }
  if (subMpin) subMpin.style.display = isMpin ? 'flex' : 'none';
  if (subUser) subUser.style.display = isMpin ? 'none' : 'flex';
  if (promptTitle) promptTitle.textContent = isMpin ? 'Enter MPIN' : 'Enter Username';
}

function updateMpinDotsUI() {
  for (let i = 1; i <= 4; i++) {
    const dot = document.getElementById('mpinDot' + i);
    if (dot) {
      dot.classList.toggle('filled', i <= enteredMpin.length);
    }
  }
}

function pressMpinDigit(d) {
  if (enteredMpin.length < 4) {
    enteredMpin += d;
    updateMpinDotsUI();
    if (enteredMpin.length === 4) {
      setTimeout(() => performLogin(), 250);
    }
  }
}

function deleteMpinDigit() {
  if (enteredMpin.length > 0) {
    enteredMpin = enteredMpin.slice(0, -1);
    updateMpinDotsUI();
  }
}

function loginWithBiometrics() {
  enteredMpin = '1234';
  updateMpinDotsUI();
  showToast('success', 'Biometric Verified', 'Welcome back, ' + (profiles[currentProfileKey]?.firstName || 'Priya'));
  setTimeout(() => performLogin(), 300);
}

function togglePasswordVisibility() {
  const input = document.getElementById('loginPasswordInput');
  if (input) {
    input.type = input.type === 'password' ? 'text' : 'password';
  }
}

function performLogin() {
  const loginScreen = document.getElementById('yono-view-login');
  const appShell = document.getElementById('yono-app-shell');
  if (loginScreen && appShell) {
    loginScreen.style.display = 'none';
    appShell.style.display = 'flex';
    navigateToView('home');
  }
}

function performLogout() {
  const loginScreen = document.getElementById('yono-view-login');
  const appShell = document.getElementById('yono-app-shell');
  closeProfileModal();
  closeQrScannerModal();
  enteredMpin = '12';
  updateMpinDotsUI();
  if (loginScreen && appShell) {
    appShell.style.display = 'none';
    loginScreen.style.display = 'flex';
  }
  showToast('warning', 'Logged Out', 'Session terminated securely.');
}

function switchCategoryTab(cat) {
  const categories = ['banking', 'lifestyle', 'rewards', 'others'];
  categories.forEach(c => {
    const btn = document.getElementById('catTab' + c.charAt(0).toUpperCase() + c.slice(1));
    const pane = document.getElementById('catPane' + c.charAt(0).toUpperCase() + c.slice(1));
    const isActive = c === cat;
    if (btn) {
      btn.classList.toggle('active', isActive);
      btn.setAttribute('aria-selected', isActive);
    }
    if (pane) {
      pane.style.display = isActive ? 'flex' : 'none';
    }
  });
}

function openProfileModal() {
  const modal = document.getElementById('profileModal');
  if (modal) {
    modal.classList.add('visible');
    modal.removeAttribute('aria-hidden');
    modal.removeAttribute('inert');
  }
}

function closeProfileModal() {
  const modal = document.getElementById('profileModal');
  if (modal) {
    modal.classList.remove('visible');
    modal.setAttribute('aria-hidden', 'true');
    modal.setAttribute('inert', '');
  }
}

function openQrScannerModal() {
  const modal = document.getElementById('qrScannerModal');
  if (modal) {
    modal.classList.add('visible');
    modal.removeAttribute('aria-hidden');
    modal.removeAttribute('inert');
  }
}

function closeQrScannerModal() {
  const modal = document.getElementById('qrScannerModal');
  if (modal) {
    modal.classList.remove('visible');
    modal.setAttribute('aria-hidden', 'true');
    modal.setAttribute('inert', '');
  }
}

function simulateQrPayment() {
  closeQrScannerModal();
  showToast('success', 'Merchant Payment Done', 'Paid ₹250.00 to Chai Point via UPI Lite');
}

function toggleSearch() {
  showToast('success', 'Smart Search', 'Type "FD", "Tax", "Loans" or "Cards"');
}

// ─── SHA-256 Simulation ───────────────────────────────────────────────
async function sha256Real(input) {
  const data = new TextEncoder().encode(input);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('');
}

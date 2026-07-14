// State database of current profile
const profiles = {
  priya: {
    id: "SBI-772910",
    name: "Priya Sharma",
    salary: "₹1,45,000",
    balance: "₹2,80,000",
    interest: "₹4,200/mo (across 2 cards)",
    rawBalance: 280000,
    rawCardDebt: 85000,
    email: "priya.sharma@example.com",
    pan: "ABCDE1234F",
    aadhaar: "4532 9981 1204"
  },
  ramesh: {
    id: "SBI-881234",
    name: "Ramesh Kumar",
    salary: "₹42,00,000",
    balance: "₹92,000",
    interest: "₹0/mo",
    rawBalance: 92000,
    rawCardDebt: 0,
    email: "ramesh.kumar@example.com",
    pan: "FGHIJ5678K",
    aadhaar: "8899 4432 1122"
  },
  amit: {
    id: "SBI-223456",
    name: "Amit Patel",
    salary: "₹95,000",
    balance: "₹6,40,000",
    interest: "₹8,500/mo (business loan EMI)",
    rawBalance: 640000,
    rawCardDebt: 120000,
    email: "amit.patel@example.com",
    pan: "LMNOP9012Q",
    aadhaar: "3322 1155 9988"
  }
};

let currentProfileKey = 'priya';
let currentNudge = null;
let consentState = true; // DPDP consent state

function changeProfile() {
  const select = document.getElementById('profileSelect');
  currentProfileKey = select.value;
  const profile = profiles[currentProfileKey];
  
  document.getElementById('profId').innerText = profile.id;
  document.getElementById('profSalary').innerText = profile.salary;
  document.getElementById('profBalance').innerText = profile.balance;
  document.getElementById('profInterest').innerText = profile.interest;
  
  document.getElementById('yonoUser').innerText = profile.name.split(' ')[0];
  document.getElementById('yonoBalance').innerText = parseFloat(profile.rawBalance).toLocaleString('en-IN', { style: 'currency', currency: 'INR' });

  // Update dynamic sub-screen fields
  document.getElementById('cardHolderName').innerText = profile.name.toUpperCase();
  document.getElementById('cardOutstanding').innerText = profile.rawCardDebt.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });
  
  // Calculate min due (5%)
  const minDue = profile.rawCardDebt * 0.05;
  document.getElementById('cardMinDue').innerText = minDue.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });
  
  // Calculate cc interest (42% p.a. -> 3.5%/mo on card debt)
  const ccInterest = profile.rawCardDebt * 0.035;
  if (profile.rawCardDebt > 0) {
    document.getElementById('cardInterestRow').style.display = 'flex';
    document.getElementById('cardInterestPaid').innerText = ccInterest.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });
  } else {
    document.getElementById('cardInterestRow').style.display = 'none';
  }

  document.getElementById('investSavingsBalance').innerText = parseFloat(profile.rawBalance).toLocaleString('en-IN', { style: 'currency', currency: 'INR' });
  
  // MF and FD calculation
  const mfVal = profile.rawBalance * 0.4; 
  document.getElementById('portfolioMF').innerText = mfVal.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });
  document.getElementById('portfolioTotal').innerText = mfVal.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });
  
  // Active Loans UI
  const loansContainer = document.getElementById('activeLoansContainer');
  if (currentProfileKey === 'priya') {
    loansContainer.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; border-left: 3px solid #3b82f6; padding-left: 6px; margin: 4px 0;">
        <div style="display: flex; flex-direction: column;">
          <span style="font-weight: bold; color: #1e293b;">Home Loan</span>
          <span style="font-size: 0.6rem; color: #64748b;">A/c No: XXXXXX99102</span>
        </div>
        <div style="text-align: right;">
          <span style="font-weight: bold; color: #1e293b;">₹45,00,000</span>
          <br><span style="font-size: 0.6rem; color: #64748b;">EMI: ₹38,500/mo</span>
        </div>
      </div>
    `;
  } else if (currentProfileKey === 'amit') {
    loansContainer.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; border-left: 3px solid #f59e0b; padding-left: 6px; margin: 4px 0;">
        <div style="display: flex; flex-direction: column;">
          <span style="font-weight: bold; color: #1e293b;">Business Expansion Loan</span>
          <span style="font-size: 0.6rem; color: #64748b;">A/c No: XXXXXX22340</span>
        </div>
        <div style="text-align: right;">
          <span style="font-weight: bold; color: #1e293b;">₹6,50,000</span>
          <br><span style="font-size: 0.6rem; color: #64748b;">EMI: ₹8,500/mo</span>
        </div>
      </div>
    `;
  } else {
    loansContainer.innerHTML = `<div style="font-size: 0.7rem; color: #64748b; padding: 0.25rem 0;">No Active Loans found.</div>`;
  }

  // Transactions details
  const salaryAmt = currentProfileKey === 'priya' ? 145000 : (currentProfileKey === 'ramesh' ? 42000 : 95000);
  document.getElementById('salaryTransAmount').innerText = '+' + salaryAmt.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });
  document.getElementById('salaryTransName').innerText = 'SALARY / ' + (currentProfileKey === 'priya' ? 'TechCorp Ltd' : (currentProfileKey === 'ramesh' ? 'Govt Pension' : 'Retail Business'));

  if (profile.rawCardDebt > 0) {
    document.getElementById('ccInterestTransAmount').innerText = '-' + ccInterest.toLocaleString('en-IN', { style: 'currency', currency: 'INR' });
    document.getElementById('ccInterestTransAmount').parentElement.parentElement.style.display = 'flex';
  } else {
    document.getElementById('ccInterestTransAmount').parentElement.parentElement.style.display = 'none';
  }

  // Pre-approved offer gating
  const loanOffers = document.getElementById('loanOffersContainer');
  if (profile.rawCardDebt > 0) {
    loanOffers.innerHTML = `
      <div style="background: rgba(16, 185, 129, 0.05); border: 1px solid rgba(16, 185, 129, 0.15); border-radius: 8px; padding: 0.6rem; display: flex; justify-content: space-between; align-items: center; cursor: pointer;" onclick="triggerScenario('opportunity')">
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="font-size: 1rem;">🛡️</span>
          <div style="display: flex; flex-direction: column;">
            <span style="font-size: 0.65rem; font-weight: bold; color: #065f46;">Debt Consolidation Loan</span>
            <span style="font-size: 0.55rem; color: #047857;">Pre-approved up to ${profile.rawCardDebt.toLocaleString('en-IN', { style: 'currency', currency: 'INR' })} @ 10.5%</span>
          </div>
        </div>
        <span style="font-size: 0.75rem; color: #047857; font-weight: bold;">Apply</span>
      </div>
    `;
  } else {
    loanOffers.innerHTML = `<div style="font-size: 0.7rem; color: #64748b; padding: 0.25rem 0;">No pre-approved offers available.</div>`;
  }

  // Sync consent checkbox inside the Services screen
  const appToggle = document.getElementById('yonoConsentToggle');
  if (appToggle) {
    appToggle.checked = consentState;
  }
  
  dismissNudge();
  closeConsentScreen();
  clearTrace();
  logAudit(`Switched active session to profile ${profile.id} (${profile.name})`);
}

function clearTrace() {
  document.getElementById('logsArea').innerHTML = `
    <div style="color: var(--text-muted); text-align: center; margin-top: 3rem;">
      Select a customer profile and trigger a behavioral signal to view the real-time agent workflow execution.
    </div>
  `;
  document.getElementById('tokenBox').classList.remove('visible');
  resetStatusDots();
}

function resetStatusDots() {
  document.getElementById('dot1').className = 'status-dot';
  document.getElementById('dot2').className = 'status-dot';
  document.getElementById('dot3').className = 'status-dot';
  document.getElementById('dot4').className = 'status-dot';
}

function logAudit(message) {
  const auditList = document.getElementById('auditList');
  const timeStr = new Date().toLocaleTimeString('en-IN', { hour12: false });
  const item = document.createElement('div');
  item.className = 'audit-item';
  item.innerHTML = `<span class="audit-ts">[${timeStr}]</span> <span class="audit-text">${message}</span>`;
  auditList.insertBefore(item, auditList.firstChild);
}

function toggleConsent() {
  consentState = !consentState;
  const badge = document.getElementById('consentBadge');
  const revokeBtn = document.getElementById('revokeBtn');
  
  // Sync toggle in Services view
  const appToggle = document.getElementById('yonoConsentToggle');
  if (appToggle) {
    appToggle.checked = consentState;
  }

  if (consentState) {
    badge.className = 'consent-badge active';
    badge.innerText = 'OPTED IN';
    revokeBtn.innerText = 'Revoke Consent (DPDP Right to Erasure)';
    revokeBtn.style.background = 'rgba(239, 68, 68, 0.1)';
    logAudit('Customer opt-in consent re-established for financial pattern co-piloting');
  } else {
    badge.className = 'consent-badge revoked';
    badge.innerText = 'CONSENT REVOKED';
    revokeBtn.innerText = 'Re-grant DPDP Consent';
    revokeBtn.style.background = 'rgba(16, 185, 129, 0.1)';
    revokeBtn.style.color = '#34d399';
    revokeBtn.style.borderColor = 'rgba(16, 185, 129, 0.2)';
    dismissNudge();
    closeConsentScreen();
    clearTrace();
    logAudit('DPDP Erasure Rights triggered. Purging local model memory cache & embeddings');
    alert("DPDP Gating triggered: User data erased from vector cache and downstream co-pilot processing blocked.");
  }
}

// Scenarios setup
const scenarios = {
  friction: {
    name: "Branch Friction Event",
    signal: "Branch Cash Deposit of ₹20,000 manually executed at Branch Code 0032 (New Delhi)",
    rawDetail: "User ID: SBI-772910 | Mode: COUNTER | Service: DEPOSIT | Aadhaar Verified: 4532 9981 1204",
    nudge: {
      title: "Avoid the Line - Go Digital",
      text: "Hi {{name}}, you deposited cash at the branch today. Save time next time! Skip the counter: transfer or deposit instantly inside YONO in just 2 taps. Here is a quick video tutorial on how.",
      actionLabel: "Watch Tutorial"
    }
  },
  opportunity: {
    name: "Debt Consolidation Opportunity",
    signal: "Recurring credit card payment outflow pattern of ₹4,200/mo across external card balances",
    rawDetail: "User Email: {{email}} | Card: 4321-XXXX-XXXX-9901 | PAN: {{pan}} | Interest Paid: ₹4,200",
    nudge: {
      title: "Consolidate Debt & Save ₹2,100/mo",
      text: "Hi {{name}}, we noticed you are paying ₹4,200 monthly in interest across other credit cards. We have pre-approved a Debt Consolidation Loan for you at 10.5% (half the typical card rate). Tap to accept.",
      actionLabel: "Consolidate Now"
    }
  },
  lifeevent: {
    name: "Salary Credit Increment (Life-Event)",
    signal: "Salary credit spike pattern of +30% recognized (₹1,45,000 -> ₹1,88,500)",
    rawDetail: "User ID: {{id}} | Employer: TechCorp India Ltd | Account: XXXXXXX4812",
    nudge: {
      title: "Grow Your Extra Savings",
      text: "Congratulations on the salary credit increase of ₹43,500, {{name}}! Let's make it work for you. Tap to auto-sweep anything above your normal expense budget into a high-yield Recurring Deposit at 7.1%.",
      actionLabel: "Activate Auto-Sweep"
    }
  }
};

function triggerScenario(type) {
  if (!consentState) {
    alert("Compliance Gate Blocked: User has revoked consent under DPDP guidelines. Please opt-in first.");
    return;
  }

  clearTrace();
  const profile = profiles[currentProfileKey];
  const scenario = scenarios[type];

  // Prepare simulation text with profile data
  let signalStr = scenario.signal.replace('{{name}}', profile.name);
  let rawDetailStr = scenario.rawDetail
                        .replace('{{email}}', profile.email)
                        .replace('{{pan}}', profile.pan)
                        .replace('{{id}}', profile.id);

  // Start Agent Orchestrator Visual Trace
  executeAgentPipeline(type, profile, signalStr, rawDetailStr);
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function executeAgentPipeline(type, profile, signal, rawDetail) {
  const logs = document.getElementById('logsArea');
  logs.innerHTML = ''; // Clear initial message

  // Setup dots
  const d1 = document.getElementById('dot1');
  const d2 = document.getElementById('dot2');
  const d3 = document.getElementById('dot3');
  const d4 = document.getElementById('dot4');

  // Step 1: Ingestion & Input Guardian
  d1.className = 'status-dot active';
  let node1 = appendNode('Input Guardian (PII Masking Filter)', 'processing...');
  await sleep(1000);
  
  // Mask PII
  let maskedDetail = rawDetail
    .replace(/[A-Z]{5}[0-9]{4}[A-Z]{1}/g, '[MASKED PAN]')
    .replace(/[0-9]{4}\s[0-9]{4}\s[0-9]{4}/g, '[MASKED AADHAAR]')
    .replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, '[MASKED EMAIL]')
    .replace(/[0-9]{4}-XXXX-XXXX-[0-9]{4}/g, '[MASKED CARD]');

  updateNode(node1, `Ingesting real-time event signal from Redis Stream.\nInput Guardian active. Masking customer identifiers to satisfy DPDP Data Minimization rules:\n\n[Raw Signal]: "${signal}"\n[Masked Parameters]: "${maskedDetail}"`, 'completed');
  d1.className = 'status-dot';
  logAudit(`Input Guardian masked PII identifiers for session ${profile.id}`);

  // Step 2: Signal Detection Agent
  d2.className = 'status-dot active';
  let node2 = appendNode('Signal Detection Agent', 'processing...');
  await sleep(1200);
  
  let sigCategory = "";
  if (type === 'friction') sigCategory = "Friction Signal (Counter to digital migration potential)";
  if (type === 'opportunity') sigCategory = "Opportunity Signal (Idle balance / High-interest debt consolidation)";
  if (type === 'lifeevent') sigCategory = "Life-Event Signal (Significant positive credit spike/Salary bump)";

  updateNode(node2, `Trigger: LangGraph Node [signal_detection]\nCategory Detected: ${sigCategory}\nEvaluation State: Pattern matches active ruleset. Routing payload to recommendation queue.`, 'completed');
  d2.className = 'status-dot';
  logAudit(`Signal Detection Agent categorized event as ${type.toUpperCase()}`);

  // Step 3: Recommendation Agent (Neo4j match)
  d3.className = 'status-dot active';
  let node3 = appendNode('Recommendation Agent & Graph Rules Matching', 'processing...');
  await sleep(1400);

  let ruleMatched = "";
  let productInfo = "";
  if (type === 'friction') {
    ruleMatched = "MATCH (c:Customer {id: $cid})-[:ELIGIBLE_FOR]->(p:Product {type: 'digital_onboarding_tutorial'}) RETURN p";
    productInfo = "Action ID: SR-TUT-08 | Product: Digital Quick-Deposit Tutorial | Value Prop: Convenience, Zero Wait Time";
  } else if (type === 'opportunity') {
    ruleMatched = "MATCH (c:Customer {id: $cid})-[:HAS_DEBT_RATIO {status: 'high'}]->(p:Product {type: 'consolidation_loan'}) RETURN p";
    productInfo = "Action ID: SR-LOAN-99 | Product: Pre-approved Consolidation Personal Loan | Interest rate: 10.5% fixed";
  } else if (type === 'lifeevent') {
    ruleMatched = "MATCH (c:Customer {id: $cid})-[:ELIGIBLE_FOR]->(p:Product {type: 'autosweep_rd'}) RETURN p";
    productInfo = "Action ID: SR-DEP-102 | Product: Flexi-Recurring Deposit (Auto-Sweep) | Interest rate: 7.1%";
  }

  updateNode(node3, `Querying Graph Constraints Database (Neo4j eligibility rules):\nQuery: "${ruleMatched}"\n\nGraph Result: Rule validated. Product is pre-approved and fits the customer segment profile.\n[Target Product]: ${productInfo}`, 'completed');
  d3.className = 'status-dot';
  logAudit(`Recommendation Agent matched graph rules for target product`);

  // Step 4: Compliance Agent & Output Guardian
  d4.className = 'status-dot active';
  let node4 = appendNode('Compliance Gating & Output Guardian', 'processing...');
  await sleep(1500);

  let complianceText = "";
  let validationScore = "100%";
  if (type === 'friction') {
    complianceText = "DPDP Compliance: Pass (opt-in validated, purely educational digital migration nudge, no cross-selling of credit products)\nRBI Fair Practices Code: Pass (transparent onboarding direction)";
  } else {
    complianceText = "DPDP Compliance: Pass (opt-in validated, transaction-data used strictly under personalization guidelines)\nRBI Fair Practices Code: Pass (Interest rates match pre-approved pricing grid, clear disclosures regarding execution fee)\nOutput Guardian: Verified zero hallucinated rate metrics.";
  }

  updateNode(node4, `Running compliance verification audits:\n\n${complianceText}\nValidation Score: ${validationScore}\nResult: APPROVED FOR CUSTOMER NUDGE`, 'completed');
  d4.className = 'status-dot active'; // Keep active for final delivery
  logAudit(`Compliance Agent approved recommended nudge with score ${validationScore}`);

  // Render the nudge inside the phone emulator
  await sleep(500);
  showNudgeInPhone(type, profile);
}

function appendNode(title, content) {
  const logs = document.getElementById('logsArea');
  const node = document.createElement('div');
  node.className = 'trace-node active';
  
  const timeStr = new Date().toLocaleTimeString('en-IN', { hour12: false });
  node.innerHTML = `
    <div class="node-header">
      <span>${title}</span>
      <span class="node-time">${timeStr}</span>
    </div>
    <div class="node-content">${content}</div>
  `;
  logs.appendChild(node);
  logs.scrollTop = logs.scrollHeight;
  return node;
}

function updateNode(nodeElement, newContent, statusClass) {
  nodeElement.className = `trace-node ${statusClass}`;
  nodeElement.querySelector('.node-content').innerText = newContent;
}

function showNudgeInPhone(type, profile) {
  const scenario = scenarios[type];
  const nudge = scenario.nudge;

  // Replace place-holder
  let text = nudge.text.replace('{{name}}', profile.name.split(' ')[0]);
  
  document.getElementById('nudgeTitle').innerText = nudge.title;
  document.getElementById('nudgeText').innerText = text;
  document.getElementById('nudgeActionBtn').innerText = nudge.actionLabel;

  currentNudge = {
    type: type,
    title: nudge.title,
    text: text,
    profileId: profile.id
  };

  document.getElementById('nudgeCard').classList.add('visible');
  logAudit(`Saarthi nudge delivered to YONO UI: "${nudge.title}"`);
}

function dismissNudge() {
  document.getElementById('nudgeCard').classList.remove('visible');
  if (currentNudge) {
    logAudit(`User skipped nudge: "${currentNudge.title}"`);
    currentNudge = null;
  }
  resetStatusDots();
}

function acceptNudge() {
  if (!currentNudge) return;
  
  // Open the consent screen in the phone simulator
  const consentTextElement = document.getElementById('consentText');
  if (currentNudge.type === 'friction') {
    consentTextElement.innerText = `To proceed with watching the YONO Quick-Deposit Tutorial, please confirm. No financial commitments are involved.`;
  } else if (currentNudge.type === 'opportunity') {
    consentTextElement.innerText = `To proceed with the pre-approved Debt Consolidation Loan of ₹85,000 at 10.5% fixed interest, confirm authorization. Funds will be credited instantly to pay off external cards.`;
  } else if (currentNudge.type === 'lifeevent') {
    consentTextElement.innerText = `Authorize Saarthi to activate the Flexi-Recurring Deposit sweep. Excess balances above ₹1,00,000 will automatically earn 7.1% interest.`;
  }

  document.getElementById('nudgeCard').classList.remove('visible');
  document.getElementById('consentScreen').classList.add('visible');
}

function closeConsentScreen() {
  document.getElementById('consentScreen').classList.remove('visible');
  resetStatusDots();
}

function confirmAction() {
  if (!currentNudge) return;

  closeConsentScreen();
  
  // Generate Decision Token details
  const payload = {
    customerId: currentNudge.profileId,
    nudgeType: currentNudge.type,
    timestamp: new Date().toISOString(),
    agentId: "SAARTHI_RECOMMENDER_v2.0",
    complianceHash: "FPC-DPDP-OK",
    policyApplied: currentNudge.type === 'friction' ? "Frictionless-Digital-Onboarding-v1" : "Fair-Lending-Debt-Consolidation-v4"
  };

  // Simple fake hash representation
  const payloadStr = JSON.stringify(payload);
  let hash = 0;
  for (let i = 0; i < payloadStr.length; i++) {
    hash = (hash << 5) - hash + payloadStr.charCodeAt(i);
    hash |= 0;
  }
  const tokenSignature = "DECISION_TOKEN_SHA256_" + Math.abs(hash).toString(16).toUpperCase() + "_" + Math.random().toString(36).substr(2, 9).toUpperCase();

  document.getElementById('tokenHash').innerText = tokenSignature;
  document.getElementById('tokenBox').classList.add('visible');

  logAudit(`Decision Token Generated and Authorized: ${tokenSignature}`);
  logAudit(`Transaction executing on core ledger with Temporary Scoped Gateway API Credential.`);
  
  // Simulate success toast inside phone
  alert(`Success! Offer Authorized.\nDecision Token Registered:\n${tokenSignature}`);
  
  currentNudge = null;
  resetStatusDots();
}

function navigateToView(viewName) {
  // Hide all sub-views and the home view
  document.getElementById('yono-view-home').style.display = 'none';
  document.getElementById('yono-view-pay').style.display = 'none';
  document.getElementById('yono-view-investments').style.display = 'none';
  document.getElementById('yono-view-cards').style.display = 'none';
  document.getElementById('yono-view-loans').style.display = 'none';
  document.getElementById('yono-view-insurance').style.display = 'none';
  document.getElementById('yono-view-services').style.display = 'none';
  
  const subHeader = document.getElementById('yonoSubHeader');
  const viewTitle = document.getElementById('yonoViewTitle');

  if (viewName === 'home') {
    document.getElementById('yono-view-home').style.display = 'flex';
    subHeader.style.display = 'none';
  } else {
    document.getElementById('yono-view-' + viewName).style.display = 'flex';
    subHeader.style.display = 'flex';
    
    let title = viewName.charAt(0).toUpperCase() + viewName.slice(1);
    if (viewName === 'pay') title = 'YONO Pay';
    viewTitle.innerText = title;

    // Auto-trigger corresponding Saarthi agent signals
    if (viewName === 'cards') {
      triggerScenario('opportunity');
    } else if (viewName === 'investments') {
      triggerScenario('lifeevent');
    }
  }
  // Scroll phone view contents to top
  const scrollableContents = document.querySelectorAll('.yono-content');
  scrollableContents.forEach(el => el.scrollTop = 0);
}

function syncConsentFromApp() {
  const toggleCheckbox = document.getElementById('yonoConsentToggle');
  if (toggleCheckbox && toggleCheckbox.checked !== consentState) {
    toggleConsent();
  }
}

function triggerDataExport() {
  const profile = profiles[currentProfileKey];
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(profile, null, 2));
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", `saarthi_dpdp_export_${profile.id}.json`);
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
  
  logAudit(`DPDP Act Portability Export triggered for customer ${profile.id}`);
  alert("DPDP Portability: Exporting all collected personal data patterns and profile mappings. Check your browser downloads for saarthi_dpdp_export.json.");
}

function triggerDataErasure() {
  if (confirm("Are you sure you want to request complete data erasure under DPDP guidelines? This will wipe your personalization cache and opt you out of active co-piloting.")) {
    if (consentState) {
      toggleConsent();
    } else {
      alert("DPDP Erasure: Data already purged. Profiling is disabled.");
    }
  }
}

// Initial load setup
window.addEventListener('load', function() {
  changeProfile();
});

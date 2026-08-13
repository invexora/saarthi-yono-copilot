import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';


const APP_SOURCE = readFileSync(new URL('../../app.js', import.meta.url), 'utf8');

function makeElement(ownerDocument = null) {
  const classes = new Set();
  const attributes = new Map();
  const element = {
    textContent: '',
    innerHTML: '',
    style: {},
    inert: false,
    disabled: false,
    focusables: [],
    children: [],
    classList: {
      add(...names) { names.forEach(name => classes.add(name)); },
      remove(...names) { names.forEach(name => classes.delete(name)); },
      contains(name) { return classes.has(name); },
    },
    setAttribute(name, value) { attributes.set(name, String(value)); },
    getAttribute(name) { return attributes.get(name) ?? null; },
    focus() { if (ownerDocument) ownerDocument.activeElement = element; },
    contains(node) { return node === element || element.focusables.includes(node); },
    closest() { return null; },
    querySelectorAll() { return element.focusables; },
    querySelector(selector) {
      if (selector === '.success-content') return null;
      if (selector === '.erasure-cancel-btn') return element.focusables[0] || null;
      return null;
    },
    append(...nodes) { element.children.push(...nodes); },
    appendChild(node) { element.children.push(node); return node; },
    prepend(node) { element.children.unshift(node); },
    remove() {},
  };
  return element;
}

function loadApp(search = '') {
  const elements = new Map();
  const document = {
    activeElement: null,
    addEventListener() {},
    createElement() { return makeElement(document); },
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, makeElement(document));
      return elements.get(id);
    },
  };
  const context = vm.createContext({
    window: { location: { search } },
    document,
    URLSearchParams,
    console,
    setTimeout() { return 1; },
    clearTimeout() {},
    fetch() { throw new Error('network calls are not permitted in this unit test'); },
  });
  vm.runInContext(APP_SOURCE, context, { filename: 'app.js' });
  return { context, elements, document };
}

function validRecommendation(overrides = {}) {
  const recommendation = {
    recommendation_id: 'recommendation-contract-001',
    product_id: 'SBI-TEST-001',
    expires_at: Date.now() / 1000 + 600,
    evidence: {
      reason_codes: ['VERIFIED_TEST'],
      presentation: {
        schema_version: 'customer-presentation-v1',
        product_id: 'SBI-TEST-001',
        title: 'Verified Product',
        body: 'Verified body',
        action_label: 'Review & Continue',
        consent_text: 'Authorize this one-time action.',
        success_text: 'The governed action was confirmed.',
        support_only: false,
      },
    },
  };
  return { ...recommendation, ...overrides };
}

test('offline execution is enabled only by an explicit mode', () => {
  assert.equal(vm.runInContext('OFFLINE_DEMO_MODE', loadApp('').context), false);
  assert.equal(vm.runInContext('OFFLINE_DEMO_MODE', loadApp('?mode=offline-demo').context), true);
});

test('server offer requires persisted presentation and matching product identity', () => {
  const { context } = loadApp();
  context.recommendation = validRecommendation();
  const accepted = vm.runInContext('normalizeServerOffer(recommendation)', context);
  assert.equal(accepted.recommendationId, 'recommendation-contract-001');
  assert.equal(accepted.productId, 'SBI-TEST-001');
  assert.equal(accepted.source, 'server');

  context.recommendation = validRecommendation();
  context.recommendation.evidence.presentation.product_id = 'SBI-DIFFERENT';
  assert.equal(vm.runInContext('normalizeServerOffer(recommendation)', context), null);

  context.recommendation = validRecommendation({ evidence: {} });
  assert.equal(vm.runInContext('normalizeServerOffer(recommendation)', context), null);
});

test('expired, support-only, or incomplete evidence cannot become an executable offer', () => {
  const { context } = loadApp();
  context.recommendation = validRecommendation({ expires_at: Date.now() / 1000 - 1 });
  assert.equal(vm.runInContext('normalizeServerOffer(recommendation)', context), null);

  context.recommendation = validRecommendation();
  context.recommendation.evidence.presentation.support_only = true;
  assert.equal(vm.runInContext('normalizeServerOffer(recommendation)', context), null);

  context.recommendation = validRecommendation();
  context.recommendation.evidence.presentation.consent_text = '';
  assert.equal(vm.runInContext('normalizeServerOffer(recommendation)', context), null);
});

test('server-controlled customer copy is rendered as text, not HTML', () => {
  const { context, elements } = loadApp();
  context.recommendation = validRecommendation();
  context.recommendation.evidence.presentation.title = '<img src=x onerror=alert(1)>';
  context.recommendation.evidence.presentation.body = '<script>steal()</script>';
  vm.runInContext('showNudgeInPhone(normalizeServerOffer(recommendation))', context);

  assert.equal(elements.get('nudgeTitle').textContent, '<img src=x onerror=alert(1)>');
  assert.equal(elements.get('nudgeTitle').innerHTML, '');
  assert.equal(elements.get('nudgeText').textContent, '<script>steal()</script>');
  assert.equal(elements.get('nudgeText').innerHTML, '');
});

test('connected action code validates authorization and execution identities', () => {
  assert.match(APP_SOURCE, /payload\.recommendation_id !== offer\.recommendationId/);
  assert.match(APP_SOURCE, /payload\.product_id !== offer\.productId/);
  assert.match(APP_SOURCE, /execution\.recommendation_id !== offer\.recommendationId/);
  assert.doesNotMatch(APP_SOURCE, /falling back to local orchestrator/i);
});

test('support journeys expose no financial or case-management action, including offline demo mode', () => {
  const { context, elements } = loadApp('?mode=offline-demo');
  assert.equal(vm.runInContext('showStressCard(null)', context), true);
  assert.equal(elements.get('stressOfflineActions').style.display, 'none');
  assert.equal(vm.runInContext('currentOffer', context), null);
});

test('navigation invalidates any in-flight offer, token, review, and delayed pipeline run', () => {
  const { context } = loadApp('?mode=offline-demo');
  vm.runInContext(`
    activePipelineRunId = 9;
    currentRecommendationId = 'recommendation-stale';
    currentDecisionToken = 'token-stale';
    currentReviewRequired = true;
    currentReviewedOffer = { stale: true };
    currentOffer = buildOfflineOffer('friction');
    actionInFlight = true;
    navigateToView('home');
  `, context);

  assert.equal(vm.runInContext('activePipelineRunId', context), 10);
  assert.equal(vm.runInContext('currentRecommendationId', context), null);
  assert.equal(vm.runInContext('currentDecisionToken', context), null);
  assert.equal(vm.runInContext('currentReviewRequired', context), false);
  assert.equal(vm.runInContext('currentReviewedOffer', context), null);
  assert.equal(vm.runInContext('currentOffer', context), null);
  assert.equal(vm.runInContext('actionInFlight', context), false);
});

test('consent dialog moves focus, traps Tab, closes on Escape, and restores focus', () => {
  const { context, elements, document } = loadApp('?mode=offline-demo');
  const screen = elements.get('consentScreen') || document.getElementById('consentScreen');
  const launchButton = document.getElementById('nudgeActionBtn');
  const title = document.getElementById('consentDialogTitle');
  const cancelButton = document.getElementById('consentCancelBtn');
  const confirmButton = document.getElementById('confirmActionBtn');
  screen.focusables = [cancelButton, confirmButton];
  document.activeElement = launchButton;

  vm.runInContext("currentOffer = buildOfflineOffer('friction'); acceptNudge();", context);
  assert.equal(screen.getAttribute('aria-hidden'), 'false');
  assert.equal(screen.inert, false);
  assert.equal(document.activeElement, title);

  document.activeElement = confirmButton;
  context.keyboardEvent = {
    key: 'Tab', shiftKey: false, prevented: false,
    preventDefault() { this.prevented = true; },
  };
  vm.runInContext('handleAccessibilityKeydown(keyboardEvent)', context);
  assert.equal(context.keyboardEvent.prevented, true);
  assert.equal(document.activeElement, cancelButton);

  context.keyboardEvent = {
    key: 'Escape', shiftKey: false, prevented: false,
    preventDefault() { this.prevented = true; },
  };
  vm.runInContext('handleAccessibilityKeydown(keyboardEvent)', context);
  assert.equal(screen.getAttribute('aria-hidden'), 'true');
  assert.equal(screen.inert, true);
  assert.equal(document.activeElement, launchButton);
});

test('inline erasure alert supports focus entry, Escape, and focus restoration', () => {
  const { context, elements, document } = loadApp('?mode=offline-demo');
  const confirmation = elements.get('erasureConfirm') || document.getElementById('erasureConfirm');
  const launchButton = document.getElementById('erasureRequestBtn');
  const cancelButton = document.getElementById('erasureCancelBtn');
  const confirmButton = document.getElementById('erasureConfirmBtn');
  confirmation.focusables = [cancelButton, confirmButton];
  document.activeElement = launchButton;

  vm.runInContext('triggerDataErasure()', context);
  assert.equal(confirmation.getAttribute('aria-hidden'), 'false');
  assert.equal(document.activeElement, cancelButton);

  document.activeElement = confirmButton;
  context.keyboardEvent = {
    key: 'Tab', shiftKey: false, prevented: false,
    preventDefault() { this.prevented = true; },
  };
  vm.runInContext('handleAccessibilityKeydown(keyboardEvent)', context);
  assert.equal(context.keyboardEvent.prevented, true);
  assert.equal(document.activeElement, cancelButton);

  context.keyboardEvent = {
    key: 'Escape', shiftKey: false, prevented: false,
    preventDefault() { this.prevented = true; },
  };
  vm.runInContext('handleAccessibilityKeydown(keyboardEvent)', context);
  assert.equal(confirmation.getAttribute('aria-hidden'), 'true');
  assert.equal(confirmation.inert, true);
  assert.equal(document.activeElement, launchButton);
});

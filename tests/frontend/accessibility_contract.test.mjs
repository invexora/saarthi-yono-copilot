import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';


const HTML = readFileSync(new URL('../../index.html', import.meta.url), 'utf8');
const CSS = readFileSync(new URL('../../style.css', import.meta.url), 'utf8');
const APP = readFileSync(new URL('../../app.js', import.meta.url), 'utf8');


test('click handlers use native buttons with explicit button types', () => {
  assert.doesNotMatch(HTML, /<(?:div|span)\b[^>]*\bonclick=/i);
  const buttons = [...HTML.matchAll(/<button\b[^>]*>/gi)].map(match => match[0]);
  assert.ok(buttons.length > 0);
  buttons.forEach(button => assert.match(button, /\btype="button"/i));
});


test('customer profile and consent controls have programmatic labels', () => {
  assert.match(HTML, /<label\b[^>]*for="profileSelect"/i);
  assert.match(HTML, /<label\b[^>]*for="yonoConsentToggle"/i);
  assert.match(HTML, /<h1\b[^>]*class="project-title"/i);
  assert.match(HTML, /<section\b[^>]*aria-labelledby="simulationHeading"/i);
  assert.match(HTML, /<section\b[^>]*aria-labelledby="traceHeading"/i);
});


test('consent and erasure confirmations expose dialog contracts', () => {
  const consentTag = HTML.match(/<div\b[^>]*id="consentScreen"[^>]*>/i)?.[0] || '';
  assert.match(consentTag, /role="dialog"/i);
  assert.match(consentTag, /aria-modal="true"/i);
  assert.match(consentTag, /aria-labelledby="consentDialogTitle"/i);
  assert.match(consentTag, /aria-hidden="true"/i);
  assert.match(consentTag, /\binert\b/i);

  const erasureTag = HTML.match(/<div\b[^>]*id="erasureConfirm"[^>]*>/i)?.[0] || '';
  assert.match(erasureTag, /role="alertdialog"/i);
  assert.match(erasureTag, /aria-modal="true"/i);
  assert.match(erasureTag, /aria-labelledby="erasureConfirmText"/i);
  assert.match(APP, /event\.key === 'Escape'/);
  assert.match(APP, /trapDialogFocus\(event, consentScreen\)/);
});


test('dynamic state is conveyed without relying only on color', () => {
  for (let index = 1; index <= 7; index += 1) {
    assert.match(HTML, new RegExp(`id="dot${index}Text"[^>]*>pending<`));
  }
  assert.match(HTML, /id="apiStatus"[^>]*role="status"[^>]*aria-live="polite"/i);
  assert.match(HTML, /id="logsArea"[^>]*role="log"[^>]*aria-live="polite"/i);
  assert.match(HTML, /id="toastContainer"[^>]*aria-live="polite"/i);
  assert.match(HTML, /role="progressbar"[^>]*aria-valuenow="40"/i);
  assert.match(APP, /Text`\)\.textContent = variant === 'amber' \? 'support mode' : 'complete'/);
});


test('focus visibility and reduced-motion preferences have CSS fallbacks', () => {
  assert.match(CSS, /:focus-visible\s*\{/);
  assert.match(CSS, /outline:\s*3px solid #fbbf24/i);
  assert.match(CSS, /@media\s*\(prefers-reduced-motion:\s*reduce\)/i);
  assert.match(CSS, /animation-duration:\s*0\.01ms\s*!important/i);
  assert.match(CSS, /transition-duration:\s*0\.01ms\s*!important/i);
});

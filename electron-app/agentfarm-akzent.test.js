// Lauf 38: the button "n8n Editor" of the Agent Farm still had blue text. It used --system-blue, which the
// VibeMind look keeps as the blue of an info status (vibemind-look.js TOKEN_PAGE_LOOK), not as the accent
// of the space. --tint is defined nowhere, so a button with it had no colour at all.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');

test('the n8n editor buttons of the Agent Farm take the accent of the space, not the info blue', () => {
  const page = read('agentfarm', 'src', 'features', 'WorkflowBuilder.tsx');
  assert.doesNotMatch(page, /var\(--system-blue\)/);
  const editorButton = page.slice(page.indexOf('setShowEditor(!showEditor)'), page.indexOf('n8n Editor'));
  assert.match(editorButton, /background: showEditor \? 'var\(--accent\)' : 'transparent'/);
  assert.match(editorButton, /color: showEditor \? '#fff' : 'var\(--accent\)'/);
  assert.match(page, /title="Im Editor oeffnen" style=\{\{[^}]*color: 'var\(--accent\)'/);
});

test('the toggle buttons use --accent, which the look sets; --tint is set nowhere', () => {
  const look = read('vibemind-look.js');
  assert.match(look, /--accent: rgb\(var\(--space-accent-rgb\)\);/);
  assert.doesNotMatch(look + read('agentfarm', 'src', 'styles', 'globals.css'), /--tint\s*:/);
  assert.doesNotMatch(read('agentfarm', 'src', 'features', 'TeamRunner.tsx'), /var\(--tint\)/);
  const page = read('agentfarm', 'src', 'features', 'WorkflowBuilder.tsx');
  assert.match(page, /background: showVibeCoder \? 'var\(--accent\)' : 'transparent'/);
});

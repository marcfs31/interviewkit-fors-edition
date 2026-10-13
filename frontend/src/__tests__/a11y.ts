import axe, { type Result } from 'axe-core';

// color-contrast needs real layout and colors, which jsdom does not compute.
// region only applies to whole pages, not to the isolated components under test.
const AXE_OPTIONS = {
  rules: {
    'color-contrast': { enabled: false },
    region: { enabled: false },
  },
};

function describeViolation(v: Result): string {
  const targets = v.nodes.map((n) => `    ${n.target.join(' ')}`).join('\n');
  return `${v.id} (${v.impact}): ${v.help}\n${targets}`;
}

// Runs axe on the given element and fails with a readable report on any violation.
export async function expectNoA11yViolations(node: Element): Promise<void> {
  const { violations } = await axe.run(node, AXE_OPTIONS);
  if (violations.length > 0) {
    throw new Error(`axe found ${violations.length} violation(s):\n${violations.map(describeViolation).join('\n')}`);
  }
}

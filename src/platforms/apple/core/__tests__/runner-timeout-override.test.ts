import { test, vi } from 'vitest';
import assert from 'node:assert/strict';

// Both budgets are resolved at module load, so each case needs a fresh module registry.
async function budgetsWith(value: string | undefined): Promise<[number, number]> {
  const previous = process.env.AGENT_DEVICE_RUNNER_TIMEOUT_MS;
  if (value === undefined) {
    delete process.env.AGENT_DEVICE_RUNNER_TIMEOUT_MS;
  } else {
    process.env.AGENT_DEVICE_RUNNER_TIMEOUT_MS = value;
  }
  try {
    vi.resetModules();
    const mod = await import('../runner/runner-transport.ts');
    return [mod.RUNNER_STARTUP_TIMEOUT_MS, mod.RUNNER_COMMAND_TIMEOUT_MS];
  } finally {
    if (previous === undefined) {
      delete process.env.AGENT_DEVICE_RUNNER_TIMEOUT_MS;
    } else {
      process.env.AGENT_DEVICE_RUNNER_TIMEOUT_MS = previous;
    }
  }
}

test('runner budgets default to 45s when unset', async () => {
  assert.deepEqual(await budgetsWith(undefined), [45_000, 45_000]);
});

test('runner budgets honour AGENT_DEVICE_RUNNER_TIMEOUT_MS', async () => {
  assert.deepEqual(await budgetsWith('180000'), [180_000, 180_000]);
});

test('runner budgets ignore unusable overrides', async () => {
  // A bad value must not remove the budget and let startup hang forever.
  for (const bad of ['0', '-5', 'nope', '']) {
    assert.deepEqual(await budgetsWith(bad), [45_000, 45_000], `expected default for ${JSON.stringify(bad)}`);
  }
});

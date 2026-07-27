import { test, vi } from 'vitest';
import assert from 'node:assert/strict';

// The envelope is resolved once at module load, so each case needs a fresh module registry.
async function envelopeWith(value: string | undefined): Promise<number> {
  const previous = process.env.AGENT_DEVICE_DAEMON_REQUEST_TIMEOUT_MS;
  if (value === undefined) {
    delete process.env.AGENT_DEVICE_DAEMON_REQUEST_TIMEOUT_MS;
  } else {
    process.env.AGENT_DEVICE_DAEMON_REQUEST_TIMEOUT_MS = value;
  }
  try {
    vi.resetModules();
    const mod = await import('../timeout-policy.ts');
    return mod.DEFAULT_TIMEOUT_POLICY.envelopeMs;
  } finally {
    if (previous === undefined) {
      delete process.env.AGENT_DEVICE_DAEMON_REQUEST_TIMEOUT_MS;
    } else {
      process.env.AGENT_DEVICE_DAEMON_REQUEST_TIMEOUT_MS = previous;
    }
  }
}

test('daemon request envelope defaults to 90s when unset', async () => {
  assert.equal(await envelopeWith(undefined), 90_000);
});

test('daemon request envelope honours AGENT_DEVICE_DAEMON_REQUEST_TIMEOUT_MS', async () => {
  assert.equal(await envelopeWith('300000'), 300_000);
});

test('daemon request envelope ignores unusable overrides', async () => {
  // A bad value must not disable the envelope and let a client hang forever.
  for (const bad of ['0', '-1', 'abc', '']) {
    assert.equal(await envelopeWith(bad), 90_000, `expected default for ${JSON.stringify(bad)}`);
  }
});

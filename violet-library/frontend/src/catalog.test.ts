import { describe, expect, it } from 'vitest';
import { decodeHalfVectors } from './catalog';

describe('compact vector format', () => {
  it('decodes little-endian float16 values used by the cloud export', () => {
    const bytes = new Uint8Array([0x00, 0x3c, 0x00, 0xc0, 0x00, 0x38]);
    expect([...decodeHalfVectors(bytes.buffer)]).toEqual([1, -2, 0.5]);
  });

  it('refuses a truncated vector file', () => {
    expect(() => decodeHalfVectors(new ArrayBuffer(3))).toThrow('incomplete');
  });
});

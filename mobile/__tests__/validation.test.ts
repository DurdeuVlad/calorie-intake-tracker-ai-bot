import { MIN_PASSWORD_LENGTH, normalizeEmail, validateEmail, validatePassword } from '../src/auth/validation';

describe('validateEmail', () => {
  it.each(['', '   ', 'no-at-sign', 'a@b', 'a b@c.co', '@x.co'])('rejects %j', (input) => {
    expect(validateEmail(input)).toBeTruthy();
  });

  it.each(['a@b.co', 'user+tag@example.com', 'UPPER@EXAMPLE.COM', '  spaced@ok.co  '])(
    'accepts %j',
    (input) => {
      expect(validateEmail(input)).toBeNull();
    },
  );
});

describe('validatePassword', () => {
  it('requires a password', () => {
    expect(validatePassword('')).toBeTruthy();
  });

  it(`enforces the server minimum of ${MIN_PASSWORD_LENGTH}`, () => {
    expect(validatePassword('x'.repeat(MIN_PASSWORD_LENGTH - 1))).toBeTruthy();
    expect(validatePassword('x'.repeat(MIN_PASSWORD_LENGTH))).toBeNull();
  });
});

describe('normalizeEmail', () => {
  it('trims and lowercases like the server validator', () => {
    expect(normalizeEmail('  User@Example.COM ')).toBe('user@example.com');
  });
});

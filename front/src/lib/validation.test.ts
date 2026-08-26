/**
 * validation.ts 는 서버 규칙(backend/accounts/serializers.py, validators.py)의 근사본이다.
 * 여기 케이스는 서버 테스트(accounts/tests/test_password_rules.py,
 * test_validation_messages.py)와 같은 입력을 쓴다 — 한쪽 규칙이 바뀌면 여기서 어긋난다.
 */
import { describe, expect, it } from 'vitest'

import {
  checkEmail,
  checkNickname,
  checkPassword,
  checkPasswordConfirm,
  EMAIL_MAX_LENGTH,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  passwordRules,
} from './validation'

const valid = (r: { state: string }) => r.state === 'valid'
const invalid = (r: { state: string }) => r.state === 'invalid'

describe('checkEmail', () => {
  it('빈 값은 idle', () => {
    expect(checkEmail('').state).toBe('idle')
  })
  it('형식이 틀리면 invalid', () => {
    expect(checkEmail('not-an-email')).toMatchObject({ state: 'invalid' })
    expect(checkEmail('a@b')).toMatchObject({ state: 'invalid' }) // TLD 없음
    expect(checkEmail('a b@example.com')).toMatchObject({ state: 'invalid' })
  })
  it('254자 경계: 254자는 통과, 262자는 실패 (서버 LengthLimitTests 와 동일)', () => {
    const atLimit = 'a'.repeat(242) + '@example.com'
    expect(atLimit).toHaveLength(EMAIL_MAX_LENGTH)
    expect(valid(checkEmail(atLimit))).toBe(true)
    const tooLong = 'a'.repeat(250) + '@example.com'
    expect(checkEmail(tooLong).message).toContain('254자')
  })
  it('정상 이메일', () => {
    expect(valid(checkEmail('climber@example.com'))).toBe(true)
  })
})

describe('checkNickname (서버 NicknameRuleTests 와 동일 입력)', () => {
  it('1자 → 2자 이상 요구', () => {
    expect(checkNickname('x').message).toContain('2자 이상')
  })
  it('특수문자 거부', () => {
    expect(checkNickname('해커!!@#').message).toContain('한글, 영문, 숫자')
  })
  it('31자 거부', () => {
    expect(checkNickname('가'.repeat(31)).message).toContain('30자 이하')
  })
  it('공백만 있으면 거부', () => {
    expect(invalid(checkNickname('   '))).toBe(true)
  })
  it('정상 닉네임', () => {
    for (const n of ['볼더왕', 'climber_01', '초크', 'my-name']) {
      expect(valid(checkNickname(n)), n).toBe(true)
    }
  })
})

describe('checkPassword (서버 PasswordRuleTests 와 동일 입력)', () => {
  const rule = (pw: string, label: string) =>
    passwordRules(pw).find((r) => r.label.includes(label))?.passed

  it('영문만 / 특수문자만 → 2종 조합 실패', () => {
    expect(rule('azbycxdw', '2종류')).toBe(false)
    expect(rule('!@#$%^&*', '2종류')).toBe(false)
  })
  it('같은 문자 3연속 (aaa) 거부', () => {
    expect(rule('s3cure!aaa', '연속')).toBe(false)
  })
  it('오름차순 123 / 내림차순 wvu 거부', () => {
    expect(rule('s3cure!123', '연속')).toBe(false)
    expect(rule('x9!wvuq2', '연속')).toBe(false)
  })
  it('길이 경계: 16자 통과, 17자 실패, 7자 실패', () => {
    const sixteen = 'x7q!w9e$r2t5u8o3'
    expect(sixteen).toHaveLength(PASSWORD_MAX_LENGTH)
    expect(valid(checkPassword(sixteen))).toBe(true)
    expect(rule(sixteen + 'p', `${PASSWORD_MIN_LENGTH}~${PASSWORD_MAX_LENGTH}자`)).toBe(false)
    expect(rule('x7q!w9e', `${PASSWORD_MIN_LENGTH}~${PASSWORD_MAX_LENGTH}자`)).toBe(false)
  })
  it('흔한 비밀번호 거부', () => {
    expect(rule('12345678', '흔한')).toBe(false)
    expect(rule('password', '흔한')).toBe(false)
  })
  it('이메일/닉네임과 유사하면 거부 (서버 PasswordSimilarityTests)', () => {
    expect(
      passwordRules('climber@example', { email: 'climber@example.com' }).find((r) =>
        r.label.includes('유사'),
      )?.passed,
    ).toBe(false)
    expect(
      passwordRules('mountain99', { email: 'mountain@example.com' }).find((r) =>
        r.label.includes('유사'),
      )?.passed,
    ).toBe(false)
    expect(
      passwordRules('climbmaster1', { nickname: 'climbmaster' }).find((r) =>
        r.label.includes('유사'),
      )?.passed,
    ).toBe(false)
  })
  it('정상 비밀번호는 모든 규칙 통과', () => {
    for (const pw of ['wall!hold9', 's3cure-pass!', 'cr1mp&sloper', 'tr4verse-wall!']) {
      expect(valid(checkPassword(pw, { email: 'fine@example.com', nickname: '정상닉' })), pw).toBe(
        true,
      )
    }
  })
  it('실패 시 첫 번째로 어긋난 규칙 라벨을 메시지로 준다', () => {
    expect(checkPassword('12345678').message).toBe('영문·숫자·특수문자 중 2종류 이상 조합')
  })
})

describe('checkPasswordConfirm', () => {
  it('빈 확인값은 idle, 불일치는 invalid, 일치는 valid', () => {
    expect(checkPasswordConfirm('abc', '').state).toBe('idle')
    expect(checkPasswordConfirm('abc', 'abd').message).toContain('일치하지')
    expect(valid(checkPasswordConfirm('abc', 'abc'))).toBe(true)
  })
})

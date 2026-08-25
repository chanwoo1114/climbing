/**
 * 회원가입/로그인 입력 검증.
 * 백엔드(accounts.serializers) 규칙과 맞춰 둔다 — 여기서 통과해도 서버가 최종 판정.
 */

export type ValidationState = 'idle' | 'valid' | 'invalid'

export interface FieldCheck {
  state: ValidationState
  message: string
}

const IDLE: FieldCheck = { state: 'idle', message: '' }

const ok = (message: string): FieldCheck => ({ state: 'valid', message })
const fail = (message: string): FieldCheck => ({ state: 'invalid', message })

/** RFC 전체를 검사하진 않고, 실수로 잘못 친 형태를 걸러내는 수준 */
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/

/** accounts_user.email 컬럼(varchar 254)과 맞춘 값 */
export const EMAIL_MAX_LENGTH = 254
/** 한국 관행 8~16자 — backend/accounts/validators.py 와 동일 유지 */
export const PASSWORD_MAX_LENGTH = 16

export function checkEmail(value: string): FieldCheck {
  if (!value) return IDLE
  if (value.length > EMAIL_MAX_LENGTH) {
    return fail(`이메일은 ${EMAIL_MAX_LENGTH}자 이하여야 합니다.`)
  }
  if (!EMAIL_RE.test(value)) return fail('이메일 형식이 올바르지 않습니다.')
  return ok('사용 가능한 형식입니다.')
}

export function checkNickname(value: string): FieldCheck {
  if (!value) return IDLE
  if (value.length < 2) return fail('닉네임은 2자 이상이어야 합니다.')
  if (value.length > 30) return fail('닉네임은 30자 이하여야 합니다.')
  if (!/^[가-힣a-zA-Z0-9_-]+$/.test(value)) {
    return fail('한글, 영문, 숫자, _ - 만 사용할 수 있습니다.')
  }
  return ok('사용 가능한 닉네임입니다.')
}

/**
 * Django의 password validator와 대응 (settings.AUTH_PASSWORD_VALIDATORS).
 * - MinimumLengthValidator: 8자 이상
 * - NumericPasswordValidator: 숫자로만 구성 금지
 * - CommonPasswordValidator: 흔한 비밀번호 금지 (서버는 2만 개 목록, 여기선 일부만)
 * - UserAttributeSimilarityValidator: 이메일·닉네임과 유사 금지
 *
 * 여기서 통과해도 최종 판정은 서버가 한다. 목적은 제출 전에 무엇이 부족한지
 * 보여주는 것.
 */
const COMMON_PASSWORDS = [
  'password',
  'password1',
  'password123',
  '12345678',
  '123456789',
  'qwerty123',
  'qwertyuiop',
  'iloveyou',
  'abc12345',
  'climbing',
  'letmein123',
  'admin123',
  'welcome1',
]

export const PASSWORD_MIN_LENGTH = 8

/** 사용자 정보 — 비밀번호 유사도 검사에 쓴다 */
export interface PasswordContext {
  email?: string
  nickname?: string
}

/** 동일 문자 3연속(aaa) 또는 연속 문자열(123, abc, cba) 여부 */
function hasSequentialChars(password: string): boolean {
  if (/(.)\1\1/.test(password)) return true
  const lowered = password.toLowerCase()
  for (let i = 0; i < lowered.length - 2; i++) {
    const [a, b, c] = [0, 1, 2].map((k) => lowered.charCodeAt(i + k))
    if (b - a === c - b && Math.abs(b - a) === 1) return true
  }
  return false
}

/** Django UserAttributeSimilarityValidator 근사 — 서버가 최종 판정 */
function isSimilarTo(password: string, attribute?: string): boolean {
  if (!attribute) return false
  const pw = password.toLowerCase()
  // 이메일은 @ 앞뒤, 점 등으로 쪼개서 각 조각과 비교한다 (Django와 동일한 방식)
  const parts = attribute
    .toLowerCase()
    .split(/[^a-z0-9가-힣]+/)
    .filter((part) => part.length >= 3)
  return [attribute.toLowerCase(), ...parts].some(
    (part) => part.length >= 3 && (pw.includes(part) || part.includes(pw)),
  )
}

export interface PasswordRule {
  label: string
  passed: boolean
}

/** 비밀번호 조건별 통과 여부 — 회원가입 폼에 체크리스트로 보여준다 */
export function passwordRules(
  value: string,
  context: PasswordContext = {},
): PasswordRule[] {
  const classes = [/[a-zA-Z]/, /\d/, /[^a-zA-Z0-9\s]/].filter((re) =>
    re.test(value),
  ).length
  return [
    {
      label: `${PASSWORD_MIN_LENGTH}~${PASSWORD_MAX_LENGTH}자`,
      passed: value.length >= PASSWORD_MIN_LENGTH && value.length <= PASSWORD_MAX_LENGTH,
    },
    { label: '영문·숫자·특수문자 중 2종류 이상 조합', passed: classes >= 2 },
    {
      label: '같은 문자 3연속·연속 문자(123, abc) 없음',
      passed: !hasSequentialChars(value),
    },
    {
      label: '흔한 비밀번호가 아님',
      passed: !COMMON_PASSWORDS.includes(value.toLowerCase()),
    },
    {
      label: '이메일·닉네임과 유사하지 않음',
      passed:
        !isSimilarTo(value, context.email) && !isSimilarTo(value, context.nickname),
    },
  ]
}

export function checkPassword(
  value: string,
  context: PasswordContext = {},
): FieldCheck {
  if (!value) return IDLE
  const failed = passwordRules(value, context).find((rule) => !rule.passed)
  if (failed) return fail(failed.label)
  return ok('사용 가능한 비밀번호입니다.')
}

export function checkPasswordConfirm(password: string, confirm: string): FieldCheck {
  if (!confirm) return IDLE
  if (password !== confirm) return fail('비밀번호가 일치하지 않습니다.')
  return ok('비밀번호가 일치합니다.')
}

/** 로그인 폼처럼 "비어 있지만 않으면 되는" 필드 */
export function checkRequired(value: string, label: string): FieldCheck {
  if (!value) return IDLE
  return value.trim() ? ok('') : fail(`${label}을(를) 입력해 주세요.`)
}

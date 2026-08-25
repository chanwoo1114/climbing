import { passwordRules, type PasswordContext } from '@/lib/validation'

interface Props {
  password: string
  context: PasswordContext
}

/** 비밀번호 조건 체크리스트 — 입력 중 조건별로 빨강/초록 표시 */
export default function PasswordRuleList({ password, context }: Props) {
  if (!password) return null

  return (
    <ul className="mt-2 space-y-1">
      {passwordRules(password, context).map((rule) => (
        <li
          key={rule.label}
          className={`flex items-center gap-1.5 text-xs ${
            rule.passed ? 'text-moss-500' : 'text-danger-500'
          }`}
        >
          <span aria-hidden>{rule.passed ? '✓' : '✕'}</span>
          {rule.label}
        </li>
      ))}
    </ul>
  )
}

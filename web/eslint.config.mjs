import nextVitals from 'eslint-config-next/core-web-vitals'

const config = [
  ...nextVitals,
  {
    rules: {
      '@next/next/no-img-element': 'warn',
      // These components intentionally synchronize refs and local UI state
      // during render/effects. Refactoring them is separate from the Next 16
      // security upgrade, so keep the existing lint contract for now.
      'react-hooks/refs': 'off',
      'react-hooks/set-state-in-effect': 'off',
    },
  },
]

export default config

import js from '@eslint/js'
import { FlatCompat } from '@eslint/eslintrc'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'

const compat = new FlatCompat({ baseDirectory: import.meta.dirname })

export default [
  js.configs.recommended,
  ...compat.extends('plugin:react/recommended'),
  {
    plugins: {
      'react-hooks': reactHooks,
    },
    languageOptions: {
      globals: {
        fetch: 'readonly',
        window: 'readonly',
        document: 'readonly',
        HTMLElement: 'readonly',
        navigator: 'readonly',
        localStorage: 'readonly',
      },
    },
    settings: {
      react: { version: '18.3' },
    },
    rules: {
      'react/prop-types': 'warn',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'no-unused-vars': 'warn',
      'no-console': 'warn',
      'react/react-in-jsx-scope': 'off',
    },
  },
  {
    ignores: ['dist/', 'node_modules/'],
  },
]

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { execFileSync } from 'node:child_process'

function getBuildHash() {
  try {
    return execFileSync('git', ['rev-parse', '--short=12', 'HEAD'], {
      encoding: 'utf8',
    }).trim()
  } catch {
    return 'UNKNOWN'
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  define: {
    __BUILD_HASH__: JSON.stringify(getBuildHash()),
  },
})

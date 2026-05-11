import { execSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '../../..')
const PYTHON = path.resolve(REPO_ROOT, '.venv/Scripts/python.exe')
const SEED_SCRIPT = path.resolve(__dirname, 'seed-logistics-pool.py')

function runSeedCommand(command) {
  return execSync(`"${PYTHON}" "${SEED_SCRIPT}" ${command}`, {
    cwd: REPO_ROOT,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim()
}

export function seedPool() {
  return runSeedCommand('seed')
}

export function cleanupPool() {
  return runSeedCommand('cleanup')
}

export function seedMyLogistics(username = 'admin') {
  return runSeedCommand(`seed-logistics ${username}`)
}

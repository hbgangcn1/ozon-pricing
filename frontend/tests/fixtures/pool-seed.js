/* eslint-env node */
import { execSync } from 'node:child_process'
import { existsSync, unlinkSync, readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { API_BASE } from './test-data.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PYTHON = path.resolve(__dirname, '../../../../.venv/Scripts/python.exe')
const SEED_SCRIPT = path.resolve(__dirname, 'create-pool-xlsx.py')
const XLSX_OUT = path.join(process.env.TEMP || '/tmp', 'e2e-pool-seed.xlsx')

export async function seedLogisticsPool(adminToken) {
  execSync(`"${PYTHON}" "${SEED_SCRIPT}" "${XLSX_OUT}"`, { stdio: 'pipe' })

  const fileBuffer = readFileSync(XLSX_OUT)
  const blob = new Blob([fileBuffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
  const form = new FormData()
  form.append('file', blob, 'pool-seed.xlsx')

  const resp = await fetch(`${API_BASE}/logistics-pool/import`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${adminToken}` },
    body: form,
  })

  if (existsSync(XLSX_OUT)) unlinkSync(XLSX_OUT)

  if (!resp.ok) {
    const body = await resp.text()
    throw new Error(`seedLogisticsPool import failed ${resp.status}: ${body}`)
  }
  return resp.json()
}

export async function cleanupPoolSeedEntries(adminToken) {
  await fetch(`${API_BASE}/logistics-pool/all`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${adminToken}` },
  })
}

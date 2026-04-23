/* eslint-env node */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import bcrypt from 'bcryptjs'
import { Pool } from 'pg'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const PROJECT_ROOT = path.resolve(__dirname, '..', '..', '..')
const ENV_PATH = path.join(PROJECT_ROOT, '.env')
const ADMIN_USERNAME = 'admin'
const BCRYPT_ROUNDS = 12

function loadEnvFile() {
  if (!fs.existsSync(ENV_PATH)) {
    return
  }

  const content = fs.readFileSync(ENV_PATH, 'utf-8')
  for (const rawLine of content.split(/\r?\n/u)) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) {
      continue
    }

    const separatorIndex = line.indexOf('=')
    if (separatorIndex <= 0) {
      continue
    }

    const key = line.slice(0, separatorIndex).trim()
    const value = line.slice(separatorIndex + 1).trim()
    if (!process.env[key]) {
      process.env[key] = value
    }
  }
}

function getDatabaseUrl() {
  loadEnvFile()

  if (process.env.DATABASE_URL) {
    return process.env.DATABASE_URL
  }

  const host = process.env.POSTGRES_HOST || 'localhost'
  const port = process.env.POSTGRES_PORT || '5432'
  const database = process.env.POSTGRES_DB
  const user = process.env.POSTGRES_USER
  const password = process.env.POSTGRES_PASSWORD

  if (!database || !user || !password) {
    throw new Error('Database connection env vars are incomplete')
  }

  return `postgresql://${encodeURIComponent(user)}:${encodeURIComponent(password)}@${host}:${port}/${database}`
}

function createPool() {
  return new Pool({
    connectionString: getDatabaseUrl(),
    max: 1,
    allowExitOnIdle: true,
  })
}

function normalizeAnswer(answer) {
  return (answer || '').trim().toLowerCase()
}

export async function upsertAdminSecurityQuestion(question, answer) {
  const pool = createPool()

  try {
    const answerHash = await bcrypt.hash(normalizeAnswer(answer), BCRYPT_ROUNDS)
    const result = await pool.query(
      `
        UPDATE users
        SET security_q1 = $1,
            security_a1 = $2
        WHERE username = $3
        RETURNING id, username, security_q1
      `,
      [question, answerHash, ADMIN_USERNAME]
    )

    if (result.rowCount !== 1) {
      throw new Error(`Admin security question upsert affected ${result.rowCount ?? 0} rows`)
    }

    return result.rows[0]
  } finally {
    await pool.end()
  }
}

export async function verifyAdminSecurityQuestion() {
  const pool = createPool()

  try {
    const result = await pool.query(
      `
        SELECT username, security_q1, security_q1 IS NOT NULL AS has_security_question
        FROM users
        WHERE username = $1
      `,
      [ADMIN_USERNAME]
    )

    if (result.rowCount !== 1) {
      throw new Error(`Admin security question verify found ${result.rowCount ?? 0} rows`)
    }

    return result.rows[0]
  } finally {
    await pool.end()
  }
}

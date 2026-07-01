<script setup lang="ts">
import { ref } from 'vue'
import type { CoverageResponse, OperatorCoverage, AddressError } from './types'

const rawInput = ref('')
const loading = ref(false)
const results = ref<CoverageResponse | null>(null)
const addressLabels = ref<Record<string, string>>({})
const apiError = ref<string | null>(null)

const OPERATORS = ['orange', 'sfr', 'bouygues', 'free'] as const
const TECHS = ['2G', '3G', '4G'] as const

const OPERATOR_LABELS: Record<string, string> = {
  orange: 'Orange',
  sfr: 'SFR',
  bouygues: 'Bouygues',
  free: 'Free',
}

function parseAddresses(): Record<string, string> {
  return Object.fromEntries(
    rawInput.value
      .split(';')
      .map(s => s.trim())
      .filter(s => s.length > 0)
      .map((addr, i) => [`addr_${i + 1}`, addr]),
  )
}

function isError(result: CoverageResult): result is AddressError {
  return 'error' in result
}

function errorLabel(code: string): string {
  if (code === 'address_not_found') return 'Address not found'
  if (code === 'geocoding_timeout') return 'Geocoding timed out'
  return 'Geocoding error'
}

async function checkCoverage() {
  const addresses = parseAddresses()
  if (Object.keys(addresses).length === 0) return

  addressLabels.value = addresses
  loading.value = true
  apiError.value = null
  results.value = null

  try {
    const response = await fetch('/coverage', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(addresses),
    })

    if (response.status === 503) {
      apiError.value = 'All addresses failed geocoding — check that the addresses are valid French addresses.'
      return
    }

    if (!response.ok) {
      apiError.value = `Unexpected error (HTTP ${response.status})`
      return
    }

    results.value = await response.json() as CoverageResponse
  } catch {
    apiError.value = 'Network error — is the API running?'
  } finally {
    loading.value = false
  }
}

type CoverageResult = OperatorCoverage | AddressError
</script>

<template>
  <div class="page">
    <header class="site-header">
      <h1>Mobile Coverage Checker</h1>
      <p>Check 2G / 3G / 4G coverage for French addresses across all four operators.</p>
    </header>

    <main>
      <section class="input-card">
        <label for="addresses">
          Addresses
          <span class="hint">— separated by semicolons</span>
        </label>
        <textarea
          id="addresses"
          v-model="rawInput"
          placeholder="157 bd MacDonald 75019 Paris; 10 rue de Rivoli 75001 Paris"
          rows="3"
          :disabled="loading"
        />
        <button
          class="btn-primary"
          :disabled="loading || rawInput.trim().length === 0"
          @click="checkCoverage"
        >
          {{ loading ? 'Checking…' : 'Check coverage' }}
        </button>
      </section>

      <p v-if="apiError" class="api-error">{{ apiError }}</p>

      <section v-if="results" class="results">
        <div
          v-for="(result, id) in results"
          :key="id"
          class="result-card"
        >
          <h2 class="address-label">{{ addressLabels[id as string] ?? id }}</h2>

          <div v-if="isError(result)" class="address-error">
            {{ errorLabel(result.error) }}
          </div>

          <table v-else class="coverage-table">
            <thead>
              <tr>
                <th />
                <th v-for="tech in TECHS" :key="tech">{{ tech }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="op in OPERATORS" :key="op">
                <td class="op-name">{{ OPERATOR_LABELS[op] }}</td>
                <td
                  v-for="tech in TECHS"
                  :key="tech"
                  :class="(result as OperatorCoverage)[op][tech] ? 'cell-yes' : 'cell-no'"
                >
                  {{ (result as OperatorCoverage)[op][tech] ? '✓' : '✗' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </main>
  </div>
</template>

<style>
*, *::before, *::after { box-sizing: border-box; }

body {
  margin: 0;
  font-family: system-ui, -apple-system, sans-serif;
  background: #f4f6f9;
  color: #1a1a2e;
}

.page {
  max-width: 760px;
  margin: 0 auto;
  padding: 2rem 1rem 4rem;
}

.site-header {
  margin-bottom: 2rem;
}

.site-header h1 {
  font-size: 1.75rem;
  margin: 0 0 0.4rem;
}

.site-header p {
  margin: 0;
  color: #555;
}

.input-card {
  background: #fff;
  border-radius: 10px;
  padding: 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,.07);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

label {
  font-weight: 600;
  font-size: 0.95rem;
}

.hint {
  font-weight: 400;
  color: #888;
  font-size: 0.85rem;
}

textarea {
  width: 100%;
  border: 1.5px solid #d1d5db;
  border-radius: 6px;
  padding: 0.6rem 0.75rem;
  font-size: 0.95rem;
  font-family: inherit;
  resize: vertical;
  transition: border-color 0.15s;
}

textarea:focus {
  outline: none;
  border-color: #4f6ef7;
}

.btn-primary {
  align-self: flex-start;
  background: #4f6ef7;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 0.6rem 1.4rem;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-primary:hover:not(:disabled) { background: #3b57e0; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.api-error {
  margin-top: 1rem;
  padding: 0.75rem 1rem;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  border-radius: 6px;
  color: #b91c1c;
  font-size: 0.9rem;
}

.results {
  margin-top: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.result-card {
  background: #fff;
  border-radius: 10px;
  padding: 1.25rem 1.5rem;
  box-shadow: 0 2px 8px rgba(0,0,0,.07);
}

.address-label {
  font-size: 1rem;
  font-weight: 600;
  margin: 0 0 1rem;
  color: #333;
  word-break: break-word;
}

.address-error {
  padding: 0.5rem 0.75rem;
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: 6px;
  color: #92400e;
  font-size: 0.9rem;
}

.coverage-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.coverage-table th,
.coverage-table td {
  padding: 0.5rem 0.75rem;
  text-align: center;
}

.coverage-table thead th {
  font-weight: 700;
  color: #555;
  border-bottom: 2px solid #e5e7eb;
}

.op-name {
  text-align: left;
  font-weight: 600;
  color: #374151;
  min-width: 90px;
}

.coverage-table tbody tr:not(:last-child) td {
  border-bottom: 1px solid #f3f4f6;
}

.cell-yes { color: #16a34a; font-weight: 700; font-size: 1rem; }
.cell-no  { color: #dc2626; font-weight: 700; font-size: 1rem; }
</style>

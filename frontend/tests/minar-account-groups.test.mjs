import test, {after} from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {transform} from 'esbuild'

const oldFetch = globalThis.fetch, oldStorage = globalThis.localStorage
const values = new Map()
globalThis.localStorage = {getItem: key => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key)}
const source = await readFile(new URL('../src/api.js', import.meta.url), 'utf8')
const {code} = await transform(source, {format: 'esm', define: {'import.meta.env': '{}'}})
const api = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
after(() => { globalThis.fetch = oldFetch; globalThis.localStorage = oldStorage })

test('account group picker calls the scoped SPACE endpoint without invalid page size or truncation', async () => {
  const groups = Array.from({length: 105}, (_, i) => ({id: i + 1, name: `Group ${i + 1}`}))
  api.setToken('test-staff-session')
  globalThis.fetch = async (url, options) => {
    assert.equal(new URL(url).pathname, '/space/admin/account-groups')
    assert.equal(new URL(url).search, '')
    assert.equal(options.headers.Authorization, 'Bearer test-staff-session')
    return {ok: true, status: 200, json: async () => groups}
  }
  assert.deepEqual(await api.fetchMinarAccountGroups(), groups)
})
test('group loading preserves actionable errors and permits a successful retry', async () => {
  globalThis.fetch = async () => ({ok: false, status: 403, json: async () => ({detail: 'Ruxsat yo‘q'})})
  await assert.rejects(api.fetchMinarAccountGroups(), e => e.status === 403 && e.message === 'Ruxsat yo‘q')
  globalThis.fetch = async () => ({ok: true, status: 200, json: async () => [{id: 7, name: 'Teacher group'}]})
  assert.deepEqual(await api.fetchMinarAccountGroups(), [{id: 7, name: 'Teacher group'}])
})

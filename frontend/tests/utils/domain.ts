/**
 * Test data for the domain pages, created through the API as the superuser.
 * Every helper uses random ids so tests can run in parallel and repeatedly
 * on the same database.
 */
import { readFileSync } from "node:fs"
import type { Page } from "@playwright/test"
import { firstSuperuser, firstSuperuserPassword } from "../config.ts"

// Recorded PubChem/Wikidata responses, shared with the unit tests
const fixture = JSON.parse(
  readFileSync(
    new URL("../../src/lib/__fixtures__/pubchem-cfc11.json", import.meta.url),
    "utf8",
  ),
)

const API = `${process.env.VITE_API_URL}/api/v1`

let token: Promise<string> | undefined

async function superuserToken(): Promise<string> {
  token ??= (async () => {
    const response = await fetch(`${API}/login/access-token`, {
      method: "POST",
      body: new URLSearchParams({
        username: firstSuperuser,
        password: firstSuperuserPassword,
      }),
    })
    if (!response.ok) throw new Error(`Login failed: ${response.status}`)
    return ((await response.json()) as { access_token: string }).access_token
  })()
  return token
}

export async function api<T = unknown>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${await superuserToken()}`,
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(
      `${method} ${path}: ${response.status} ${await response.text()}`,
    )
  }
  return (await response.json()) as T
}

/** Lower-case alphanumeric id, unique enough for a test run. */
export const randomId = (prefix = "t") =>
  `${prefix}${Math.random().toString(36).slice(2, 10)}`

/** A random UTC time in 2026, as ISO string (no milliseconds). */
export const randomTime = () =>
  new Date(Date.UTC(2026, 0, 1) + Math.floor(Math.random() * 3e10))
    .toISOString()
    .replace(/\.\d{3}Z$/, "Z")

export const createCompound = (body: Record<string, unknown> = {}) =>
  api<{ id: string }>("POST", "/compounds/", { id: randomId("c"), ...body })

export const createInstrument = () =>
  api<{ id: string }>("POST", "/instruments/", {
    id: randomId("i"),
    name: "Test GC-MS",
  })

export const createContainer = () =>
  api<{ id: string }>("POST", "/containers/", {
    id: randomId("flask"),
    kind: "flask",
  })

export const createSample = (containerId: string, filledAt = randomTime()) =>
  api<{ id: string }>("POST", "/samples/", {
    id: randomId("s"),
    container_id: containerId,
    filled_at: filledAt,
  })

export type Measurement = { id: number; measured_at: string }

export const createMeasurement = (body: {
  instrument_id: string
  type?: string
  sample_id?: string
  measured_at?: string
  description?: string
  results?: { compound_id: string; concentration?: number; area?: number }[]
}) =>
  api<Measurement>("POST", "/measurements/", {
    type: "air",
    measured_at: randomTime(),
    ...body,
  })

/** Answer PubChem and Wikidata requests with recorded CFC-11 responses. */
export async function mockPubChem(page: Page, { found = true } = {}) {
  await page.route("https://pubchem.ncbi.nlm.nih.gov/rest/**", (route) => {
    const url = route.request().url()
    if (!found) return route.fulfill({ status: 404, json: {} })
    if (url.includes("/cids/")) {
      return route.fulfill({ json: { IdentifierList: { CID: [6389] } } })
    }
    if (url.includes("/property/")) {
      return route.fulfill({ json: fixture.properties })
    }
    if (url.includes("/synonyms/")) {
      return route.fulfill({ json: fixture.synonyms })
    }
    if (url.includes("pug_view")) {
      return route.fulfill({ json: fixture.boilingPoint })
    }
    return route.fulfill({ status: 404, json: {} })
  })
  await page.route("https://www.wikidata.org/**", (route) =>
    route.fulfill({ json: fixture.wikidataSearch }),
  )
}

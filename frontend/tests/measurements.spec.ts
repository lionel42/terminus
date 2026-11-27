import { readFile } from "node:fs/promises"
import { expect, test } from "@playwright/test"

import {
  createCompound,
  createContainer,
  createInstrument,
  createMeasurement,
  createSample,
} from "./utils/domain"

/** One instrument per test keeps the lists independent of other tests. */
async function setup() {
  const instrument = await createInstrument()
  const compound = await createCompound({ industrial_name: "CFC-11" })
  const container = await createContainer()
  const sample = await createSample(container.id, "2026-03-01T08:00:00Z")
  const tank = await createMeasurement({
    instrument_id: instrument.id,
    type: "tank",
    sample_id: sample.id,
    measured_at: "2026-03-02T10:00:00Z",
    description: "tank run",
    results: [
      { compound_id: compound.id, concentration: 220.123456, area: 1e5 },
    ],
  })
  const air = await createMeasurement({
    instrument_id: instrument.id,
    type: "air",
    measured_at: "2026-03-05T10:00:00Z",
    results: [{ compound_id: compound.id, concentration: 221 }],
  })
  return { instrument, compound, container, sample, tank, air }
}

test("lists and filters measurements through the URL", async ({ page }) => {
  const { instrument } = await setup()

  await page.goto(`/measurements?instrument_id=${instrument.id}`)
  await expect(page.locator("tbody tr")).toHaveCount(2)

  await page.goto(`/measurements?instrument_id=${instrument.id}&type=tank`)
  await expect(page.locator("tbody tr")).toHaveCount(1)
  await expect(page.locator("tbody")).toContainText("2026-03-02 10:00:00")

  await page.goto(
    `/measurements?instrument_id=${instrument.id}&from=2026-03-03&to=2026-03-31`,
  )
  await expect(page.locator("tbody tr")).toHaveCount(1)
  await expect(page.locator("tbody")).toContainText("2026-03-05 10:00:00")
})

test("applies date filters from the filter bar", async ({ page }) => {
  const { instrument } = await setup()
  await page.goto(`/measurements?instrument_id=${instrument.id}`)
  await page.getByLabel("From (UTC)").fill("2026-03-01")
  await page.getByLabel("To (UTC)").fill("2026-03-02")
  await page.getByRole("button", { name: "Apply" }).click()
  await page.waitForURL(/from=2026-03-01/)
  await expect(page.locator("tbody tr")).toHaveCount(1)
  await expect(page.locator("tbody")).toContainText("tank run")
})

test("shows a measurement with its sample, container and results", async ({
  page,
}) => {
  const { instrument, compound, container, sample, tank } = await setup()
  await page.goto(`/measurements/${tank.id}`)

  await expect(
    page.getByRole("heading", { name: `Measurement #${tank.id}` }),
  ).toBeVisible()
  await expect(page.getByText(instrument.id)).toBeVisible()
  await expect(page.getByText(sample.id)).toBeVisible()
  await expect(page.getByRole("link", { name: container.id })).toBeVisible()

  const row = page.getByRole("row").filter({ hasText: compound.id })
  await expect(row).toContainText("CFC-11") // name from the compound
  await expect(row).toContainText("220.123") // 6 significant digits
  await expect(row).toContainText("100000")
})

test("edits and deletes a measurement", async ({ page }) => {
  const { instrument, tank } = await setup()
  await page.goto(`/measurements/${tank.id}`)

  await page.getByRole("button", { name: "Actions" }).click()
  await page.getByRole("menuitem", { name: "Edit" }).click()
  await page
    .getByRole("dialog")
    .locator('input[name="description"]')
    .fill("checked again")
  await page.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Measurement updated successfully")).toBeVisible()
  await expect(page.getByText("checked again")).toBeVisible()

  await page.getByRole("button", { name: "Actions" }).click()
  await page.getByRole("menuitem", { name: "Delete" }).click()
  await page.getByRole("dialog").getByRole("button", { name: "Delete" }).click()
  await page.waitForURL("/measurements")

  await page.goto(`/measurements?instrument_id=${instrument.id}`)
  await expect(page.locator("tbody tr")).toHaveCount(1)
})

test("shows results and downloads them as CSV", async ({ page }) => {
  const { instrument, compound, container } = await setup()
  await page.goto(`/results?instrument_id=${instrument.id}`)
  await expect(page.locator("tbody tr")).toHaveCount(2)
  await expect(page.locator("tbody")).toContainText(container.id)

  await page.goto(`/results?instrument_id=${instrument.id}&type=air`)
  await expect(page.locator("tbody tr")).toHaveCount(1)

  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("button", { name: "Download CSV" }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toBe("results.csv")
  const lines = (await readFile(await download.path(), "utf8"))
    .trim()
    .split(/\r?\n/)
  expect(lines[0]).toContain("measurement_id")
  expect(lines[0]).toContain("concentration")
  expect(lines).toHaveLength(2)
  expect(lines[1]).toContain(compound.id)
  expect(lines[1]).toContain(",air,")
})

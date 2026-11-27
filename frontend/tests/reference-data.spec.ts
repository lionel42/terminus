import { expect, test } from "@playwright/test"

import { createContainer, createSample, randomId } from "./utils/domain"

test("creates an instrument and a container", async ({ page }) => {
  for (const [path, label, extra] of [
    ["/instruments", "Instrument", "name"],
    ["/containers", "Container", "kind"],
  ] as const) {
    const id = randomId()
    await page.goto(path)
    await page.getByRole("button", { name: `Add ${label}` }).click()
    const dialog = page.getByRole("dialog")
    await dialog.locator('input[name="id"]').fill(id.toUpperCase())
    await dialog.locator(`input[name="${extra}"]`).fill("test value")
    await dialog.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText(`${label} created successfully`)).toBeVisible()
    // Duplicates (any case) are refused
    await page.getByRole("button", { name: `Add ${label}` }).click()
    await dialog.locator('input[name="id"]').fill(id)
    await dialog.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText(`'${id}' already exists`)).toBeVisible()
  }
})

test("shows the filling history of a container", async ({ page }) => {
  const container = await createContainer()
  const older = await createSample(container.id, "2026-02-01T09:00:00Z")
  const newer = await createSample(container.id, "2026-02-08T09:00:00Z")

  await page.goto(`/samples?container_id=${container.id}`)
  const rows = page.locator("tbody tr")
  await expect(rows).toHaveCount(2)
  // Newest first
  await expect(rows.first()).toContainText(newer.id)
  await expect(rows.last()).toContainText(older.id)
})

test("creates a sample in a container", async ({ page }) => {
  const container = await createContainer()
  const id = randomId("s")
  await page.goto(`/samples?container_id=${container.id}`)
  await page.getByRole("button", { name: "Add Sample" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.locator('input[name="id"]').fill(id)
  // Pre-filled from the filter
  await expect(dialog.locator('input[name="container_id"]')).toHaveValue(
    container.id,
  )
  await dialog.locator('input[name="filled_at"]').fill("2026-04-01T12:00:00")
  await dialog.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText("Sample created successfully")).toBeVisible()
  await expect(page.locator("tbody")).toContainText("2026-04-01 12:00:00")
})

test("refuses a sample in an unknown container", async ({ page }) => {
  await page.goto("/samples")
  await page.getByRole("button", { name: "Add Sample" }).click()
  const dialog = page.getByRole("dialog")
  await dialog.locator('input[name="id"]').fill(randomId("s"))
  await dialog.locator('input[name="container_id"]').fill(randomId("none"))
  await dialog.locator('input[name="filled_at"]').fill("2026-04-01T12:00:00")
  await dialog.getByRole("button", { name: "Save" }).click()
  await expect(page.getByText(/Container '.*' does not exist/)).toBeVisible()
})

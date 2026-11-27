import { expect, test } from "@playwright/test"

import {
  createCompound,
  createInstrument,
  createMeasurement,
} from "./utils/domain"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

// Start logged out, then log in as a normal (non-superuser) user
test.use({ storageState: { cookies: [], origins: [] } })

test("normal users can read but not write domain data", async ({ page }) => {
  const email = randomEmail()
  const password = randomPassword()
  await createUser({ email, password })
  const compound = await createCompound({ industrial_name: "CFC-12" })
  const instrument = await createInstrument()
  const measurement = await createMeasurement({
    instrument_id: instrument.id,
    results: [{ compound_id: compound.id, concentration: 500 }],
  })

  await logInUser(page, email, password)

  for (const [path, button] of [
    ["/compounds", "Add Compound"],
    ["/instruments", "Add Instrument"],
    ["/containers", "Add Container"],
    ["/samples", "Add Sample"],
    ["/measurements", "Add Measurement"],
  ]) {
    await page.goto(path)
    await expect(page.locator("tbody tr").first()).toBeVisible()
    await expect(page.getByRole("button", { name: button })).toHaveCount(0)
    await expect(page.getByRole("button", { name: "Actions" })).toHaveCount(0)
  }

  await page.goto(`/compounds/${compound.id}`)
  await expect(page.getByText("CFC-12").first()).toBeVisible()
  await expect(
    page.getByRole("button", { name: "Fill from PubChem" }),
  ).toHaveCount(0)
  await expect(page.getByLabel("New alias")).toHaveCount(0)
  await expect(
    page.getByRole("button", { name: "Add Boiling point" }),
  ).toHaveCount(0)

  await page.goto(`/measurements/${measurement.id}`)
  await expect(page.getByText("CFC-12")).toBeVisible()
  await expect(page.getByRole("button", { name: "Actions" })).toHaveCount(0)
})

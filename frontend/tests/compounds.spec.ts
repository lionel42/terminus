import { expect, type Page, test } from "@playwright/test"

import {
  api,
  createCompound,
  createInstrument,
  createMeasurement,
  mockPubChem,
  randomId,
} from "./utils/domain"

const field = (page: Page, name: string) =>
  page.getByRole("dialog").locator(`input[name="${name}"]`)

test.describe("Compounds list", () => {
  test("shows compounds with their aliases and links", async ({ page }) => {
    const compound = await createCompound({
      industrial_name: "HFC-134a",
      status: "measured",
      cas_number: "811-97-2",
      wikidata_id: "Q423239",
    })
    const alias = `R-134a ${randomId()}`
    await api("POST", `/compounds/${compound.id}/aliases`, { alias })

    await page.goto("/compounds")
    await page.getByLabel("Search compounds").fill(compound.id)
    await page.getByRole("button", { name: "Search" }).click()

    const row = page.getByRole("row").filter({ hasText: compound.id })
    await expect(row).toHaveCount(1)
    await expect(row).toContainText("HFC-134a")
    await expect(row).toContainText("measured")
    await expect(row).toContainText("811-97-2")
    await expect(row).toContainText(alias)
    await expect(
      row.getByRole("link", { name: "Wikipedia page" }),
    ).toHaveAttribute("href", /GoToLinkedPage\/enwiki\/Q423239$/)
    await expect(
      row.getByRole("link", { name: "PubChem page" }),
    ).toHaveAttribute("href", /#query=811-97-2$/)
  })

  test("searches by alias and filters by status", async ({ page }) => {
    const target = await createCompound({ status: "target" })
    const other = await createCompound({ status: "suspect" })
    const alias = `Alias${randomId()}`
    await api("POST", `/compounds/${target.id}/aliases`, { alias })

    await page.goto("/compounds")
    await page.getByLabel("Search compounds").fill(alias.toUpperCase())
    await page.getByRole("button", { name: "Search" }).click()
    await expect(page.getByRole("link", { name: target.id })).toBeVisible()
    await expect(page.locator("tbody tr")).toHaveCount(1)

    await page.getByLabel("Search compounds").fill("")
    await page.getByRole("button", { name: "Search" }).click()
    await page.getByLabel("Status").click()
    await page.getByRole("option", { name: "suspect" }).click()
    await expect(page.getByRole("link", { name: other.id })).toBeVisible()
    await expect(page.getByRole("link", { name: target.id })).toHaveCount(0)
  })

  test("creates a compound with a lower-cased id", async ({ page }) => {
    const id = randomId("new")
    await page.goto("/compounds")
    await page.getByRole("button", { name: "Add Compound" }).click()

    await field(page, "id").fill("cfc-11")
    await field(page, "industrial_name").click()
    await expect(page.getByText("Only letters and digits")).toBeVisible()

    await field(page, "id").fill(id.toUpperCase())
    await field(page, "industrial_name").fill("CFC-113")
    await field(page, "molar_mass").fill("187.37")
    await page.getByRole("button", { name: "Save" }).click()

    await expect(page.getByText("Compound created successfully")).toBeVisible()
    await page.getByLabel("Search compounds").fill(id)
    await page.getByRole("button", { name: "Search" }).click()
    await expect(
      page.getByRole("link", { name: id, exact: true }),
    ).toBeVisible()
  })

  test("rejects an invalid CAS number", async ({ page }) => {
    await page.goto("/compounds")
    await page.getByRole("button", { name: "Add Compound" }).click()
    await field(page, "id").fill(randomId())
    await field(page, "cas_number").fill("75-69-5")
    await page.getByRole("button", { name: "Save" }).click()
    await expect(page.getByText(/invalid CAS number/)).toBeVisible()
  })

  test("fills the create form from PubChem", async ({ page }) => {
    await mockPubChem(page)
    await page.goto("/compounds")
    await page.getByRole("button", { name: "Add Compound" }).click()
    await field(page, "id").fill(randomId("cfc"))
    await field(page, "industrial_name").fill("My own name")

    await page.getByRole("button", { name: "Fill from PubChem" }).click()

    await expect(field(page, "cas_number")).toHaveValue("75-69-4")
    await expect(field(page, "pubchem_cid")).toHaveValue("6389")
    await expect(field(page, "iupac_name")).toHaveValue(
      "trichloro(fluoro)methane",
    )
    await expect(field(page, "wikidata_id")).toHaveValue("Q423000")
    // Fields already filled in are kept
    await expect(field(page, "industrial_name")).toHaveValue("My own name")
  })

  test("reports a compound PubChem does not know", async ({ page }) => {
    await mockPubChem(page, { found: false })
    await page.goto("/compounds")
    await page.getByRole("button", { name: "Add Compound" }).click()
    await field(page, "id").fill(randomId())
    await page.getByRole("button", { name: "Fill from PubChem" }).click()
    await expect(page.getByText(/Not found in PubChem/)).toBeVisible()
  })
})

test.describe("Compound detail", () => {
  test("shows names and identifiers", async ({ page }) => {
    const compound = await createCompound({
      industrial_name: "CFC-11",
      iupac_name: "trichloro(fluoro)methane",
      formula: "CCl3F",
      cas_number: "75-69-4",
      pubchem_cid: 6389,
      molar_mass: 137.36,
    })
    await page.goto(`/compounds/${compound.id}`)

    await expect(page.getByRole("heading", { name: compound.id })).toBeVisible()
    await expect(page.getByText("CFC-11 · CCl3F")).toBeVisible()
    await expect(page.getByText("137.36 g/mol")).toBeVisible()
    await expect(page.getByRole("link", { name: "6389" })).toHaveAttribute(
      "href",
      "https://pubchem.ncbi.nlm.nih.gov/compound/6389",
    )
    await expect(page.getByRole("link", { name: /NIST/ })).toHaveAttribute(
      "href",
      /ID=75-69-4/,
    )
  })

  test("adds and removes aliases; aliases are unique", async ({ page }) => {
    const compound = await createCompound()
    const other = await createCompound()
    const taken = `Taken${randomId()}`
    await api("POST", `/compounds/${other.id}/aliases`, { alias: taken })
    const alias = `Freon ${randomId()}`

    await page.goto(`/compounds/${compound.id}`)
    await page.getByLabel("New alias").fill(alias)
    await page.getByRole("button", { name: "Add", exact: true }).click()
    await expect(page.getByText(alias)).toBeVisible()
    await expect(page.getByLabel("New alias")).toHaveValue("")

    await page.getByLabel("New alias").fill(taken.toLowerCase())
    await page.getByRole("button", { name: "Add", exact: true }).click()
    await expect(
      page.getByText(`already names compound '${other.id}'`),
    ).toBeVisible()

    await page.getByLabel(`Remove alias ${alias}`).click()
    await expect(page.getByText(alias)).toHaveCount(0)
  })

  test("adds and deletes a boiling point", async ({ page }) => {
    const compound = await createCompound()
    await page.goto(`/compounds/${compound.id}`)

    await page.getByRole("button", { name: "Add Boiling point" }).click()
    await field(page, "temperature_c").fill("-161.5")
    await field(page, "source").fill("CRC Handbook")
    await field(page, "reference_url").fill("https://example.org/crc")
    await page.getByRole("button", { name: "Save" }).click()

    const row = page.getByRole("row").filter({ hasText: "CRC Handbook" })
    await expect(row).toContainText("-161.5")
    await expect(
      row.getByRole("link", { name: "CRC Handbook" }),
    ).toHaveAttribute("href", "https://example.org/crc")

    await row.getByRole("button", { name: "Delete boiling point" }).click()
    await expect(page.getByText("No boiling point stored.")).toBeVisible()
  })

  test("applies PubChem data chosen in the review dialog", async ({ page }) => {
    await mockPubChem(page)
    const compound = await createCompound({
      industrial_name: "CFC-11",
      formula: "CCl3F",
    })
    await page.goto(`/compounds/${compound.id}`)
    await page.getByRole("button", { name: "Fill from PubChem" }).click()

    const dialog = page.getByRole("dialog")
    await expect(dialog.getByText("CID 6389")).toBeVisible()
    // Formula and industrial name already match: not offered
    await expect(dialog.getByRole("cell", { name: "Formula" })).toHaveCount(0)
    // Skip the SMILES and one boiling point
    await dialog.getByLabel("Apply SMILES").uncheck()
    await dialog.getByLabel("Add boiling point 23.72 °C").uncheck()
    await dialog.getByRole("button", { name: /^Apply/ }).click()
    await expect(page.getByText("PubChem data applied")).toBeVisible()

    await expect(page.getByText("CYRMSUTZVYGINF-UHFFFAOYSA-N")).toBeVisible()
    await expect(page.getByText("75-69-4")).toBeVisible()
    await expect(page.getByText("C(F)(Cl)(Cl)Cl")).toHaveCount(0)
    await expect(
      page
        .getByRole("row")
        .filter({ hasText: "Hazardous Substances Data Bank" }),
    ).toContainText("23.7")
    await expect(
      page.getByRole("row").filter({ hasText: "CAMEO" }),
    ).toHaveCount(0)

    // A second lookup marks stored boiling points
    await page.getByRole("button", { name: "Fill from PubChem" }).click()
    await expect(
      dialog.getByLabel("Add boiling point 23.7 °C").first(),
    ).toBeDisabled()
  })

  test("deleting a compound used by results is refused", async ({ page }) => {
    const compound = await createCompound()
    const instrument = await createInstrument()
    await createMeasurement({
      instrument_id: instrument.id,
      results: [{ compound_id: compound.id, concentration: 1 }],
    })
    await page.goto(`/compounds/${compound.id}`)
    await page.getByRole("button", { name: "Actions" }).click()
    await page.getByRole("menuitem", { name: "Delete" }).click()
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Delete" })
      .click()
    await expect(
      page.getByText("Compound is used by measurement results"),
    ).toBeVisible()
  })

  test("deletes an unused compound with its reference data", async ({
    page,
  }) => {
    const compound = await createCompound()
    await api("POST", `/compounds/${compound.id}/aliases`, {
      alias: `x${randomId()}`,
    })
    await page.goto(`/compounds/${compound.id}`)
    await page.getByRole("button", { name: "Actions" }).click()
    await page.getByRole("menuitem", { name: "Delete" }).click()
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Delete" })
      .click()
    await page.waitForURL("/compounds")
    await expect(page.getByText("Compound deleted")).toBeVisible()
  })
})

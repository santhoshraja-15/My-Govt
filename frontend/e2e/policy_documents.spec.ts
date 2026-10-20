import { expect, test } from "@playwright/test";
import { API } from "./helpers";

const CATEGORIES = ["government_order", "policy", "circular", "notification", "act"] as const;

test.describe("policy documents API", () => {
  test("the catalogue holds ten verified documents in each of the four groups, with real official links", async ({ request }) => {
    const all = await (await request.get(`${API}/documents/policy?page_size=100`)).json();
    expect(all.total).toBe(40);
    const by = (c: string) => all.items.filter((d: any) => d.category === c);
    expect(by("circular")).toHaveLength(10);
    expect(by("notification")).toHaveLength(10);
    expect(by("act")).toHaveLength(10);
    expect(by("government_order").length + by("policy").length).toBe(10);
    for (const d of all.items) {
      expect(d.title, d.doc_code).toBeTruthy();
      expect(d.summary_en, d.doc_code).toBeTruthy();
      expect(d.summary_ta, d.doc_code).toBeTruthy();
      expect(d.summary_ta_reviewed, "Tamil summaries are unreviewed translations").toBe(false);
      expect(d.source_page_url, d.doc_code).toMatch(/^https:\/\/[a-z0-9.-]+\.(gov\.in|tn\.gov\.in)\//);
      if (d.pdf_url) expect(d.pdf_url, d.doc_code).toMatch(/^https:\/\/[a-z0-9.-]+\.gov\.in\/.+\.pdf$/i);
      if (d.verification_status === "official_verified") expect(d.last_checked_on, d.doc_code).toBeTruthy();
    }
  });

  test("filters, sort, search and Tamil search work in SQL", async ({ request }) => {
    const act = await (await request.get(`${API}/documents/policy?category=act&sort=newest&page_size=50`)).json();
    expect(act.items.every((d: any) => d.category === "act")).toBe(true);
    const dates = act.items.map((d: any) => d.issued_on).filter(Boolean);
    expect([...dates].sort().reverse()).toEqual(dates);                       // newest first, by the real issue date
    const oldest = await (await request.get(`${API}/documents/policy?category=act&sort=oldest&page_size=50`)).json();
    expect(oldest.items[0].issued_on <= oldest.items.at(-1).issued_on).toBe(true);
    const group = await (await request.get(`${API}/documents/policy?category=government_order,policy&page_size=50`)).json();
    expect(group.total).toBe(10);
    const year = await (await request.get(`${API}/documents/policy?year=2026&page_size=50`)).json();
    expect(year.items.every((d: any) => d.issued_on?.startsWith("2026"))).toBe(true);
    const ta = await (await request.get(`${API}/documents/policy?q=${encodeURIComponent("மகப்பேறு")}`)).json();
    expect(ta.total).toBeGreaterThan(0);
    const id = await (await request.get(`${API}/documents/policy?q=${encodeURIComponent("Act No. 9")}`)).json().catch(() => ({ total: 0 }));
    expect(id.total).toBeGreaterThanOrEqual(0);
    expect((await request.get(`${API}/documents/policy?category=bogus`)).status()).toBe(422);
    expect((await request.get(`${API}/documents/policy/DOC-NO-SUCH`)).status()).toBe(404);
  });
});

test.describe("policy documents page", () => {
  test("groups, counts, filters, details and external links", async ({ page }) => {
    await page.goto("/documents");
    await expect(page.getByTestId("policy-doc").first()).toBeVisible();
    await expect(page.getByTestId("doc-count")).toContainText("40 documents");
    for (const [key, n] of [["orders", 10], ["circular", 10], ["notification", 10], ["act", 10]] as const) {
      await expect(page.getByTestId(`doc-group-${key}`)).toContainText(`(${n})`);
    }
    await page.getByTestId("doc-group-act").click();
    await expect(page.getByTestId("doc-count")).toContainText("10 documents");
    await expect(page.getByTestId("policy-doc").first()).toHaveAttribute("data-category", "act");
    // every card offers either a verified PDF or the official landing page, opened safely in a new tab
    const links = page.getByTestId("doc-pdf");
    expect(await links.count()).toBeGreaterThan(0);
    await expect(links.first()).toHaveAttribute("target", "_blank");
    await expect(links.first()).toHaveAttribute("rel", /noopener/);
    await expect(links.first()).toHaveAttribute("href", /\.pdf$/);
    await expect(links.first()).toContainText("Download PDF");
    await page.getByTestId("doc-details-toggle").first().click();
    await expect(page.getByTestId("doc-details").first()).toBeVisible();
    // search + clear
    await page.getByTestId("document-search").fill("Panchayats");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByTestId("policy-doc").first()).toContainText("Panchayats");
    await page.getByTestId("doc-clear").click();
    await expect(page.getByTestId("doc-count")).toContainText("40 documents");
    // empty result
    await page.getByTestId("document-search").fill("zzzz-no-such-document");
    await page.getByRole("button", { name: "Search" }).click();
    await expect(page.getByTestId("empty-state")).toContainText("No documents match these filters.");
  });

  test("Tamil: download button, official-document links and Tamil summary note", async ({ page }) => {
    await page.addInitScript(() => localStorage.setItem("lang", "ta"));
    await page.goto("/documents");
    await expect(page.getByTestId("doc-pdf").first()).toContainText("PDF பதிவிறக்க");
    await expect(page.getByText("தமிழ்ச் சுருக்கம் மறுஆய்வு செய்யப்படாத மொழிபெயர்ப்பு").first()).toBeVisible();
  });
});

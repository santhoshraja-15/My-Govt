import { expect, test } from "@playwright/test";
import { API, apiCitizen, bearer, registerViaUI, alertBox } from "./helpers";

async function openFileTab(page: import("@playwright/test").Page) {
  await page.goto("/complaints");
  await page.getByRole("tab", { name: "File Complaint" }).click();
}

test.describe("complaint lifecycle (citizen)", () => {
  test("file a categorised complaint, see routing + SLA, then track it", async ({ page }) => {
    await registerViaUI(page, "Complainant One");
    await openFileTab(page);
    await page.getByLabel("Category").selectOption({ label: "Water Supply Disruption" });
    await page.getByLabel(/Subject/).fill("No water supply for three days");
    await page.getByLabel(/Description/).fill("The street tap has had no water since Monday morning.");
    await page.getByRole("button", { name: "Submit Complaint" }).click();

    await expect(page.getByTestId("submit-success")).toBeVisible();
    const ref = (await page.getByTestId("new-reference").innerText()).trim();
    expect(ref).toMatch(/^MYG-\d{4}-\d{6}$/);
    // honest routing: a department-level target, not a named office
    await expect(page.getByTestId("assignment-text")).toContainText("department level");
    await expect(page.getByTestId("assignment-text")).toContainText("has not been assigned yet");

    await page.getByRole("tab", { name: "Track Status" }).click();
    await page.getByLabel("Reference number").fill(ref);
    await page.getByRole("button", { name: "Track" }).click();
    await expect(page.getByTestId("reference")).toHaveText(ref);
    await expect(page.getByTestId("status-badge").first()).toHaveAttribute("data-status", "classified");
    await expect(page.getByTestId("sla")).toContainText("platform target");
    await expect(page.getByTestId("assignment")).toContainText("department level");
  });

  test("an uncategorised complaint is reported as awaiting triage, not silently routed", async ({ page }) => {
    await registerViaUI(page, "Complainant Two");
    await openFileTab(page);
    await page.getByLabel(/Subject/).fill("Something unusual happened");
    await page.getByLabel(/Description/).fill("I am not sure which department handles this issue.");
    await page.getByRole("button", { name: "Submit Complaint" }).click();
    await expect(page.getByTestId("assignment-text")).toContainText("awaiting triage");
  });

  test("my complaints lists only my own", async ({ page }) => {
    await registerViaUI(page, "Complainant Three");
    await openFileTab(page);
    await page.getByLabel(/Subject/).fill("Mine only complaint");
    await page.getByLabel(/Description/).fill("This one belongs to the signed-in citizen only.");
    await page.getByRole("button", { name: "Submit Complaint" }).click();
    await expect(page.getByTestId("submit-success")).toBeVisible();
    await page.getByRole("tab", { name: "My complaints" }).click();
    await expect(page.getByTestId("my-complaints").getByText("Mine only complaint")).toBeVisible();
    await expect(page.getByTestId("my-complaints").locator("li")).toHaveCount(1);
  });

  test("client-side validation, location consent and anonymous tracking", async ({ page }) => {
    await registerViaUI(page, "Complainant Four");
    await openFileTab(page);
    await page.getByRole("button", { name: "Submit Complaint" }).click();
    await expect(alertBox(page)).toContainText("Subject must be at least 3 characters");

    await page.getByLabel(/Subject/).fill("Streetlight broken");
    await page.getByLabel(/Description/).fill("The streetlight near the park has not worked for a week.");
    await page.getByLabel("Latitude").fill("13.08");
    await page.getByRole("button", { name: "Submit Complaint" }).click();
    await expect(alertBox(page)).toContainText("both latitude and longitude");

    await page.getByLabel("Longitude").fill("80.27");
    await page.getByRole("button", { name: "Submit Complaint" }).click();
    await expect(alertBox(page)).toContainText("agree to share your location");

    await page.getByLabel(/I agree to share this location/).check();
    await page.getByLabel(/Hide my identity/).check();
    await page.getByRole("button", { name: "Submit Complaint" }).click();
    await expect(page.getByTestId("submit-success")).toBeVisible();
    const ref = (await page.getByTestId("new-reference").innerText()).trim();

    await page.getByRole("tab", { name: "Track Status" }).click();
    await page.getByLabel("Reference number").fill(ref);
    await page.getByRole("button", { name: "Track" }).click();
    await expect(alertBox(page)).toContainText("No complaint found");     // anonymous: not publicly trackable
  });

  test("unknown reference gives a clear message", async ({ page }) => {
    await page.goto("/complaints");
    await page.getByRole("tab", { name: "Track Status" }).click();
    await page.getByLabel("Reference number").fill("MYG-0000-000000");
    await page.getByRole("button", { name: "Track" }).click();
    await expect(alertBox(page)).toContainText("No complaint found");
  });

  test("submission failure from the server is shown, not swallowed", async ({ page }) => {
    await registerViaUI(page, "Complainant Five");
    await openFileTab(page);
    await page.route("**/api/v1/complaints", (r) => r.request().method() === "POST"
      ? r.fulfill({ status: 500, contentType: "application/json", body: '{"code":"INTERNAL_ERROR","message":"An internal error occurred."}' })
      : r.continue());
    await page.getByLabel(/Subject/).fill("Will fail on the server");
    await page.getByLabel(/Description/).fill("This submission is forced to fail for the test.");
    await page.getByRole("button", { name: "Submit Complaint" }).click();
    await expect(alertBox(page)).toBeVisible();
    await expect(page.getByTestId("submit-success")).toHaveCount(0);
  });

  test("another citizen cannot read my complaint through the API", async ({ page, request }) => {
    await registerViaUI(page, "Complainant Six");
    await openFileTab(page);
    await page.getByLabel(/Subject/).fill("Private complaint");
    await page.getByLabel(/Description/).fill("Only the owner and staff may open this complaint.");
    await page.getByRole("button", { name: "Submit Complaint" }).click();
    await expect(page.getByTestId("submit-success")).toBeVisible();
    const token = await page.evaluate(() => localStorage.getItem("access_token"));
    const mine = await (await request.get(`${API}/complaints/mine`, { headers: bearer(token!) })).json();
    const id = mine.items[0].complaint_id;
    const other = await apiCitizen(request);
    expect((await request.get(`${API}/complaints/${id}`, { headers: bearer(other.token) })).status()).toBe(403);
    expect((await request.get(`${API}/complaints/${id}`, { headers: bearer(token!) })).status()).toBe(200);
  });
});

test.describe("AI citizen assistant", () => {
  test("answers cite their sources and flag unverified records", async ({ page }) => {
    await page.goto("/assistant");
    await page.getByLabel("Ask a question").fill("Tell me about the breakfast scheme for school children");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.getByTestId("assistant-answer")).toContainText("NOT been confirmed");
    await expect(page.getByTestId("unverified-notice")).toBeVisible();
    await expect(page.getByText("Sources", { exact: true })).toBeVisible();
    await expect(page.getByText(/Breakfast Scheme/).first()).toBeVisible();
    await expect(page.getByText(/provisional/i).first()).toBeVisible();
  });

  test("cites an ingested document passage with its page and labels it unverified", async ({ page }) => {
    await page.goto("/assistant");
    await page.getByLabel("Ask a question").fill("What does the Zorblax scholarship notice describe?");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.getByText(/\[E2E TEST FIXTURE\] Zorblax scholarship notice · p\.2/)).toBeVisible();
    await expect(page.getByTestId("unverified-notice")).toBeVisible();
    await expect(page.getByTestId("assistant-answer")).toContainText("fictional monthly grant");
    await expect(page.getByTestId("assistant-answer")).not.toContainText("You are eligible");
  });

  test("abstains instead of inventing an answer when nothing matches", async ({ page }) => {
    await page.goto("/assistant");
    await page.getByLabel("Ask a question").fill("zzqqxx vvwwyy");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.getByTestId("assistant-answer")).toContainText("couldn't find verified information");
    await expect(page.getByTestId("unverified-notice")).toHaveCount(0);
  });

  test("a server failure is reported to the user", async ({ page }) => {
    await page.route("**/api/v1/chat/message", (r) => r.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
    await page.goto("/assistant");
    await page.getByLabel("Ask a question").fill("pension scheme");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.getByText(/trouble connecting/i)).toBeVisible();
  });
});

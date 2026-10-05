/**
 * D7 QA（独立 QA 资产）—— GZ-PAY-106 admin 支付流水「只看迟到付款」筛选 + 标红提示。
 *
 * 数据来源：QA 已在真后端造好 timeout 单并推过成功回调（gz_pay_callback_log.process_status='late_paid'），
 * 本 spec 不造数据，只断言：
 *   1. 勾选「只看迟到付款」→ 发出 latePaid=true 的真请求，响应行数 == 库里 late_paid 的去重单数（反空转）；
 *   2. 页面行数 / 单号与后端响应逐条一致，每行带「迟到付款」tag，顶部红色提示出现；
 *   3. 取消勾选 → 列表回到全量，未迟到的单不带 tag。
 * 用 gz_owner（非超管）跑一遍，验权限面。
 */
import { expect, test, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';

const BACKEND = process.env.ADMIN_E2E_BACKEND || 'http://127.0.0.1:8080';
const CLIENT_ID = 'e5cd7e4891bf95d1d19206ce24a7b32e';
const ROUTE = '/gz-order-recon/transaction';

function sql(q: string): string {
  return execFileSync('docker', ['exec', '-i', 'sensenran-dev-mysql', 'mysql', '-uroot', '-proot', 'ry-vue', '-N', '-e', q], {
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe']
  }).trim();
}

async function token(user: string, pass: string): Promise<string> {
  for (const k of ['HTTP_PROXY', 'http_proxy', 'HTTPS_PROXY', 'https_proxy', 'ALL_PROXY', 'all_proxy']) delete process.env[k];
  process.env.NO_PROXY = '*';
  const res = await fetch(`${BACKEND}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', clientid: CLIENT_ID },
    body: JSON.stringify({ clientId: CLIENT_ID, grantType: 'password', tenantId: '1001', username: user, password: pass })
  });
  const json = (await res.json()) as { data?: { access_token?: string } };
  if (!json?.data?.access_token) throw new Error(`login ${user} failed: ${JSON.stringify(json).slice(0, 200)}`);
  return json.data.access_token;
}

async function open(page: Page, tk: string) {
  await page.goto('/index', { waitUntil: 'domcontentloaded' });
  await page.evaluate((t) => localStorage.setItem('Admin-Token', t), tk);
  await page.goto('/index', { waitUntil: 'domcontentloaded' });
  await expect(page).not.toHaveURL(/login/, { timeout: 30_000 });
  await page.waitForTimeout(2500);
  await page.goto(ROUTE, { waitUntil: 'domcontentloaded' });
  await expect(page.getByText('只看迟到付款')).toBeVisible({ timeout: 30_000 });
}

for (const [user, pass] of [
  ['admin', 'admin123'],
  ['gz_owner', 'gz_owner123!']
] as const) {
  test(`迟到付款筛选（${user}）：数据来自后端 + 标红`, async ({ page }) => {
    const dbLate = Number(sql("SELECT COUNT(DISTINCT out_trade_no) FROM gz_pay_callback_log WHERE process_status='late_paid' AND del_flag='0'"));
    expect(dbLate).toBeGreaterThan(0);
    await open(page, await token(user, pass));

    const respPromise = page.waitForResponse((r) => r.url().includes('/system/gz/pay/transaction/list') && r.url().includes('latePaid=true'));
    await page.getByText('只看迟到付款').click();
    const resp = await respPromise;
    const body = (await resp.json()) as { code: number; total: number; rows: Array<{ outTradeNo: string; latePaid: boolean }> };
    console.log(`[QA-E2E] ${user} latePaid=true → code=${body.code} total=${body.total} dbLate=${dbLate} first=${body.rows[0]?.outTradeNo}`);
    expect(body.code).toBe(200);
    expect(body.total).toBe(dbLate);
    expect(body.rows.every((r) => r.latePaid === true)).toBe(true);

    const rows = page.locator('.el-table__body-wrapper tbody tr');
    await expect(rows).toHaveCount(Math.min(body.rows.length, body.total));
    // 首行单号与后端响应首行一致（页面渲染的就是后端那批数据）
    await expect(rows.first()).toContainText(body.rows[0].outTradeNo);
    await expect(page.locator('.el-table__body-wrapper tbody tr.late-paid-row')).toHaveCount(body.rows.length);
    await expect(rows.first().getByText('迟到付款', { exact: true })).toBeVisible();
    await expect(page.getByText('迟到付款：微信已扣款，但本地支付单已超时或关闭，业务未生效').first()).toBeVisible();

    // 取消勾选 → 全量（总数 > 迟到数）且含非迟到行（无 tag）
    const allPromise = page.waitForResponse((r) => r.url().includes('/system/gz/pay/transaction/list') && !r.url().includes('latePaid=true'));
    await page.getByText('只看迟到付款').click();
    const all = (await (await allPromise).json()) as { total: number; rows: Array<{ outTradeNo: string; latePaid: boolean }> };
    console.log(`[QA-E2E] ${user} unfiltered total=${all.total} latePaidOnPage=${all.rows.filter((r) => r.latePaid).length}/${all.rows.length}`);
    expect(all.total).toBeGreaterThan(body.total);
    const plainIdx = all.rows.findIndex((r) => !r.latePaid);
    expect(plainIdx).toBeGreaterThanOrEqual(0);
    const plainRow = rows.nth(plainIdx);
    await expect(plainRow).toContainText(all.rows[plainIdx].outTradeNo);
    await expect(plainRow).not.toHaveClass(/late-paid-row/);
  });
}

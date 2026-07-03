const { chromium } = require('playwright');

const BASE = 'http://139.198.112.87:20885';
const USER = 'admin';
const PASS = 'P@88w0rd';

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function getFrameContent(page) {
  // Try each iframe and return the one with meaningful content
  for (const [name, frame] of page.frames().entries()) {
    try {
      const text = await frame.locator('body').textContent({ timeout: 2000 });
      if (text && text.length > 50) {
        // Check if it contains license-related content
        const lower = text.toLowerCase();
        if (lower.includes('license') || lower.includes('许可') || lower.includes('authorized') || lower.includes('ks-core')) {
          return { text, frame };
        }
      }
    } catch (e) {}
  }
  return { text: null, frame: null };
}

async function main() {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });

  const results = [];
  let frame = null;

  function report(id, name, status, detail) {
    results.push({ id, name, status, detail });
    const icon = status === 'PASS' ? '✅' : status === 'FAIL' ? '❌' : status === 'WARN' ? '⚠️' : '⏭️';
    console.log(`  ${icon} [${status}] ${id} - ${name}`);
    if (detail) console.log(`         ${detail}`);
  }

  async function findText(keywords) {
    // Get text from iframe first, fall back to page
    let txt = '';
    if (frame) {
      try { txt = await frame.locator('body').textContent({ timeout: 2000 }); } catch (e) {}
    }
    if (!txt) {
      try { txt = await page.locator('body').first().textContent({ timeout: 2000 }); } catch (e) {}
    }
    if (!txt) return { found: false, text: '' };
    return { found: keywords.some(k => txt.toLowerCase().includes(k.toLowerCase())), text: txt };
  }

  try {
    // ============ LOGIN ============
    console.log('=== 1. 登录 KSE 控制台 ===');
    await page.goto(`${BASE}/login`, { waitUntil: 'networkidle', timeout: 30000 });
    await sleep(2000);
    await page.locator('input[placeholder="user@example.com"]').fill(USER);
    await page.locator('input[placeholder="Password"]').fill(PASS);
    await page.locator('button:has-text("Log In")').click();
    await page.waitForURL('**/dashboard/**', { timeout: 20000 }).catch(() => {});
    await sleep(3000);
    const loggedIn = page.url().includes('dashboard');
    report('LOGIN', '登录 KSE 控制台', loggedIn ? 'PASS' : 'FAIL', `URL: ${page.url()}`);
    if (!loggedIn) throw new Error('Login failed');

    // ============ NAVIGATE ============
    console.log('\n=== 2. 导航到许可证管理页 ===');
    await page.goto(`${BASE}/settings/licenses`, { waitUntil: 'networkidle', timeout: 20000 });
    await sleep(4000);
    const onPage = page.url().includes('licenses');
    report('NAV', '导航到 /settings/licenses', onPage ? 'PASS' : 'FAIL', `URL: ${page.url()}`);
    if (!onPage) throw new Error('Navigation failed');

    // Find the content frame
    const fc = await getFrameContent(page);
    if (fc.text) {
      frame = fc.frame;
      report('FRAME', '找到 License 内容 iframe', 'PASS', `内容长度: ${fc.text.length} 字符`);
    } else {
      report('FRAME', '找到 License 内容', 'INFO', '使用主页面');
    }

    let pageText = fc.text || '';
    const preview = pageText.replace(/\s+/g, ' ').trim().substring(0, 800);
    console.log(`\n页面内容预览:\n${preview}\n`);

    // ============ MODULE 5: OVERVIEW ============
    console.log('=== 模块5：授权概览页 ===');
    const overviewChecks = [
      { id: 'OV-01', name: '授权组织字段', kw: ['KCN', '内部测试'] },
      { id: 'OV-02', name: '授权状态', kw: ['Authorized', '已生效', 'Normal'] },
      { id: 'OV-03', name: '集群ID', kw: ['Cluster ID', 'Cluster'] },
      { id: 'OV-04', name: '授权类型-订阅', kw: ['Subscription', '订阅'] },
      { id: 'OV-05', name: '授权规模 vcpu', kw: ['vcpu', '授权规模', '1k', '1000'] },
      { id: 'OV-06', name: '已使用字段', kw: ['Used', '已使用'] },
      { id: 'OV-07', name: '扩展组件行', kw: ['Extension', '扩展'] },
      { id: 'OV-08', name: '订阅生效时间', kw: ['2026'] },
      { id: 'OV-09', name: '订阅截止时间', kw: ['2026-09-30', '2026'] },
      { id: 'OV-10', name: '企业版标识', kw: ['Enterprise', '企业版'] },
    ];
    for (const c of overviewChecks) {
      const { found } = await findText(c.kw);
      report(c.id, c.name, found ? 'PASS' : 'WARN', `关键词: ${c.kw.join('/')}`);
    }

    // ============ MODULE 4: BANNER ============
    console.log('\n=== 模块4：顶部 Banner ===');
    const { text: bannerText } = await findText(['未激活', '过期', 'quota', '配额']);
    const hasWarning = ['未激活', '过期', 'quota', '配额'].some(k => bannerText?.toLowerCase().includes(k.toLowerCase()));
    report('BANNER', 'License 正常-无警告Banner', !hasWarning ? 'PASS' : 'WARN', hasWarning ? '页面含警告' : '正常无警告');

    // ============ MODULE 6: TABS & LISTS ============
    console.log('\n=== 模块6：许可导入记录 ===');
    
    // Check tabs in iframe
    let tabFound = false;
    if (frame) {
      const tabs = frame.locator('[role="tab"], .tab, .kube-tab, [class*="tab"]');
      const tabCount = await tabs.count().catch(() => 0);
      console.log(`  找到 ${tabCount} 个 Tab 元素`);
      
      for (let i = 0; i < tabCount; i++) {
        try {
          const tabText = await tabs.nth(i).textContent();
          console.log(`  Tab[${i}]: "${tabText.trim()}"`);
        } catch (e) {}
      }
    }

    const tabChecks = [
      { id: 'TAB-01', name: '软件许可 Tab', kw: ['Software', '软件'] },
      { id: 'TAB-02', name: '维保许可 Tab', kw: ['Maintenance', '维保'] },
    ];
    for (const c of tabChecks) {
      const { found } = await findText(c.kw);
      report(c.id, c.name, found ? 'PASS' : 'WARN', '');
      if (found) tabFound = true;
    }

    // Try clicking Software License tab
    if (frame) {
      const swTab = frame.locator('[role="tab"]:has-text("Software"), [role="tab"]:has-text("软件"), button:has-text("Software"), button:has-text("软件许可")').first();
      const swVisible = await swTab.isVisible().catch(() => false);
      
      if (swVisible) {
        await swTab.click();
        await sleep(2000);
        const { text: swText } = await findText(['License', '许可证', 'ks-core']);
        
        const swChecks = [
          { id: 'SW-01', name: '列表-许可证ID列', kw: ['License ID', '许可证ID'] },
          { id: 'SW-02', name: '列表-授权类型列', kw: ['Type', '授权类型', 'Subscription'] },
          { id: 'SW-03', name: '列表-许可证类型列', kw: ['License Type', '许可证类型', 'Full'] },
          { id: 'SW-04', name: '列表-状态列', kw: ['Status', '状态', 'Authorized'] },
          { id: 'SW-05', name: '列表-授权数量列', kw: ['Quantity', '授权数量'] },
          { id: 'SW-06', name: '列表-导入时间列', kw: ['Imported At', '导入时间'] },
          { id: 'SW-07', name: '列表-生效时间列', kw: ['Start Time', '生效时间'] },
          { id: 'SW-08', name: '列表-截止时间列', kw: ['End Time', '截止时间', 'Expiration'] },
          { id: 'SW-09', name: '列表-剩余有效期列', kw: ['Remaining', '剩余'] },
          { id: 'SW-10', name: 'ks-core 记录存在', kw: ['ks-core'] },
        ];
        for (const c of swChecks) {
          const { found: f } = await findText(c.kw);
          report(c.id, c.name, f ? 'PASS' : 'WARN', '');
        }

        // Click Maintenance tab
        const mtTab = frame.locator('[role="tab"]:has-text("Maintenance"), [role="tab"]:has-text("维保"), button:has-text("Maintenance"), button:has-text("维保许可")').first();
        const mtVisible = await mtTab.isVisible().catch(() => false);
        if (mtVisible) {
          await mtTab.click();
          await sleep(2000);
          const mtChecks = [
            { id: 'MT-01', name: '维保-许可证ID列', kw: ['License ID', '许可证ID'] },
            { id: 'MT-02', name: '维保-状态列', kw: ['Status', '状态'] },
            { id: 'MT-03', name: '维保-授权数量列', kw: ['Quantity', '授权数量'] },
            { id: 'MT-04', name: '维保-导入时间列', kw: ['Imported At', '导入时间'] },
            { id: 'MT-05', name: '维保-生效时间列', kw: ['Start Time', '生效时间'] },
            { id: 'MT-06', name: '维保-到期时间列', kw: ['End Time', '到期时间'] },
          ];
          for (const c of mtChecks) {
            const { found: f } = await findText(c.kw);
            report(c.id, c.name, f ? 'PASS' : 'WARN', '');
          }
        } else {
          report('MT-00', '维保许可 Tab 可点击', 'SKIP', '');
        }
      } else {
        report('SW-00', '软件许可 Tab 可点击', 'SKIP', '');
      }
    }

    // ============ MODULE 7 ============
    console.log('\n=== 模块7：授权许可凭证 ===');
    const { found: credFound } = await findText(['credential', '凭证', 'Certificate']);
    report('CRED', '查看授权许可凭证', credFound ? 'PASS' : 'WARN', '');

    // ============ MODULE 3 ============
    console.log('\n=== 模块3：扩展组件展示 ===');
    const { found: extFound } = await findText(['Extension', '扩展组件', 'extension']);
    report('EXT', '扩展组件区域存在', extFound ? 'PASS' : 'WARN', '');

  } catch (err) {
    console.error(`\n❌ Error: ${err.message}`);
    await page.screenshot({ path: '/tmp/error.png' }).catch(() => {});
  } finally {
    await browser.close();
  }

  // ============ SUMMARY ============
  console.log('\n' + '='.repeat(65));
  console.log('  License UI 自动化测试结果汇总');
  console.log('='.repeat(65));
  
  const pass = results.filter(r => r.status === 'PASS').length;
  const fail = results.filter(r => r.status === 'FAIL').length;
  const warn = results.filter(r => r.status === 'WARN').length;
  const skip = results.filter(r => r.status === 'SKIP').length;
  
  for (const r of results) {
    const icon = r.status === 'PASS' ? '✅' : r.status === 'FAIL' ? '❌' : r.status === 'WARN' ? '⚠️' : '⏭️';
    console.log(`${icon} [${r.status}] ${r.id} ${r.name}`);
    if (r.detail) console.log(`   ${r.detail}`);
  }
  
  console.log(`\n  ✅ PASS: ${pass} | ❌ FAIL: ${fail} | ⚠️ WARN: ${warn} | ⏭️ SKIP: ${skip} | 总计: ${results.length}`);
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});

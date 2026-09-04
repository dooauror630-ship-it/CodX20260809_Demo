import { expect, test, type Locator } from "@playwright/test";


test("ordinary user sees only the personal workspace and can log back in", async ({ page }, testInfo) => {
  const suffix = testInfo.project.name.includes("mobile") ? "mobile" : "desktop";
  const username = `e2e_${suffix[0]}_${Date.now().toString(36).slice(-8)}`;
  const password = "StageOne123";
  const displayName = suffix === "mobile" ? "移动验收" : "桌面验收";

  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "欢迎回来" })).toBeVisible();

  await page.getByRole("tab", { name: "注册" }).click();
  await page.getByPlaceholder("请输入姓名").fill(displayName);
  await page.getByPlaceholder("4-20 位字符").fill(username);
  await page.getByPlaceholder("至少 8 位，含字母和数字").fill(password);
  await page.getByPlaceholder("请再次输入密码").fill(password);
  await page.getByRole("button", { name: "创建账户" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: `${displayName}，欢迎回来` })).toBeVisible();
  await expect(page.locator(".user-identity-badge")).toHaveText("普通用户");
  await expect(page.getByText("生产经营工作台已就绪。")).toBeVisible();
  await expect(page.getByRole("link", { name: "用户管理" })).toHaveCount(0);
  await expect(page.getByRole("img", { name: "最近六个月账户创建数量柱状图" })).toHaveCount(0);
  await expect(
    page.getByRole("article").filter({ hasText: "账户状态" }).getByText("正常", { exact: true }),
  ).toBeVisible();
  if (suffix === "desktop") await expect(page.getByText("MySQL 已连接")).toBeVisible();

  await page.screenshot({ path: testInfo.outputPath(`dashboard-${suffix}.png`), fullPage: true });

  await page.getByRole("button", { name: `${displayName}普通用户账户菜单` }).click();
  await page.getByRole("menuitem", { name: "退出登录" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByPlaceholder("请输入账号").fill(username);
  await page.getByPlaceholder("请输入密码").fill(password);
  await page.getByRole("button", { name: "登录系统" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("cell", { name: username, exact: true })).toBeVisible();
});


test("administrator can manage users", async ({ page }, testInfo) => {
  const isMobile = testInfo.project.name.includes("mobile");
  const username = `e2e_a_${Date.now().toString(36).slice(-8)}`;
  const password = "StageOne123";

  await page.goto("/login");
  if (!isMobile) {
    await page.getByRole("tab", { name: "注册" }).click();
    await page.getByPlaceholder("请输入姓名").fill("后台验收用户");
    await page.getByPlaceholder("4-20 位字符").fill(username);
    await page.getByPlaceholder("至少 8 位，含字母和数字").fill(password);
    await page.getByPlaceholder("请再次输入密码").fill(password);
    await page.getByRole("button", { name: "创建账户" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);

    await page.getByRole("button", { name: "后台验收用户普通用户账户菜单" }).click();
    await page.getByRole("menuitem", { name: "退出登录" }).click();
  }
  await page.getByPlaceholder("请输入账号").fill("admin");
  await page.getByPlaceholder("请输入密码").fill("123456");
  await page.getByRole("button", { name: "登录系统" }).click();

  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.locator(".user-identity-badge")).toHaveText("管理员");
  await expect(page.getByRole("img", { name: "最近六个月账户创建数量柱状图" })).toBeVisible();
  if (isMobile) await page.getByRole("button", { name: "打开导航" }).click();
  await page.getByRole("link", { name: "用户管理" }).click();
  await expect(page).toHaveURL(/\/admin\/users$/);
  await expect(page.getByRole("heading", { name: "用户管理" })).toBeVisible();

  if (isMobile) {
    const hasHorizontalOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasHorizontalOverflow).toBe(false);
    await page.screenshot({ path: testInfo.outputPath("admin-users-mobile.png"), fullPage: true });
    return;
  }

  await page.getByPlaceholder("搜索账号或姓名").fill(username);
  await page.getByRole("button", { name: "查询" }).click();
  let userRow = page.getByRole("row", { name: new RegExp(username) });
  await expect(userRow).toBeVisible();
  await userRow.getByRole("button", { name: "编辑" }).click();

  const editDialog = page.getByRole("dialog", { name: "编辑用户" });
  await editDialog.getByLabel("姓名").fill("已更新用户");
  await editDialog.getByRole("button", { name: "保存修改" }).click();
  await expect(editDialog).toBeHidden();

  userRow = page.getByRole("row", { name: new RegExp(username) });
  await expect(userRow.getByText("已更新用户")).toBeVisible();
  await userRow.getByRole("button", { name: "重置密码" }).click();
  const passwordDialog = page.getByRole("dialog", { name: "重置密码" });
  await passwordDialog.getByPlaceholder("至少 8 位，含字母和数字").fill("ResetPass123");
  await passwordDialog.getByPlaceholder("请再次输入新密码").fill("ResetPass123");
  await passwordDialog.getByRole("button", { name: "确认重置" }).click();
  await expect(passwordDialog).toBeHidden();

  await expect(page.locator(".el-message")).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath("admin-users.png"), fullPage: true });
});


test("farm roles collaborate through inventory and pig head-count operations", async ({ page }, testInfo) => {
  test.setTimeout(270_000);
  const browserErrors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().startsWith("Failed to load resource:")) {
      browserErrors.push(message.text());
    }
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400 && response.status() !== 401) {
      browserErrors.push(`${response.status()} ${response.url()}`);
    }
  });
  const isMobile = testInfo.project.name.includes("mobile");
  const suffix = `${isMobile ? "m" : "d"}_${Date.now().toString(36).slice(-7)}`;
  const managerUsername = `mgr_${suffix}`;
  const operatorUsername = `op_${suffix}`;
  const viewerUsername = `view_${suffix}`;
  const managerName = "农场负责人";
  const operatorName = "采购操作员";
  const viewerName = "库存查看员";
  const farmCode = `E2E-${suffix}`.toUpperCase();
  const farmName = `验收农场${suffix}`;
  const barnCode = `BARN-${suffix}`.toUpperCase();
  const secondaryBarnCode = `BARN2-${suffix}`.toUpperCase();
  const barnName = "育肥验收一舍";
  const secondaryBarnName = "育肥验收二舍";
  const plotCode = `PLOT-${suffix}`.toUpperCase();
  const warehouseCode = `WH-${suffix}`.toUpperCase();
  const secondaryWarehouseCode = `WH2-${suffix}`.toUpperCase();
  const warehouseName = "生产物资主仓";
  const secondaryWarehouseName = "生产物资分仓";
  const categoryCode = `CAT-${suffix}`.toUpperCase();
  const itemCode = `ITEM-${suffix}`.toUpperCase();
  const supplierCode = `SUP-${suffix}`.toUpperCase();
  const supplierName = `验收供应商${suffix}`;
  const purchaseNo = `PO-${suffix}`.toUpperCase();
  const transferNo = `TR-${suffix}`.toUpperCase();
  const productionIssueNo = `PI-${suffix}`.toUpperCase();
  const productionReturnNo = `PR-${suffix}`.toUpperCase();
  const purchaseReturnNo = `RT-${suffix}`.toUpperCase();
  const inventoryCountNo = `IC-${suffix}`.toUpperCase();
  const pigBatchNo = `PIG-${suffix}`.toUpperCase();
  const pigEntryNo = `EN-${suffix}`.toUpperCase();
  const pigTransferNo = `LTF-${suffix}`.toUpperCase();
  const pigDeathNo = `LDT-${suffix}`.toUpperCase();
  const pigCullNo = `LCL-${suffix}`.toUpperCase();
  const pigExitNo = `LEX-${suffix}`.toUpperCase();
  const pigBatchName = `育肥验收批次${suffix}`;
  const lotNo = `LOT-${suffix}`.toUpperCase();
  const password = "StageTwo123";
  const now = new Date();
  const businessDate = [now.getFullYear(), now.getMonth() + 1, now.getDate()]
    .map((value, index) => String(value).padStart(index === 0 ? 4 : 2, "0"))
    .join("-");
  const expiry = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 15);
  const expiryDate = [expiry.getFullYear(), expiry.getMonth() + 1, expiry.getDate()]
    .map((value, index) => String(value).padStart(index === 0 ? 4 : 2, "0"))
    .join("-");

  async function openNavigationLink(name: string) {
    if (isMobile) await page.getByRole("button", { name: "打开导航" }).click();
    await page.getByRole("link", { name }).click();
  }

  async function openLabeledSelect(container: Locator, name: string) {
    await container
      .getByLabel(name)
      .locator("xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' el-select ')][1]")
      .click();
  }

  async function logout(displayName: string, identity: string) {
    await page.getByRole("button", { name: `${displayName}${identity}账户菜单` }).click();
    await page.getByRole("menuitem", { name: "退出登录" }).click();
    await expect(page).toHaveURL(/\/login$/);
  }

  async function login(username: string) {
    await page.getByPlaceholder("请输入账号").fill(username);
    await page.getByPlaceholder("请输入密码").fill(password);
    await page.getByRole("button", { name: "登录系统" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  }

  async function registerUser(username: string, displayName: string) {
    await page.getByRole("tab", { name: "注册" }).click();
    await page.getByPlaceholder("请输入姓名").fill(displayName);
    await page.getByPlaceholder("4-20 位字符").fill(username);
    await page.getByPlaceholder("至少 8 位，含字母和数字").fill(password);
    await page.getByPlaceholder("请再次输入密码").fill(password);
    await page.getByRole("button", { name: "创建账户" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await logout(displayName, "普通用户");
  }

  function pigBatchRow() {
    return page.getByRole("row", { name: new RegExp(pigBatchNo) }).filter({
      has: page.getByRole("button", { name: "查看批次", exact: true }),
    });
  }

  await page.goto("/login");
  await registerUser(managerUsername, managerName);
  await registerUser(operatorUsername, operatorName);
  await registerUser(viewerUsername, viewerName);

  await page.getByPlaceholder("请输入账号").fill("admin");
  await page.getByPlaceholder("请输入密码").fill("123456");
  await page.getByRole("button", { name: "登录系统" }).click();
  await openNavigationLink("农场档案");
  await expect(page).toHaveURL(/\/base\/farms$/);

  await page.getByRole("button", { name: "新建农场" }).click();
  const farmDialog = page.getByRole("dialog", { name: "新建农场" });
  await farmDialog.getByLabel("农场编号").fill(farmCode);
  await farmDialog.getByLabel("农场名称").fill(farmName);
  await farmDialog.getByLabel("负责人").fill("验收负责人");
  await farmDialog.getByLabel("农场地址").fill("云南省验收示范村");
  await farmDialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(farmDialog).toBeHidden();

  await page.getByPlaceholder("搜索农场编号、名称或负责人").fill(farmCode);
  await page.getByRole("button", { name: "查询" }).click();
  const farmRow = page.getByRole("row", { name: new RegExp(farmCode) });
  await expect(farmRow).toBeVisible();
  await farmRow.getByRole("button", { name: "成员管理" }).click();

  const memberDialog = page.getByRole("dialog", { name: new RegExp("成员管理") });
  async function addMember(username: string, roleName: string) {
    await memberDialog.getByLabel("选择系统用户").click();
    await page.getByRole("option", { name: new RegExp(username) }).click();
    await memberDialog.getByLabel("选择农场角色").press("ArrowDown");
    await page.getByRole("option", { name: roleName, exact: true }).click();
    await memberDialog.getByRole("button", { name: "添加成员" }).click();
    await expect(memberDialog.getByRole("row", { name: new RegExp(username) })).toBeVisible();
  }
  await addMember(managerUsername, "农场负责人");
  await addMember(operatorUsername, "生产操作员");
  await addMember(viewerUsername, "只读人员");
  await page.keyboard.press("Escape");
  await expect(memberDialog).toBeHidden();

  await openNavigationLink("圈舍管理");
  await page.getByRole("button", { name: "新建圈舍" }).click();
  const barnDialog = page.getByRole("dialog", { name: "新建圈舍" });
  await barnDialog.getByLabel("圈舍编号").fill(barnCode);
  await barnDialog.getByLabel("圈舍名称").fill(barnName);
  await barnDialog.getByLabel("设计容量").fill("180");
  await barnDialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(barnDialog).toBeHidden();
  await expect(page.getByRole("row", { name: new RegExp(barnCode) })).toBeVisible();
  await page.getByRole("button", { name: "新建圈舍" }).click();
  const secondaryBarnDialog = page.getByRole("dialog", { name: "新建圈舍" });
  await secondaryBarnDialog.getByLabel("圈舍编号").fill(secondaryBarnCode);
  await secondaryBarnDialog.getByLabel("圈舍名称").fill(secondaryBarnName);
  await secondaryBarnDialog.getByLabel("设计容量").fill("120");
  await secondaryBarnDialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(secondaryBarnDialog).toBeHidden();
  await expect(page.getByRole("row", { name: new RegExp(secondaryBarnCode) })).toBeVisible();

  await openNavigationLink("地块管理");
  await page.getByRole("button", { name: "新建地块" }).click();
  const plotDialog = page.getByRole("dialog", { name: "新建地块" });
  await plotDialog.getByLabel("地块编号").fill(plotCode);
  await plotDialog.getByLabel("地块名称").fill("东山烟田");
  await plotDialog.getByLabel("地块面积").fill("12.5");
  await plotDialog.getByLabel("土壤说明").fill("红壤");
  await plotDialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(plotDialog).toBeHidden();
  await expect(page.getByRole("row", { name: new RegExp(plotCode) })).toBeVisible();

  await openNavigationLink("仓库管理");
  await page.getByRole("button", { name: "新建仓库" }).click();
  const warehouseDialog = page.getByRole("dialog", { name: "新建仓库" });
  await warehouseDialog.getByLabel("仓库编号").fill(warehouseCode);
  await warehouseDialog.getByLabel("仓库名称").fill(warehouseName);
  await warehouseDialog.getByLabel("仓库位置").fill("主院北侧");
  await warehouseDialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(warehouseDialog).toBeHidden();
  await expect(page.getByRole("row", { name: new RegExp(warehouseCode) })).toBeVisible();
  await page.getByRole("button", { name: "新建仓库" }).click();
  const secondaryWarehouseDialog = page.getByRole("dialog", { name: "新建仓库" });
  await secondaryWarehouseDialog.getByLabel("仓库编号").fill(secondaryWarehouseCode);
  await secondaryWarehouseDialog.getByLabel("仓库名称").fill(secondaryWarehouseName);
  await secondaryWarehouseDialog.getByLabel("仓库位置").fill("养殖区东侧");
  await secondaryWarehouseDialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(secondaryWarehouseDialog).toBeHidden();
  await expect(page.getByRole("row", { name: new RegExp(secondaryWarehouseCode) })).toBeVisible();

  await openNavigationLink("物料管理");
  await page.getByRole("tab", { name: "物料分类" }).click();
  await page.getByRole("button", { name: "新建分类" }).click();
  const categoryDialog = page.getByRole("dialog", { name: "新建物料分类" });
  await categoryDialog.getByLabel("分类编号").fill(categoryCode);
  await categoryDialog.getByLabel("分类名称").fill("饲料");
  await categoryDialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(categoryDialog).toBeHidden();
  await expect(page.getByRole("row", { name: new RegExp(categoryCode) })).toBeVisible();

  await page.getByRole("tab", { name: "物料档案" }).click();
  await page.getByRole("button", { name: "新建物料" }).click();
  const itemDialog = page.getByRole("dialog", { name: "新建物料" });
  await itemDialog.getByLabel("物料编号").fill(itemCode);
  await itemDialog.getByLabel("物料名称").fill("育肥猪全价料");
  await itemDialog.getByLabel("物料分类").click();
  await page.getByRole("option", { name: "饲料" }).click();
  await itemDialog.getByLabel("计量单位").click();
  await page.getByRole("option", { name: "千克 (KG)" }).click();
  await itemDialog.getByLabel("安全库存").fill("500");
  await itemDialog.locator(".el-switch").click();
  await itemDialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(itemDialog).toBeHidden();
  await expect(page.getByRole("row", { name: new RegExp(itemCode) })).toBeVisible();

  await logout("系统管理员", "管理员");
  await login(managerUsername);
  await expect(page.locator(".user-identity-badge")).toHaveText("负责人");
  await openNavigationLink("采购入库");
  await page.getByRole("tab", { name: "供应商" }).click();
  await page.getByRole("button", { name: "新建供应商" }).click();
  const supplierDialog = page.getByRole("dialog", { name: "新建供应商" });
  await supplierDialog.getByLabel("供应商编号").fill(supplierCode);
  await supplierDialog.getByLabel("供应商名称").fill(supplierName);
  await supplierDialog.getByLabel("供应商联系人").fill("验收联系人");
  await supplierDialog.getByLabel("供应商联系电话").fill("13800000000");
  await supplierDialog.getByRole("button", { name: "保存", exact: true }).click();
  await expect(supplierDialog).toBeHidden();
  await expect(page.getByRole("row", { name: new RegExp(supplierCode) })).toBeVisible();

  await openNavigationLink("生猪管理");
  await page.getByRole("button", { name: "批次入栏" }).click();
  const pigEntryDialog = page.getByRole("dialog", { name: "生猪批次入栏" });
  await pigEntryDialog.getByLabel("批次编号").fill(pigBatchNo);
  await pigEntryDialog.getByLabel("批次名称").fill(pigBatchName);
  await pigEntryDialog.getByLabel("入栏单号").fill(pigEntryNo);
  await expect(pigEntryDialog.getByLabel("入栏日期")).toHaveValue(businessDate);
  await openLabeledSelect(pigEntryDialog, "入栏圈舍");
  await page.getByRole("option", { name: new RegExp(barnName) }).click();
  await pigEntryDialog.getByLabel("初始头数").fill("60");
  await pigEntryDialog.getByLabel("生猪来源").fill("本地仔猪供应户");
  await pigEntryDialog.getByRole("button", { name: "确认入栏" }).click();
  await expect(pigEntryDialog).toBeHidden();
  const managerPigBatchRow = pigBatchRow();
  await expect(managerPigBatchRow).toContainText("60");
  await expect(page.getByLabel("生猪存栏汇总")).toContainText("当前存栏60头");

  await logout(managerName, "负责人");
  await login(operatorUsername);
  await expect(page.locator(".user-identity-badge")).toHaveText("操作员");
  await openNavigationLink("采购入库");
  await page.getByRole("tab", { name: "采购单", exact: true }).click();
  await page.getByRole("button", { name: "新建采购单" }).click();
  const purchaseDialog = page.getByRole("dialog", { name: "新建采购单" });
  await expect(purchaseDialog.getByLabel("采购日期", { exact: true })).toHaveValue(businessDate);
  await purchaseDialog.getByLabel("采购单号").fill(purchaseNo);
  await purchaseDialog.getByLabel("供应商", { exact: true }).click();
  await page.getByRole("option", { name: supplierName }).click();
  await purchaseDialog.getByLabel("入库仓库").click();
  await page.getByRole("option", { name: warehouseName, exact: true }).click();
  await purchaseDialog.getByLabel("采购数量").fill("25");
  await purchaseDialog.getByLabel("采购单价").fill("3.5");
  await purchaseDialog.getByLabel("物料批号").fill(lotNo);
  await purchaseDialog.getByLabel("物料有效期").fill(expiryDate);
  await purchaseDialog.getByRole("button", { name: "保存草稿" }).click();
  await expect(purchaseDialog).toBeHidden();
  const purchaseRow = page.getByRole("row", { name: new RegExp(purchaseNo) });
  await expect(purchaseRow).toBeVisible();
  await purchaseRow.getByRole("button", { name: "过账" }).click();
  const postDialog = page.getByRole("dialog", { name: "确认过账" });
  await postDialog.getByRole("button", { name: "确认过账" }).click();
  await expect(postDialog).toBeHidden();
  await expect(page.getByRole("row", { name: new RegExp(purchaseNo) }).getByText("已过账")).toBeVisible();

  await openNavigationLink("库存管理");
  const initialStockRow = page.getByRole("row").filter({ hasText: itemCode }).filter({ hasText: warehouseName });
  await expect(initialStockRow).toContainText("25");
  await page.getByRole("button", { name: "新建调拨" }).click();
  const transferDialog = page.getByRole("dialog", { name: "新建库存调拨" });
  await transferDialog.getByLabel("调拨单号").fill(transferNo);
  await expect(transferDialog.getByText(warehouseName, { exact: true })).toBeVisible();
  await expect(transferDialog.getByText(secondaryWarehouseName, { exact: true })).toBeVisible();
  await expect(transferDialog.getByText(new RegExp(itemCode))).toBeVisible();
  await transferDialog.getByLabel("调拨数量").fill("10");
  await transferDialog.getByLabel("调拨批号").fill(lotNo);
  await transferDialog.getByRole("button", { name: "确认调拨" }).click();
  const transferConfirm = page.getByRole("dialog", { name: "确认库存调拨" });
  await transferConfirm.getByRole("button", { name: "确认调拨" }).click();
  await expect(transferDialog).toBeHidden();

  const transferRows = page.getByRole("row", { name: new RegExp(transferNo) });
  await expect(transferRows).toHaveCount(2);
  await expect(transferRows.filter({ hasText: warehouseName })).toContainText("-10");
  await expect(transferRows.filter({ hasText: secondaryWarehouseName })).toContainText("+10");
  await page.getByRole("tab", { name: "库存现状" }).click();
  const mainStockRow = page.getByRole("row").filter({ hasText: itemCode }).filter({ hasText: warehouseName });
  const secondaryStockRow = page.getByRole("row").filter({ hasText: itemCode }).filter({ hasText: secondaryWarehouseName });
  await expect(mainStockRow).toContainText("15");
  await expect(secondaryStockRow).toContainText("10");
  await page.getByRole("tab", { name: "库存流水" }).click();
  await expect(page.getByRole("row", { name: new RegExp(transferNo) })).toHaveCount(2);

  await page.getByRole("button", { name: "生产领退料" }).click();
  let productionDialog = page.getByRole("dialog", { name: "生产领退料" });
  await productionDialog.getByLabel("领退料单号").fill(productionIssueNo);
  await productionDialog.getByLabel("领退仓库").click();
  await page.getByRole("option", { name: warehouseName, exact: true }).click();
  await expect(productionDialog.getByText(new RegExp(itemCode))).toBeVisible();
  await productionDialog.getByLabel("领退数量").fill("5");
  await productionDialog.getByLabel("领退批号").fill(lotNo);
  await productionDialog.getByText("圈舍", { exact: true }).click();
  await productionDialog.getByRole("combobox", { name: "使用对象", exact: true }).click();
  await page.getByRole("option", { name: new RegExp("育肥验收一舍") }).click();
  await productionDialog.getByRole("button", { name: "确认领料" }).click();
  const issueConfirm = page.getByRole("dialog", { name: "确认生产领料" });
  await issueConfirm.getByRole("button", { name: "确认领料" }).click();
  await expect(productionDialog).toBeHidden();
  const issueRow = page.getByRole("row", { name: new RegExp(productionIssueNo) });
  await expect(issueRow).toContainText("生产领料");
  await expect(issueRow).toContainText("育肥验收一舍");
  await expect(issueRow).toContainText("-5");

  await page.getByRole("button", { name: "生产领退料" }).click();
  productionDialog = page.getByRole("dialog", { name: "生产领退料" });
  await productionDialog.getByText("生产退料", { exact: true }).click();
  await productionDialog.getByLabel("领退料单号").fill(productionReturnNo);
  await productionDialog.getByLabel("领退仓库").click();
  await page.getByRole("option", { name: warehouseName, exact: true }).click();
  await productionDialog.getByLabel("领退数量").fill("2");
  await productionDialog.getByLabel("领退批号").fill(lotNo);
  await productionDialog.getByText("圈舍", { exact: true }).click();
  await productionDialog.getByRole("combobox", { name: "使用对象", exact: true }).click();
  await page.getByRole("option", { name: new RegExp("育肥验收一舍") }).click();
  await productionDialog.getByRole("button", { name: "确认退料" }).click();
  const returnConfirm = page.getByRole("dialog", { name: "确认生产退料" });
  await returnConfirm.getByRole("button", { name: "确认退料" }).click();
  await expect(productionDialog).toBeHidden();
  const returnRow = page.getByRole("row", { name: new RegExp(productionReturnNo) });
  await expect(returnRow).toContainText("生产退料");
  await expect(returnRow).toContainText("育肥验收一舍");
  await expect(returnRow).toContainText("+2");

  await page.getByRole("tab", { name: "库存现状" }).click();
  await expect(page.getByRole("row").filter({ hasText: itemCode }).filter({ hasText: warehouseName })).toContainText("12");
  await expect(page.getByRole("row").filter({ hasText: itemCode }).filter({ hasText: secondaryWarehouseName })).toContainText("10");
  await page.getByRole("tab", { name: "库存流水" }).click();
  await page.getByRole("button", { name: "重置" }).click();
  await expect(page.getByText("共 5 条流水")).toBeVisible();
  await expect(page.getByRole("row", { name: new RegExp(purchaseNo) })).toHaveCount(1);
  await expect(page.getByRole("row", { name: new RegExp(transferNo) })).toHaveCount(2);
  await expect(page.getByRole("row", { name: new RegExp(productionIssueNo) })).toHaveCount(1);
  await expect(page.getByRole("row", { name: new RegExp(productionReturnNo) })).toHaveCount(1);

  await openNavigationLink("采购入库");
  let postedPurchaseRow = page.getByRole("row", { name: new RegExp(purchaseNo) });
  await postedPurchaseRow.getByRole("button", { name: "退货" }).click();
  const purchaseReturnDialog = page.getByRole("dialog", { name: "采购退货", exact: true });
  await expect(purchaseReturnDialog.getByLabel("原采购单", { exact: true })).toHaveValue(purchaseNo);
  await expect(purchaseReturnDialog.getByLabel("退货供应商")).toHaveValue(supplierName);
  await expect(purchaseReturnDialog.getByLabel("退货日期", { exact: true })).toHaveValue(businessDate);
  await purchaseReturnDialog.getByLabel("退货单号").fill(purchaseReturnNo);
  await expect(purchaseReturnDialog.getByText("可退 25 千克", { exact: false })).toBeVisible();
  await purchaseReturnDialog.getByLabel("退货数量").fill("2");
  await expect(purchaseReturnDialog.getByText("¥ 7.00", { exact: true })).toBeVisible();
  await purchaseReturnDialog.getByRole("button", { name: "确认退货" }).click();
  const purchaseReturnConfirm = page.getByRole("dialog", { name: "确认采购退货" });
  await purchaseReturnConfirm.getByRole("button", { name: "确认退货" }).click();
  await expect(purchaseReturnDialog).toBeHidden();

  postedPurchaseRow = page.getByRole("row", { name: new RegExp(purchaseNo) });
  await postedPurchaseRow.getByRole("button", { name: "查看" }).click();
  let purchaseDetailDialog = page.getByRole("dialog", { name: "采购单详情" });
  await expect(purchaseDetailDialog.getByText("已退 2，可退 23", { exact: true })).toBeVisible();
  await purchaseDetailDialog.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(purchaseDetailDialog).toBeHidden();

  await openNavigationLink("库存管理");
  await expect(page.getByRole("row").filter({ hasText: itemCode }).filter({ hasText: warehouseName })).toContainText("10");
  await expect(page.getByRole("row").filter({ hasText: itemCode }).filter({ hasText: secondaryWarehouseName })).toContainText("10");
  await page.getByRole("tab", { name: "库存流水" }).click();
  const purchaseReturnRow = page.getByRole("row", { name: new RegExp(purchaseReturnNo) });
  await expect(purchaseReturnRow).toContainText("采购退货");
  await expect(purchaseReturnRow).toContainText("-2");
  await expect(page.getByText("共 6 条流水")).toBeVisible();

  await page.getByRole("button", { name: "新建盘点" }).click();
  let inventoryCountDialog = page.getByRole("dialog", { name: "新建库存盘点" });
  await expect(inventoryCountDialog.getByLabel("盘点日期", { exact: true })).toHaveValue(businessDate);
  await inventoryCountDialog.getByLabel("盘点单号").fill(inventoryCountNo);
  await inventoryCountDialog.getByLabel("盘点仓库").click();
  await page.getByRole("option", { name: warehouseName, exact: true }).click();
  await inventoryCountDialog.getByRole("button", { name: "生成盘点单" }).click();

  inventoryCountDialog = page.getByRole("dialog", { name: "盘点录入" });
  await expect(inventoryCountDialog.getByText(itemCode, { exact: true })).toBeVisible();
  await expect(inventoryCountDialog.getByText(lotNo, { exact: true })).toBeVisible();
  await inventoryCountDialog.getByLabel(`实盘数量-${itemCode}-${lotNo}`).fill("9");
  await inventoryCountDialog.getByRole("button", { name: "保存草稿" }).click();
  await expect(page.getByText(`“育肥猪全价料”存在盘点差异，请填写原因`)).toBeVisible();
  await inventoryCountDialog.getByLabel(`差异原因-${itemCode}-${lotNo}`).fill("实盘短少");
  await expect(inventoryCountDialog.getByText("-1 千克", { exact: true })).toBeVisible();
  await inventoryCountDialog.getByRole("button", { name: "保存草稿" }).click();
  await expect(page.getByText("盘点草稿已保存")).toBeVisible();
  await inventoryCountDialog.getByRole("button", { name: "确认过账" }).click();
  const inventoryCountConfirm = page.getByRole("dialog", { name: "确认盘点过账" });
  await expect(inventoryCountConfirm).toContainText("1 条差异");
  await inventoryCountConfirm.getByRole("button", { name: "确认过账" }).click();
  inventoryCountDialog = page.getByRole("dialog", { name: "盘点单详情" });
  await expect(inventoryCountDialog.getByLabel("盘点状态")).toHaveValue("已过账");
  await inventoryCountDialog.getByRole("button", { name: "关闭", exact: true }).click();

  const inventoryAdjustmentRow = page.getByRole("row", { name: new RegExp(inventoryCountNo) });
  await expect(inventoryAdjustmentRow).toContainText("盘亏调整");
  await expect(inventoryAdjustmentRow).toContainText("-1");
  await expect(page.getByText("共 7 条流水")).toBeVisible();
  await page.getByRole("tab", { name: "库存现状" }).click();
  await expect(page.getByRole("row").filter({ hasText: itemCode }).filter({ hasText: warehouseName })).toContainText("9");
  await expect(page.getByRole("row").filter({ hasText: itemCode }).filter({ hasText: secondaryWarehouseName })).toContainText("10");
  await page.getByRole("tab", { name: "库存盘点" }).click();
  const inventoryCountRow = page.getByRole("row", { name: new RegExp(inventoryCountNo) });
  await expect(inventoryCountRow).toContainText("已过账");
  await expect(inventoryCountRow).toContainText("1 条");

  await page.getByRole("tab", { name: "库存分析" }).click();
  const analysisMetrics = page.getByLabel("库存分析汇总");
  await expect(analysisMetrics).toContainText("¥ 129.50");
  await expect(analysisMetrics).toContainText("¥ 63.00");
  await expect(analysisMetrics.locator("> div").filter({ hasText: "临期批次" })).toContainText("2");
  await expect(analysisMetrics.locator("> div").filter({ hasText: "过期批次" })).toContainText("0");
  const consumedRow = page.locator(".consumption-row").filter({ hasText: itemCode });
  await expect(consumedRow).toContainText("3 千克");
  await expect(consumedRow).toContainText("¥ 10.50");
  const expiryRows = page.getByRole("row", { name: new RegExp(lotNo) });
  await expect(expiryRows).toHaveCount(2);
  await expect(expiryRows.filter({ hasText: warehouseName })).toContainText("9");
  await expect(expiryRows.filter({ hasText: secondaryWarehouseName })).toContainText("10");
  await expect(expiryRows.first()).toContainText(expiryDate);
  const trendCanvas = page.locator(".inventory-trend-chart canvas");
  await expect(trendCanvas).toBeVisible();
  const chartHasPixels = await trendCanvas.evaluate((element) => {
    const canvas = element as HTMLCanvasElement;
    const pixels = canvas.getContext("2d")?.getImageData(0, 0, canvas.width, canvas.height).data ?? [];
    return Array.from(pixels).some((value, index) => index % 4 === 3 && value > 0);
  });
  expect(chartHasPixels).toBe(true);
  await page
    .getByRole("combobox", { name: "效期预警范围" })
    .locator("xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' el-select ')][1]")
    .click();
  await page.getByRole("option", { name: "7 天内到期", exact: true }).click();
  await expect(page.getByRole("row", { name: new RegExp(lotNo) })).toHaveCount(0);
  await expect(page.getByText("当前范围内暂无效期预警")).toBeVisible();

  await openNavigationLink("生猪管理");
  async function recordPigMovement(
    typeName: "转舍" | "死亡" | "淘汰" | "出栏",
    movementNo: string,
    fromBarnName: string,
    quantity: string,
    toBarnName?: string,
    reason?: string,
  ) {
    const batchRow = pigBatchRow();
    await batchRow.getByRole("button", { name: "登记变动" }).click();
    const dialog = page.getByRole("dialog", { name: "登记存栏变动" });
    await dialog.getByText(typeName, { exact: true }).click();
    await dialog.getByLabel("变动单号").fill(movementNo);
    await openLabeledSelect(dialog, "来源圈舍");
    await page.getByRole("option", { name: new RegExp(fromBarnName) }).click();
    if (toBarnName) {
      await openLabeledSelect(dialog, "目标圈舍");
      await page.getByRole("option", { name: new RegExp(toBarnName) }).click();
    }
    await dialog.getByLabel("变动头数").fill(quantity);
    if (reason) await dialog.getByLabel("变动原因").fill(reason);
    await dialog.getByRole("button", { name: "确认登记" }).click();
    await expect(dialog).toBeHidden();
  }
  await recordPigMovement("转舍", pigTransferNo, barnName, "20", secondaryBarnName);
  await expect(pigBatchRow()).toContainText("60");
  await recordPigMovement("死亡", pigDeathNo, secondaryBarnName, "2", undefined, "应激死亡");
  await recordPigMovement("淘汰", pigCullNo, barnName, "1", undefined, "生长不良");
  await recordPigMovement("出栏", pigExitNo, barnName, "10");
  const operatorPigBatchRow = pigBatchRow();
  await expect(operatorPigBatchRow).toContainText("47");
  await expect(operatorPigBatchRow).toContainText(`${barnName} 29`);
  await expect(operatorPigBatchRow).toContainText(`${secondaryBarnName} 18`);
  await expect(page.getByLabel("生猪存栏汇总")).toContainText("累计死亡率3.33% · 2 头");
  await operatorPigBatchRow.getByRole("button", { name: "查看批次" }).click();
  let pigDetailDialog = page.getByRole("dialog", { name: "生猪批次详情" });
  await expect(pigDetailDialog).toContainText("当前存栏47 头");
  await expect(pigDetailDialog.getByRole("row", { name: new RegExp(pigTransferNo) })).toContainText("转舍");
  await expect(pigDetailDialog.getByRole("row", { name: new RegExp(pigDeathNo) })).toContainText("应激死亡");
  await pigDetailDialog.getByRole("button", { name: "关闭", exact: true }).click();

  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasHorizontalOverflow).toBe(false);

  await logout(operatorName, "操作员");
  await login(viewerUsername);
  await expect(page.locator(".user-identity-badge")).toHaveText("查看员");
  await openNavigationLink("农场档案");

  await expect(page.getByRole("row", { name: new RegExp(farmCode) })).toBeVisible();
  await expect(page.getByRole("button", { name: "新建农场" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "成员管理" })).toHaveCount(0);
  await expect(page.locator(".farm-context")).toContainText(farmName);

  await openNavigationLink("圈舍管理");
  await expect(page.getByRole("row", { name: new RegExp(barnCode) })).toBeVisible();
  await expect(page.getByRole("row", { name: new RegExp(secondaryBarnCode) })).toBeVisible();
  await expect(page.getByRole("button", { name: "新建圈舍" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "编辑圈舍" })).toHaveCount(0);

  await openNavigationLink("地块管理");
  await expect(page.getByRole("row", { name: new RegExp(plotCode) })).toBeVisible();
  await expect(page.getByRole("button", { name: "新建地块" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "编辑地块" })).toHaveCount(0);

  await openNavigationLink("仓库管理");
  await expect(page.getByRole("row", { name: new RegExp(warehouseCode) })).toBeVisible();
  await expect(page.getByRole("row", { name: new RegExp(secondaryWarehouseCode) })).toBeVisible();
  await expect(page.getByRole("button", { name: "新建仓库" })).toHaveCount(0);

  await openNavigationLink("物料管理");
  await expect(page.getByRole("row", { name: new RegExp(itemCode) })).toBeVisible();
  await expect(page.getByRole("button", { name: "新建物料" })).toHaveCount(0);
  await page.getByRole("tab", { name: "物料分类" }).click();
  await expect(page.getByRole("row", { name: new RegExp(categoryCode) })).toBeVisible();
  await expect(page.getByRole("button", { name: "新建分类" })).toHaveCount(0);

  await openNavigationLink("采购入库");
  const viewerPurchaseRow = page.getByRole("row", { name: new RegExp(purchaseNo) });
  await expect(viewerPurchaseRow).toBeVisible();
  await expect(page.getByRole("button", { name: "新建采购单" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "退货" })).toHaveCount(0);
  await viewerPurchaseRow.getByRole("button", { name: "查看" }).click();
  purchaseDetailDialog = page.getByRole("dialog", { name: "采购单详情" });
  await expect(purchaseDetailDialog.getByText("已退 2，可退 23", { exact: true })).toBeVisible();
  await purchaseDetailDialog.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("tab", { name: "供应商" }).click();
  await expect(page.getByRole("row", { name: new RegExp(supplierCode) })).toBeVisible();
  await expect(page.getByRole("button", { name: "新建供应商" })).toHaveCount(0);

  await openNavigationLink("库存管理");
  await expect(page.getByRole("button", { name: "新建盘点" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "新建调拨" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "生产领退料" })).toHaveCount(0);
  const viewerStockRows = page.getByRole("row", { name: new RegExp(itemCode) });
  await expect(viewerStockRows).toHaveCount(2);
  await expect(viewerStockRows.filter({ hasText: warehouseName })).toContainText("9");
  await expect(viewerStockRows.filter({ hasText: secondaryWarehouseName })).toContainText("10");
  await page.getByRole("tab", { name: "库存流水" }).click();
  await expect(page.getByText("共 7 条流水")).toBeVisible();
  await expect(page.getByRole("row", { name: new RegExp(purchaseNo) })).toBeVisible();
  await expect(page.getByRole("row", { name: new RegExp(transferNo) })).toHaveCount(2);
  const viewerPurchaseReturnRow = page.getByRole("row", { name: new RegExp(purchaseReturnNo) });
  await expect(viewerPurchaseReturnRow).toContainText("采购退货");
  await expect(viewerPurchaseReturnRow).toContainText("-2");
  const viewerIssueRow = page.getByRole("row", { name: new RegExp(productionIssueNo) });
  const viewerReturnRow = page.getByRole("row", { name: new RegExp(productionReturnNo) });
  await expect(viewerIssueRow).toContainText("生产领料");
  await expect(viewerIssueRow).toContainText("-5");
  await expect(viewerReturnRow).toContainText("生产退料");
  await expect(viewerReturnRow).toContainText("+2");
  const viewerInventoryAdjustmentRow = page.getByRole("row", { name: new RegExp(inventoryCountNo) });
  await expect(viewerInventoryAdjustmentRow).toContainText("盘亏调整");
  await expect(viewerInventoryAdjustmentRow).toContainText("-1");
  const issueQuantity = Number(await viewerIssueRow.locator(".quantity-out").textContent());
  const returnQuantity = Number(await viewerReturnRow.locator(".quantity-in").textContent());
  expect(-(issueQuantity + returnQuantity)).toBe(3);
  await page.getByRole("tab", { name: "库存盘点" }).click();
  const viewerInventoryCountRow = page.getByRole("row", { name: new RegExp(inventoryCountNo) });
  await expect(viewerInventoryCountRow).toContainText("已过账");
  await viewerInventoryCountRow.getByRole("button", { name: "查看" }).click();
  const viewerInventoryCountDialog = page.getByRole("dialog", { name: "盘点单详情" });
  await expect(viewerInventoryCountDialog.getByText("实盘短少", { exact: true })).toBeVisible();
  await expect(viewerInventoryCountDialog.getByRole("button", { name: "保存草稿" })).toHaveCount(0);
  await expect(viewerInventoryCountDialog.getByRole("button", { name: "确认过账" })).toHaveCount(0);
  await viewerInventoryCountDialog.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("tab", { name: "库存分析" }).click();
  await expect(page.getByLabel("库存分析汇总")).toContainText("¥ 129.50");
  const viewerExpiryRows = page.getByRole("row", { name: new RegExp(lotNo) });
  await expect(viewerExpiryRows).toHaveCount(2);
  await expect(viewerExpiryRows.filter({ hasText: warehouseName })).toContainText("9");
  await expect(viewerExpiryRows.filter({ hasText: secondaryWarehouseName })).toContainText("10");
  await expect(page.locator(".consumption-row").filter({ hasText: itemCode })).toContainText("3 千克");
  await expect(page.locator(".inventory-trend-chart canvas")).toBeVisible();

  await openNavigationLink("生猪管理");
  await expect(page.getByRole("button", { name: "批次入栏" })).toHaveCount(0);
  const viewerPigBatchRow = pigBatchRow();
  await expect(viewerPigBatchRow).toContainText("47");
  await expect(viewerPigBatchRow).toContainText(`${barnName} 29`);
  await expect(viewerPigBatchRow).toContainText(`${secondaryBarnName} 18`);
  await expect(viewerPigBatchRow.getByRole("button", { name: "登记变动" })).toHaveCount(0);
  await viewerPigBatchRow.getByRole("button", { name: "查看批次" }).click();
  pigDetailDialog = page.getByRole("dialog", { name: "生猪批次详情" });
  await expect(pigDetailDialog.getByRole("row", { name: new RegExp(pigEntryNo) })).toContainText("入栏");
  await expect(pigDetailDialog.getByRole("row", { name: new RegExp(pigExitNo) })).toContainText("出栏");
  await expect(pigDetailDialog).toContainText("当前存栏47 头");
  await pigDetailDialog.getByRole("button", { name: "关闭", exact: true }).click();
  await expect(pigDetailDialog).toBeHidden();
  await expect(page.locator(".el-message")).toHaveCount(0);
  expect(browserErrors).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath(`role-collaboration-${isMobile ? "mobile" : "desktop"}.png`), fullPage: true });
});

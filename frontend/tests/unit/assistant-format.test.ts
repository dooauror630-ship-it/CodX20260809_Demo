import { describe, expect, it } from "vitest";
import { buildBusinessReport, renderBusinessMessage } from "@/modules/assistant/messageFormat";

function documentOf(source: string) {
  return new DOMParser().parseFromString(renderBusinessMessage(source), "text/html");
}

describe("业务输出自动排版", () => {
  it.each([
    ["库存", "物料 | 当前库存 | 单位", "DEMO-CORN | 120 | 千克"],
    ["采购", "单号 | 金额 | 状态", "PO-001 | 52.00 | 草稿"],
    ["盘点", "物料 | 账面数量 | 实盘数量", "饲料 | 120 | 118"],
    ["调拨", "调出仓 | 调入仓 | 数量", "一号仓 | 二号仓 | 15"],
    ["养殖", "批次 | 存栏 | 健康状态", "PIG-001 | 84 | 正常"],
    ["种植", "地块 | 作物 | 面积", "PLOT-001 | 玉米 | 10"],
    ["销售", "订单 | 客户 | 应收金额", "SALE-001 | 合作社 | 1000.00"],
    ["用户权限", "姓名 | 角色 | 农场", "张三 | 查看员 | 测试农场"],
    ["新增业务", "字段甲 | 字段乙 | 字段丙", "任意值 | 0 | 未提供"],
  ])("%s：独立标题、表格和建议，列数不变", (name, header, row) => {
    const doc = documentOf(`## ${name}\n\n查询结果如下：\n\n| ${header} |\n| --- | --- | --- |\n| ${row} |\n\n- 核对明细\n- 继续查询`);
    expect(doc.querySelector("h2")?.textContent).toBe(name);
    expect(doc.querySelectorAll("table")).toHaveLength(1);
    expect(doc.querySelectorAll("th")).toHaveLength(3);
    expect([...doc.querySelectorAll("td")].map((cell) => cell.textContent)).toEqual(row.split(" | "));
    expect(doc.querySelectorAll("ul > li")).toHaveLength(2);
    expect(doc.querySelector("table")?.textContent).not.toContain("继续查询");
    expect(doc.body.textContent).not.toContain("库存概览");
  });

  it("保留 CRLF、带缩进表头、相邻摘要表和明细表的边界", () => {
    const doc = documentOf("库存摘要\r\n\r\n | 指标 | 数值 |\r\n | --- | --- |\r\n | 总值 | 1,740.00 |\r\n\r\n**低库存明细**\r\n\r\n物料 | 库存\r\n--- | ---\r\nDEMO-CORN | 120\r\n\r\n说明：请核对库存。");
    expect(doc.querySelectorAll("table")).toHaveLength(2);
    expect(doc.querySelectorAll("table")[0].textContent).toContain("1,740.00");
    expect(doc.querySelectorAll("table")[0].textContent).not.toContain("低库存明细");
    expect(doc.querySelectorAll("table")[1].textContent).not.toContain("说明");
  });

  it("步骤、嵌套建议和无数据提示不强制转成表格", () => {
    const doc = documentOf("没有符合条件的记录。\n\n1. 选择农场\n2. 核对条件\n   - 核对日期\n   - 核对状态\n\n完成后重新查询。");
    expect(doc.querySelectorAll("table")).toHaveLength(0);
    expect(doc.querySelectorAll("ol > li")).toHaveLength(2);
    expect(doc.querySelectorAll("ol ul > li")).toHaveLength(2);
    expect(doc.body.textContent).toContain("没有符合条件的记录");
  });

  it("转义竖线、粗体和负数不会破坏表格或丢掉内容", () => {
    const doc = documentOf("| 物料 | 差异 |\n| --- | ---: |\n| **玉米\\|豆粕** | -2.50 |\n");
    expect(doc.querySelectorAll("td")).toHaveLength(2);
    expect(doc.querySelector("td strong")?.textContent).toBe("玉米|豆粕");
    expect(doc.body.textContent).toContain("-2.50");
  });

  it("流式不完整内容持续可渲染，最终表格完整；孤立分隔线不生成表格", () => {
    const source = "结果：\n\n| 编号 | 数值 |\n| --- | --- |\n| DEMO-CORN | 120 |\n\n- 请核对";
    for (let index = 0; index <= source.length; index++) expect(() => renderBusinessMessage(source.slice(0, index))).not.toThrow();
    expect(documentOf(source).querySelectorAll("td")).toHaveLength(2);
    expect(documentOf("| --- | --- |\n\n普通说明").querySelector("table")).toBeNull();
  });

  it("页面和报告均禁止注入 HTML、脚本链接，且保留相同表格和列表", () => {
    const source = "<img src=x onerror=alert(1)>\n\n![外部图片](https://example.com/track)\n\n[点击](javascript:alert(1))\n\n| 名称 | 数值 |\n| --- | --- |\n| 饲料 | 20 |\n\n1. 核对\n2. 确认";
    const doc = documentOf(source);
    const report = new DOMParser().parseFromString(buildBusinessReport(source), "text/html");
    for (const output of [doc, report]) {
      expect(output.querySelector("img, script, iframe, [onerror], a[href^='javascript:']")).toBeNull();
      expect(output.querySelectorAll("td")).toHaveLength(2);
      expect(output.querySelectorAll("ol > li")).toHaveLength(2);
    }
    expect(report.querySelector("table")?.outerHTML).toBe(doc.querySelector("table")?.outerHTML);
  });
});

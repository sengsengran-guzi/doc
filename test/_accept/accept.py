#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kevin-test.xlsx 验收账本 —— sensenran-guzi ③验收层的机器可读状态。

甲方在 doc/test/kevin-test.xlsx 里填「路径 / 问题描述 / 问题截图 / 处理状态」，
本脚本把 xlsx 抽成有稳定 ID 的账本（ledger.json），并把处理结果**回写** xlsx 的「处理状态」列。

为什么不用 openpyxl
-------------------
该 xlsx 的截图是 WPS 的 DISPIMG 嵌入图（`xl/cellimages.xml` + `xl/media/*`，单元格里是
`=DISPIMG("ID_...",1)` 公式）。openpyxl 保存时会**丢掉 cellimages.xml**，导致所有
DISPIMG 公式失效、甲方贴的截图全部消失（已实测：321KB → 9.9KB，cellimages.xml 消失）。
所以读写一律走 zip + XML 层面，**除目标单元格外的所有 part 逐字节保留**，写完还会自检。

ID 稳定性
---------
ID 由「路径 + 问题描述」的 sha1 前 8 位派生，**不用行号**：甲方在表中间插行 / 清空重填
都不会让已有条目的 ID 漂移。行号只作为提示字段，每次 sync 刷新。

用法
----
    python3 doc/test/_accept/accept.py sync        # xlsx → ledger（保留人工字段）
    python3 doc/test/_accept/accept.py list        # 看还有哪些没处理
    python3 doc/test/_accept/accept.py show <id>   # 看单条详情
    python3 doc/test/_accept/accept.py shots <id>  # 导出该条截图到 /tmp 供人看
    python3 doc/test/_accept/accept.py set <id> --status 已修复 --note "..." [--cell-note "..."]
    python3 doc/test/_accept/accept.py writeback   # ledger 状态 → xlsx「处理状态」列（自动备份 + 自检）
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(HERE, os.pardir, "kevin-test.xlsx")
LEDGER = os.path.join(HERE, "ledger.json")
SHOT_DIR = "/tmp/gz-accept-shots"

# 状态词表 —— 只有这些值允许回写，避免账号本里出现无法机检的自由文本
STATUS = ["待处理", "处理中", "已修复", "已验收", "已拒绝", "重复"]
# 归因（对齐 xuqiu §4 归因回流）：doc=蓝图/文档缺陷 · impl=实现缺陷 · misread=测试人误解 · env=环境
CAUSE = ["doc", "impl", "misread", "env", "unknown"]

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
SHEET_PART = "xl/worksheets/sheet1.xml"
COLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def col_of(ref):
    return re.match(r"([A-Z]+)", ref).group(1)


def row_of(ref):
    return int(re.search(r"(\d+)$", ref).group(1))


# ──────────────────────────── 读 xlsx ────────────────────────────

def _shared_strings(z):
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    out = []
    for si in root.findall(NS_MAIN + "si"):
        out.append("".join(t.text or "" for t in si.iter(NS_MAIN + "t")))
    return out


def read_rows(path=None):
    """→ [{'row': int, 'A':…, 'B':…, 'C':…, 'D':…, 'E':…}]，只含非空行（跳过表头）。

    注意 path 默认值必须在**调用时**解析 XLSX 全局（不能用 `path=XLSX` 的默认参数，
    那会在 import 时绑死，--xlsx 覆盖不生效）。"""
    import xml.etree.ElementTree as ET
    path = path or XLSX
    with zipfile.ZipFile(path) as z:
        strings = _shared_strings(z)
        sheet = z.read(SHEET_PART)
    root = ET.fromstring(sheet)
    rows = []
    for r in root.iter(NS_MAIN + "row"):
        rnum = int(r.get("r"))
        cells = {}
        for c in r.findall(NS_MAIN + "c"):
            ref = c.get("r") or ""
            letter = col_of(ref)
            v = c.find(NS_MAIN + "v")
            val = v.text if v is not None else ""
            if c.get("t") == "s" and val != "":
                val = strings[int(val)]
            elif c.get("t") == "inlineStr":
                isn = c.find(NS_MAIN + "is")
                val = "".join(t.text or "" for t in isn.iter(NS_MAIN + "t")) if isn is not None else ""
            cells[letter] = (val or "").strip()
        if rnum == 1:          # 表头
            continue
        if not (cells.get("A") or cells.get("B")):
            continue           # 空行
        cells["row"] = rnum
        rows.append(cells)
    return rows


def item_id(row):
    raw = (row.get("A", "") + "\u0000" + row.get("B", "")).encode("utf-8")
    return "ACC-" + hashlib.sha1(raw).hexdigest()[:8]


def xlsx_fingerprint(path=None):
    path = path or XLSX
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()[:12]


# ──────────────────────────── 账本读写 ────────────────────────────

def load():
    if os.path.exists(LEDGER):
        with open(LEDGER, encoding="utf-8") as f:
            return json.load(f)
    return {"version": 1, "source": "doc/test/kevin-test.xlsx",
            "source_fp": None, "last_sync": None, "items": {}}


def save(led):
    tmp = LEDGER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(led, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, LEDGER)


# ──────────────────────────── 命令 ────────────────────────────

def cmd_sync(args):
    led = load()
    rows = read_rows()
    seen, added, updated, gone = [], [], [], []

    for row in rows:
        iid = item_id(row)
        seen.append(iid)
        it = led["items"].get(iid)
        if it is None:
            it = {
                "id": iid,
                "path": row.get("A", ""),
                "desc": row.get("B", ""),
                "shots": [row.get("C", ""), row.get("D", "")],
                "row": row["row"],
                "status": "待处理",
                "cause": "unknown",
                "note": "",
                "cell_note": "",
                "first_seen": datetime.now().strftime("%Y-%m-%d"),
                "history": [],
            }
            led["items"][iid] = it
            added.append(iid)
        elif it["row"] != row["row"]:
            it["history"].append({"at": datetime.now().isoformat(timespec="seconds"),
                                  "event": f"行号 {it['row']} → {row['row']}"})
            it["row"] = row["row"]
            updated.append(iid)

    for iid, it in led["items"].items():
        if iid not in seen:
            it.setdefault("history", []).append(
                {"at": datetime.now().isoformat(timespec="seconds"), "event": "已从 xlsx 消失"})
            gone.append(iid)

    led["source_fp"] = xlsx_fingerprint()
    led["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    save(led)

    print(f"sync 完成：xlsx 里 {len(rows)} 条")
    print(f"  新增 {len(added)}：{' '.join(added) if added else '—'}")
    print(f"  移动 {len(updated)}：{' '.join(updated) if updated else '—'}")
    if gone:
        print(f"  ⚠️ 账本里有 {len(gone)} 条已不在 xlsx（未删，仅记事件）：{' '.join(gone)}")
    pend = [i for i in led["items"].values() if i["status"] == "待处理"]
    print(f"  当前待处理：{len(pend)}")
    return 0


def cmd_list(args):
    led = load()
    items = sorted(led["items"].values(), key=lambda x: x["row"])
    if not items:
        print("账本为空 —— 先跑 sync（且 xlsx 里要有数据行）")
        return 0
    only = args.status
    if only:
        items = [i for i in items if i["status"] == only]
    width = max((len(i["path"]) for i in items), default=8)
    print(f"{'ID':<13} {'行':>3}  {'状态':<6} {'路径':<{width}}  问题")
    print("-" * (40 + width + 30))
    for i in items:
        d = i["desc"].replace("\n", " / ")[:60]
        print(f"{i['id']:<13} {i['row']:>3}  {i['status']:<6} {i['path']:<{width}}  {d}")
    print(f"\n共 {len(items)} 条")
    return 0


def cmd_show(args):
    led = load()
    it = led["items"].get(args.id)
    if not it:
        print(f"没有这个 ID：{args.id}", file=sys.stderr)
        return 1
    print(f"ID      {it['id']}")
    print(f"行号    {it['row']}   （路径：{it['path']}）")
    print(f"状态    {it['status']}   归因：{it['cause']}")
    print(f"首次    {it['first_seen']}")
    print("\n问题描述：")
    for line in it["desc"].splitlines():
        print("   " + line)
    print(f"\n截图    {[s[:24] + '…' for s in it['shots'] if s] or '（无）'}")
    if it["note"]:
        print(f"\n处置    {it['note']}")
    if it.get("cell_note"):
        print(f"回写值  {it['cell_note']}")
    if it.get("history"):
        print("\n事件：")
        for h in it["history"]:
            print(f"   {h['at']}  {h['event']}")
    return 0


def cmd_shots(args):
    """导出该条的内嵌截图（DISPIMG → media 文件）供人 / 模型看。"""
    import xml.etree.ElementTree as ET
    led = load()
    it = led["items"].get(args.id)
    if not it:
        print(f"没有这个 ID：{args.id}", file=sys.stderr)
        return 1
    ids = []
    for f in it["shots"]:
        m = re.search(r'DISPIMG\(\s*"([^"]+)"', f or "")
        if m:
            ids.append(m.group(1))
    if not ids:
        print("该条没有内嵌截图公式（可能是空列或普通图片）")
        return 0

    os.makedirs(SHOT_DIR, exist_ok=True)
    with zipfile.ZipFile(XLSX) as z:
        if "xl/cellimages.xml" not in z.namelist():
            print("⚠️ xl/cellimages.xml 不存在 —— 该文件的嵌入图已被破坏", file=sys.stderr)
            return 1
        rels = ET.fromstring(z.read("xl/_rels/cellimages.xml.rels"))
        NSR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
        rmap = {r.get("Id"): r.get("Target") for r in rels}
        ci = ET.fromstring(z.read("xl/cellimages.xml"))
        name2media = {}
        for pic in ci.iter():
            if pic.tag.endswith("pic"):
                nv = [e for e in pic.iter() if e.tag.endswith("cNvPr")]
                blip = [e for e in pic.iter() if e.tag.endswith("blip")]
                if nv and blip:
                    name2media[nv[0].get("name")] = rmap.get(blip[0].get(NSR + "embed"))
        for i, did in enumerate(ids, 1):
            media = name2media.get(did)
            if not media:
                print(f"  ⚠️ {did} 未在 cellimages.xml 里找到")
                continue
            src = "xl/" + media.lstrip("/")
            dst = os.path.join(SHOT_DIR, f"{it['id']}-{i}.png")
            with z.open(src) as f, open(dst, "wb") as o:
                shutil.copyfileobj(f, o)
            print(f"  ✓ {dst}")
    print(f"\n用 read_image 打开上面路径即可看甲方截图。目录：{SHOT_DIR}")
    return 0


def cmd_set(args):
    led = load()
    it = led["items"].get(args.id)
    if not it:
        print(f"没有这个 ID：{args.id}", file=sys.stderr)
        return 1
    if args.status:
        if args.status not in STATUS:
            print(f"状态必须是 {STATUS} 之一", file=sys.stderr)
            return 2
        it["status"] = args.status
    if args.cause:
        if args.cause not in CAUSE:
            print(f"归因必须是 {CAUSE} 之一", file=sys.stderr)
            return 2
        it["cause"] = args.cause
    if args.note is not None:
        it["note"] = args.note
    if args.cell_note is not None:
        it["cell_note"] = args.cell_note
    it.setdefault("history", []).append(
        {"at": datetime.now().isoformat(timespec="seconds"),
         "event": f"set status={it['status']} cause={it['cause']}" + (f" note={it['note']}" if it["note"] else "")})
    save(led)
    print(f"{it['id']} → {it['status']}（归因 {it['cause']}）")
    if it["note"]:
        print(f"  处置：{it['note']}")
    return 0


ROW_RE = re.compile(rb"<row\b[^>]*/>|<row\b[^>]*>.*?</row>", re.S)
# bytes 模式（被替换的是 XML 字节流，str 模式会 TypeError）
CELL_RE_TMPL = rb'<c\b[^>]*\br="E%d"[^>]*/>|<c\b[^>]*\br="E%d"[^>]*>.*?</c>'


def build_cell(rnum, text):
    return (f'<c r="E{rnum}" t="inlineStr"><is><t xml:space="preserve">'
            f'{escape(text)}</t></is></c>').encode("utf-8")


def cmd_writeback(args):
    """把账本状态写回 xlsx 的「处理状态」列。XML 层面改，其余 part 逐字节保留。"""
    led = load()
    if not os.path.exists(XLSX):
        print(f"找不到 {XLSX}", file=sys.stderr)
        return 1

    current_fp = xlsx_fingerprint()
    if led.get("source_fp") and led["source_fp"] != current_fp:
        print(f"⚠️ xlsx 自上次 sync 后已被改动（指纹 {led['source_fp']} → {current_fp}）。")
        print("   建议先 `accept.py sync` 再回写，否则行号可能对不上。")
        if not args.force:
            print("   确认要按当前账本行号回写就加 --force。")
            return 3

    bak = XLSX + ".bak-" + datetime.now().strftime("%Y%m%d%H%M%S")
    shutil.copy2(XLSX, bak)

    with zipfile.ZipFile(XLSX) as z:
        entries = [(i, z.read(i.filename)) for i in z.infolist()]
        names = [i.filename for i in z.infolist()]

    by_name = {info.filename: data for info, data in entries}
    sheet = by_name[SHEET_PART]
    updates = {}
    for it in led["items"].values():
        if it["status"] == "待处理":
            continue
        cell = it.get("cell_note") or it["status"]
        updates[it["row"]] = cell

    if not updates:
        print("没有需要回写的状态（全部仍是「待处理」）")
        return 0

    def fix_row(m):
        block = m.group(0)
        rm = re.search(rb'\br="(\d+)"', block)
        if not rm:
            return block
        rnum = int(rm.group(1))
        if rnum not in updates:
            return block
        if block.endswith(b"/>") and b"<c " not in block:      # 自闭合空行 → 展开
            block = block[:-2] + b">" + build_cell(rnum, updates[rnum]) + b"</row>"
            return block
        block = re.sub(CELL_RE_TMPL % (rnum, rnum), b"", block, flags=re.S)   # 去掉旧 E 列
        return block.replace(b"</row>", build_cell(rnum, updates[rnum]) + b"</row>")

    new_sheet = ROW_RE.sub(fix_row, sheet)

    tmp = XLSX + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        for info, data in entries:
            out.writestr(info, new_sheet if info.filename == SHEET_PART else data)
    os.replace(tmp, XLSX)

    # ── 自检：嵌入图与 DISPIMG 公式必须原样在 ──────────────────────
    ok = True
    with zipfile.ZipFile(XLSX) as z:
        n2 = z.namelist()
        if "xl/cellimages.xml" not in n2:
            print("  ✗ cellimages.xml 丢失！"); ok = False
        media_old = [n for n in names if n.startswith("xl/media/")]
        media_new = [n for n in n2 if n.startswith("xl/media/")]
        if len(media_old) != len(media_new):
            print(f"  ✗ media 数量变了：{len(media_old)} → {len(media_new)}"); ok = False
        body = z.read(SHEET_PART).decode("utf-8")
        for it in led["items"].values():
            for f in it["shots"]:
                m = re.search(r'DISPIMG\(\s*"([^"]+)"', f or "")
                if m and m.group(1) not in body:
                    print(f"  ✗ {it['id']} 的 DISPIMG 公式丢失（{m.group(1)}）"); ok = False
        print(f"  写入 {len(updates)} 个「处理状态」单元格")
        print(f"  嵌入图 media {len(media_new)} 个 / cellimages.xml {'在' if 'xl/cellimages.xml' in n2 else '缺失'}")
        print("  ✓ 自检通过：截图与公式完好" if ok else "  ✗ 自检未通过，请用备份回滚")
    print(f"  备份：{bak}")
    return 0 if ok else 1


def main():
    global XLSX, LEDGER
    p = argparse.ArgumentParser(description="kevin-test.xlsx 验收账本")
    p.add_argument("--xlsx", default=XLSX, help="xlsx 路径（默认 doc/test/kevin-test.xlsx；测试用）")
    p.add_argument("--ledger", default=LEDGER, help="账本路径（默认同目录 ledger.json）")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sync", help="xlsx → ledger").set_defaults(fn=cmd_sync)

    pl = sub.add_parser("list", help="列出条目")
    pl.add_argument("--status", choices=STATUS, help="只看某状态")
    pl.set_defaults(fn=cmd_list)

    ps = sub.add_parser("show", help="看单条")
    ps.add_argument("id")
    ps.set_defaults(fn=cmd_show)

    ph = sub.add_parser("shots", help="导出该条甲方截图")
    ph.add_argument("id")
    ph.set_defaults(fn=cmd_shots)

    pst = sub.add_parser("set", help="改状态 / 归因 / 处置")
    pst.add_argument("id")
    pst.add_argument("--status", choices=STATUS)
    pst.add_argument("--cause", choices=CAUSE)
    pst.add_argument("--note")
    pst.add_argument("--cell-note", dest="cell_note", help="回写到 xlsx 的文本（默认=状态）")
    pst.set_defaults(fn=cmd_set)

    pw = sub.add_parser("writeback", help="ledger → xlsx「处理状态」列")
    pw.add_argument("--force", action="store_true", help="xlsx 指纹变了也照写")
    pw.set_defaults(fn=cmd_writeback)

    args = p.parse_args()
    XLSX = args.xlsx
    LEDGER = args.ledger
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())

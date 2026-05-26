#!/usr/bin/env bash
# 用 freelance/templates/reference-contract.docx（即智慧农场合同副本）作为
# pandoc 参考样式，生成 03-contract-formal.docx。
#
# 参考样式提取自 /tmp/zhny-docx 解压结果（智慧农场合同）：
#   - Normal（styles.xml）：Arial / sz=22（11pt）
#   - 正文 run 实际用：汉仪书宋二KW / sz=28（14pt）/ line=360（1.5 倍行距）
#   - heading 1: sz=48（24pt），spacing before/after 240
#   - heading 2: sz=36（18pt），spacing before/after 225
#   - heading 3: sz=28（14pt），spacing before/after 240
#   - heading 4: sz=24（12pt），spacing before/after 255
#
# 注意：pandoc 只取 reference 的 styles.xml + theme，所以效果以 styles.xml
# 里的 Normal/Heading 为准（不是 document.xml 里的内联格式）。如果跑出来
# 偏淡/字小，下一步要直接改 templates/reference-contract.docx 里的
# styles.xml，把 Normal 的字体改成汉仪书宋二KW + sz=28。

set -euo pipefail

cd "$(dirname "$0")"

INPUT="03-contract-formal.md"
OUTPUT="03-contract-formal.docx"
REFERENCE="../../templates/reference-contract.docx"

if [[ ! -f "$REFERENCE" ]]; then
  echo "[error] reference doc 不存在：$REFERENCE" >&2
  exit 1
fi

pandoc "$INPUT" \
  -o "$OUTPUT" \
  --reference-doc="$REFERENCE" \
  --from=gfm \
  --to=docx

echo "[ok] 已生成 $OUTPUT"

#!/usr/bin/env python
"""Prepare an offline, review-required Teacher corpus from named lecture files."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.learning.materials import MaterialsError, prepare_materials


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Chuẩn bị nguồn học từ PDF, PPTX và DOCX; không gọi AI hoặc huấn luyện model.")
    parser.add_argument("--title", required=True, help="Tên môn học hoặc chương.")
    parser.add_argument("--output", required=True, help="Thư mục mới, nên nằm dưới .agent/learning/materials/.")
    parser.add_argument("--files", required=True, nargs="+", help="Các file được chọn rõ ràng; không quét thư mục.")
    args = parser.parse_args(argv)
    try:
        manifest = prepare_materials(args.files, title=args.title, output_dir=args.output)
    except MaterialsError as error:
        print(f"{error.code}: {error}", file=sys.stderr)
        return 2
    print(f"Đã chuẩn bị {manifest['source_count']} tài liệu, {manifest['unit_count']} phần nguồn, {manifest['chunk_count']} đoạn trích.")
    print(f"Thư mục: {Path(args.output).absolute()}")
    print("Trạng thái: cần kiểm tra preview.txt và đối chiếu file gốc. Chưa đưa vào Teacher hoặc tạo câu hỏi.")
    if not manifest["chunk_count"]:
        print("Chưa trích được chữ để dùng. Tài liệu có thể cần OCR hoặc chuyển đổi định dạng.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

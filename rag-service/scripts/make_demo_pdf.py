"""Crear una entrada reproducible para la demostración, sin contenido universitario real."""

import argparse
from pathlib import Path


def make_pdf() -> bytes:
    lines = [
        "SPRINT 1 - DOCUMENTO SINTETICO DE DEMOSTRACION",
        "Este documento solo verifica la ingesta del gestor academico virtual.",
        "No contiene reglamentos ni informacion oficial de una universidad.",
    ]
    content = b"BT /F1 12 Tf 40 740 Td 20 TL\n"
    for line in lines:
        content += f"({line}) Tj T*\n".encode("ascii")
    content += b"ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010} 00000 n \n".encode())
    data.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode(),
    )
    return bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/inbox/sprint1-demo.pdf"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("xb") as output:
            output.write(make_pdf())
    except FileExistsError:
        parser.error("El archivo ya existe; elija otra ruta con --output.")
    print(args.output)


if __name__ == "__main__":
    main()

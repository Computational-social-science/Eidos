"""Structural artifact checks and rollback of SDK-owned delivery files.

These checks establish a file-format envelope, not scientific or journal approval.
"""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
import zipfile
import zlib

from framework.artifacts import atomic_output
from framework import subprocesses as processes


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular_file(path: Path, root: Path) -> None:
    if (
        not path.is_file()
        or path.is_symlink()
        or not path.resolve().is_relative_to(root.resolve())
        or any(p.is_symlink() for p in path.parents if p.is_relative_to(root))
    ):
        raise ValueError("missing, external or linked delivery file: " + str(path))


class _HTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.opened = set()
        self.closed = set()
        self.resources = []

    def handle_starttag(self, tag, attrs):
        self.opened.add(tag)
        values = dict(attrs)
        if tag in {
            "img",
            "script",
            "source",
            "video",
            "audio",
            "iframe",
        } and values.get("src"):
            self.resources.append(values["src"])
        if tag == "object" and values.get("data"):
            self.resources.append(values["data"])
        if (
            tag == "link"
            and set(values.get("rel", "").lower().split())
            & {"stylesheet", "icon", "preload"}
            and values.get("href")
        ):
            self.resources.append(values["href"])

    def handle_endtag(self, tag):
        self.closed.add(tag)


def validate(path: Path, fmt: str, root: Path) -> None:
    regular_file(path, root)
    body = path.read_bytes()
    if not body:
        raise ValueError("empty " + fmt + " artifact")
    if fmt == "html":
        parser = _HTML()
        parser.feed(body.decode("utf-8-sig"))
        if not {"html", "body"}.issubset(parser.opened & parser.closed):
            raise ValueError("incomplete HTML envelope")
        for resource in parser.resources:
            url = urlsplit(resource)
            if url.scheme or url.netloc or not url.path:
                continue
            # Local document resources must travel with the staged publication.
            reference = path.parent / unquote(url.path)
            regular_file(reference, root)
    elif fmt == "pdf":
        trailer = re.search(rb"startxref\s+(\d+)\s+%%EOF\s*$", body)
        if not body.startswith(b"%PDF-") or not trailer:
            raise ValueError("incomplete PDF envelope")
        offset = int(trailer[1])
        if offset >= len(body) or not re.match(
            rb"(xref\b|\d+\s+\d+\s+obj\b)", body[offset:]
        ):
            raise ValueError("invalid PDF cross-reference offset")
        binary = shutil.which("pdfinfo")
        if not binary:
            raise ValueError("PDF validation requires Poppler pdfinfo on PATH")
        result = processes.run_tree(
            [binary, "-f", "1", "-l", "1", str(path)], cwd=root, timeout=30
        )
        pages = re.search(r"^Pages:\s+(\d+)\s*$", result.stdout, re.MULTILINE)
        if result.returncode != 0 or pages is None or int(pages[1]) < 1:
            raise ValueError(
                "PDF parser rejected the document: " + result.stderr[-500:]
            )
    elif fmt == "docx":
        try:
            with zipfile.ZipFile(path) as archive:
                if any(
                    info.flag_bits & 1
                    or info.compress_type
                    not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    for info in archive.infolist()
                ):
                    raise ValueError("encrypted or unsupported DOCX compression")
                if archive.testzip() is not None:
                    raise ValueError("corrupt DOCX member")
                names = archive.namelist()
                if len(names) != len(set(names)):
                    raise ValueError("duplicate DOCX members")
                types = ET.fromstring(archive.read("[Content_Types].xml"))
                rels = ET.fromstring(archive.read("_rels/.rels"))
                document = ET.fromstring(archive.read("word/document.xml"))
                if (
                    types.tag
                    != "{http://schemas.openxmlformats.org/package/2006/content-types}Types"
                    or rels.tag
                    != "{http://schemas.openxmlformats.org/package/2006/relationships}Relationships"
                    or document.tag
                    != "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document"
                ):
                    raise ValueError("invalid DOCX roots")
                relations = [
                    r
                    for r in rels
                    if r.tag
                    == "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
                    and r.get("Type")
                    == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
                ]
                if (
                    len(relations) != 1
                    or relations[0].get("TargetMode") == "External"
                    or relations[0].get("Target")
                    not in {"word/document.xml", "/word/document.xml"}
                ):
                    raise ValueError("missing or external DOCX main document relation")
                main = [
                    t
                    for t in types
                    if t.tag
                    == "{http://schemas.openxmlformats.org/package/2006/content-types}Override"
                    and t.get("PartName") == "/word/document.xml"
                ]
                if (
                    len(main) != 1
                    or main[0].get("ContentType")
                    != "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
                ):
                    raise ValueError("missing DOCX main document content type")
                if (
                    document.find(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body"
                    )
                    is None
                ):
                    raise ValueError("missing DOCX body")
                overrides = {
                    t.get("PartName"): t.get("ContentType")
                    for t in types
                    if t.tag
                    == "{http://schemas.openxmlformats.org/package/2006/content-types}Override"
                }
                defaults = {
                    t.get("Extension"): t.get("ContentType")
                    for t in types
                    if t.tag
                    == "{http://schemas.openxmlformats.org/package/2006/content-types}Default"
                }
                for name in names:
                    if name.endswith("/") or name == "[Content_Types].xml":
                        continue
                    if not overrides.get("/" + name) and not defaults.get(
                        name.rsplit(".", 1)[-1]
                    ):
                        raise ValueError("DOCX member has no content type: " + name)
        except (
            zipfile.BadZipFile,
            KeyError,
            ET.ParseError,
            zlib.error,
            RuntimeError,
            NotImplementedError,
        ) as exc:
            raise ValueError("invalid DOCX envelope") from exc
    elif fmt == "svg":
        try:
            element = ET.fromstring(body)
        except ET.ParseError as exc:
            raise ValueError("invalid SVG envelope") from exc
        if element.tag != "{http://www.w3.org/2000/svg}svg":
            raise ValueError("invalid SVG root")
    elif fmt == "png":
        if (
            not body.startswith(b"\x89PNG\r\n\x1a\n")
            or len(body) < 33
            or body[12:16] != b"IHDR"
        ):
            raise ValueError("invalid PNG envelope")
        if not body.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82"):
            raise ValueError("incomplete PNG envelope")
        from PIL import Image

        with Image.open(path) as image:
            if image.format != "PNG":
                raise ValueError("not a PNG image")
            image.verify()
    else:
        raise ValueError("unsupported artifact format")


def publish(
    files: dict[str, Path],
    directory: Path,
    receipt_name: str,
    receipt: bytes,
    checksums: dict[str, str],
    verify_inputs=None,
) -> None:
    """Caller holds output_lock; publish receipt last and restore on any failure.

    Readers can verify the receipt hashes to reject a mixed concurrent read.
    Files not named by this publication are never removed.
    """
    from framework.executable_package import relative_name, unique_paths

    names = [*files, receipt_name]
    if any(relative_name(name) != name for name in names):
        raise ValueError("aliased publication path")
    unique_paths(names)
    if files.keys() != checksums.keys():
        raise ValueError("publication checksum inventory differs")
    with tempfile.TemporaryDirectory(prefix="eidos-delivery-backup-") as backup:
        saved: dict[str, Path | None] = {}
        written = []
        try:
            for name, source in [*files.items(), (receipt_name, None)]:
                relative = Path(name)
                target = directory / relative
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or target.is_symlink()
                    or not target.resolve().is_relative_to(directory.resolve())
                    or any(
                        p.is_symlink()
                        for p in target.parents
                        if p.is_relative_to(directory)
                    )
                ):
                    raise ValueError("unsafe delivery target: " + name)
                if target.exists():
                    regular_file(target, directory)
                    old = Path(backup) / str(len(saved))
                    shutil.copyfile(target, old)
                    saved[name] = old
                else:
                    saved[name] = None
                with atomic_output(target) as temporary:
                    if source is None:
                        if verify_inputs is not None:
                            verify_inputs()
                        if any(
                            digest(directory / item) != expected
                            for item, expected in checksums.items()
                        ):
                            raise ValueError(
                                "published files differ from validated artifacts"
                            )
                        temporary.write_bytes(receipt)
                    else:
                        shutil.copyfile(source, temporary)
                written.append(name)
        except BaseException as original:
            errors = []
            for name in reversed(written):
                target = directory / name
                try:
                    if saved[name] is None:
                        target.unlink(missing_ok=True)
                    else:
                        with atomic_output(target) as temporary:
                            shutil.copyfile(saved[name], temporary)
                except OSError as exc:
                    errors.append(str(exc))
            if errors:
                raise OSError(
                    "delivery rollback incomplete: " + "; ".join(errors)
                ) from original
            raise
